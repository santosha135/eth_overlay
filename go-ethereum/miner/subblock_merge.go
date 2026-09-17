package miner

import (
	"fmt"
	"os"
	"time"

	"github.com/ethereum/go-ethereum/common"
	"github.com/ethereum/go-ethereum/core"
	"github.com/ethereum/go-ethereum/core/tracing"
	"github.com/ethereum/go-ethereum/log"
	"github.com/holiman/uint256"
)

// joinSubBlocks assembles the block out of the leaders' sub-blocks.
//
// A sub-block whose state does not overlap one already applied is joined: its
// state diff is written straight into the block state and its receipts are
// renumbered, with no EVM execution. Only an overlapping sub-block is
// re-executed, in bucket order, against the state as merged so far.
//
// The merge makes no judgement about which transactions belong in the block. A
// sub-block is dropped only when it cannot be applied at all: it does not fit,
// its receipts are inconsistent, or re-execution fails.
func (miner *Miner) joinSubBlocks(
	env *environment,
	fp FragmentProvider,
	numBuckets uint32,
) (
	receivedFragments int,
	totalTransactions int,
	collectionDuration time.Duration,
	mergeDuration time.Duration,
) {

	if env.gasPool == nil {
		env.gasPool = new(core.GasPool).AddGas(env.header.GasLimit)
	}

	hostname := os.Getenv("HOSTNAME")
	blockNumber := env.header.Number.Uint64()

	log.Info(
		"FINAL VALIDATOR SUB-BLOCK PROCESSING START",
		"numBuckets", numBuckets,
		"block", env.header.Number,
	)

	// ============================================================
	// 1. SUB-BLOCK COLLECTION
	// ============================================================

	subs := make([]*SubBlock, 0, numBuckets)
	metas := make(map[uint32]SubBlockMeta, numBuckets)
	missing := make([]uint32, 0)

	// Arrival tracking. These are wall-clock stamps taken on this node when a
	// sub-block landed, so they are comparable with each other even though the
	// leaders' own clocks are not.
	var (
		firstArrival time.Time
		lastArrival  time.Time
		stragglerBucket = -1
	)

	for bucket := uint32(0); bucket < numBuckets; bucket++ {

		lookupStart := time.Now()

		sub, ok := fp.GetSubBlock(bucket)

		lookupDuration := time.Since(lookupStart)
		collectionDuration += lookupDuration

		log.Info(
			"FINAL VALIDATOR SUB-BLOCK LOOKUP",
			"bucket", bucket,
			"available", ok,
			"lookupDurationNs", lookupDuration.Nanoseconds(),
			"lookupDurationUs", lookupDuration.Microseconds(),
		)

		if !ok || sub == nil || len(sub.Txs) == 0 {
			missing = append(missing, bucket)
			continue
		}

		if meta, metaOK := fp.GetSubBlockMeta(bucket); metaOK {
			metas[bucket] = meta

			if firstArrival.IsZero() || meta.ReceivedAt.Before(firstArrival) {
				firstArrival = meta.ReceivedAt
			}
			if meta.ReceivedAt.After(lastArrival) {
				lastArrival = meta.ReceivedAt
				stragglerBucket = int(bucket)
			}
		}

		receivedFragments++
		totalTransactions += len(sub.Txs)
		subs = append(subs, sub)
	}

	// A sub-block that never arrived is a silent transaction loss, so record one
	// row per missing bucket too.
	for _, bucket := range missing {
		RecordSubBlockMetric(SubBlockMetric{
			TimestampUTC:   time.Now().UTC().Format(time.RFC3339Nano),
			Role:           "proposer",
			Hostname:       hostname,
			BlockNumber:    blockNumber,
			NumBuckets:     numBuckets,
			BucketID:       bucket,
			Outcome:        "missing",
			Reason:         "no sub-block at merge time",
			ConflictBucket: -1,
		})
	}

	log.Info(
		"FINAL VALIDATOR SUB-BLOCK COLLECTION COMPLETE",
		"expectedSubBlocks", numBuckets,
		"receivedSubBlocks", receivedFragments,
		"missingSubBlocks", len(missing),
		"totalTransactions", totalTransactions,
		"firstArrival", stampOrEmpty(firstArrival),
		"lastArrival", stampOrEmpty(lastArrival),
		"stragglerBucket", stragglerBucket,
		"arrivalSpreadUs", arrivalSpread(firstArrival, lastArrival).Microseconds(),
		"collectionDurationNs", collectionDuration.Nanoseconds(),
		"collectionDurationUs", collectionDuration.Microseconds(),
	)

	// ============================================================
	// 2. JOIN / CONFLICT RE-EXECUTION
	// ============================================================

	mergeStart := time.Now()

	var (
		joined     int
		reexecuted int
		dropped    int

		// Which bucket last wrote each piece of state, so a conflict can name
		// the sub-block it collided with.
		wroteSlots = make(map[StorageSlot]uint32)
		wroteAccts = make(map[common.Address]uint32)

		totalReexecTxs int
		totalReexecGas uint64
	)

	for _, sub := range subs {

		subStart := time.Now()

		conflict, reason, conflictBucket, conflictKey := subBlockConflicts(sub, wroteAccts, wroteSlots)

		var (
			outcome        = "joined"
			applyDuration  time.Duration
			reexecDuration time.Duration
			reexecTxs      int
			reexecGas      uint64
		)

		joinedFromDiff := false

		if !conflict {
			applyStart := time.Now()
			joinedFromDiff = miner.applySubBlockDiff(env, sub)
			applyDuration = time.Since(applyStart)

			if !joinedFromDiff && reason == "" {
				reason = "diff not applicable"
			}
		}

		if joinedFromDiff {
			joined++
			recordDiffWrites(sub, wroteAccts, wroteSlots)
		} else {
			reexecStart := time.Now()
			ok, txs, gas := miner.reexecuteSubBlock(env, sub)
			reexecDuration = time.Since(reexecStart)

			if ok {
				outcome = "reexecuted"
				reexecuted++
				reexecTxs = txs
				reexecGas = gas
				totalReexecTxs += txs
				totalReexecGas += gas
				// Re-execution can change more than the leader's diff described,
				// so record the wider touched set.
				recordAccessWrites(sub, wroteAccts, wroteSlots)
			} else {
				outcome = "dropped"
				dropped++
				if reason == "" {
					reason = "re-execution failed"
				}
			}
		}

		subDuration := time.Since(subStart)
		mergeDuration += subDuration

		storageWrites, balanceDeltas, nonceWrites, codeWrites, codeBytes := subBlockDiffSizes(sub)

		meta := metas[sub.BucketID]
		waitDuration := time.Duration(0)
		if !meta.ReceivedAt.IsZero() {
			waitDuration = mergeStart.Sub(meta.ReceivedAt)
		}

		log.Info(
			"FINAL VALIDATOR SUB-BLOCK APPLY",
			"bucket", sub.BucketID,
			"subBlock", sub.Hash(),
			"txs", len(sub.Txs),
			"gasUsed", sub.GasUsed,
			"blobBytes", meta.BlobBytes,
			"conflict", conflict,
			"conflictBucket", conflictBucket,
			"conflictKey", conflictKey,
			"outcome", outcome,
			"reason", reason,
			"storageWrites", storageWrites,
			"readSlots", len(sub.Access.ReadSlots),
			"writtenSlots", len(sub.Access.WrittenSlots),
			"waitDurationUs", waitDuration.Microseconds(),
			"applyDurationUs", applyDuration.Microseconds(),
			"reexecDurationUs", reexecDuration.Microseconds(),
			"durationNs", subDuration.Nanoseconds(),
			"durationUs", subDuration.Microseconds(),
		)

		RecordSubBlockMetric(SubBlockMetric{
			TimestampUTC: time.Now().UTC().Format(time.RFC3339Nano),
			Role:         "proposer",
			Hostname:     hostname,

			BlockNumber:  blockNumber,
			NumBuckets:   numBuckets,
			BucketID:     sub.BucketID,
			SubBlockHash: sub.Hash().Hex(),

			Txs:       len(sub.Txs),
			GasUsed:   sub.GasUsed,
			BlobBytes: meta.BlobBytes,

			StorageWrites: storageWrites,
			BalanceDeltas: balanceDeltas,
			NonceWrites:   nonceWrites,
			CodeWrites:    codeWrites,
			CodeBytes:     codeBytes,

			ReadAccounts:    len(sub.Access.ReadAccounts),
			ReadSlots:       len(sub.Access.ReadSlots),
			WrittenAccounts: len(sub.Access.WrittenAccounts),
			WrittenSlots:    len(sub.Access.WrittenSlots),

			Outcome:        outcome,
			Reason:         reason,
			ConflictBucket: conflictBucket,
			ConflictKey:    conflictKey,

			ReceivedAtUTC: stampOrEmpty(meta.ReceivedAt),
			MergeStartUTC: mergeStart.UTC().Format(time.RFC3339Nano),
			WaitDuration:  waitDuration,

			ApplyDuration:  applyDuration,
			ReexecDuration: reexecDuration,
			TotalDuration:  subDuration,

			ReexecTxs:        reexecTxs,
			ReexecGas:        reexecGas,
			GasPoolRemaining: env.gasPool.Gas(),
		})
	}

	log.Info(
		"FINAL VALIDATOR SUB-BLOCK MERGE COMPLETE",
		"receivedSubBlocks", receivedFragments,
		"missingSubBlocks", len(missing),
		"joinedSubBlocks", joined,
		"reexecutedSubBlocks", reexecuted,
		"droppedSubBlocks", dropped,
		"totalTransactions", totalTransactions,
		"reexecutedTxs", totalReexecTxs,
		"reexecutedGas", totalReexecGas,
		"stragglerBucket", stragglerBucket,
		"blockGasUsed", env.header.GasUsed,
		"mergeDurationNs", mergeDuration.Nanoseconds(),
		"mergeDurationUs", mergeDuration.Microseconds(),
	)

	return receivedFragments, totalTransactions, collectionDuration, mergeDuration
}

// stampOrEmpty formats an arrival stamp, or returns "" when it was never set.
func stampOrEmpty(t time.Time) string {
	if t.IsZero() {
		return ""
	}
	return t.UTC().Format(time.RFC3339Nano)
}

// arrivalSpread is the gap between the first and last sub-block to land: how
// long the proposer could have been waiting on the slowest leader.
func arrivalSpread(first, last time.Time) time.Duration {
	if first.IsZero() || last.IsZero() {
		return 0
	}
	return last.Sub(first)
}

// subBlockConflicts reports whether this sub-block's state overlaps what the
// sub-blocks already merged have changed, and names the collision.
//
// Balance changes are additive and never conflict on their own, which is what
// keeps the shared coinbase, credited by every sub-block, from colliding every
// time. Storage, nonces and code are absolute values and do conflict.
func subBlockConflicts(
	sub *SubBlock,
	wroteAccts map[common.Address]uint32,
	wroteSlots map[StorageSlot]uint32,
) (conflict bool, reason string, conflictBucket int, conflictKey string) {

	for _, slot := range sub.Access.ReadSlots {
		if bucket, ok := wroteSlots[slot]; ok {
			return true, "read slot written by earlier sub-block", int(bucket), slotKey(slot)
		}
	}
	for _, slot := range sub.Access.WrittenSlots {
		if bucket, ok := wroteSlots[slot]; ok {
			return true, "write to slot written by earlier sub-block", int(bucket), slotKey(slot)
		}
	}
	for _, addr := range sub.Access.ReadAccounts {
		if bucket, ok := wroteAccts[addr]; ok {
			return true, "read account changed by earlier sub-block", int(bucket), addr.Hex()
		}
	}
	for _, write := range sub.Diff.Nonces {
		if bucket, ok := wroteAccts[write.Addr]; ok {
			return true, "nonce write to account changed by earlier sub-block", int(bucket), write.Addr.Hex()
		}
	}
	for _, write := range sub.Diff.Codes {
		if bucket, ok := wroteAccts[write.Addr]; ok {
			return true, "code write to account changed by earlier sub-block", int(bucket), write.Addr.Hex()
		}
	}
	return false, "", -1, ""
}

// slotKey renders an account/slot pair for the metrics row.
func slotKey(slot StorageSlot) string {
	return fmt.Sprintf("%s:%s", slot.Addr.Hex(), slot.Slot.Hex())
}

// recordDiffWrites notes exactly what a joined sub-block changed.
func recordDiffWrites(
	sub *SubBlock,
	wroteAccts map[common.Address]uint32,
	wroteSlots map[StorageSlot]uint32,
) {
	for _, write := range sub.Diff.Storage {
		wroteSlots[StorageSlot{Addr: write.Addr, Slot: write.Slot}] = sub.BucketID
	}
	for _, write := range sub.Diff.Balances {
		wroteAccts[write.Addr] = sub.BucketID
	}
	for _, write := range sub.Diff.Nonces {
		wroteAccts[write.Addr] = sub.BucketID
	}
	for _, write := range sub.Diff.Codes {
		wroteAccts[write.Addr] = sub.BucketID
	}
}

// recordAccessWrites notes the touched set of a re-executed sub-block, which is
// a superset of what it actually changed.
func recordAccessWrites(
	sub *SubBlock,
	wroteAccts map[common.Address]uint32,
	wroteSlots map[StorageSlot]uint32,
) {
	for _, slot := range sub.Access.WrittenSlots {
		wroteSlots[slot] = sub.BucketID
	}
	for _, addr := range sub.Access.WrittenAccounts {
		wroteAccts[addr] = sub.BucketID
	}
}

// applySubBlockDiff joins a sub-block without running the EVM: it writes the
// leader's state diff into the block state and carries the leader's receipts
// over, renumbered against the merged block. It reports false when the sub-block
// cannot be joined this way, leaving the block state untouched.
func (miner *Miner) applySubBlockDiff(env *environment, sub *SubBlock) bool {

	// ---- validate before touching anything ----

	if len(sub.Receipts) != len(sub.Txs) {
		log.Debug("Sub-block cannot be joined: receipts missing",
			"bucket", sub.BucketID,
			"txs", len(sub.Txs),
			"receipts", len(sub.Receipts),
		)
		return false
	}

	if sub.GasUsed > env.gasPool.Gas() {
		log.Debug("Sub-block cannot be joined: block gas exhausted",
			"bucket", sub.BucketID,
			"gasUsed", sub.GasUsed,
			"available", env.gasPool.Gas(),
		)
		return false
	}

	for _, tx := range sub.Txs {
		if tx == nil {
			return false
		}
		if !env.txFitsSize(tx) {
			log.Debug("Sub-block cannot be joined: block size limit",
				"bucket", sub.BucketID,
				"hash", tx.Hash(),
			)
			return false
		}
	}

	// Receipt gas must be monotonic and add up to the sub-block's own total.
	perTxGas := make([]uint64, len(sub.Receipts))
	previousCumulative := uint64(0)

	for i, receipt := range sub.Receipts {
		if receipt == nil || receipt.CumulativeGasUsed < previousCumulative {
			log.Debug("Sub-block cannot be joined: inconsistent receipts",
				"bucket", sub.BucketID,
				"index", i,
			)
			return false
		}
		perTxGas[i] = receipt.CumulativeGasUsed - previousCumulative
		previousCumulative = receipt.CumulativeGasUsed
	}

	if previousCumulative != sub.GasUsed {
		log.Debug("Sub-block cannot be joined: receipt gas does not match sub-block gas",
			"bucket", sub.BucketID,
			"receiptGas", previousCumulative,
			"subBlockGas", sub.GasUsed,
		)
		return false
	}

	balances := make([]*uint256.Int, len(sub.Diff.Balances))

	for i, write := range sub.Diff.Balances {
		if write.Amount == nil {
			balances[i] = new(uint256.Int)
			continue
		}
		amount, overflow := uint256.FromBig(write.Amount)
		if overflow {
			log.Debug("Sub-block cannot be joined: balance delta overflow",
				"bucket", sub.BucketID,
				"addr", write.Addr,
			)
			return false
		}
		balances[i] = amount
	}

	// ---- apply ----

	if err := env.gasPool.SubGas(sub.GasUsed); err != nil {
		return false
	}

	for _, write := range sub.Diff.Storage {
		env.state.SetState(write.Addr, write.Slot, write.Value)
	}

	for i, write := range sub.Diff.Balances {
		if write.Neg {
			env.state.SubBalance(write.Addr, balances[i], tracing.BalanceChangeUnspecified)
		} else {
			env.state.AddBalance(write.Addr, balances[i], tracing.BalanceChangeUnspecified)
		}
	}

	for _, write := range sub.Diff.Nonces {
		env.state.SetNonce(write.Addr, write.Nonce, tracing.NonceChangeUnspecified)
	}

	for _, write := range sub.Diff.Codes {
		env.state.SetCode(write.Addr, write.Code, tracing.CodeChangeUnspecified)
	}

	for i, tx := range sub.Txs {
		env.header.GasUsed += perTxGas[i]

		receipt := *sub.Receipts[i]
		receipt.TxHash = tx.Hash()
		receipt.GasUsed = perTxGas[i]
		receipt.CumulativeGasUsed = env.header.GasUsed
		receipt.TransactionIndex = uint(env.tcount)

		env.txs = append(env.txs, tx)
		env.receipts = append(env.receipts, &receipt)
		env.size += tx.Size()
		env.tcount++
	}

	return true
}

// reexecuteSubBlock runs a sub-block's transactions against the state as merged
// so far. It is the fallback for a sub-block that overlaps an earlier one, or
// that cannot be joined from its diff. All or nothing: a failure leaves the
// block exactly as it was.
//
// It reports how many transactions were re-executed and the gas they burned,
// which is the work the conflict cost.
func (miner *Miner) reexecuteSubBlock(env *environment, sub *SubBlock) (bool, int, uint64) {

	snap := env.state.Snapshot()

	var (
		gasBefore      = env.gasPool.Gas()
		gasUsedBefore  = env.header.GasUsed
		txsBefore      = len(env.txs)
		receiptsBefore = len(env.receipts)
		sizeBefore     = env.size
		countBefore    = env.tcount
	)

	rollback := func() {
		env.state.RevertToSnapshot(snap)
		env.gasPool.SetGas(gasBefore)
		env.header.GasUsed = gasUsedBefore
		env.txs = env.txs[:txsBefore]
		env.receipts = env.receipts[:receiptsBefore]
		env.size = sizeBefore
		env.tcount = countBefore
	}

	executed := 0

	for _, tx := range sub.Txs {

		if tx == nil {
			continue
		}

		if !env.txFitsSize(tx) {
			log.Debug("Sub-block re-execution rejected: block size limit",
				"bucket", sub.BucketID,
				"hash", tx.Hash(),
			)
			rollback()
			return false, 0, 0
		}

		env.state.SetTxContext(tx.Hash(), env.tcount)

		if err := miner.commitTransaction(env, tx); err != nil {
			log.Debug("Sub-block re-execution failed",
				"bucket", sub.BucketID,
				"hash", tx.Hash(),
				"err", err,
			)
			rollback()
			return false, 0, 0
		}

		executed++
	}

	return true, executed, env.header.GasUsed - gasUsedBefore
}
