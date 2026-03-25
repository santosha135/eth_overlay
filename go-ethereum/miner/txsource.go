package miner

import "github.com/ethereum/go-ethereum/core/types"

type TxSource interface {
    // Returns up to max txs; may return fewer.
    Next(max int) ([]*types.Transaction, bool /*done*/, error)
}

type TxSourceFactory interface {
    New() TxSource
}