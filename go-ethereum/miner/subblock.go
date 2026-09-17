package miner

import (
	"math/big"
	"time"

	"github.com/ethereum/go-ethereum/common"
	"github.com/ethereum/go-ethereum/core/types"
	"github.com/ethereum/go-ethereum/crypto"
	"github.com/ethereum/go-ethereum/rlp"
)

// StorageSlot identifies one storage slot of one account.
type StorageSlot struct {
	Addr common.Address
	Slot common.Hash
}

// StorageWrite is the final value of a storage slot once the sub-block finished.
type StorageWrite struct {
	Addr  common.Address
	Slot  common.Hash
	Value common.Hash
}

// BalanceDelta is an additive balance change. Balances are carried as deltas
// rather than absolute values because every sub-block credits the same coinbase,
// so absolute balances would collide on every merge.
type BalanceDelta struct {
	Addr   common.Address
	Neg    bool     // true when the balance decreased
	Amount *big.Int // magnitude of the change, never negative
}

// NonceWrite is an absolute nonce. Absolute is safe here: bucket assignment is
// sender-sticky and nonce-gated, so one account's transactions never span buckets
// within a block.
type NonceWrite struct {
	Addr  common.Address
	Nonce uint64
}

// CodeWrite is code deployed by the sub-block.
type CodeWrite struct {
	Addr common.Address
	Code []byte
}

// StateDiff is everything the sub-block changed, in a form the merge can apply
// without running the EVM again.
type StateDiff struct {
	Storage  []StorageWrite
	Balances []BalanceDelta
	Nonces   []NonceWrite
	Codes    []CodeWrite
}

// AccessSet is the state the sub-block touched. The merge uses it to decide
// whether this sub-block overlaps one already applied. Over-approximating is
// safe; it only costs an unnecessary re-execution.
type AccessSet struct {
	ReadAccounts    []common.Address
	ReadSlots       []StorageSlot
	WrittenAccounts []common.Address
	WrittenSlots    []StorageSlot
}

// SubBlockMeta is what the proposer knows about a sub-block that is not part of
// the sub-block itself: when it landed here and how many bytes arrived. It is
// kept outside SubBlock so it never enters the RLP encoding.
type SubBlockMeta struct {
	ReceivedAt time.Time
	BlobBytes  int
}

// SubBlock is what a bucket leader produces: a self-contained, executed piece of
// the block, built on the shared parent state.
type SubBlock struct {
	BucketID    uint32
	LeaderIndex uint32

	ParentHash common.Hash
	ParentRoot common.Hash
	Number     *big.Int

	Txs      []*types.Transaction
	Receipts []*types.Receipt

	// PostRoot is the state root after applying only this sub-block's txs on top
	// of ParentRoot. It is not the merged block's root.
	PostRoot common.Hash
	GasUsed  uint64

	Access AccessSet
	Diff   StateDiff
}

// subBlockIdent is the hashed identity of a sub-block. Receipts are left out:
// they are derived from the txs, and their consensus encoding drops fields.
type subBlockIdent struct {
	BucketID   uint32
	ParentHash common.Hash
	ParentRoot common.Hash
	PostRoot   common.Hash
	GasUsed    uint64
	TxHashes   []common.Hash
}

// Hash gives the sub-block a stable identity for logging and for the merge to
// refer to it by.
func (sb *SubBlock) Hash() common.Hash {
	ident := subBlockIdent{
		BucketID:   sb.BucketID,
		ParentHash: sb.ParentHash,
		ParentRoot: sb.ParentRoot,
		PostRoot:   sb.PostRoot,
		GasUsed:    sb.GasUsed,
		TxHashes:   make([]common.Hash, 0, len(sb.Txs)),
	}
	for _, tx := range sb.Txs {
		if tx == nil {
			continue
		}
		ident.TxHashes = append(ident.TxHashes, tx.Hash())
	}

	encoded, err := rlp.EncodeToBytes(&ident)
	if err != nil {
		return common.Hash{}
	}
	return crypto.Keccak256Hash(encoded)
}
