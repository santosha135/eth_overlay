package miner

import "github.com/ethereum/go-ethereum/core/types"

type SliceTxSourceFactory struct {
    Txs []*types.Transaction
}

func (f *SliceTxSourceFactory) New() TxSource {
    return &sliceTxSource{txs: f.Txs}
}

type sliceTxSource struct {
    txs []*types.Transaction
    i   int
}

func (s *sliceTxSource) Next(max int) ([]*types.Transaction, bool, error) {
    if s.i >= len(s.txs) {
        return nil, true, nil
    }
    end := s.i + max
    if end > len(s.txs) {
        end = len(s.txs)
    }
    out := s.txs[s.i:end]
    s.i = end
    return out, s.i >= len(s.txs), nil
}