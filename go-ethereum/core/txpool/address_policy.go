package txpool

import (
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"strings"
	"sync/atomic"
	"github.com/ethereum/go-ethereum/log"
	"github.com/ethereum/go-ethereum/core/state"
	"github.com/ethereum/go-ethereum/common"
)

type AddressPolicyConfig struct {
	Enabled            bool     `json:"enabled"`
	RejectAnyHardcoded bool     `json:"reject_any_hardcoded"`
	RejectZeroAddress  bool     `json:"reject_zero_address"`
	Blocked            []string `json:"blocked"`
	AllowHardcoded     []string `json:"allow_hardcoded"`
}

type AddressPolicy struct {
	Enabled            bool
	RejectAnyHardcoded bool
	BlockedMap         map[common.Address]struct{}
}

var globalPolicy atomic.Value // stores *AddressPolicy

func SetAddressPolicy(p *AddressPolicy) { globalPolicy.Store(p) }
func GetAddressPolicy() *AddressPolicy {
	v := globalPolicy.Load()
	if v == nil {
		return nil
	}
	return v.(*AddressPolicy)
}

func LoadAddressPolicyJSON(path string) (*AddressPolicy, error) {
	b, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var cfg AddressPolicyConfig
	if err := json.Unmarshal(b, &cfg); err != nil {
		return nil, err
	}

	p := &AddressPolicy{
		Enabled:            cfg.Enabled,
		RejectAnyHardcoded: cfg.RejectAnyHardcoded,
		BlockedMap:         make(map[common.Address]struct{}),
	}
	for _, s := range cfg.Blocked {
		s = strings.TrimSpace(s)
		if !common.IsHexAddress(s) {
			return nil, fmt.Errorf("invalid blocked address in config: %q", s)
		}
		p.BlockedMap[common.HexToAddress(s)] = struct{}{}
	}
	return p, nil
}

func extractPush20Addresses(code []byte) []common.Address {
	var out []common.Address
	for i := 0; i < len(code); i++ {
		op := code[i]
		// PUSH1..PUSH32
		if op >= 0x60 && op <= 0x7f {
			n := int(op - 0x5f)
			if i+1+n > len(code) {
				break
			}
			if n == 20 {
				var a common.Address
				copy(a[:], code[i+1:i+1+20])
				out = append(out, a)
			}
			i += n
		}
	}
	// unique preserve order
	seen := make(map[common.Address]struct{}, len(out))
	uniq := make([]common.Address, 0, len(out))
	for _, a := range out {
		if _, ok := seen[a]; ok {
			continue
		}
		seen[a] = struct{}{}
		uniq = append(uniq, a)
	}
	return uniq
}

// CheckBytecodeBlocked returns error ONLY if a hard-coded address is in blocked list.
// If RejectAnyHardcoded == true, it rejects any PUSH20 (you will keep it false).
func (p *AddressPolicy) CheckBytecodeBlocked(code []byte) error {
	if p == nil || !p.Enabled {
		return nil
	}
	addrs := extractPush20Addresses(code)

	for _, a := range addrs {
		log.Info("Detected hardcoded address in bytecode", "address", a.Hex())
	}


	// Your requested mode: reject only if hard-coded address in blocked list
	if !p.RejectAnyHardcoded {
		for _, a := range addrs {
			_, blocked := p.BlockedMap[a] 
			log.Info("Checking detected address against blocked map",
				"detected", a.Hex(),
				"blocked", blocked,
				"blockedMapSize", len(p.BlockedMap),
			)

						
			if blocked {
				log.Warn("Rejecting bytecode due to blocked hardcoded address", "address", a.Hex())
				return fmt.Errorf("rejected: bytecode hard-codes blocked address %s", a.Hex())
			}
		}
		return nil
	}

	// Strict mode (not used by you, but kept for completeness)
	if len(addrs) > 0 {
		log.Warn("Rejecting bytecode because hardcoded addresses exist", "count", len(addrs))
		return fmt.Errorf("rejected: bytecode contains hard-coded addresses (strict mode enabled)")
	}
	return nil
}

// CheckTxAdmission enforces:
// 1) block tx.To if it is blocked (direct censorship)
// 2) if contract creation (tx.To()==nil): scan initcode for PUSH20 blocked
func (p *AddressPolicy) CheckTxAdmission(txTo *common.Address, input []byte) error {
	if p == nil || !p.Enabled {
		return nil
	}
	if txTo != nil {
		if _, blocked := p.BlockedMap[*txTo]; blocked {
			return fmt.Errorf("rejected: tx.To is blocked %s", txTo.Hex())
		}
		return nil
	}
	// creation initcode check
	if len(input) == 0 {
		return errors.New("rejected: empty initcode")
	}
	return p.CheckBytecodeBlocked(input)
}

// CheckCallTargetRuntime scans deployed runtime bytecode of `to`
// and rejects if it hard-codes any blocked address.
func (p *AddressPolicy) CheckCallTargetRuntime(st *state.StateDB, to common.Address) error {
	if p == nil || !p.Enabled {
		return nil
	}

	// Direct censorship: block calling a blocked address
	if _, blocked := p.BlockedMap[to]; blocked {
		return fmt.Errorf("rejected: call target is blocked %s", to.Hex())
	}

	// If it's a contract, scan runtime bytecode
	code := st.GetCode(to)
	if len(code) == 0 {
		return nil // EOA, nothing to scan
	}
	return p.CheckBytecodeBlocked(code)
}