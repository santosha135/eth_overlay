package txpool

import (
	"sync"

	"github.com/ethereum/go-ethereum/common"
)

// BucketIndex keeps txHash -> bucketID mapping.
type BucketIndex struct {
	mu     sync.RWMutex
	byHash map[common.Hash]int
}

func newBucketIndex() *BucketIndex {
	return &BucketIndex{
		byHash: make(map[common.Hash]int, 8192),
	}
}

func (bi *BucketIndex) set(h common.Hash, bucketID int) {
	bi.mu.Lock()
	bi.byHash[h] = bucketID
	bi.mu.Unlock()
}

func (bi *BucketIndex) get(h common.Hash) (int, bool) {
	bi.mu.RLock()
	b, ok := bi.byHash[h]
	bi.mu.RUnlock()
	return b, ok
}

func (bi *BucketIndex) Del(h common.Hash) {
	bi.mu.Lock()
	delete(bi.byHash, h)
	bi.mu.Unlock()
}