package catalyst

import (
	"encoding/binary"

	"github.com/ethereum/go-ethereum/beacon/engine"
	"github.com/ethereum/go-ethereum/common"
	"github.com/ethereum/go-ethereum/crypto"
)

type SlotKey struct {
	Parent  common.Hash
	Time    uint64
	Version engine.PayloadVersion
}

func (slotKey SlotKey) Bytes() []byte {
	bytes := make([]byte, 32+8+1) // 32 for parent, 8 for time, 1 for version
	copy(bytes[0:32], slotKey.Parent[:]) //Set parent
	binary.BigEndian.PutUint64(bytes[32:40], slotKey.Time) //Set time
	bytes[40] = byte(slotKey.Version) //Set version
	return bytes
}

func (slotKey SlotKey) ID() common.Hash {
	return crypto.Keccak256Hash(slotKey.Bytes())
}