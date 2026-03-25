package bucket

import (
	"encoding/binary"
	"sync/atomic"

	"github.com/ethereum/go-ethereum/common"
)

const DefaultNumBuckets = 10

// Scheduler computes epoch + active bucket for a node's group.
type Scheduler struct {
	numBuckets     uint64
	groupID        uint64
	rotationBlocks uint64
	headBlock      atomic.Uint64
}

func NewScheduler(numBuckets int, groupID int, rotationBlocks uint64) *Scheduler {
	if numBuckets <= 0 {
		numBuckets = DefaultNumBuckets
	}
	if rotationBlocks == 0 {
		rotationBlocks = 1
	}
	s := &Scheduler{
		numBuckets:     uint64(numBuckets),
		groupID:        uint64(groupID),
		rotationBlocks: rotationBlocks,
	}
	s.headBlock.Store(0)
	return s
}

func (s *Scheduler) SetHeadBlock(blockNumber uint64) {
	s.headBlock.Store(blockNumber)
}

func (s *Scheduler) Epoch() uint64 {
	return s.headBlock.Load() / s.rotationBlocks
}

func (s *Scheduler) ActiveBucket() int {
	e := s.Epoch()
	return int((e + s.groupID) % s.numBuckets)
}

// Deterministic tx hash -> bucket mapping.
func BucketForHash(h common.Hash, numBuckets int) int {
	nb := uint64(numBuckets)
	if nb == 0 {
		nb = DefaultNumBuckets
	}
	// last 8 bytes for fast stable mapping
	v := binary.BigEndian.Uint64(h[24:32])
	return int(v % nb)
}

// Deterministic leader index inside group for given bucket.
func LeaderIndex(epoch uint64, bucketID int, groupSize int) int {
	if groupSize <= 0 {
		return 0
	}
	return int((epoch + uint64(bucketID)) % uint64(groupSize))
}


func (s *Scheduler) RotationBlocks() uint64 { return s.rotationBlocks }
func (s *Scheduler) NumBuckets() int        { return int(s.numBuckets) }