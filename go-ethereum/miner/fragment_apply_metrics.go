package miner

import (
	"encoding/csv"
	"os"
	"strconv"
	"sync"
	"time"

	"github.com/ethereum/go-ethereum/log"
)

// FragmentMeta is what the proposer knows about a fragment that the fragment
// itself does not carry: when it landed here and how many bytes arrived.
type FragmentMeta struct {
	ReceivedAt time.Time
	Bytes      int
}

// FragmentApplyMetric is one row of per-fragment accounting. Both sides write
// rows: the leader that built and sent the fragment, and the proposer that
// merged it. Role says which.
//
// This is deliberately separate from FragmentMergeMetric, which stays per-block
// and untouched.
type FragmentApplyMetric struct {
	TimestampUTC string
	Role         string // "leader" or "proposer"
	Hostname     string

	BlockNumber uint64
	NumBuckets  uint32
	BucketID    uint32

	Txs     int
	Bytes   int
	GasUsed uint64

	// Outcome on the proposer: accepted, rejected, missing.
	Outcome   string
	Reason    string
	FailingTx string
	WantRoot  string
	GotRoot   string

	// Leader-side timing.
	BuildDuration time.Duration
	SendDuration  time.Duration

	// Proposer-side timing.
	ReceivedAtUTC     string
	MergeStartUTC     string
	WaitDuration      time.Duration // how long this fragment sat before merge began
	ExecDuration      time.Duration // executing its transactions
	RootCheckDuration time.Duration // computing and comparing the post root
	TotalDuration     time.Duration

	ExecutedTxs      int
	GasPoolRemaining uint64
}

var fragmentApplyMetricMu sync.Mutex

// RecordFragmentApplyMetric appends one row to the per-fragment CSV. The path
// comes from GETH_FRAGMENT_APPLY_METRICS_PATH, defaulting to
// fragment_apply_metrics.csv.
func RecordFragmentApplyMetric(m FragmentApplyMetric) {

	path := os.Getenv("GETH_FRAGMENT_APPLY_METRICS_PATH")

	if path == "" {
		path = "fragment_apply_metrics.csv"
	}

	fragmentApplyMetricMu.Lock()
	defer fragmentApplyMetricMu.Unlock()

	file, err := os.OpenFile(
		path,
		os.O_CREATE|os.O_APPEND|os.O_WRONLY,
		0644,
	)

	if err != nil {
		log.Error(
			"Failed to open fragment apply metrics file",
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

			"txs",
			"bytes",
			"gas_used",

			"outcome",
			"reason",
			"failing_tx",
			"want_root",
			"got_root",

			"build_duration_ns",
			"build_duration_us",
			"send_duration_ns",
			"send_duration_us",

			"received_at_utc",
			"merge_start_utc",
			"wait_duration_ns",
			"wait_duration_us",
			"exec_duration_ns",
			"exec_duration_us",
			"root_check_duration_ns",
			"root_check_duration_us",
			"total_duration_ns",
			"total_duration_us",

			"executed_txs",
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

		strconv.Itoa(m.Txs),
		strconv.Itoa(m.Bytes),
		strconv.FormatUint(m.GasUsed, 10),

		m.Outcome,
		m.Reason,
		m.FailingTx,
		m.WantRoot,
		m.GotRoot,

		strconv.FormatInt(m.BuildDuration.Nanoseconds(), 10),
		strconv.FormatInt(m.BuildDuration.Microseconds(), 10),
		strconv.FormatInt(m.SendDuration.Nanoseconds(), 10),
		strconv.FormatInt(m.SendDuration.Microseconds(), 10),

		m.ReceivedAtUTC,
		m.MergeStartUTC,
		strconv.FormatInt(m.WaitDuration.Nanoseconds(), 10),
		strconv.FormatInt(m.WaitDuration.Microseconds(), 10),
		strconv.FormatInt(m.ExecDuration.Nanoseconds(), 10),
		strconv.FormatInt(m.ExecDuration.Microseconds(), 10),
		strconv.FormatInt(m.RootCheckDuration.Nanoseconds(), 10),
		strconv.FormatInt(m.RootCheckDuration.Microseconds(), 10),
		strconv.FormatInt(m.TotalDuration.Nanoseconds(), 10),
		strconv.FormatInt(m.TotalDuration.Microseconds(), 10),

		strconv.Itoa(m.ExecutedTxs),
		strconv.FormatUint(m.GasPoolRemaining, 10),
	})
}

// fragmentStampOrEmpty formats an arrival stamp, or returns "" when unset.
func fragmentStampOrEmpty(t time.Time) string {
	if t.IsZero() {
		return ""
	}
	return t.UTC().Format(time.RFC3339Nano)
}

// fragmentArrivalSpread is the gap between the first and last fragment to land:
// how long the proposer could have been waiting on the slowest leader.
func fragmentArrivalSpread(first, last time.Time) time.Duration {
	if first.IsZero() || last.IsZero() {
		return 0
	}
	return last.Sub(first)
}
