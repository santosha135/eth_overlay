package catalyst

import (
	"context"
	"sync"
	"time"

	"github.com/ethereum/go-ethereum/beacon/engine"
	"github.com/ethereum/go-ethereum/common"
	"github.com/ethereum/go-ethereum/core/types"
	"github.com/ethereum/go-ethereum/miner"
	"github.com/ethereum/go-ethereum/src/bucket"
)

type OverlayArgs struct {
	Parent       common.Hash
	Timestamp    uint64
	FeeRecipient common.Address
	Random       common.Hash
	Withdrawals  types.Withdrawals
	BeaconRoot   *common.Hash
	Version      engine.PayloadVersion // engine.PayloadVersion underlying
}

// OverlaySvc stores leader-built sub-blocks keyed by (slot, bucketID).
type OverlaySvc struct {
	mu            sync.RWMutex
	args          map[SlotKey]*OverlayArgs                 // slot args for leaders
	subs          map[SlotKey]map[uint32]*miner.SubBlock   // sub-blocks keyed by slot then bucket
	meta          map[SlotKey]map[uint32]miner.SubBlockMeta // arrival time and wire size, for metrics
	scheduler     *bucket.Scheduler                        // scheduler for leader selection
	active        SlotKey                                  // active slot
	activeSet     bool
	activeEpoch   uint64
	numBuckets    int
	groupID       int
	groupSize     int
	myMemberIndex int
}

func NewOverlaySvc(sched *bucket.Scheduler, numBuckets, groupID, groupSize, myMemberIndex int) *OverlaySvc {
	return &OverlaySvc{
		args:          make(map[SlotKey]*OverlayArgs),
		subs:          make(map[SlotKey]map[uint32]*miner.SubBlock),
		meta:          make(map[SlotKey]map[uint32]miner.SubBlockMeta),
		scheduler:     sched,
		numBuckets:    numBuckets,
		groupID:       groupID,
		groupSize:     groupSize,
		myMemberIndex: myMemberIndex,
	}
}

func (o *OverlaySvc) SetActiveSlot(slotkey SlotKey, epoch uint64, args *OverlayArgs) {
	o.mu.Lock()
	defer o.mu.Unlock()

	o.active = slotkey
	o.activeSet = true
	o.activeEpoch = epoch

	argCopy := *args
	o.args[slotkey] = &argCopy

	if o.subs[slotkey] == nil {
		o.subs[slotkey] = make(map[uint32]*miner.SubBlock)
	}
	if o.meta[slotkey] == nil {
		o.meta[slotkey] = make(map[uint32]miner.SubBlockMeta)
	}

	// Keep only current slot to prevent unbounded memory growth.
	for k := range o.args {
		if k != slotkey {
			delete(o.args, k)
		}
	}
	for k := range o.subs {
		if k != slotkey {
			delete(o.subs, k)
		}
	}
	for k := range o.meta {
		if k != slotkey {
			delete(o.meta, k)
		}
	}
}

func (o *OverlaySvc) GetActiveSlot() (SlotKey, uint64, bool) {
	o.mu.RLock()
	defer o.mu.RUnlock()
	return o.active, o.activeEpoch, o.activeSet
}

func (o *OverlaySvc) GetSlotArgs(slotkey SlotKey) (*OverlayArgs, bool) {
	o.mu.RLock()
	defer o.mu.RUnlock()
	a, ok := o.args[slotkey]
	return a, ok
}

// PutSubBlock is used by leaders. It overwrites the sub-block for
// (slot, bucketID).
func (o *OverlaySvc) PutSubBlock(slot SlotKey, sub *miner.SubBlock, blobBytes int) {
	if sub == nil {
		return
	}

	receivedAt := time.Now()

	o.mu.Lock() // Make sure no one tries to alter the overlay
	sub_list := o.subs[slot]
	if sub_list == nil {
		sub_list = make(map[uint32]*miner.SubBlock)
		o.subs[slot] = sub_list
	}
	sub_list[sub.BucketID] = sub

	meta_list := o.meta[slot]
	if meta_list == nil {
		meta_list = make(map[uint32]miner.SubBlockMeta)
		o.meta[slot] = meta_list
	}
	meta_list[sub.BucketID] = miner.SubBlockMeta{ReceivedAt: receivedAt, BlobBytes: blobBytes}
	o.mu.Unlock()
}

// GetSubBlockMeta reports when a sub-block landed here and how big it was on the
// wire.
func (o *OverlaySvc) GetSubBlockMeta(slot SlotKey, bucketID uint32) (miner.SubBlockMeta, bool) {
	o.mu.RLock()
	defer o.mu.RUnlock()
	meta_list := o.meta[slot]
	if meta_list == nil {
		return miner.SubBlockMeta{}, false
	}
	meta, ok := meta_list[bucketID]
	return meta, ok
}

// PutFragment is the legacy path: a bare tx list with a claimed post root and no
// state diff. It is stored as a sub-block the merge can only re-execute.
func (o *OverlaySvc) PutFragment(slot SlotKey, bucketID uint32, txs []*types.Transaction, postRoot common.Hash) {
	o.PutSubBlock(slot, &miner.SubBlock{
		BucketID: bucketID,
		Txs:      append([]*types.Transaction(nil), txs...),
		PostRoot: postRoot,
	}, 0)
}

// GetSubBlock is used by the proposer to collect what the leaders built.
func (o *OverlaySvc) GetSubBlock(slot SlotKey, bucketID uint32) (*miner.SubBlock, bool) {
	o.mu.RLock()
	defer o.mu.RUnlock()
	sub_list := o.subs[slot]
	if sub_list == nil {
		return nil, false
	}
	sub, ok := sub_list[bucketID]
	if !ok || sub == nil {
		return nil, false
	}
	return sub, true
}

// GetFragment is the narrower view of a stored sub-block.
func (o *OverlaySvc) GetFragment(slot SlotKey, bucketID uint32) ([]*types.Transaction, common.Hash, bool) {
	sub, ok := o.GetSubBlock(slot, bucketID)
	if !ok {
		return nil, common.Hash{}, false
	}
	return sub.Txs, sub.PostRoot, true
}

// BeginSlot: attach the sub-block provider to the args so the miner can pull
// sub-blocks.
func (o *OverlaySvc) BeginSlot(ctx context.Context, slot SlotKey, args *miner.BuildPayloadArgs) {
	args.FragmentKey = slot.ID()
	args.FragPro = &slotFragmentProvider{o: o, slot: slot}
}

func (o *OverlaySvc) EndSlot(slot SlotKey) {
	o.mu.Lock()
	delete(o.args, slot)
	delete(o.subs, slot)
	delete(o.meta, slot)
	o.mu.Unlock()
}

// Adapter that satisfies miner.FragmentProvider.
type slotFragmentProvider struct {
	o    *OverlaySvc
	slot SlotKey
}

func (p *slotFragmentProvider) GetFragment(bucketID uint32) ([]*types.Transaction, common.Hash, bool) {
	return p.o.GetFragment(p.slot, bucketID)
}

func (p *slotFragmentProvider) GetSubBlock(bucketID uint32) (*miner.SubBlock, bool) {
	return p.o.GetSubBlock(p.slot, bucketID)
}

func (p *slotFragmentProvider) GetSubBlockMeta(bucketID uint32) (miner.SubBlockMeta, bool) {
	return p.o.GetSubBlockMeta(p.slot, bucketID)
}
