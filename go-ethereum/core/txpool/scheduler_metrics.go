package txpool

import (
	"encoding/csv"
	"os"
	"strconv"
	"sync"
	// "time"

	"github.com/ethereum/go-ethereum/log"
)

type SchedulerMetric struct {
	TimestampUTC string
	Node         string

	BlockNumber uint64
	Epoch       uint64

	GroupID     int
	MemberIndex int
	GroupSize   int

	ActiveBucket int
	LeaderIndex  int
	IsLeader     bool

	RotationDurationNs int64
	RotationDurationUs int64

	LeaderDurationNs int64
	LeaderDurationUs int64
}

var (
	schedulerMetricsMu     sync.Mutex
	schedulerMetricsHeader bool
)

func (p *TxPool) recordSchedulerMetric(m SchedulerMetric) {
	path := os.Getenv("GETH_SCHED_METRICS_PATH")
	if path == "" {
		path = "scheduler_metrics.csv"
	}

	schedulerMetricsMu.Lock()
	defer schedulerMetricsMu.Unlock()

	file, err := os.OpenFile(
		path,
		os.O_CREATE|os.O_WRONLY|os.O_APPEND,
		0644,
	)
	if err != nil {
		log.Error(
			"Could not open scheduler metrics file",
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
			"node",
			"block_number",
			"epoch",
			"group_id",
			"member_index",
			"group_size",
			"active_bucket",
			"leader_index",
			"is_leader",
			"rotation_duration_ns",
			"rotation_duration_us",
			"leader_selection_duration_ns",
			"leader_selection_duration_us",
		})
	}

	hostname, _ := os.Hostname()

	writer.Write([]string{
		m.TimestampUTC,
		hostname,
		strconv.FormatUint(m.BlockNumber, 10),
		strconv.FormatUint(m.Epoch, 10),
		strconv.Itoa(m.GroupID),
		strconv.Itoa(m.MemberIndex),
		strconv.Itoa(m.GroupSize),
		strconv.Itoa(m.ActiveBucket),
		strconv.Itoa(m.LeaderIndex),
		strconv.FormatBool(m.IsLeader),
		strconv.FormatInt(m.RotationDurationNs, 10),
		strconv.FormatInt(m.RotationDurationUs, 10),
		strconv.FormatInt(m.LeaderDurationNs, 10),
		strconv.FormatInt(m.LeaderDurationUs, 10),
	})
}
