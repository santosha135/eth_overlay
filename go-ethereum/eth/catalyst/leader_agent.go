package catalyst

import (
	"context"
	"fmt"

	"github.com/ethereum/go-ethereum/common/hexutil"
	"github.com/ethereum/go-ethereum/eth"
	"github.com/ethereum/go-ethereum/miner"
	"github.com/ethereum/go-ethereum/rlp"
	"github.com/ethereum/go-ethereum/rpc"
)

// LeaderAgent runs on a leader node and submits built sub-blocks to the proposer.
type LeaderAgent struct {
	eth         *eth.Ethereum // local node (leader) for building the sub-block
	proposerRPC *rpc.Client   // RPC client pointing to proposer node
}

func NewLeaderAgent(eth *eth.Ethereum, proposerRPC *rpc.Client) *LeaderAgent {
	return &LeaderAgent{eth: eth, proposerRPC: proposerRPC}
}

// BuildAndSubmitSubBlock builds the local sub-block for bucketID and submits it
// to the proposer.
func (a *LeaderAgent) BuildAndSubmitSubBlock(ctx context.Context, bucketID uint32, args *miner.BuildPayloadArgs) error {
	if a.eth == nil || a.proposerRPC == nil {
		return fmt.Errorf("leader agent not initialized")
	}
	if args == nil {
		return fmt.Errorf("nil BuildPayloadArgs")
	}

	// 1) Build the sub-block locally.
	sub, err := a.eth.Miner().BuildSubBlock(args, bucketID)
	if err != nil {
		return err
	}

	// 2) Encode it for transport.
	blob, err := rlp.EncodeToBytes(sub)
	if err != nil {
		return err
	}

	// 3) Submit it to the proposer.
	var ok bool
	if err := a.proposerRPC.CallContext(
		ctx,
		&ok,
		"overlay_submitSubBlock",
		args.Parent,
		args.Timestamp,
		byte(args.Version),
		hexutil.Bytes(blob),
	); err != nil {
		return err
	}
	if !ok {
		return fmt.Errorf("overlay_submitSubBlock returned false")
	}
	return nil
}
