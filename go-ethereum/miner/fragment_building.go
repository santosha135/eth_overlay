package miner

import (
	"bytes"
	"fmt"
	"math/big"
	"time"

	"github.com/ethereum/go-ethereum/common"
	"github.com/ethereum/go-ethereum/core/state"
	"github.com/ethereum/go-ethereum/core/types"
	"github.com/ethereum/go-ethereum/log"
)

// BuildSubBlock executes this bucket's transactions on top of the parent state
// and returns them as a sub-block: the executed txs in order, their receipts,
// the post-state root, the gas they burned, the state they touched, and the
// state diff they produced.
//
// The merge on the proposer applies the diff directly and only re-executes the
// txs when this sub-block overlaps one already applied.
func (miner *Miner) BuildSubBlock(args *BuildPayloadArgs, bucketID uint32) (*SubBlock, error) {
	if args == nil {
		return nil, fmt.Errorf("nil args")
	}

	start := time.Now()

	log.Debug("SUB-BLOCK BUILD START",
		"bucket", bucketID,
		"time", time.Now().UnixMilli(),
	)

	// Restrict the pool to this bucket for the duration of the build.
	if sw, ok := any(miner.txpool).(interface {
		SetActiveBucket(uint32)
		ClearActiveBucket()
	}); ok {
		log.Debug("FORCED ACTIVE BUCKET SET", "bucket", bucketID)
		sw.SetActiveBucket(bucketID)
		defer func() {
			sw.ClearActiveBucket()
			log.Debug("FORCED ACTIVE BUCKET CLEARED", "bucket", bucketID)
		}()
	}

	// Build an env on top of Parent at Timestamp, like normal payload building.
	gen := &generateParams{
		timestamp:   args.Timestamp,
		forceTime:   true,
		parentHash:  args.Parent,
		coinbase:    args.FeeRecipient,
		random:      args.Random,
		withdrawals: args.Withdrawals,
		beaconRoot:  args.BeaconRoot,
		noTxs:       false,
		txSource:    nil,
	}

	// prepareWork builds header, loads parent state, creates EVM, etc.
	env, err := miner.prepareWork(gen, false /*witness*/)
	if err != nil {
		return nil, err
	}

	// The parent state is needed to turn final values into a diff.
	parentHeader := miner.chain.GetHeaderByHash(env.header.ParentHash)
	if parentHeader == nil {
		return nil, fmt.Errorf("parent header %s not found", env.header.ParentHash)
	}
	parentState, err := miner.chain.StateAt(parentHeader.Root)
	if err != nil {
		return nil, fmt.Errorf("parent state %s unavailable: %w", parentHeader.Root, err)
	}

	// Record what the sub-block touches while it runs.
	tracer := newAccessTracer()
	env.evm.Config.Tracer = tracer.hooks()

	// Execute transactions using the existing selection logic. Leaders do not
	// need interrupts, so keep it nil.
	if err := miner.fillTransactions(nil, env); err != nil {
		return nil, err
	}

	// Fees always move the sender and the coinbase, with no opcode to reveal it.
	tracer.markAccountWritten(env.coinbase)
	for _, tx := range env.txs {
		if tx == nil {
			continue
		}
		if from, err := types.Sender(env.signer, tx); err == nil {
			tracer.markAccountWritten(from)
		}
		if to := tx.To(); to != nil {
			tracer.markAccountWritten(*to)
		}
	}

	post := env.state.IntermediateRoot(miner.chainConfig.IsEIP158(env.header.Number))

	sub := &SubBlock{
		BucketID:   bucketID,
		ParentHash: env.header.ParentHash,
		ParentRoot: parentHeader.Root,
		Number:     new(big.Int).Set(env.header.Number),
		Txs:        append([]*types.Transaction(nil), env.txs...),
		Receipts:   append([]*types.Receipt(nil), env.receipts...),
		PostRoot:   post,
		GasUsed:    env.header.GasUsed,
		Access:     tracer.accessSet(),
		Diff:       buildStateDiff(env.state, parentState, tracer),
	}

	log.Debug("SUB-BLOCK BUILD DONE",
		"bucket", bucketID,
		"hash", sub.Hash(),
		"txs", len(sub.Txs),
		"gasUsed", sub.GasUsed,
		"postRoot", sub.PostRoot,
		"storageWrites", len(sub.Diff.Storage),
		"balanceDeltas", len(sub.Diff.Balances),
		"elapsed", time.Since(start),
	)

	return sub, nil
}

// BuildExecutedFragment is the older, narrower view of a sub-block, kept for
// callers that only want the txs and the post-state root.
func (miner *Miner) BuildExecutedFragment(args *BuildPayloadArgs, bucketID uint32) ([]*types.Transaction, common.Hash, error) {
	sub, err := miner.BuildSubBlock(args, bucketID)
	if err != nil {
		return nil, common.Hash{}, err
	}
	return sub.Txs, sub.PostRoot, nil
}

// buildStateDiff reads the final value of everything the sub-block touched and
// records how it differs from the parent state.
//
// Balances are recorded as deltas, because every sub-block credits the same
// coinbase and absolute balances would then collide on every merge. Nonces and
// code are absolute: bucket assignment is sender-sticky and nonce-gated, so one
// account's transactions never span buckets within a block.
func buildStateDiff(post *state.StateDB, pre *state.StateDB, tracer *accessTracer) StateDiff {
	diff := StateDiff{}

	for slot := range tracer.writtenSlots {
		value := post.GetState(slot.Addr, slot.Slot)
		if value == pre.GetState(slot.Addr, slot.Slot) {
			continue // touched but unchanged, or written then reverted
		}
		diff.Storage = append(diff.Storage, StorageWrite{
			Addr:  slot.Addr,
			Slot:  slot.Slot,
			Value: value,
		})
	}

	for addr := range tracer.writtenAccounts {
		postBalance := post.GetBalance(addr).ToBig()
		preBalance := pre.GetBalance(addr).ToBig()

		if delta := new(big.Int).Sub(postBalance, preBalance); delta.Sign() != 0 {
			diff.Balances = append(diff.Balances, BalanceDelta{
				Addr:   addr,
				Neg:    delta.Sign() < 0,
				Amount: new(big.Int).Abs(delta),
			})
		}

		if postNonce := post.GetNonce(addr); postNonce != pre.GetNonce(addr) {
			diff.Nonces = append(diff.Nonces, NonceWrite{Addr: addr, Nonce: postNonce})
		}

		if postCode := post.GetCode(addr); !bytes.Equal(postCode, pre.GetCode(addr)) {
			diff.Codes = append(diff.Codes, CodeWrite{
				Addr: addr,
				Code: append([]byte(nil), postCode...),
			})
		}
	}

	return diff
}
