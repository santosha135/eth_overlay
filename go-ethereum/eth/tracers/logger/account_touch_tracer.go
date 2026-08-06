package logger

import (
	"math/big"

	"github.com/ethereum/go-ethereum/common"
	"github.com/ethereum/go-ethereum/core/tracing"
	"github.com/ethereum/go-ethereum/core/types"
	"github.com/ethereum/go-ethereum/core/vm"
)

// AccountTouchTracer records every account touched by one transaction.
type AccountTouchTracer struct {
	touched map[common.Address]struct{}
}

func NewAccountTouchTracer() *AccountTouchTracer {
	return &AccountTouchTracer{
		touched: make(map[common.Address]struct{}),
	}
}

func (t *AccountTouchTracer) Hooks() *tracing.Hooks {
	return &tracing.Hooks{
		OnTxStart: t.onTxStart,
		OnEnter:   t.onEnter,
		OnOpcode:  t.onOpcode,
	}
}

func (t *AccountTouchTracer) TouchedAddresses() []common.Address {
	addresses := make([]common.Address, 0, len(t.touched))
	for address := range t.touched {
		addresses = append(addresses, address)
	}
	return addresses
}

func (t *AccountTouchTracer) onTxStart(
	evm *tracing.VMContext,
	tx *types.Transaction,
	from common.Address,
) {
	t.touched[from] = struct{}{}
	if to := tx.To(); to != nil {
		t.touched[*to] = struct{}{}
	}
}

func (t *AccountTouchTracer) onEnter(
	depth int,
	typ byte,
	from common.Address,
	to common.Address,
	input []byte,
	gas uint64,
	value *big.Int,
) {
	t.touched[to] = struct{}{}
}

func (t *AccountTouchTracer) onOpcode(
	pc uint64,
	opcode byte,
	gas uint64,
	cost uint64,
	scope tracing.OpContext,
	returnData []byte,
	depth int,
	err error,
) {
	op := vm.OpCode(opcode)
	stack := scope.StackData()

	if len(stack) == 0 {
		return
	}

	switch op {
	case vm.EXTCODECOPY,
		vm.EXTCODEHASH,
		vm.EXTCODESIZE,
		vm.BALANCE,
		vm.SELFDESTRUCT:

		address := common.Address(stack[len(stack)-1].Bytes20())
		t.touched[address] = struct{}{}
	}
}