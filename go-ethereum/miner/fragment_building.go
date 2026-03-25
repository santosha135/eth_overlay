package miner

import (
	"fmt"

	"github.com/ethereum/go-ethereum/common"
	"github.com/ethereum/go-ethereum/core/types"
)

// BuildExecutedFragment executes bucket-local transactions on top of Parent and returns:
// - the executed txs (in the exact executed order)
// - the resulting post-state root (IntermediateRoot)
// The proposer will re-execute these txs and compare roots.
func (miner *Miner) BuildExecutedFragment(args *BuildPayloadArgs, bucketID uint32) ([]*types.Transaction, common.Hash, error) {
	if args == nil {
		return nil, common.Hash{}, fmt.Errorf("nil args")
	}

	// TODO: verify if this is needed otherwise delete the if
	if sw, ok := any(miner.txpool).(interface{ SetActiveBucket(uint32) }); ok {
		sw.SetActiveBucket(bucketID)
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
		txSource: nil,
	}

	// prepareWork builds header, loads parent state, creates EVM, etc.
	env, err := miner.prepareWork(gen, false /*witness*/)
	if err != nil {
		return nil, common.Hash{}, err
	}

	// Execute transactions using the existing selection logic.
	// We do not need interrupts on leaders, keep it nil for now.
	if err := miner.fillTransactions(nil, env); err != nil {
		return nil, common.Hash{}, err
	}

	// Compute post root after executing the fragment txs.
	post := env.state.IntermediateRoot(miner.chainConfig.IsEIP158(env.header.Number))
	return env.txs, post, nil
}