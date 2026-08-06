// package txpool

// import "github.com/ethereum/go-ethereum/common"
// import "github.com/ethereum/go-ethereum/log"

// // PendingActiveBucket returns only txs in the active bucket.
// // If leader gating is enabled and this node is NOT leader, returns empty.
// func (p *TxPool) PendingActiveBucket(filter PendingFilter) map[common.Address][]*LazyTransaction {
// 	if !p.IsLeaderForActiveBucket() {
// 		return map[common.Address][]*LazyTransaction{}
// 	}
// 	if p.bucketSched == nil || p.bucketIdx == nil || p.numBuckets <= 0 {
// 		return p.Pending(filter)
// 	}

// 	active := p.bucketSched.ActiveBucket()
// 	log.Debug("Filtering pending transactions for active bucket", "activeBucket", active)
// 	all := p.Pending(filter)

// 	out := make(map[common.Address][]*LazyTransaction, len(all))
// 	for addr, set := range all {
// 		kept := set[:0]
// 		for _, lazy := range set {
// 			if lazy == nil {
// 				continue
// 			}
// 			if bid, ok := p.bucketIdx.get(lazy.Hash); ok && bid == active {
// 				kept = append(kept, lazy)
// 			}
// 		}
// 		if len(kept) > 0 {
// 			out[addr] = kept
// 		}
// 	}
// 	return out
// }
package txpool

import (
	"time"
	"github.com/ethereum/go-ethereum/common"
	"github.com/ethereum/go-ethereum/src/bucket"
	"github.com/ethereum/go-ethereum/log"
)

// PendingActiveBucket returns txs in the active bucket.
// Safety rule:
// If a tx has no bucket mapping, keep it instead of hiding it forever.
// func (p *TxPool) PendingActiveBucket(filter PendingFilter) map[common.Address][]*LazyTransaction {
// 	// if !p.IsLeaderForActiveBucket() {
// 	// 	log.Debug("Scheduler leader gating: not leader for active bucket",
// 	// 		"epoch", p.Epoch(),
// 	// 		"activeBucket", p.ActiveBucket(),
// 	// 	)
// 	// 	return map[common.Address][]*LazyTransaction{}
// 	// }

// 	if p.bucketSched == nil || p.bucketIdx == nil || p.numBuckets <= 0 {
// 		return p.Pending(filter)
// 	}

// 	// active := p.bucketSched.ActiveBucket()

// 	// active := p.bucketSched.ActiveBucket()
// 	// if forced, ok := p.ForcedActiveBucket(); ok {
// 	// 	active = forced
// 	// }

// 	// log.Debug("PENDING BUCKET DECISION",
// 	// 	"epoch", p.Epoch(),
// 	// 	"schedulerBucket", p.bucketSched.ActiveBucket(),
// 	// 	"forcedBucket", active,
// 	// 	"leaderGating", p.leaderGating,
// 	// 	"groupSize", p.groupSize,
// 	// 	"myMemberIndex", p.myMemberIndex,
// 	// )

// 	// if p.leaderGating && p.groupSize > 0 {
// 	// 	// leader := bucket.LeaderIndex(p.Epoch(), active, p.groupSize)
// 	// 	leader := bucket.LeaderIndex(p.Epoch(), p.groupID, p.groupSize)
// 	// 	log.Debug("PENDING BUCKET DECISION",
// 	// 		"epoch", p.Epoch(),
// 	// 		"activeBucket", active,
// 	// 		"groupID", p.groupID,
// 	// 		"groupSize", p.groupSize,
// 	// 		"leaderIndex", leader,
// 	// 		"myMemberIndex", p.myMemberIndex,
// 	// 		"isLeader", p.myMemberIndex == leader,
// 	// 	)
// 	// 	if p.myMemberIndex != leader {
// 	// 		log.Debug("Scheduler leader gating: not leader for bucket",
// 	// 			"epoch", p.Epoch(),
// 	// 			"bucket", active,
// 	// 			"leaderIndex", leader,
// 	// 			"myMemberIndex", p.myMemberIndex,
// 	// 		)
// 	// 		return map[common.Address][]*LazyTransaction{}
// 	// 	}
// 	// }
// 	// active := p.bucketSched.ActiveBucket()

// 	// forced, hasForced := p.ForcedActiveBucket()
// 	// if hasForced {
// 	// 	active = forced
// 	// }
// 	forced, hasForced := p.ForcedActiveBucket()

// 	// Critical latency fix:
// 	// normal proposer path should not wait for active bucket/leader.
// 	if !hasForced {
// 		return p.Pending(filter)
// 	}

// 	active := forced

// 	log.Debug("PENDING BUCKET DECISION",
// 		"epoch", p.Epoch(),
// 		"schedulerBucket", p.bucketSched.ActiveBucket(),
// 		"activeBucket", active,
// 		"hasForced", hasForced,
// 		"leaderGating", p.leaderGating,
// 		"groupID", p.groupID,
// 		"groupSize", p.groupSize,
// 		"myMemberIndex", p.myMemberIndex,
// 	)

// 	if p.leaderGating && p.groupSize > 0 && !hasForced {
// 		leader := bucket.LeaderIndex(p.Epoch(), p.groupID, p.groupSize)

// 		log.Debug("PENDING LEADER DECISION",
// 			"epoch", p.Epoch(),
// 			"activeBucket", active,
// 			"groupID", p.groupID,
// 			"groupSize", p.groupSize,
// 			"leaderIndex", leader,
// 			"myMemberIndex", p.myMemberIndex,
// 			"isLeader", p.myMemberIndex == leader,
// 		)

// 		if p.myMemberIndex != leader {
// 			return map[common.Address][]*LazyTransaction{}
// 		}
// 	}
		
	
// 	start := time.Now()
// 	all := p.Pending(filter)
// 	// all := p.Pending(filter)

// 	log.Debug("PENDING FETCH",
// 		"activeBucket", active,
// 		"accounts", len(all),
// 		"elapsed", time.Since(start),
// 	)

// 	out := make(map[common.Address][]*LazyTransaction, len(all))

// 	for addr, set := range all {
// 		kept := make([]*LazyTransaction, 0, len(set))

// 		for _, lazy := range set {
// 			if lazy == nil {
// 				continue
// 			}

// 			bid, ok := p.bucketIdx.get(lazy.Hash)

// 			// log.Debug("BUCKET FILTER CHECK",
// 			// 	"hash", lazy.Hash,
// 			// 	"activeBucket", active,
// 			// 	"mappedBucket", bid,
// 			// 	"hasMapping", ok,
// 			// )

// 			// Important safety fallback:
// 			// if tx has no bucket mapping, include it.
// 			if !ok {
// 				kept = append(kept, lazy)
// 				continue
// 			}

// 			// Future bucket tx should not be selected yet.
// 			if bid == futureBucketID {
// 				continue
// 			}

// 			if bid == active {
// 				kept = append(kept, lazy)
// 			}
// 		}

// 		if len(kept) > 0 {
// 			out[addr] = kept
// 		}
// 	}

// 	log.Debug("Scheduler pending bucket filter",
// 		"activeBucket", active,
// 		"accountsBefore", len(all),
// 		"accountsAfter", len(out),
// 	)

// 	return out
// }
func (p *TxPool) PendingActiveBucket(filter PendingFilter) map[common.Address][]*LazyTransaction {
	if p.bucketSched == nil || p.bucketIdx == nil || p.numBuckets <= 0 {
		return p.Pending(filter)
	}

	forced, hasForced := p.ForcedActiveBucket()

	// Normal final validator / proposer path should not be gated by the active
	// bucket logic. Only when a bucket is explicitly forced (fragment build)
	// do we restrict the returned transaction set to that bucket.
	if !hasForced {
		return p.Pending(filter)
	}

	active := forced

	// if p.leaderGating && p.groupSize > 0 && !p.IsLeaderForActiveBucket() {
	// 	log.Debug("Scheduler leader gating: not leader for active bucket",
	// 		"epoch", p.Epoch(),
	// 		"activeBucket", active,
	// 		"groupID", p.groupID,
	// 		"groupSize", p.groupSize,
	// 		"myMemberIndex", p.myMemberIndex,
	// 	)
	// 	return map[common.Address][]*LazyTransaction{}
	// }

	log.Debug("PENDING ACTIVE BUCKET",
		"epoch", p.Epoch(),
		"schedulerBucket", p.bucketSched.ActiveBucket(),
		"activeBucket", active,
		"groupID", p.groupID,
		"groupSize", p.groupSize,
		"myMemberIndex", p.myMemberIndex,
	)

	start := time.Now()
	all := p.Pending(filter)
	fetchElapsed := time.Since(start)
	log.Debug("PENDING FETCH",
		"activeBucket", active,
		"accounts", len(all),
		"elapsed_ms", fetchElapsed.Milliseconds(),
	)
	out := make(map[common.Address][]*LazyTransaction, len(all))

	for addr, set := range all {
		kept := make([]*LazyTransaction, 0, len(set))

		for _, lazy := range set {
			if lazy == nil {
				continue
			}

			bid, ok := p.bucketIdx.get(lazy.Hash)
			if !ok {
				bid = bucket.BucketForHash(lazy.Hash, p.numBuckets)
				p.bucketIdx.set(lazy.Hash, bid)
				log.Debug("Assigned unmapped tx to bucket on-the-fly", "hash", lazy.Hash, "bucketID", bid)
			}
			if bid == futureBucketID {
				// For future txs, optionally log admission age
				p.futureMu.Lock()
				addt, ok := p.futureAddTime[lazy.Hash]
				p.futureMu.Unlock()
				if ok {
					log.Debug("Skipping future tx (not yet promotable)", "hash", lazy.Hash, "admission_age_ms", time.Since(addt).Milliseconds())
				} else {
					log.Debug("Skipping future tx (not yet promotable)", "hash", lazy.Hash)
				}
				continue
			}
			if bid == active {
				kept = append(kept, lazy)
			}
		}

		if len(kept) > 0 {
			out[addr] = kept
		}
	}

	return out
}
var _ common.Address