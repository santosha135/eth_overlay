package catalyst

import (
	"context"
	"fmt"

	"github.com/ethereum/go-ethereum/common/hexutil"
	"github.com/ethereum/go-ethereum/eth"
	"github.com/ethereum/go-ethereum/miner"
	"github.com/ethereum/go-ethereum/rpc"	
)

// LeaderAgent runs on a leader node and submits executed fragments to the proposer.
type LeaderAgent struct {
	eth          *eth.Ethereum  // local node (leader) for building fragment
	proposerRPC  *rpc.Client    // RPC client pointing to proposer node
}

func NewLeaderAgent(eth *eth.Ethereum, proposerRPC *rpc.Client) *LeaderAgent {
	return &LeaderAgent{eth: eth, proposerRPC: proposerRPC}
}

// BuildAndSubmitFragment executes the local fragment for bucketID and submits it to proposer.
func (a *LeaderAgent) BuildAndSubmitFragment(ctx context.Context, payloadIDHex string, bucketID uint32, args *miner.BuildPayloadArgs) error {
	if a.eth == nil || a.proposerRPC == nil {
		return fmt.Errorf("leader agent not initialized")
	}
	if args == nil {
		return fmt.Errorf("nil BuildPayloadArgs")
	}

	// 1) Build executed fragment locally
	txs, postRoot, err := a.eth.Miner().BuildExecutedFragment(args, bucketID)
	if err != nil {
		return err
	}

	// 2) Convert txs to bytes for RPC
	out := make([]hexutil.Bytes, 0, len(txs))
	for _, tx := range txs {
		if tx == nil {
			continue
		}
		b, err := tx.MarshalBinary()
		if err != nil {
			return err
		}
		out = append(out, b)
	}

	// 3) Submit fragment to proposer
	var ok bool
	if err := a.proposerRPC.CallContext(ctx, &ok, "overlay_submitFragment", payloadIDHex, bucketID, out, postRoot); err != nil {
		return err
	}
	if !ok {
		return fmt.Errorf("overlay_submitFragment returned false")
	}
	return nil
}