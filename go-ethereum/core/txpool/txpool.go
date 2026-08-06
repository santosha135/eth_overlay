// Copyright 2014 The go-ethereum Authors
// This file is part of the go-ethereum library.
//
// The go-ethereum library is free software: you can redistribute it and/or modify
// it under the terms of the GNU Lesser General Public License as published by
// the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.
//
// The go-ethereum library is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
// GNU Lesser General Public License for more details.
//
// You should have received a copy of the GNU Lesser General Public License
// along with the go-ethereum library. If not, see <http://www.gnu.org/licenses/>.

package txpool

import (
	"os"
	"strconv"
	"sync/atomic"
	"time"
	"regexp"
	"errors"
	"fmt"
	"math/big"
	"sync"
	"encoding/binary"
	"github.com/ethereum/go-ethereum/crypto"
	"github.com/ethereum/go-ethereum/src/bucket"
	// "github.com/ethereum/go-ethereum/src"
	
	"github.com/ethereum/go-ethereum/common"
	"github.com/ethereum/go-ethereum/core"
	"github.com/ethereum/go-ethereum/core/state"
	"github.com/ethereum/go-ethereum/core/types"
	"github.com/ethereum/go-ethereum/event"
	"github.com/ethereum/go-ethereum/log"
	"github.com/ethereum/go-ethereum/params"

)

// TxStatus is the current status of a transaction as seen by the pool.
type TxStatus uint

const (
	TxStatusUnknown TxStatus = iota
	TxStatusQueued
	TxStatusPending
	TxStatusIncluded
	
)

const futureBucketID = -1

// BlockChain defines the minimal set of methods needed to back a tx pool with
// a chain. Exists to allow mocking the live chain out of tests.
type BlockChain interface {
	// Config retrieves the chain's fork configuration.
	Config() *params.ChainConfig

	// CurrentBlock returns the current head of the chain.
	CurrentBlock() *types.Header

	// SubscribeChainHeadEvent subscribes to new blocks being added to the chain.
	SubscribeChainHeadEvent(ch chan<- core.ChainHeadEvent) event.Subscription

	// StateAt returns a state database for a given root hash (generally the head).
	StateAt(root common.Hash) (*state.StateDB, error)
}

// TxPool is an aggregator for various transaction specific pools, collectively
// tracking all the transactions deemed interesting by the node. Transactions
// enter the pool when they are received from the network or submitted locally.
// They exit the pool when they are included in the blockchain or evicted due to
// resource constraints.
type TxPool struct {
	subpools []SubPool // List of subpools for specialized transaction handling
	chain    BlockChain

	stateLock sync.RWMutex   // The lock for protecting state instance
	state     *state.StateDB // Current state at the blockchain head

	subs event.SubscriptionScope // Subscription scope to unsubscribe all on shutdown
	quit chan chan error         // Quit channel to tear down the head updater
	term chan struct{}           // Termination channel to detect a closed pool

	sync chan chan error // Testing / simulator channel to block until internal reset is done
	// bucket *bucket.Bucket

	senderMu sync.Mutex
	// ---- future bucket tracking (per sender) ----
	futureMu sync.Mutex
	// future   map[common.Address]map[uint64]*types.Transaction // sender -> nonce -> txHash
	future map[common.Address]map[uint64]common.Hash
	futureAddTime map[common.Hash]time.Time
		// ---- bucket config ----
	numBuckets     int
	groupID        int
	rotationBlocks uint64

	// ---- leader config ----
	leaderGating  bool
	groupSize     int
	myMemberIndex int

	// ---- runtime ----
	bucketSched *bucket.Scheduler
	bucketIdx   *BucketIndex

	forcedActiveBucket atomic.Int64


}

func detectMemberIndexFromHostname() (int, bool) {
	hostname, err := os.Hostname()
	if err != nil {
		log.Warn("Could not read hostname for scheduler identity", "err", err)
		return 0, false
	}

	// Expected pod hostname:
	// el-01-geth-lighthouse
	// el-02-geth-lighthouse
	// ...
	// el-10-geth-lighthouse
	re := regexp.MustCompile(`^el-([0-9]+)-`)
	matches := re.FindStringSubmatch(hostname)
	if len(matches) != 2 {
		log.Warn("Could not detect scheduler member index from hostname", "hostname", hostname)
		return 0, false
	}

	nodeNum, err := strconv.Atoi(matches[1])
	if err != nil || nodeNum <= 0 {
		log.Warn("Invalid node number in hostname", "hostname", hostname, "nodeNum", matches[1])
		return 0, false
	}

	memberIndex := nodeNum - 1

	log.Debug("Detected scheduler identity from hostname",
		"hostname", hostname,
		"nodeNum", nodeNum,
		"memberIndex", memberIndex,
	)

	return memberIndex, true
}

func getenvInt(name string, def int) int {
	v := os.Getenv(name)
	if v == "" {
		return def
	}
	n, err := strconv.Atoi(v)
	if err != nil {
		log.Warn("Invalid scheduler env int, using default", "name", name, "value", v, "default", def)
		return def
	}
	return n
}

func getenvBool(name string, def bool) bool {
	v := os.Getenv(name)
	if v == "" {
		return def
	}
	b, err := strconv.ParseBool(v)
	if err != nil {
		log.Warn("Invalid scheduler env bool, using default", "name", name, "value", v, "default", def)
		return def
	}
	return b
}

// New creates a new transaction pool to gather, sort and filter inbound
// transactions from the network.
func New(gasTip uint64, chain BlockChain, subpools []SubPool) (*TxPool, error) {
	// Retrieve the current head so that all subpools and this main coordinator
	// pool will have the same starting state, even if the chain moves forward
	// during initialization.
	head := chain.CurrentBlock()

	// Initialize the state with head block, or fallback to empty one in
	// case the head state is not available (might occur when node is not
	// fully synced).
	statedb, err := chain.StateAt(head.Root)
	if err != nil {
		statedb, err = chain.StateAt(types.EmptyRootHash)
	}
	if err != nil {
		return nil, err
	}
	pool := &TxPool{
		subpools: subpools,
		chain:    chain,
		state:    statedb,
		quit:     make(chan chan error),
		term:     make(chan struct{}),
		sync:     make(chan chan error),
		// bucket:   bucket.New(),
	}

	// pool.future = make(map[common.Address]map[uint64]*types.Transaction)
	pool.future = make(map[common.Address]map[uint64]common.Hash)
	pool.futureAddTime = make(map[common.Hash]time.Time)

		// ---- BUCKET + LEADER CONFIG (static for now) ----
	// pool.numBuckets = 4
	// pool.groupID = 0              // TODO: set per node
	// pool.rotationBlocks = 1       // rotate every N blocks (1 = every block)

	// pool.leaderGating = true
	// pool.groupSize = 1            // TODO: number of miners/workers in this group
	// pool.myMemberIndex = 0        // TODO: unique id within group [0..groupSize-1]

	// pool.numBuckets = getenvInt("GETH_SCHED_NUM_BUCKETS", 1)
	// pool.groupID = getenvInt("GETH_SCHED_GROUP_ID", 0)
	// pool.rotationBlocks = uint64(getenvInt("GETH_SCHED_ROTATION_BLOCKS", 1))

	// pool.leaderGating = getenvBool("GETH_SCHED_LEADER_GATING", false)
	// pool.groupSize = getenvInt("GETH_SCHED_GROUP_SIZE", 10)
	// pool.myMemberIndex = getenvInt("GETH_SCHED_MEMBER_INDEX", pool.groupID)
	pool.numBuckets = getenvInt("GETH_SCHED_NUM_BUCKETS", 15)
	pool.rotationBlocks = uint64(getenvInt("GETH_SCHED_ROTATION_BLOCKS", 1))

	pool.leaderGating = getenvBool("GETH_SCHED_LEADER_GATING", true)
	// pool.groupSize = getenvInt("GETH_SCHED_GROUP_SIZE", pool.numBuckets)

	// // Default identity from env
	// pool.groupID = getenvInt("GETH_SCHED_GROUP_ID", -1)
	// pool.myMemberIndex = getenvInt("GETH_SCHED_MEMBER_INDEX", -1)

	// pool.numBuckets = getenvInt("GETH_SCHED_NUM_BUCKETS", 10)
	// pool.rotationBlocks = uint64(getenvInt("GETH_SCHED_ROTATION_BLOCKS", 1))
	// pool.leaderGating = getenvBool("GETH_SCHED_LEADER_GATING", true)

	totalMiners := getenvInt("GETH_SCHED_TOTAL_MINERS", 30)

	minerIndex := getenvInt("GETH_SCHED_MINER_INDEX", -1)
	if minerIndex < 0 {
		minerIndex = getenvInt("GETH_SCHED_MEMBER_INDEX", -1)
	}
	if minerIndex < 0 {
		if detected, ok := detectMemberIndexFromHostname(); ok {
			minerIndex = detected
		}
	}
	if minerIndex < 0 {
		minerIndex = 0
	}

	// pool.groupID = minerIndex % pool.numBuckets
	// pool.myMemberIndex = minerIndex / pool.numBuckets

	// pool.groupSize = 1 + (totalMiners-1-pool.groupID)/pool.numBuckets
	// if pool.groupSize <= 0 {
	// 	pool.groupSize = 1
	// }
	pool.groupID, pool.myMemberIndex, pool.groupSize =
	bucket.BuildMinerGroupAssignment(minerIndex, totalMiners, pool.numBuckets)

	log.Debug("Tx scheduler config",
		"numBuckets", pool.numBuckets,
		"totalMiners", totalMiners,
		"minerIndex", minerIndex,
		"groupID", pool.groupID,
		"memberIndex", pool.myMemberIndex,
		"groupSize", pool.groupSize,
		"rotationBlocks", pool.rotationBlocks,
		"leaderGating", pool.leaderGating,
	)
	// If env is missing, auto-detect from hostname
	if pool.groupID < 0 || pool.myMemberIndex < 0 {
		if detected, ok := detectMemberIndexFromHostname(); ok {
			if pool.groupID < 0 {
				pool.groupID = detected
			}
			if pool.myMemberIndex < 0 {
				pool.myMemberIndex = detected
			}
		}
	}

	// Final fallback
	if pool.groupID < 0 {
		pool.groupID = 0
	}
	if pool.myMemberIndex < 0 {
		pool.myMemberIndex = 0
	}

	if pool.groupID < 0 || pool.groupID >= pool.numBuckets {
		log.Warn("Invalid groupID, normalizing", "groupID", pool.groupID, "numBuckets", pool.numBuckets)
		pool.groupID = pool.groupID % pool.numBuckets
		if pool.groupID < 0 {
			pool.groupID += pool.numBuckets
		}
	}

	log.Debug("Tx scheduler config",
		"numBuckets", pool.numBuckets,
		"groupID", pool.groupID,
		"rotationBlocks", pool.rotationBlocks,
		"leaderGating", pool.leaderGating,
		"groupSize", pool.groupSize,
		"memberIndex", pool.myMemberIndex,
	)

	if pool.myMemberIndex < 0 || pool.myMemberIndex >= pool.groupSize {
		log.Warn("Invalid memberIndex, normalizing",
			"memberIndex", pool.myMemberIndex,
			"groupSize", pool.groupSize,
		)
		pool.myMemberIndex = pool.myMemberIndex % pool.groupSize
		if pool.myMemberIndex < 0 {
			pool.myMemberIndex += pool.groupSize
		}
	}

	pool.bucketSched = bucket.NewScheduler(pool.numBuckets, pool.groupID, pool.rotationBlocks)
	pool.bucketIdx = newBucketIndex()

	pool.forcedActiveBucket.Store(-1)
	
	// ---- ADDRESS POLICY (censorship + hard-coded address detection) ----
	// Configure via env var GETH_CENSORSHIP_CONFIG (JSON file). If unset, defaults to ./blocked_addresses.json.
	policyPath := os.Getenv("GETH_CENSORSHIP_CONFIG")
	if policyPath == "" {
		policyPath = "blocked_addresses.json"
	}
	if pol, err := LoadAddressPolicyJSON(policyPath); err != nil {
		log.Warn("Address policy not loaded (continuing without it)", "path", policyPath, "err", err)
	} else if pol != nil && pol.Enabled {
		SetAddressPolicy(pol)
		log.Debug("Address policy loaded", "path", policyPath, "rejectAnyHardcoded", pol.RejectAnyHardcoded, "blocked", len(pol.BlockedMap))
	} else {
		log.Debug("Address policy disabled", "path", policyPath)
	}


	if head != nil {
		pool.bucketSched.SetHeadBlock(head.Number.Uint64())
	}

	reserver := NewReservationTracker()
	// for i, subpool := range subpools {
	// 	if err := subpool.Init(gasTip, head, reserver.NewHandle(i)); err != nil {
	// 		subpool.SetBucketIndex(pool.bucketIdx) // inject bucket index to subpools initialized so far
	// 		for j := i - 1; j >= 0; j-- {
	// 			subpools[j].Close()
	// 		}
	// 		return nil, err
	// 	}
	// }
	for i, subpool := range subpools {
	subpool.SetBucketIndex(pool.bucketIdx)

	if err := subpool.Init(gasTip, head, reserver.NewHandle(i)); err != nil {
		for j := i - 1; j >= 0; j-- {
			subpools[j].Close()
		}
		return nil, err
	}
	}
	go pool.loop(head)
	return pool, nil
}

// Close terminates the transaction pool and all its subpools.
func (p *TxPool) Close() error {
	var errs []error

	// Terminate the reset loop and wait for it to finish
	errc := make(chan error)
	p.quit <- errc
	if err := <-errc; err != nil {
		errs = append(errs, err)
	}
	// Terminate each subpool
	for _, subpool := range p.subpools {
		if err := subpool.Close(); err != nil {
			errs = append(errs, err)
		}
	}
	// Unsubscribe anyone still listening for tx events
	p.subs.Close()

	if len(errs) > 0 {
		return fmt.Errorf("subpool close errors: %v", errs)
	}
	return nil
}

// loop is the transaction pool's main event loop, waiting for and reacting to
// outside blockchain events as well as for various reporting and transaction
// eviction events.
func (p *TxPool) loop(head *types.Header) {
	// Close the termination marker when the pool stops
	defer close(p.term)

	// Subscribe to chain head events to trigger subpool resets
	var (
		newHeadCh  = make(chan core.ChainHeadEvent)
		newHeadSub = p.chain.SubscribeChainHeadEvent(newHeadCh)
	)
	defer newHeadSub.Unsubscribe()

	// Track the previous and current head to feed to an idle reset
	var (
		oldHead = head
		newHead = oldHead
	)
	// Consume chain head events and start resets when none is running
	var (
		resetBusy = make(chan struct{}, 1) // Allow 1 reset to run concurrently
		resetDone = make(chan *types.Header)

		resetForced bool       // Whether a forced reset was requested, only used in simulator mode
		resetWaiter chan error // Channel waiting on a forced reset, only used in simulator mode
	)
	// Notify the live reset waiter to not block if the txpool is closed.
	defer func() {
		if resetWaiter != nil {
			resetWaiter <- errors.New("pool already terminated")
			resetWaiter = nil
		}
	}()
	var errc chan error
	for errc == nil {
		// Something interesting might have happened, run a reset if there is
		// one needed but none is running. The resetter will run on its own
		// goroutine to allow chain head events to be consumed contiguously.
		if newHead != oldHead || resetForced {
			// Try to inject a busy marker and start a reset if successful
			select {
			case resetBusy <- struct{}{}:
				// Updates the statedb with the new chain head. The head state may be
				// unavailable if the initial state sync has not yet completed.
				if statedb, err := p.chain.StateAt(newHead.Root); err != nil {
					log.Error("Failed to reset txpool state", "err", err)
				} else {
					p.stateLock.Lock()
					p.state = statedb
					p.stateLock.Unlock()
				}

				// Busy marker injected, start a new subpool reset
				go func(oldHead, newHead *types.Header) {
					for _, subpool := range p.subpools {
						subpool.Reset(oldHead, newHead)
					}
					select {
					case resetDone <- newHead:
					case <-p.term:
					}
				}(oldHead, newHead)

				// If the reset operation was explicitly requested, consider it
				// being fulfilled and drop the request marker. If it was not,
				// this is a noop.
				resetForced = false

			default:
				// Reset already running, wait until it finishes.
				//
				// Note, this will not drop any forced reset request. If a forced
				// reset was requested, but we were busy, then when the currently
				// running reset finishes, a new one will be spun up.
			}
		}
		// Wait for the next chain head event or a previous reset finish
		select {
		case event := <-newHeadCh:
			// Chain moved forward, store the head for later consumption
			newHead = event.Header

			if p.bucketSched != nil && newHead != nil {
				p.bucketSched.SetHeadBlock(newHead.Number.Uint64())
			}


		case head := <-resetDone:
			// Previous reset finished, update the old head and allow a new reset
			oldHead = head
			if p.bucketSched != nil && oldHead != nil {
				p.bucketSched.SetHeadBlock(oldHead.Number.Uint64())
			}

			<-resetBusy

			// Block imported / head changed: nonce may have advanced, so promote future txs
			p.promoteAllFuture()
			
			// If someone is waiting for a reset to finish, notify them, unless
			// the forced op is still pending. In that case, wait another round
			// of resets.
			if resetWaiter != nil && !resetForced {
				resetWaiter <- nil
				resetWaiter = nil
			}

		case errc = <-p.quit:
			// Termination requested, break out on the next loop round

		case syncc := <-p.sync:
			// Transaction pool is running inside a simulator, and we are about
			// to create a new block. Request a forced sync operation to ensure
			// that any running reset operation finishes to make block imports
			// deterministic. On top of that, run a new reset operation to make
			// transaction insertions deterministic instead of being stuck in a
			// queue waiting for a reset.
			resetForced = true
			resetWaiter = syncc
		}
	}
	// Notify the closer of termination (no error possible for now)
	errc <- nil
}

// SetGasTip updates the minimum gas tip required by the transaction pool for a
// new transaction, and drops all transactions below this threshold.
func (p *TxPool) SetGasTip(tip *big.Int) {
	for _, subpool := range p.subpools {
		subpool.SetGasTip(tip)
	}
}

// Has returns an indicator whether the pool has a transaction cached with the
// given hash.
func (p *TxPool) Has(hash common.Hash) bool {
	for _, subpool := range p.subpools {
		if subpool.Has(hash) {
			return true
		}
	}
	return false
}

// Get returns a transaction if it is contained in the pool, or nil otherwise.
func (p *TxPool) Get(hash common.Hash) *types.Transaction {
	for _, subpool := range p.subpools {
		if tx := subpool.Get(hash); tx != nil {
			return tx
		}
	}
	return nil
}

// GetRLP returns a RLP-encoded transaction if it is contained in the pool.
func (p *TxPool) GetRLP(hash common.Hash) []byte {
	for _, subpool := range p.subpools {
		encoded := subpool.GetRLP(hash)
		if len(encoded) != 0 {
			return encoded
		}
	}
	return nil
}

// GetMetadata returns the transaction type and transaction size with the given
// hash.
func (p *TxPool) GetMetadata(hash common.Hash) *TxMetadata {
	for _, subpool := range p.subpools {
		if meta := subpool.GetMetadata(hash); meta != nil {
			return meta
		}
	}
	return nil
}

// checkAddressPolicy enforces:
// - reject if tx.To is blocked directly
// - if contract creation: scan initcode
// - if calling an existing contract: scan the deployed runtime bytecode from state
func (p *TxPool) checkAddressPolicy(tx *types.Transaction) error {
	pol := GetAddressPolicy()
	if pol == nil || !pol.Enabled {
		return nil
	}

	// Contract creation: tx.To() == nil → scan initcode (tx.Data)
	to := tx.To()
	if to == nil {
		return pol.CheckTxAdmission(nil, tx.Data())
	}

	// 1) Direct censorship: tx.To is blocked
	if _, blocked := pol.BlockedMap[*to]; blocked {
		return fmt.Errorf("rejected: tx.To is blocked %s", to.Hex())
	}

	// 2) If it's a contract call, scan deployed runtime bytecode from current head state
	// p.stateLock.RLock()
	// code := p.state.GetCode(*to)
	// p.stateLock.RUnlock()
	p.stateLock.Lock()
	code := p.state.GetCode(*to)
	p.stateLock.Unlock()

	// log.Debug("Scanning contract runtime bytecode",
    // "contract", to.Hex(),
    // "codeSize", len(code))
	
	// If code length is 0, it's an EOA (not a contract), nothing to scan
	if len(code) == 0 {
		return nil
	}

	log.Debug("Scanning contract runtime bytecode",
		"contract", to.Hex(),
		"codeSize", len(code),
	)
	// Scan runtime bytecode for PUSH20 hard-coded addresses
	return pol.CheckBytecodeBlocked(code)
}

// Add enqueues a batch of transactions into the pool if they are valid. Due
// to the large transaction churn, add may postpone fully integrating the tx
// to a later point to batch multiple ones together.
//
// Note, if sync is set the method will block until all internal maintenance
// related to the add is finished. Only use this during tests for determinism.
func (p *TxPool) Add(txs []*types.Transaction, sync bool) []error {
	// Split the input transactions between the subpools. It shouldn't really
	// happen that we receive merged batches, but better graceful than strange
	// errors.
	//
	// We also need to track how the transactions were split across the subpools,
	// so we can piece back the returned errors into the original order.
	log.Debug("Adding transactions to pool", "count", len(txs))
	

	// example policy (you should load these from config/flags)
	// policy := AddressPolicy{
	// 	RejectZeroAddress: true,
	// 	Deny: map[common.Address]struct{}{
	// 		// common.HexToAddress("0x..."): {},
	// 	},
	// }

	txsets := make([][]*types.Transaction, len(p.subpools))
	splits := make([]int, len(txs))

	preErr := make([]error, len(txs))

	localNext := make(map[common.Address]uint64, 128)
	seenSender := make(map[common.Address]bool, 128)
	sendersTouched := make(map[common.Address]struct{}, 128)


	for i, tx := range txs {

		//pre-check BEFORE subpool routing / bucket indexing
		// if err := p.checkAddressPolicy(tx, policy); err != nil {
		// 	splits[i] = -2        // special marker: rejected by policy
		// 	preErr[i] = err
		// 	continue
		// }

		// if pol := GetAddressPolicy(); pol != nil && pol.Enabled {
		// if err := pol.CheckTxAdmission(tx); err != nil {
		// 	splits[i] = -2
		// 	preErr[i] = err
		// 	continue
		// }

		//commented
		// if pol := GetAddressPolicy(); pol != nil && pol.Enabled {
		// 	// Contract creation: scan initcode (tx.Data())
		// 	if tx.To() == nil {
		// 		if err := pol.CheckTxAdmission(nil, tx.Data()); err != nil {
		// 			splits[i] = -2
		// 			preErr[i] = err
		// 			continue
		// 		}
		// 	} else {
		// 		// Call to existing address: scan deployed runtime bytecode from the pool's head state
		// 		p.stateLock.RLock()
		// 		err := pol.CheckCallTargetRuntime(p.state, *tx.To())
		// 		p.stateLock.RUnlock()

		// 		if err != nil {
		// 			splits[i] = -2
		// 			preErr[i] = err
		// 			continue
		// 		}
		// 	}
		// }

	

		if err := p.checkAddressPolicy(tx); err != nil {
			splits[i] = -2
			preErr[i] = err
			log.Error("Rejecting tx in txpool by address policy",
				"hash", tx.Hash(),
				"err", err,
			)
			continue
		}

		// Mark this transaction belonging to no-subpool
		splits[i] = -1

		// Try to find a subpool that accepts the transaction
		for j, subpool := range p.subpools {
			if subpool.Filter(tx) {
				txsets[j] = append(txsets[j], tx)
				splits[i] = j
				break
			}
		}

		//new bucket code 
		// Index bucket mapping only if tx was assigned to some subpool
		// if splits[i] != -1 && p.bucketIdx != nil && p.numBuckets > 0 {
		// 		h := tx.Hash()
		// 		bid := bucket.BucketForHash(h, p.numBuckets)
		// 		log.Debug("Assigning transaction to bucket", "hash", h, "bucketID", bid)
		// 		p.bucketIdx.set(h, bid)
		// }

		// ---- sender-bucket + future-bucket assignment ----

		if splits[i] != -1 && p.bucketIdx != nil && p.numBuckets > 0 {
		p.senderMu.Lock()
		head := p.chain.CurrentBlock()
		signer := types.MakeSigner(p.chain.Config(), head.Number, head.Time)
		from, err := types.Sender(signer, tx)
		p.senderMu.Unlock()

		if err != nil {
			h := tx.Hash()
			if _, ok := p.bucketIdx.get(h); ok {
				continue
			}
			bid := bucket.BucketForHash(h, p.numBuckets)
			p.bucketIdx.set(h, bid)
			continue
		}

		sendersTouched[from] = struct{}{}
		h := tx.Hash()

		if _, ok := p.bucketIdx.get(h); ok {
			continue
		}

		expected := localNext[from]
		if !seenSender[from] {
			expected = p.PoolNonce(from)
			localNext[from] = expected
			seenSender[from] = true
		}
		// if expected == 0 && !seenSender[from] {
		// 	expected = p.PoolNonce(from)
		// 	if expected == 0 {
		// 		expected = p.Nonce(from)
		// 	}
		// 	localNext[from] = expected
		// 	seenSender[from] = true
		// }

		n := tx.Nonce()

		if n > expected {
			p.bucketIdx.set(h, futureBucketID)
			p.trackFuture(from, n, h)

			ts := time.Now()
			p.futureMu.Lock()
			p.futureAddTime[h] = ts
			p.futureMu.Unlock()

			log.Debug("Assigned tx to FUTURE bucket",
				"from", from,
				"hash", h,
				"nonce", n,
				"expected", expected,
				"ts", ts,
			)
		} else {
			bid := bucket.BucketForHash(h, p.numBuckets)
			p.bucketIdx.set(h, bid)

			log.Debug("Assigned tx to NORMAL bucket",
				"from", from,
				"hash", h,
				"bucketID", bid,
				"nonce", n,
				"expected", expected,
			)

			if n == expected {
				localNext[from] = expected + 1
			}
		}
	}
		// if splits[i] != -1 && p.bucketIdx != nil && p.numBuckets > 0 {

		// 	// Recover sender
		// 	// head := p.chain.CurrentBlock()
		// 	// signer := types.MakeSigner(p.chain.Config(), head.Number, head.Time)
		// 	// from, err := types.Sender(signer, tx)
		// 	p.senderMu.Lock()
		// 	head := p.chain.CurrentBlock()
		// 	signer := types.MakeSigner(p.chain.Config(), head.Number, head.Time)
		// 	from, err := types.Sender(signer, tx)
		// 	p.senderMu.Unlock()

		// 	sendersTouched[from] = struct{}{}
		// 	if err != nil {
		// 		// If we can't recover sender, fall back to hash-based bucket (or skip)
		// 		h := tx.Hash()
		// 		bid := bucket.BucketForHash(h, p.numBuckets)
		// 		p.bucketIdx.set(h, bid)
		// 	} else {
		// 		h := tx.Hash()

		// 		// Batch-local expected nonce tracker (so multiple txs from same sender in same Add call behave correctly)
		// 		// We'll keep it in a map outside the loop. See below.
		// 		expected := localNext[from]

		// 		// If this is the first time we see this sender in this batch, seed expected.
		// 		if expected == 0 && !seenSender[from] {
		// 			expected = p.PoolNonce(from)
		// 			if expected == 0 {
		// 				expected = p.Nonce(from)
		// 			}
		// 			localNext[from] = expected
		// 			seenSender[from] = true
		// 		}

		// 		n := tx.Nonce()

		// 		// If nonce is ahead of expected -> FUTURE bucket
		// 		if n > expected {
		// 						p.bucketIdx.set(h, futureBucketID)
		// 						p.trackFuture(from, n, h)
		// 						p.futureMu.Lock()
		// 						p.futureAddTime[h] = time.Now()
		// 						p.futureMu.Unlock()
		// 						log.Debug("Assigned tx to FUTURE bucket", "from", from, "hash", h, "nonce", n, "expected", expected, "ts", p.futureAddTime[h])
		// 		} else {
		// 			// Normal bucket for sender (includes n==expected or replacement n<expected)
		// 			// bid := p.bucketForSender(from)
		// 			bid := bucket.BucketForHash(h, p.numBuckets)
		// 			p.bucketIdx.set(h, bid)
		// 			log.Debug("TX ARRIVED", "hash", h, "from", from, "nonce", n, "time", time.Now().UnixMilli(),)
		// 			log.Debug("Assigned tx to NORMAL sender bucket", "from", from, "hash", h, "bucketID", bid, "nonce", n, "expected", expected)

		// 			// If it matches expected, advance expected for this batch
		// 				if n == expected {
		// 					localNext[from] = expected + 1
		// 				}
		// 		}
		// 	}
		// }
	}

	// Add into subpools
	errsets := make([][]error, len(p.subpools))
	for i := 0; i < len(p.subpools); i++ {
		errsets[i] = p.subpools[i].Add(txsets[i], sync)
	}

	// Reassemble errors
	errs := make([]error, len(txs))
	for i, split := range splits {
		if split == -2 { // rejected by your address policy
			errs[i] = preErr[i]
			continue
		}
		if split == -1 {
			errs[i] = fmt.Errorf("%w: received type %d", core.ErrTxTypeNotSupported, txs[i].Type())
			continue
		}
		errs[i] = errsets[split][0]
		errsets[split] = errsets[split][1:]
	}

	// After transactions are added to subpools, try promoting any future txs that became ready.
	for from := range sendersTouched {
		p.promoteFutureIfReady(from)
	}
	return errs

	// Add the transactions split apart to the individual subpools and piece
	// back the errors into the original sort order.
	// errsets := make([][]error, len(p.subpools))
	// for i := 0; i < len(p.subpools); i++ {
	// 	errsets[i] = p.subpools[i].Add(txsets[i], sync)
	// }
	// errs := make([]error, len(txs))
	// for i, split := range splits {
	// 	// If the transaction was rejected by all subpools, mark it unsupported
	// 	if split == -1 {
	// 		errs[i] = fmt.Errorf("%w: received type %d", core.ErrTxTypeNotSupported, txs[i].Type())
	// 		continue
	// 	}
	// 	// Find which subpool handled it and pull in the corresponding error
	// 	errs[i] = errsets[split][0]
	// 	errsets[split] = errsets[split][1:]
	// }
	// return errs
}

// Pending retrieves all currently processable transactions, grouped by origin
// account and sorted by nonce.
//
// The transactions can also be pre-filtered by the dynamic fee components to
// reduce allocations and load on downstream subsystems.
func (p *TxPool) Pending(filter PendingFilter) map[common.Address][]*LazyTransaction {
	txs := make(map[common.Address][]*LazyTransaction)
	for _, subpool := range p.subpools {
		for addr, set := range subpool.Pending(filter) {
			txs[addr] = set
		}
	}
	return txs
}

// SubscribeTransactions registers a subscription for new transaction events,
// supporting feeding only newly seen or also resurrected transactions.
func (p *TxPool) SubscribeTransactions(ch chan<- core.NewTxsEvent, reorgs bool) event.Subscription {
	subs := make([]event.Subscription, len(p.subpools))
	for i, subpool := range p.subpools {
		subs[i] = subpool.SubscribeTransactions(ch, reorgs)
	}
	return p.subs.Track(event.JoinSubscriptions(subs...))
}

// PoolNonce returns the next nonce of an account, with all transactions executable
// by the pool already applied on top.
func (p *TxPool) PoolNonce(addr common.Address) uint64 {
	// Since (for now) accounts are unique to subpools, only one pool will have
	// (at max) a non-state nonce. To avoid stateful lookups, just return the
	// highest nonce for now.
	var nonce uint64
	for _, subpool := range p.subpools {
		if next := subpool.Nonce(addr); nonce < next {
			nonce = next
		}
	}
	return nonce
}

// Nonce returns the next nonce of an account at the current chain head. Unlike
// PoolNonce, this function does not account for pending executable transactions.
func (p *TxPool) Nonce(addr common.Address) uint64 {
	// p.stateLock.RLock()
	p.stateLock.Lock()

	// defer p.stateLock.RUnlock()
	defer p.stateLock.Unlock()


	return p.state.GetNonce(addr)
}

// bucketForSender returns a deterministic bucket for an address.
func (p *TxPool) bucketForSender(from common.Address) int {
	if p.numBuckets <= 0 {
		return 0
	}
	// keccak(address) then last 8 bytes mod N
	h := crypto.Keccak256Hash(from.Bytes())
	v := binary.BigEndian.Uint64(h[24:32])
	return int(v % uint64(p.numBuckets))
}

// trackFuture remembers that tx is future (nonce > expected at time of admission).
func (p *TxPool) trackFuture(from common.Address, nonce uint64, hash common.Hash) {
	p.futureMu.Lock()
	defer p.futureMu.Unlock()

	m := p.future[from]
	if m == nil {
		m = make(map[uint64]common.Hash)
		p.future[from] = m
	}
	m[nonce] = hash
	// ensure we have an admission timestamp for tracked future txs
	if _, ok := p.futureAddTime[hash]; !ok {
		p.futureAddTime[hash] = time.Now()
	}
}

// untrackFuture removes from future tracking.
// func (p *TxPool) untrackFuture(from common.Address, nonce uint64) {
// 	p.futureMu.Lock()
// 	defer p.futureMu.Unlock()

// 	m := p.future[from]
// 	if m == nil {
// 		m = make(map[uint64]*types.Transaction)
// 		p.future[from] = m
// 	}
// 	m[nonce] = tx
// }
func (p *TxPool) untrackFuture(from common.Address, nonce uint64) {
	p.futureMu.Lock()
	defer p.futureMu.Unlock()

	m := p.future[from]
	if m == nil {
		return
	}
	delete(m, nonce)
	if len(m) == 0 {
		delete(p.future, from)
	}
}
// promoteFutureIfReady moves any future txs whose nonce has become "next" into normal sender bucket.
// NOTE: This only updates the bucket index mapping; actual tx execution status is handled by subpools.
func (p *TxPool) promoteFutureIfReady(from common.Address) {
	if p.bucketIdx == nil {
		return
	}
	// Determine the "next" nonce the pool expects now
	// next := p.PoolNonce(from)
	// if next == 0 {
	// 	next = p.Nonce(from)
	// }
	next := p.PoolNonce(from)

	for {
		var h common.Hash
		var ok bool

		p.futureMu.Lock()
		m := p.future[from]
		if m != nil {
			h, ok = m[next]
			if ok {
				delete(m, next)
				if len(m) == 0 {
					delete(p.future, from)
				}
			}
		}
		p.futureMu.Unlock()

		if !ok {
			return
		}

		// If tx disappeared (mined/evicted), clean mapping and continue
		if !p.Has(h) {
			p.bucketIdx.Del(h)
			next++
			continue
		}

		//TODO: implement overdraft solution
		
		// Promote bucket mapping: future -> normal sender bucket
		// bid := p.bucketForSender(from)
		bid := bucket.BucketForHash(h, p.numBuckets)
		p.bucketIdx.set(h, bid)
		p.futureMu.Lock()
		addt, ok := p.futureAddTime[h]
		if ok {
			delete(p.futureAddTime, h)
		}
		p.futureMu.Unlock()
		if ok {
			latency := time.Since(addt)
			log.Debug("Promoted tx from future bucket to normal sender bucket", "from", from, "hash", h, "bucketID", bid, "nonce", next, "admission_latency_ms", latency.Milliseconds())
		} else {
			log.Debug("Promoted tx from future bucket to normal sender bucket", "from", from, "hash", h, "bucketID", bid, "nonce", next)
		}

		next++
	}
}

// promoteAllFuture runs promotion for all senders that have future txs.
// Call this after head resets (block import) to reflect nonce progression.
func (p *TxPool) promoteAllFuture() {
	// copy keys to avoid holding lock while calling PoolNonce/Has
	p.futureMu.Lock()
	addrs := make([]common.Address, 0, len(p.future))
	for a := range p.future {
		addrs = append(addrs, a)
	}
	p.futureMu.Unlock()

	for _, a := range addrs {
		p.promoteFutureIfReady(a)
	}
}

// Stats retrieves the current pool stats, namely the number of pending and the
// number of queued (non-executable) transactions.
func (p *TxPool) Stats() (int, int) {
	var runnable, blocked int
	for _, subpool := range p.subpools {
		run, block := subpool.Stats()

		runnable += run
		blocked += block
	}
	return runnable, blocked
}

// Content retrieves the data content of the transaction pool, returning all the
// pending as well as queued transactions, grouped by account and sorted by nonce.
func (p *TxPool) Content() (map[common.Address][]*types.Transaction, map[common.Address][]*types.Transaction) {
	var (
		runnable = make(map[common.Address][]*types.Transaction)
		blocked  = make(map[common.Address][]*types.Transaction)
	)
	for _, subpool := range p.subpools {
		run, block := subpool.Content()

		for addr, txs := range run {
			runnable[addr] = txs
		}
		for addr, txs := range block {
			blocked[addr] = txs
		}
	}
	return runnable, blocked
}

// ContentFrom retrieves the data content of the transaction pool, returning the
// pending as well as queued transactions of this address, grouped by nonce.
func (p *TxPool) ContentFrom(addr common.Address) ([]*types.Transaction, []*types.Transaction) {
	for _, subpool := range p.subpools {
		run, block := subpool.ContentFrom(addr)
		if len(run) != 0 || len(block) != 0 {
			return run, block
		}
	}
	return []*types.Transaction{}, []*types.Transaction{}
}

// Status returns the known status (unknown/pending/queued) of a transaction
// identified by its hash.
func (p *TxPool) Status(hash common.Hash) TxStatus {
	for _, subpool := range p.subpools {
		if status := subpool.Status(hash); status != TxStatusUnknown {
			return status
		}
	}
	return TxStatusUnknown
}

// Sync is a helper method for unit tests or simulator runs where the chain events
// are arriving in quick succession, without any time in between them to run the
// internal background reset operations. This method will run an explicit reset
// operation to ensure the pool stabilises, thus avoiding flakey behavior.
//
// Note, this method is only used for testing and is susceptible to DoS vectors.
// In production code, the pool is meant to reset on a separate thread.
func (p *TxPool) Sync() error {
	sync := make(chan error)
	select {
	case p.sync <- sync:
		return <-sync
	case <-p.term:
		return errors.New("pool already terminated")
	}
}

// Clear removes all tracked txs from the subpools.
//
// Note, this method invokes Sync() and is only used for testing, because it is
// susceptible to DoS vectors. In production code, the pool is meant to reset on
// a separate thread.
func (p *TxPool) Clear() {
	// Invoke Sync to ensure that txs pending addition don't get added to the pool after
	// the subpools are subsequently cleared
	p.Sync()
	for _, subpool := range p.subpools {
		subpool.Clear()
	}
}

// FilterType returns whether a transaction with the given type is supported
// (can be added) by the pool.
func (p *TxPool) FilterType(kind byte) bool {
	for _, subpool := range p.subpools {
		if subpool.FilterType(kind) {
			return true
		}
	}
	return false
}

func (p *TxPool) SetActiveBucket(bucketID uint32) {
	p.forcedActiveBucket.Store(int64(bucketID))
}

func (p *TxPool) ClearActiveBucket() {
	p.forcedActiveBucket.Store(-1)
}

func (p *TxPool) ForcedActiveBucket() (int, bool) {
	v := p.forcedActiveBucket.Load()
	if v < 0 {
		return 0, false
	}
	return int(v), true
}
