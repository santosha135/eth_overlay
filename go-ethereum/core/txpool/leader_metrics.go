package txpool

import (
	"os"
	"strconv"
	"sync"
	// "time"

	"github.com/ethereum/go-ethereum/log"
	"github.com/xuri/excelize/v2"
)

type LeaderSelectionMetric struct {
	TimestampUTC string
	Node         string
	Epoch        uint64
	ActiveBucket int
	GroupID      int
	GroupSize    int
	LeaderIndex  int
	MemberIndex  int
	IsLeader     bool
	DurationNs   int64
	DurationUs   int64
}

var leaderMetricsMu sync.Mutex

func (p *TxPool) recordLeaderSelectionMetric(m LeaderSelectionMetric) {
	path := os.Getenv("GETH_LEADER_METRICS_PATH")
	if path == "" {
		path = "leader_selection_metrics.xlsx"
	}

	leaderMetricsMu.Lock()
	defer leaderMetricsMu.Unlock()

	const sheet = "leader_selection"

	// ------------------------------------------------------------
	// Open existing workbook, or create a new one
	// ------------------------------------------------------------

	var f *excelize.File
	var err error

	if _, statErr := os.Stat(path); statErr == nil {
		f, err = excelize.OpenFile(path)
		if err != nil {
			log.Error(
				"Could not open leader metrics Excel file",
				"path", path,
				"err", err,
			)
			return
		}
	} else {
		f = excelize.NewFile()

		defaultSheet := f.GetSheetName(0)

		index, err := f.NewSheet(sheet)
		if err != nil {
			log.Error(
				"Could not create leader metrics sheet",
				"err", err,
			)
			return
		}

		f.SetActiveSheet(index)

		if defaultSheet != "" && defaultSheet != sheet {
			_ = f.DeleteSheet(defaultSheet)
		}

		// Header
		headers := []string{
			"timestamp_utc",
			"node",
			"epoch",
			"active_bucket",
			"group_id",
			"group_size",
			"leader_index",
			"member_index",
			"is_leader",
			"duration_ns",
			"duration_us",
		}

		for i, header := range headers {
			cell, _ := excelize.CoordinatesToCellName(i+1, 1)
			_ = f.SetCellValue(sheet, cell, header)
		}
	}

	defer f.Close()

	// ------------------------------------------------------------
	// Determine next available row
	// ------------------------------------------------------------

	rows, err := f.GetRows(sheet)
	if err != nil {
		log.Error(
			"Could not read leader metrics Excel rows",
			"path", path,
			"err", err,
		)
		return
	}

	nextRow := len(rows) + 1

	hostname, _ := os.Hostname()

	values := []interface{}{
		m.TimestampUTC,
		hostname,
		m.Epoch,
		m.ActiveBucket,
		m.GroupID,
		m.GroupSize,
		m.LeaderIndex,
		m.MemberIndex,
		m.IsLeader,
		m.DurationNs,
		m.DurationUs,
	}

	for i, value := range values {
		cell, _ := excelize.CoordinatesToCellName(
			i+1,
			nextRow,
		)

		if err := f.SetCellValue(sheet, cell, value); err != nil {
			log.Error(
				"Could not write leader metric cell",
				"cell", cell,
				"err", err,
			)
			return
		}
	}

	// ------------------------------------------------------------
	// Save workbook
	// ------------------------------------------------------------

	if err := f.SaveAs(path); err != nil {
		log.Error(
			"Could not save leader metrics Excel file",
			"path", path,
			"err", err,
		)
		return
	}

	log.Debug(
		"Leader selection metric written",
		"path", path,
		"epoch", strconv.FormatUint(m.Epoch, 10),
		"leaderIndex", m.LeaderIndex,
		"durationNs", m.DurationNs,
	)
}
