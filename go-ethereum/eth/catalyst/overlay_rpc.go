package catalyst

import (
	"context"
	"encoding/hex"
	"errors"
	"strings"

	"github.com/ethereum/go-ethereum/beacon/engine"
	"github.com/ethereum/go-ethereum/common"	
	"github.com/ethereum/go-ethereum/common/hexutil"
	"github.com/ethereum/go-ethereum/core/types"
	"github.com/ethereum/go-ethereum/rpc"
)

type OverlayRPC struct {
	overlay *OverlaySvc
}

func NewOverlayRPC(overlay *OverlaySvc) *OverlayRPC {
	return &OverlayRPC{overlay: overlay}
}

type ActiveSlotResponse struct {
	SlotID   common.Hash     `json:"slotId"`
	Parent   common.Hash     `json:"parent"`
	Time     uint64          `json:"time"`
	Version  byte            `json:"version"`
	Epoch    uint64          `json:"epoch"`
}

type SubmitFragmentReq struct {
    Parent    common.Hash          `json:"parent"`
    Timestamp uint64               `json:"timestamp"`
    Version   engine.PayloadVersion `json:"version"`
    BucketID  uint32               `json:"bucketID"`

    // tx bytes are tx.MarshalBinary()
    Txs      []hexutil.Bytes       `json:"txs"`
    PostRoot common.Hash           `json:"postRoot"`
}

func (o *OverlayRPC) GetActiveSlot(_ context.Context) (ActiveSlotResponse, error) {
	if o.overlay == nil {
		return ActiveSlotResponse{}, errors.New("overlay disabled")
	}
	slot, epoch, ok := o.overlay.GetActiveSlot()
	if !ok {
		return ActiveSlotResponse{}, rpc.ErrNoResult
	}
	return ActiveSlotResponse{
		SlotID:  slot.ID(),
		Parent:  slot.Parent,
		Time:    slot.Time,
		Version: byte(slot.Version),
		Epoch:   epoch,
	}, nil
}

func (o *OverlayRPC) GetSlotArgs(_ context.Context, parent common.Hash, timestamp uint64, version byte) (*OverlayArgs, error) {
	if o.overlay == nil {
		return nil, errors.New("overlay disabled")
	}
	slot := SlotKey{Parent: parent, Time: timestamp, Version: engine.PayloadVersion(version)}
	args, ok := o.overlay.GetSlotArgs(slot)
	if !ok || args == nil {
		return nil, rpc.ErrNoResult
	}
	return args, nil
}


// overlay_submitFragment(parent, timestamp, version, bucketID, txBytes[], postRoot)
// txsRlpHex items are transaction bytes (tx.MarshalBinary / UnmarshalBinary).
func (o *OverlayRPC) SubmitFragment(_ context.Context, parent common.Hash, timestamp uint64, version byte, bucketID uint32, txsRlpHex []hexutil.Bytes, postRoot common.Hash) (bool, error) {
	//Check if overlay is active
	if o.overlay == nil {
		return false, errors.New("overlay disabled")
	}
	slot := SlotKey{Parent: parent, Time: timestamp, Version: engine.PayloadVersion(version)}

	//Decode the txs, first make an array (decoded_tx) of the correct size
	decoded_tx := make([]*types.Transaction, 0, len(txsRlpHex))
	//decode each tx in txsRlpHex, and append
	for _, b := range txsRlpHex {
		var tx types.Transaction
		if err := tx.UnmarshalBinary(b); err != nil {
			return false, err
		}
		decoded_tx = append(decoded_tx, &tx)
	}
	o.overlay.PutFragment(slot, bucketID, decoded_tx, postRoot)
	return true, nil
}

func parsePayloadID(s string) (engine.PayloadID, error) {
	s = strings.TrimPrefix(s, "0x")
	raw, err := hex.DecodeString(s)
	if err != nil {
		return engine.PayloadID{}, err
	}
	if len(raw) != 8 {
		return engine.PayloadID{}, errors.New("payloadID must be 8 bytes")
	}
	var id engine.PayloadID
	copy(id[:], raw)
	return id, nil
}