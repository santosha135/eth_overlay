package txpool

import "github.com/ethereum/go-ethereum/src/bucket"
import "github.com/ethereum/go-ethereum/log"

func (p *TxPool) Epoch() uint64 {
	if p.bucketSched == nil {
		return 0
	}
	return p.bucketSched.Epoch()
}

func (p *TxPool) ActiveBucket() int {
	if p.bucketSched == nil {
		return 0
	}
	return p.bucketSched.ActiveBucket()
}

func (p *TxPool) IsLeaderForActiveBucket() bool {
	if !p.leaderGating {
		return true
	}
	if p.bucketSched == nil || p.groupSize <= 0 {
		return true // safe fallback (strict mode would return false)
	}
	epoch := p.bucketSched.Epoch()
	active := p.bucketSched.ActiveBucket()
	leader := bucket.LeaderIndex(epoch, active, p.groupSize)
	log.Info("Checking leader gating for active bucket", "epoch", epoch, "activeBucket", active, "leaderIndex", leader, "myMemberIndex", p.myMemberIndex)
	return p.myMemberIndex == leader
}