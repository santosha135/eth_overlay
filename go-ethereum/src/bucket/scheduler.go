// package bucket

// import (
// 	"encoding/binary"
// 	"sync/atomic"

// 	"github.com/ethereum/go-ethereum/common"
// )

// const DefaultNumBuckets = 10

// // Scheduler computes epoch + active bucket for a node's group.
// type Scheduler struct {
// 	numBuckets     uint64
// 	groupID        uint64
// 	rotationBlocks uint64
// 	headBlock      atomic.Uint64
// }

// func NewScheduler(numBuckets int, groupID int, rotationBlocks uint64) *Scheduler {
// 	if numBuckets <= 0 {
// 		numBuckets = DefaultNumBuckets
// 	}
// 	if rotationBlocks == 0 {
// 		rotationBlocks = 1
// 	}
// 	s := &Scheduler{
// 		numBuckets:     uint64(numBuckets),
// 		groupID:        uint64(groupID),
// 		rotationBlocks: rotationBlocks,
// 	}
// 	s.headBlock.Store(0)
// 	return s
// }

// func (s *Scheduler) SetHeadBlock(blockNumber uint64) {
// 	s.headBlock.Store(blockNumber)
// }

// func (s *Scheduler) Epoch() uint64 {
// 	return s.headBlock.Load() / s.rotationBlocks
// }

// func (s *Scheduler) ActiveBucket() int {
// 	e := s.Epoch()
// 	return int((e + s.groupID) % s.numBuckets)
// }

// // Deterministic tx hash -> bucket mapping.
// func BucketForHash(h common.Hash, numBuckets int) int {
// 	nb := uint64(numBuckets)
// 	if nb == 0 {
// 		nb = DefaultNumBuckets
// 	}
// 	// last 8 bytes for fast stable mapping
// 	v := binary.BigEndian.Uint64(h[24:32])
// 	return int(v % nb)
// }

// // Deterministic leader index inside group for given bucket.
// // func LeaderIndex(epoch uint64, bucketID int, groupSize int) int {
// // 	if groupSize <= 0 {
// // 		return 0
// // 	}
// // 	return int((epoch + uint64(bucketID)) % uint64(groupSize))
// // }

// func LeaderIndex(epoch uint64, groupID int, groupSize int) int {
// 	if groupSize <= 0 {
// 		return 0
// 	}
// 	return int(epoch % uint64(groupSize))
// }
// // func LeaderIndex(epoch uint64, bucketID int, groupSize int) int {
// // 	if groupSize <= 0 {
// // 		return 0
// // 	}

// // 	leader := (bucketID - int(epoch%uint64(groupSize))) % groupSize
// // 	if leader < 0 {
// // 		leader += groupSize
// // 	}
// // 	return leader
// // }
// // func LeaderIndex(epoch uint64, bucketID int, groupSize int) int {
// // 	if groupSize <= 0 {
// // 		return 0
// // 	}

// // 	leader := bucketID % groupSize
// // 	if leader < 0 {
// // 		leader += groupSize
// // 	}
// // 	return leader
// // }


// func (s *Scheduler) RotationBlocks() uint64 { return s.rotationBlocks }
// func (s *Scheduler) NumBuckets() int        { return int(s.numBuckets) }

// func (s *Scheduler) GroupID() int {
// 	return int(s.groupID)
// }

// func (s *Scheduler) MemberIndex() int {
// 	// return int(s.groupID)
// 	return 0

// }
package bucket

import (
	"encoding/binary"
	"sync/atomic"

	"github.com/ethereum/go-ethereum/common"
)

const DefaultNumBuckets = 15

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
	if groupID < 0 {
		groupID = 0
	}
	groupID = groupID % numBuckets

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
	return ActiveBucketForGroup(s.Epoch(), int(s.groupID), int(s.numBuckets))
}

func (s *Scheduler) RotationBlocks() uint64 { return s.rotationBlocks }
func (s *Scheduler) NumBuckets() int        { return int(s.numBuckets) }
func (s *Scheduler) GroupID() int           { return int(s.groupID) }

// Deterministic tx hash -> bucket mapping.
func BucketForHash(h common.Hash, numBuckets int) int {
	nb := uint64(numBuckets)
	if nb == 0 {
		nb = DefaultNumBuckets
	}
	v := binary.BigEndian.Uint64(h[24:32])
	return int(v % nb)
}

// Deterministic pseudo-random number.
func splitmix64(x uint64) uint64 {
	x += 0x9e3779b97f4a7c15
	x = (x ^ (x >> 30)) * 0xbf58476d1ce4e5b9
	x = (x ^ (x >> 27)) * 0x94d049bb133111eb
	return x ^ (x >> 31)
}

// ActiveBucketForGroup gives one unique active bucket per group.
// It creates a deterministic random permutation of buckets per epoch.
//
// Example epoch 0 may produce:
// group 0 -> bucket 7
// group 1 -> bucket 2
// ...
//
// Epoch 1 produces a different deterministic mapping.
// All nodes compute the same result.
func ActiveBucketForGroup(epoch uint64, groupID int, numBuckets int) int {
	if numBuckets <= 0 {
		numBuckets = DefaultNumBuckets
	}
	if groupID < 0 {
		groupID = 0
	}
	groupID = groupID % numBuckets

	perm := make([]int, numBuckets)
	for i := 0; i < numBuckets; i++ {
		perm[i] = i
	}

	seed := splitmix64(epoch ^ 0xBADC0FFEE)
	for i := numBuckets - 1; i > 0; i-- {
		r := splitmix64(seed + uint64(i))
		j := int(r % uint64(i+1))
		perm[i], perm[j] = perm[j], perm[i]
	}

	return perm[groupID]
}

// BuildMinerGroupAssignment creates your required group layout.
//
// For 10 buckets, 12 miners:
// miner 0  -> group 0 member 0
// miner 1  -> group 1 member 0
// ...
// miner 9  -> group 9 member 0
// miner 10 -> group 1 member 1
// miner 11 -> group 0 member 1
func BuildMinerGroupAssignment(minerIndex int, totalMiners int, numBuckets int) (groupID int, memberIndex int, groupSize int) {
	if numBuckets <= 0 {
		numBuckets = DefaultNumBuckets
	}
	if totalMiners <= 0 {
		totalMiners = numBuckets
	}
	if minerIndex < 0 {
		minerIndex = 0
	}
	if minerIndex >= totalMiners {
		minerIndex = minerIndex % totalMiners
	}

	groups := make([][]int, numBuckets)

	// First numBuckets miners: one base miner per bucket group.
	base := totalMiners
	if base > numBuckets {
		base = numBuckets
	}
	for i := 0; i < base; i++ {
		groups[i] = append(groups[i], i)
	}

	// Extra miners are assigned in reverse order to low bucket groups.
	// For 12 miners, 10 buckets:
	// miner 10 -> group 1
	// miner 11 -> group 0
	extra := totalMiners - numBuckets
	for i := numBuckets; i < totalMiners; i++ {
		offset := i - numBuckets
		g := extra - 1 - offset
		if g < 0 {
			g = ((g % numBuckets) + numBuckets) % numBuckets
		}
		g = g % numBuckets
		groups[g] = append(groups[g], i)
	}

	for g, members := range groups {
		for idx, m := range members {
			if m == minerIndex {
				return g, idx, len(members)
			}
		}
	}

	return 0, 0, 1
}

// Deterministic random leader inside the group.
func LeaderIndex(epoch uint64, groupID int, groupSize int) int {
	if groupSize <= 1 {
		return 0
	}
	r := splitmix64(epoch ^ uint64(groupID)*0x9e3779b97f4a7c15)
	return int(r % uint64(groupSize))
}