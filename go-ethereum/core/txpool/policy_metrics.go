package txpool

import (
	"fmt"
	"github.com/ethereum/go-ethereum/log"
	"github.com/xuri/excelize/v2"
	"os"
	"path/filepath"
	"time"
)

type PolicyMetric struct {
	TxHash string

	StartTimeUTC time.Time
	EndTimeUTC   time.Time

	TotalPolicyDuration time.Duration

	BytecodeStart    time.Time
	BytecodeEnd      time.Time
	BytecodeDuration time.Duration

	CodeSize int

	TxTo          string
	OperationType string

	CheckType string
	Status    string
	Reason    string
}

func (p *TxPool) recordPolicyMetric(metric PolicyMetric) {
	if p.policyMetricsCh == nil {
		return
	}

	select {
	case p.policyMetricsCh <- metric:
	default:
		// Do not block transaction processing just because
		// the metrics writer is behind.
		log.Warn(
			"Policy metrics channel full",
			"hash", metric.TxHash,
		)
	}
}

func (p *TxPool) policyMetricsWriter(path string) {

	f := excelize.NewFile()

	sheet := "policy_metrics"

	defaultSheet := f.GetSheetName(0)
	if defaultSheet != "" {
		f.SetSheetName(defaultSheet, sheet)
	}

	// headers := []string{
	// 	"tx_hash",
	// 	"start_time_utc",
	// 	"end_time_utc",

	// 	"total_policy_duration_ns",
	// 	"total_policy_duration_us",
	// 	"total_policy_duration_ms",

	// 	"bytecode_start_utc",
	// 	"bytecode_end_utc",

	// 	"bytecode_duration_ns",
	// 	"bytecode_duration_us",
	// 	"bytecode_duration_ms",

	// 	"code_size_bytes",

	// 	"check_type",
	// 	"status",
	// 	"reason",
	// }

	headers := []string{
		"tx_hash",
		"start_time_utc",
		"end_time_utc",

		"total_policy_duration_ns",
		"total_policy_duration_us",
		"total_policy_duration_ms",

		"bytecode_start_utc",
		"bytecode_end_utc",

		"bytecode_duration_ns",
		"bytecode_duration_us",
		"bytecode_duration_ms",

		"code_size_bytes",

		"tx_to",
		"operation_type",

		"check_type",
		"status",
		"reason",
	}

	for col, value := range headers {
		cell, _ := excelize.CoordinatesToCellName(col+1, 1)
		f.SetCellValue(sheet, cell, value)
	}

	row := 2

	// Save periodically so data survives while geth is running.
	ticker := time.NewTicker(2 * time.Second)
	defer ticker.Stop()

	dirty := false

	save := func() {
		if !dirty {
			return
		}

		if err := f.SaveAs(path); err != nil {
			log.Error(
				"Failed saving policy metrics Excel",
				"path", path,
				"err", err,
			)
		} else {
			dirty = false
		}
	}

	for {
		select {

		case metric, ok := <-p.policyMetricsCh:
			if !ok {
				save()
				f.Close()

				if p.policyMetricsDone != nil {
					close(p.policyMetricsDone)
				}

				return
			}

			// values := []interface{}{
			// 	metric.TxHash,

			// 	metric.StartTimeUTC.Format(
			// 		time.RFC3339Nano,
			// 	),

			// 	metric.EndTimeUTC.Format(
			// 		time.RFC3339Nano,
			// 	),

			// 	metric.TotalPolicyDuration.Nanoseconds(),
			// 	metric.TotalPolicyDuration.Microseconds(),
			// 	float64(metric.TotalPolicyDuration.Nanoseconds()) /
			// 		1_000_000.0,

			// 	formatMetricTime(metric.BytecodeStart),
			// 	formatMetricTime(metric.BytecodeEnd),

			// 	metric.BytecodeDuration.Nanoseconds(),
			// 	metric.BytecodeDuration.Microseconds(),
			// 	float64(metric.BytecodeDuration.Nanoseconds()) /
			// 		1_000_000.0,

			// 	metric.CodeSize,

			// 	metric.CheckType,
			// 	metric.Status,
			// 	metric.Reason,
			// }
			values := []interface{}{
				metric.TxHash,

				metric.StartTimeUTC.Format(time.RFC3339Nano),
				metric.EndTimeUTC.Format(time.RFC3339Nano),

				metric.TotalPolicyDuration.Nanoseconds(),
				metric.TotalPolicyDuration.Microseconds(),
				float64(metric.TotalPolicyDuration.Nanoseconds()) / 1_000_000.0,

				formatMetricTime(metric.BytecodeStart),
				formatMetricTime(metric.BytecodeEnd),

				metric.BytecodeDuration.Nanoseconds(),
				metric.BytecodeDuration.Microseconds(),
				float64(metric.BytecodeDuration.Nanoseconds()) / 1_000_000.0,

				metric.CodeSize,

				metric.TxTo,
				metric.OperationType,

				metric.CheckType,
				metric.Status,
				metric.Reason,
			}

			for col, value := range values {
				cell, _ :=
					excelize.CoordinatesToCellName(
						col+1,
						row,
					)

				f.SetCellValue(sheet, cell, value)
			}

			row++
			dirty = true

		case <-ticker.C:
			save()
		}
	}
}

func formatMetricTime(t time.Time) string {
	if t.IsZero() {
		return ""
	}

	return t.UTC().Format(time.RFC3339Nano)
}

// func policyMetricsPath() string {

// 	path := os.Getenv("GETH_POLICY_METRICS_XLSX")

// 	if path == "" {
// 		path = "/tmp/tx_policy_metrics.xlsx"
// 	}

//		return path
//	}
func policyMetricsPath() string {
	path := os.Getenv("GETH_POLICY_METRICS_XLSX")

	if path == "" {
		path = "tx_policy_metrics.xlsx"
	}

	return path
}

func ensureMetricDirectory(path string) error {
	dir := filepath.Dir(path)

	if dir == "." || dir == "" {
		return nil
	}

	return os.MkdirAll(dir, 0755)
}

func policyMetricLogPath(path string) string {
	return fmt.Sprintf("%s", path)
}
