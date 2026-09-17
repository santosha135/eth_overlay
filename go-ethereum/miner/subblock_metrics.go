package miner

import (
	"encoding/csv"
	"os"
	"strconv"
	"sync"
	"time"

	"github.com/ethereum/go-ethereum/log"
)

// SubBlockMetric is one row of per-sub-block accounting. Both sides write rows:
// the leader that built and sent the sub-block, and the proposer that joined it.
// Role says which.
//
// This is deliberately separate from FragmentMergeMetric, which stays per-block
// and untouched.
type SubBlockMetric struct {
	TimestampUTC string
	Role         string // "leader" or "proposer"
	Hostname     string

	BlockNumber uint64
	NumBuckets  uint32
	BucketID    uint32
	SubBlockHash string

	Txs      int
	GasUsed  uint64
	BlobBytes int

	// Diff size: what the merge has to write when it joins this sub-block.
	StorageWrites int
	BalanceDeltas int
	NonceWrites   int
	CodeWrites    int
	CodeBytes     int

	// Access-set size: what decides whether this sub-block conflicts.
	ReadAccounts    int
	ReadSlots       int
	WrittenAccounts int
	WrittenSlots    int

	// Outcome on the proposer: joined, reexecuted, dropped, missing.
	Outcome        string
	Reason         string
	ConflictBucket int    // bucket it collided with, -1 when none
	ConflictKey    string // account or slot that caused the collision

	// Leader-side timing.
	BuildDuration  time.Duration
	EncodeDuration time.Duration
	SendDuration   time.Duration

	// Proposer-side timing.
	ReceivedAtUTC  string
	MergeStartUTC  string
	WaitDuration   time.Duration // how long this sub-block sat before merge began
	ApplyDuration  time.Duration // joining it from its diff
	ReexecDuration time.Duration // re-executing it after a conflict
	TotalDuration  time.Duration

	ReexecTxs        int
	ReexecGas        uint64
	GasPoolRemaining uint64
}

var subBlockMetricMu sync.Mutex

// RecordSubBlockMetric appends one row to the per-sub-block CSV. The path comes
// from GETH_SUBBLOCK_METRICS_PATH, defaulting to sub_block_metrics.csv.
func RecordSubBlockMetric(m SubBlockMetric) {

	path := os.Getenv("GETH_SUBBLOCK_METRICS_PATH")

	if path == "" {
		path = "sub_block_metrics.csv"
	}

	subBlockMetricMu.Lock()
	defer subBlockMetricMu.Unlock()

	file, err := os.OpenFile(
		path,
		os.O_CREATE|os.O_APPEND|os.O_WRONLY,
		0644,
	)

	if err != nil {
		log.Error(
			"Failed to open sub-block metrics file",
			"path", path,
			"err", err,
		)
		return
	}

	defer file.Close()

	writer := csv.NewWriter(file)
	defer writer.Flush()

	info, err := file.Stat()

	if err == nil && info.Size() == 0 {
		writer.Write([]string{
			"timestamp_utc",
			"role",
			"hostname",

			"block_number",
			"num_buckets",
			"bucket_id",
			"sub_block_hash",

			"txs",
			"gas_used",
			"blob_bytes",

			"storage_writes",
			"balance_deltas",
			"nonce_writes",
			"code_writes",
			"code_bytes",

			"read_accounts",
			"read_slots",
			"written_accounts",
			"written_slots",

			"outcome",
			"reason",
			"conflict_bucket",
			"conflict_key",

			"build_duration_ns",
			"build_duration_us",
			"encode_duration_ns",
			"send_duration_ns",
			"send_duration_us",

			"received_at_utc",
			"merge_start_utc",
			"wait_duration_ns",
			"wait_duration_us",
			"apply_duration_ns",
			"apply_duration_us",
			"reexec_duration_ns",
			"reexec_duration_us",
			"total_duration_ns",
			"total_duration_us",

			"reexec_txs",
			"reexec_gas",
			"gas_pool_remaining",
		})
	}

	writer.Write([]string{
		m.TimestampUTC,
		m.Role,
		m.Hostname,

		strconv.FormatUint(m.BlockNumber, 10),
		strconv.FormatUint(uint64(m.NumBuckets), 10),
		strconv.FormatUint(uint64(m.BucketID), 10),
		m.SubBlockHash,

		strconv.Itoa(m.Txs),
		strconv.FormatUint(m.GasUsed, 10),
		strconv.Itoa(m.BlobBytes),

		strconv.Itoa(m.StorageWrites),
		strconv.Itoa(m.BalanceDeltas),
		strconv.Itoa(m.NonceWrites),
		strconv.Itoa(m.CodeWrites),
		strconv.Itoa(m.CodeBytes),

		strconv.Itoa(m.ReadAccounts),
		strconv.Itoa(m.ReadSlots),
		strconv.Itoa(m.WrittenAccounts),
		strconv.Itoa(m.WrittenSlots),

		m.Outcome,
		m.Reason,
		strconv.Itoa(m.ConflictBucket),
		m.ConflictKey,

		strconv.FormatInt(m.BuildDuration.Nanoseconds(), 10),
		strconv.FormatInt(m.BuildDuration.Microseconds(), 10),
		strconv.FormatInt(m.EncodeDuration.Nanoseconds(), 10),
		strconv.FormatInt(m.SendDuration.Nanoseconds(), 10),
		strconv.FormatInt(m.SendDuration.Microseconds(), 10),

		m.ReceivedAtUTC,
		m.MergeStartUTC,
		strconv.FormatInt(m.WaitDuration.Nanoseconds(), 10),
		strconv.FormatInt(m.WaitDuration.Microseconds(), 10),
		strconv.FormatInt(m.ApplyDuration.Nanoseconds(), 10),
		strconv.FormatInt(m.ApplyDuration.Microseconds(), 10),
		strconv.FormatInt(m.ReexecDuration.Nanoseconds(), 10),
		strconv.FormatInt(m.ReexecDuration.Microseconds(), 10),
		strconv.FormatInt(m.TotalDuration.Nanoseconds(), 10),
		strconv.FormatInt(m.TotalDuration.Microseconds(), 10),

		strconv.Itoa(m.ReexecTxs),
		strconv.FormatUint(m.ReexecGas, 10),
		strconv.FormatUint(m.GasPoolRemaining, 10),
	})
}

// subBlockDiffSizes reports how much state a sub-block changes, which is what
// the join has to write.
func subBlockDiffSizes(sub *SubBlock) (storage, balances, nonces, codes, codeBytes int) {
	storage = len(sub.Diff.Storage)
	balances = len(sub.Diff.Balances)
	nonces = len(sub.Diff.Nonces)
	codes = len(sub.Diff.Codes)
	for _, write := range sub.Diff.Codes {
		codeBytes += len(write.Code)
	}
	return
}
