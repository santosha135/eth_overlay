package catalyst

import (
	"context"
	"github.com/ethereum/go-ethereum/common"
	"github.com/ethereum/go-ethereum/common/hexutil"
	"github.com/ethereum/go-ethereum/core/types"
	"github.com/ethereum/go-ethereum/eth"
	"github.com/ethereum/go-ethereum/log"
	"github.com/ethereum/go-ethereum/miner"
	"github.com/ethereum/go-ethereum/rpc"
	"github.com/ethereum/go-ethereum/src/bucket"
	"time"
)

type LeaderLoop struct {
	LocalEth   *eth.Ethereum
	OverlayRPC *rpc.Client

	Scheduler *bucket.Scheduler
	MyIndex   int

	NumBuckets    int
	GroupID       int
	GroupSize     int
	MyMemberIndex int

	PollEvery time.Duration
}

func (l *LeaderLoop) Run(ctx context.Context) error {
	if l.PollEvery == 0 {
		l.PollEvery = 200 * time.Millisecond
	}

	var lastSlotID [32]byte

	for {
		select {
		case <-ctx.Done():
			return ctx.Err()
		case <-time.After(l.PollEvery):
		}

		// 1) poll active slot
		var active ActiveSlotResponse
		if err := l.OverlayRPC.CallContext(ctx, &active, "overlay_getActiveSlot"); err != nil {
			continue
		}
		var cur [32]byte
		copy(cur[:], active.SlotID[:])
		if cur == lastSlotID {
			continue
		}
		lastSlotID = cur

		// 2) fetch args
		var argsLite OverlayArgs
		if err := l.OverlayRPC.CallContext(ctx, &argsLite, "overlay_getSlotArgs", active.Parent, active.Time, active.Version); err != nil {
			continue
		}

		// 3) for each bucket, if I am leader, build fragment and submit
		// activeBucket := int((active.Epoch + uint64(l.GroupID)) % uint64(l.NumBuckets))
		// leaderIdx := bucket.LeaderIndex(active.Epoch, l.GroupID, l.GroupSize)

		activeBucket := bucket.ActiveBucketForGroup(active.Epoch, l.GroupID, l.NumBuckets)
		leaderIdx := bucket.LeaderIndex(active.Epoch, l.GroupID, l.GroupSize)

		log.Debug("LEADER LOOP DECISION",
			"epoch", active.Epoch,
			"groupID", l.GroupID,
			"activeBucket", activeBucket,
			"groupSize", l.GroupSize,
			"leaderIndex", leaderIdx,
			"myMemberIndex", l.MyMemberIndex,
			"isLeader", l.MyMemberIndex == leaderIdx,
		)

		if l.MyMemberIndex != leaderIdx {
			continue
		}

		bucketID := activeBucket

		buildArgs := &miner.BuildPayloadArgs{
			Parent:       argsLite.Parent,
			Timestamp:    argsLite.Timestamp,
			FeeRecipient: argsLite.FeeRecipient,
			Random:       argsLite.Random,
			Withdrawals:  argsLite.Withdrawals,
			BeaconRoot:   argsLite.BeaconRoot,
			Version:      argsLite.Version,
			NumBuckets:   uint32(l.NumBuckets),
		}

		txs, postRoot, err := l.buildExecutedFragment(ctx, buildArgs, uint32(bucketID))
		if err != nil {
			log.Warn("LeaderLoop build fragment failed", "bucket", bucketID, "err", err)
			continue
		}

		out := make([]hexutil.Bytes, 0, len(txs))
		for _, tx := range txs {
			b, err := tx.MarshalBinary()
			if err != nil {
				out = nil
				break
			}
			out = append(out, b)
		}
		if out == nil {
			continue
		}

		sendStart := time.Now()

		log.Debug("FRAGMENT SEND START",
			"bucket", bucketID,
			"txs", len(txs),
		)

		var ok bool
		err = l.OverlayRPC.CallContext(
			ctx,
			&ok,
			"overlay_submitFragment",
			active.Parent,
			active.Time,
			active.Version,
			uint32(bucketID),
			out,
			postRoot,
		)

		log.Debug("FRAGMENT SEND DONE",
			"bucket", bucketID,
			"txs", len(txs),
			"ok", ok,
			"err", err,
			"elapsed", time.Since(sendStart),
		)
		// bucketID := activeBucket
		// groupSize := l.Scheduler.NumBuckets()
		// for bucketID := 0; bucketID < groupSize; bucketID++ {
		// 	leaderIdx := bucket.LeaderIndex(active.Epoch, bucketID, groupSize)
		// 	if leaderIdx != l.MyIndex {
		// 		continue
		// 	}

		// 	buildArgs := &miner.BuildPayloadArgs{
		// 		Parent:       argsLite.Parent,
		// 		Timestamp:    argsLite.Timestamp,
		// 		FeeRecipient: argsLite.FeeRecipient,
		// 		Random:       argsLite.Random,
		// 		Withdrawals:  argsLite.Withdrawals,
		// 		BeaconRoot:   argsLite.BeaconRoot,
		// 		Version:      engine.PayloadVersion(argsLite.Version),
		// 	}

		// 	txs, postRoot, err := l.buildExecutedFragment(ctx, buildArgs, uint32(bucketID))
		// 	if err != nil {
		// 		continue
		// 	}

		// 	out := make([]hexutil.Bytes, 0, len(txs))
		// 	for _, tx := range txs {
		// 		b, err := tx.MarshalBinary()
		// 		if err != nil {
		// 			out = nil
		// 			break
		// 		}
		// 		out = append(out, b)
		// 	}
		// 	if out == nil {
		// 		continue
		// 	}

		// 	sendStart := time.Now()

		// 	log.Debug("FRAGMENT SEND START",
		// 		"bucket", bucketID,
		// 		"txs", len(txs),
		// 	)

		// 	log.Debug(
		// 		"LeaderLoop sending fragment",
		// 		"bucket", bucketID,
		// 		"txs", len(txs),
		// 		"hostname", os.Getenv("HOSTNAME"),)

		// 	var ok bool
		// 	_ = l.OverlayRPC.CallContext(ctx, &ok, "overlay_submitFragment", active.Parent, active.Time, active.Version, uint32(bucketID), out, postRoot)

		// 	log.Debug("FRAGMENT SEND DONE",
		// 		"bucket", bucketID,
		// 		"txs", len(txs),
		// 		"ok", ok,
		// 		"err", err,
		// 		"elapsed", time.Since(sendStart),
		// 	)
		// }
	}
}

// buildExecutedFragment executes the leader's bucket fragment using the existing geth selection code
func (l *LeaderLoop) buildExecutedFragment(ctx context.Context, args *miner.BuildPayloadArgs, bucketID uint32) ([]*types.Transaction, common.Hash, error) {
	return l.LocalEth.Miner().BuildExecutedFragment(args, bucketID)
}
