package txpool

import "github.com/ethereum/go-ethereum/common"
import "github.com/ethereum/go-ethereum/log"

// PendingActiveBucket returns only txs in the active bucket.
// If leader gating is enabled and this node is NOT leader, returns empty.
func (p *TxPool) PendingActiveBucket(filter PendingFilter) map[common.Address][]*LazyTransaction {
	if !p.IsLeaderForActiveBucket() {
		return map[common.Address][]*LazyTransaction{}
	}
	if p.bucketSched == nil || p.bucketIdx == nil || p.numBuckets <= 0 {
		return p.Pending(filter)
	}

	active := p.bucketSched.ActiveBucket()
	log.Info("Filtering pending transactions for active bucket", "activeBucket", active)
	all := p.Pending(filter)

	out := make(map[common.Address][]*LazyTransaction, len(all))
	for addr, set := range all {
		kept := set[:0]
		for _, lazy := range set {
			if lazy == nil {
				continue
			}
			if bid, ok := p.bucketIdx.get(lazy.Hash); ok && bid == active {
				kept = append(kept, lazy)
			}
		}
		if len(kept) > 0 {
			out[addr] = kept
		}
	}
	return out
}