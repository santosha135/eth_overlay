package miner

import (
	"encoding/csv"
	"os"
	"strconv"
	"sync"
	"time"

	"github.com/ethereum/go-ethereum/log"
)

type FragmentMergeMetric struct {
	TimestampUTC string

	PayloadID string

	ExpectedFragments int
	ReceivedFragments int

	TotalTransactions int

	CollectionDuration time.Duration
	MergeDuration      time.Duration
	BlockBuildDuration time.Duration

	TotalDuration time.Duration
}

var fragmentMetricMu sync.Mutex

func recordFragmentMergeMetric(m FragmentMergeMetric) {

	path := os.Getenv("GETH_FRAGMENT_METRICS_PATH")

	if path == "" {
		path = "fragment_merge_metrics.csv"
	}

	fragmentMetricMu.Lock()
	defer fragmentMetricMu.Unlock()

	file, err := os.OpenFile(
		path,
		os.O_CREATE|os.O_APPEND|os.O_WRONLY,
		0644,
	)

	if err != nil {
		log.Error(
			"Failed to open fragment metrics file",
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

		// writer.Write([]string{
		// 	"timestamp_utc",
		// 	"payload_id",

		// 	"expected_fragments",
		// 	"received_fragments",

		// 	"total_transactions",

		// 	"collection_duration_us",
		// 	"merge_duration_us",
		// 	"block_build_duration_us",

		// 	"total_duration_us",
		// })
		writer.Write([]string{
			"timestamp_utc",
			"payload_id",

			"expected_fragments",
			"received_fragments",

			"total_transactions",

			"collection_duration_ns",
			"collection_duration_us",

			"merge_duration_ns",
			"merge_duration_us",

			"block_build_duration_ns",
			"block_build_duration_us",

			"total_duration_ns",
			"total_duration_us",
		})
	}

	// writer.Write([]string{
	// 	m.TimestampUTC,
	// 	m.PayloadID,

	// 	strconv.Itoa(m.ExpectedFragments),
	// 	strconv.Itoa(m.ReceivedFragments),

	// 	strconv.Itoa(m.TotalTransactions),

	// 	strconv.FormatInt(
	// 		m.CollectionDuration.Microseconds(),
	// 		10,
	// 	),

	// 	strconv.FormatInt(
	// 		m.MergeDuration.Microseconds(),
	// 		10,
	// 	),

	// 	strconv.FormatInt(
	// 		m.BlockBuildDuration.Microseconds(),
	// 		10,
	// 	),

	// 	strconv.FormatInt(
	// 		m.TotalDuration.Microseconds(),
	// 		10,
	// 	),
	// })
	writer.Write([]string{
		m.TimestampUTC,
		m.PayloadID,

		strconv.Itoa(m.ExpectedFragments),
		strconv.Itoa(m.ReceivedFragments),

		strconv.Itoa(m.TotalTransactions),

		strconv.FormatInt(
			m.CollectionDuration.Nanoseconds(),
			10,
		),
		strconv.FormatInt(
			m.CollectionDuration.Microseconds(),
			10,
		),

		strconv.FormatInt(
			m.MergeDuration.Nanoseconds(),
			10,
		),
		strconv.FormatInt(
			m.MergeDuration.Microseconds(),
			10,
		),

		strconv.FormatInt(
			m.BlockBuildDuration.Nanoseconds(),
			10,
		),
		strconv.FormatInt(
			m.BlockBuildDuration.Microseconds(),
			10,
		),

		strconv.FormatInt(
			m.TotalDuration.Nanoseconds(),
			10,
		),
		strconv.FormatInt(
			m.TotalDuration.Microseconds(),
			10,
		),
	})
}
