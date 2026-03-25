package catalyst

import (
	"context"
	"sync"

	"github.com/ethereum/go-ethereum/common"
	"github.com/ethereum/go-ethereum/core/types"
	"github.com/ethereum/go-ethereum/miner"
	"github.com/ethereum/go-ethereum/src/bucket"
	"github.com/ethereum/go-ethereum/beacon/engine"
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

type ExecFragment struct {
	BucketID  uint32
	Txs       []*types.Transaction
	PostRoot  common.Hash
}

// OverlaySvc stores leader-executed fragments keyed by (payloadID, bucketID).
type OverlaySvc struct {
	mu      	sync.RWMutex
	args 		map[SlotKey]*OverlayArgs 			// slot args for leaders
	frags 		map[SlotKey]map[uint32]ExecFragment // fragments keyed by slot then bucket
	scheduler 	*bucket.Scheduler 							// scheduler for leader selection
	active		SlotKey 							// active slot
	activeSet  	bool
	activeEpoch uint64	
}

func NewOverlaySvc(sched *bucket.Scheduler) *OverlaySvc {
	return &OverlaySvc{
		args:      make(map[SlotKey]*OverlayArgs),
		frags:     make(map[SlotKey]map[uint32]ExecFragment),
		scheduler: sched,
	}
}

func (o *OverlaySvc) SetActiveSlot(slotkey SlotKey, epoch uint64, args *OverlayArgs) {
	o.mu.Lock()
	o.active = slotkey
	o.activeSet = true
	o.activeEpoch = epoch

	// store args for leaders
	arg_cp := *args
	o.args[slotkey] = &arg_cp

	// ensure frag map exists
	if o.frags[slotkey] == nil {
		o.frags[slotkey] = make(map[uint32]ExecFragment)
	}
	o.mu.Unlock()
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

// PutFragment method used by Leaders.
// Overwrites a fragment for (payloadID, bucketID).
func (o *OverlaySvc) PutFragment(slot SlotKey, bucketID uint32, txs []*types.Transaction, postRoot common.Hash) {
	tx_list := append([]*types.Transaction(nil), txs...)

	o.mu.Lock() //Make sure no one tryes to alter overlay
	frag_list := o.frags[slot]
	if frag_list == nil {
		frag_list = make(map[uint32]ExecFragment)
		o.frags[slot] = frag_list
	}
	frag_list[bucketID] = ExecFragment{BucketID: bucketID, Txs: tx_list, PostRoot: postRoot}
	o.mu.Unlock()
}

// FragmentProvider method used by Validator.
// Returns (txs, postRoot, ok).
func (o *OverlaySvc) GetFragment(slot SlotKey, bucketID uint32) ([]*types.Transaction, common.Hash, bool) {
	o.mu.RLock()
	defer o.mu.RUnlock()
	frag_list := o.frags[slot]
	if frag_list == nil {
		return nil, common.Hash{}, false
	}
	fragment, ok := frag_list[bucketID]
	if !ok {
		return nil, common.Hash{}, false
	}
	return fragment.Txs, fragment.PostRoot, true
}

// BeginSlot: attach fragment provider to the args so miner can pull fragments.
func (o *OverlaySvc) BeginSlot(ctx context.Context, slot SlotKey, args *miner.BuildPayloadArgs) {
	args.FragmentKey = slot.ID()
	args.FragPro = &slotFragmentProvider{o: o, slot: slot}}

func (o *OverlaySvc) EndSlot(slot SlotKey) {
	o.mu.Lock()
	delete(o.args, slot)
	delete(o.frags, slot)
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
