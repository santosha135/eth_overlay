package miner

import (
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

	log.Info(
		"FINAL VALIDATOR SUB-BLOCK PROCESSING START",
		"numBuckets", numBuckets,
		"block", env.header.Number,
	)

	// ============================================================
	// 1. SUB-BLOCK COLLECTION
	// ============================================================

	subs := make([]*SubBlock, 0, numBuckets)

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
			continue
		}

		receivedFragments++
		totalTransactions += len(sub.Txs)
		subs = append(subs, sub)
	}

	log.Info(
		"FINAL VALIDATOR SUB-BLOCK COLLECTION COMPLETE",
		"expectedSubBlocks", numBuckets,
		"receivedSubBlocks", receivedFragments,
		"totalTransactions", totalTransactions,
		"collectionDurationNs", collectionDuration.Nanoseconds(),
		"collectionDurationUs", collectionDuration.Microseconds(),
	)

	// ============================================================
	// 2. JOIN / CONFLICT RE-EXECUTION
	// ============================================================

	var (
		joined     int
		reexecuted int
		dropped    int
		wroteSlots = make(map[StorageSlot]struct{})
		wroteAccts = make(map[common.Address]struct{})
	)

	for _, sub := range subs {

		subStart := time.Now()

		conflict := subBlockConflicts(sub, wroteAccts, wroteSlots)

		outcome := "joined"

		if conflict || !miner.applySubBlockDiff(env, sub) {
			if miner.reexecuteSubBlock(env, sub) {
				outcome = "reexecuted"
				reexecuted++
				// Re-execution can change more than the leader's diff described,
				// so record the wider touched set.
				recordAccessWrites(sub, wroteAccts, wroteSlots)
			} else {
				outcome = "dropped"
				dropped++
			}
		} else {
			joined++
			recordDiffWrites(sub, wroteAccts, wroteSlots)
		}

		subDuration := time.Since(subStart)
		mergeDuration += subDuration

		log.Info(
			"FINAL VALIDATOR SUB-BLOCK APPLY",
			"bucket", sub.BucketID,
			"subBlock", sub.Hash(),
			"txs", len(sub.Txs),
			"gasUsed", sub.GasUsed,
			"conflict", conflict,
			"outcome", outcome,
			"durationNs", subDuration.Nanoseconds(),
			"durationUs", subDuration.Microseconds(),
		)
	}

	log.Info(
		"FINAL VALIDATOR SUB-BLOCK MERGE COMPLETE",
		"receivedSubBlocks", receivedFragments,
		"joinedSubBlocks", joined,
		"reexecutedSubBlocks", reexecuted,
		"droppedSubBlocks", dropped,
		"totalTransactions", totalTransactions,
		"blockGasUsed", env.header.GasUsed,
		"mergeDurationNs", mergeDuration.Nanoseconds(),
		"mergeDurationUs", mergeDuration.Microseconds(),
	)

	return receivedFragments, totalTransactions, collectionDuration, mergeDuration
}

// subBlockConflicts reports whether this sub-block's state overlaps what the
// sub-blocks already merged have changed.
//
// Balance changes are additive and never conflict on their own, which is what
// keeps the shared coinbase, credited by every sub-block, from colliding every
// time. Storage, nonces and code are absolute values and do conflict.
func subBlockConflicts(
	sub *SubBlock,
	wroteAccts map[common.Address]struct{},
	wroteSlots map[StorageSlot]struct{},
) bool {

	for _, slot := range sub.Access.ReadSlots {
		if _, ok := wroteSlots[slot]; ok {
			return true
		}
	}
	for _, slot := range sub.Access.WrittenSlots {
		if _, ok := wroteSlots[slot]; ok {
			return true
		}
	}
	for _, addr := range sub.Access.ReadAccounts {
		if _, ok := wroteAccts[addr]; ok {
			return true
		}
	}
	for _, write := range sub.Diff.Nonces {
		if _, ok := wroteAccts[write.Addr]; ok {
			return true
		}
	}
	for _, write := range sub.Diff.Codes {
		if _, ok := wroteAccts[write.Addr]; ok {
			return true
		}
	}
	return false
}

// recordDiffWrites notes exactly what a joined sub-block changed.
func recordDiffWrites(
	sub *SubBlock,
	wroteAccts map[common.Address]struct{},
	wroteSlots map[StorageSlot]struct{},
) {
	for _, write := range sub.Diff.Storage {
		wroteSlots[StorageSlot{Addr: write.Addr, Slot: write.Slot}] = struct{}{}
	}
	for _, write := range sub.Diff.Balances {
		wroteAccts[write.Addr] = struct{}{}
	}
	for _, write := range sub.Diff.Nonces {
		wroteAccts[write.Addr] = struct{}{}
	}
	for _, write := range sub.Diff.Codes {
		wroteAccts[write.Addr] = struct{}{}
	}
}

// recordAccessWrites notes the touched set of a re-executed sub-block, which is
// a superset of what it actually changed.
func recordAccessWrites(
	sub *SubBlock,
	wroteAccts map[common.Address]struct{},
	wroteSlots map[StorageSlot]struct{},
) {
	for _, slot := range sub.Access.WrittenSlots {
		wroteSlots[slot] = struct{}{}
	}
	for _, addr := range sub.Access.WrittenAccounts {
		wroteAccts[addr] = struct{}{}
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
func (miner *Miner) reexecuteSubBlock(env *environment, sub *SubBlock) bool {

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
			return false
		}

		env.state.SetTxContext(tx.Hash(), env.tcount)

		if err := miner.commitTransaction(env, tx); err != nil {
			log.Debug("Sub-block re-execution failed",
				"bucket", sub.BucketID,
				"hash", tx.Hash(),
				"err", err,
			)
			rollback()
			return false
		}
	}

	return true
}
