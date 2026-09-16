package txpool

import "github.com/ethereum/go-ethereum/src/bucket"
import "github.com/ethereum/go-ethereum/log"
import (
	"time"
)

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

// func (p *TxPool) IsLeaderForActiveBucket() bool {
// 	if !p.leaderGating {
// 		return true
// 	}
// 	if p.bucketSched == nil || p.groupSize <= 0 {
// 		return true // safe fallback (strict mode would return false)
// 	}
// 	epoch := p.bucketSched.Epoch()
// 	active := p.bucketSched.ActiveBucket()
// 	leader := bucket.LeaderIndex(epoch, p.groupID, p.groupSize)
// 	// leader := bucket.LeaderIndex(epoch, active, p.groupSize)
// 	log.Debug("Checking leader gating for active bucket", "epoch", epoch, "activeBucket", active, "leaderIndex", leader, "myMemberIndex", p.myMemberIndex)
// 	return p.myMemberIndex == leader
// }

// func (p *TxPool) IsLeaderForActiveBucket() bool {

// 	if !p.leaderGating {
// 		return true
// 	}

// 	if p.bucketSched == nil || p.groupSize <= 0 {
// 		return true
// 	}

// 	epoch := p.bucketSched.Epoch()
// 	active := p.bucketSched.ActiveBucket()

// 	// ============================================================
// 	// LEADER SELECTION TIMING START
// 	// ============================================================

// 	start := time.Now()

// 	leader := bucket.LeaderIndex(
// 		epoch,
// 		p.groupID,
// 		p.groupSize,
// 	)

// 	duration := time.Since(start)

// 	// ============================================================
// 	// LEADER RESULT
// 	// ============================================================

// 	isLeader := p.myMemberIndex == leader

// 	// ============================================================
// 	// DISPLAY IN GETH LOG
// 	// ============================================================

// 	log.Info(
// 		"LEADER SELECTION TIMING",
// 		"epoch", epoch,
// 		"activeBucket", active,
// 		"groupID", p.groupID,
// 		"groupSize", p.groupSize,
// 		"leaderIndex", leader,
// 		"myMemberIndex", p.myMemberIndex,
// 		"isLeader", isLeader,
// 		"durationNs", duration.Nanoseconds(),
// 		"durationUs", duration.Microseconds(),
// 	)

// 	// ============================================================
// 	// SAVE TO EXCEL
// 	// ============================================================

// 	p.recordLeaderSelectionMetric(
// 		LeaderSelectionMetric{
// 			TimestampUTC: time.Now().
// 				UTC().
// 				Format(time.RFC3339Nano),

// 			Epoch:        epoch,
// 			ActiveBucket: active,

// 			GroupID:   p.groupID,
// 			GroupSize: p.groupSize,

// 			LeaderIndex: leader,
// 			MemberIndex: p.myMemberIndex,

// 			IsLeader: isLeader,

// 			DurationNs: duration.Nanoseconds(),
// 			DurationUs: duration.Microseconds(),
// 		},
// 	)

// 	return isLeader
// }

func (p *TxPool) IsLeaderForActiveBucket() bool {
    if !p.leaderGating {
        return true
    }

    if p.bucketSched == nil || p.groupSize <= 0 {
        return true
    }

    epoch := p.bucketSched.Epoch()
    active := p.bucketSched.ActiveBucket()

    start := time.Now()

    leader := bucket.LeaderIndex(
        epoch,
        p.groupID,
        p.groupSize,
    )

    duration := time.Since(start)

    isLeader := p.myMemberIndex == leader

    log.Info(
        "LEADER SELECTION TIMING",
        "epoch", epoch,
        "activeBucket", active,
        "groupID", p.groupID,
        "groupSize", p.groupSize,
        "leaderIndex", leader,
        "myMemberIndex", p.myMemberIndex,
        "isLeader", isLeader,
        "durationNs", duration.Nanoseconds(),
        "durationUs", duration.Microseconds(),
    )

    return isLeader
}
