package miner

import (
	"math/big"

	"github.com/ethereum/go-ethereum/common"
	"github.com/ethereum/go-ethereum/core/tracing"
	"github.com/ethereum/go-ethereum/core/vm"
)

// accessTracer records the accounts and storage slots a sub-block touched while
// it executed. It deliberately over-approximates: the state diff is built from
// final post-state values, so a spurious entry just repeats the parent's value,
// and a spurious conflict just costs one re-execution at merge time.
type accessTracer struct {
	readAccounts    map[common.Address]struct{}
	readSlots       map[StorageSlot]struct{}
	writtenAccounts map[common.Address]struct{}
	writtenSlots    map[StorageSlot]struct{}
}

func newAccessTracer() *accessTracer {
	return &accessTracer{
		readAccounts:    make(map[common.Address]struct{}),
		readSlots:       make(map[StorageSlot]struct{}),
		writtenAccounts: make(map[common.Address]struct{}),
		writtenSlots:    make(map[StorageSlot]struct{}),
	}
}

// hooks returns the tracing hooks to hang on the EVM config.
func (t *accessTracer) hooks() *tracing.Hooks {
	return &tracing.Hooks{
		OnEnter:  t.onEnter,
		OnOpcode: t.onOpcode,
	}
}

// markAccountRead notes an account whose fields were observed.
func (t *accessTracer) markAccountRead(addr common.Address) {
	t.readAccounts[addr] = struct{}{}
}

// markAccountWritten notes an account whose fields may have changed.
func (t *accessTracer) markAccountWritten(addr common.Address) {
	t.writtenAccounts[addr] = struct{}{}
}

// onEnter fires for every call frame, including the top-level one. Both ends of
// a frame can have their balance or nonce moved, so both count as written.
func (t *accessTracer) onEnter(depth int, typ byte, from common.Address, to common.Address, input []byte, gas uint64, value *big.Int) {
	t.markAccountWritten(from)
	t.markAccountWritten(to)
}

// onOpcode picks up state reads and writes the call structure does not reveal.
func (t *accessTracer) onOpcode(pc uint64, op byte, gas, cost uint64, scope tracing.OpContext, rData []byte, depth int, err error) {
	stack := scope.StackData()
	if len(stack) == 0 {
		return
	}
	top := stack[len(stack)-1]

	switch vm.OpCode(op) {
	case vm.SLOAD:
		t.readSlots[StorageSlot{Addr: scope.Address(), Slot: common.Hash(top.Bytes32())}] = struct{}{}

	case vm.SSTORE:
		t.writtenSlots[StorageSlot{Addr: scope.Address(), Slot: common.Hash(top.Bytes32())}] = struct{}{}

	case vm.BALANCE, vm.EXTCODESIZE, vm.EXTCODEHASH, vm.EXTCODECOPY:
		t.markAccountRead(common.Address(top.Bytes20()))

	case vm.SELFBALANCE:
		t.markAccountRead(scope.Address())

	case vm.SELFDESTRUCT:
		// Destroys this account and credits the beneficiary on the stack.
		t.markAccountWritten(scope.Address())
		t.markAccountWritten(common.Address(top.Bytes20()))
	}
}

// accessSet converts the collected sets into the sub-block's serialisable form.
func (t *accessTracer) accessSet() AccessSet {
	out := AccessSet{
		ReadAccounts:    make([]common.Address, 0, len(t.readAccounts)),
		ReadSlots:       make([]StorageSlot, 0, len(t.readSlots)),
		WrittenAccounts: make([]common.Address, 0, len(t.writtenAccounts)),
		WrittenSlots:    make([]StorageSlot, 0, len(t.writtenSlots)),
	}
	for addr := range t.readAccounts {
		out.ReadAccounts = append(out.ReadAccounts, addr)
	}
	for slot := range t.readSlots {
		out.ReadSlots = append(out.ReadSlots, slot)
	}
	for addr := range t.writtenAccounts {
		out.WrittenAccounts = append(out.WrittenAccounts, addr)
	}
	for slot := range t.writtenSlots {
		out.WrittenSlots = append(out.WrittenSlots, slot)
	}
	return out
}
