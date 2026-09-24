#!/usr/bin/env bash

set -euo pipefail

# ============================================================
# CONFIGURATION
# ============================================================

BIN="./build/bin/scheduler-bench"
NUM_RUNS=5

# ============================================================
# CHECK BINARY
# ============================================================

if [ ! -x "$BIN" ]; then
    echo "ERROR: Benchmark binary not found:"
    echo "$BIN"
    echo
    echo "Build it first:"
    echo "go build -o build/bin/scheduler-bench ./cmd/scheduler-bench"
    exit 1
fi


# ============================================================
# RUN BENCHMARK
# ============================================================

for run in $(seq 1 "$NUM_RUNS"); do

    RUN_ID=$(printf "%02d" "$run")
    RUN_DIR="run_${RUN_ID}"

    echo
    echo "============================================================"
    echo "RUN ${run}/${NUM_RUNS}"
    echo "Output directory: ${RUN_DIR}"
    echo "============================================================"

    mkdir -p "$RUN_DIR"

    # Run benchmark inside run directory.
    # CSV files will therefore be stored separately for each run.
    (
        cd "$RUN_DIR"
        "../build/bin/scheduler-bench"
    )

    echo
    echo "Run ${run} completed."

    # Small delay between independent executions
    sleep 2

done


echo
echo "============================================================"
echo "ALL ${NUM_RUNS} BENCHMARK RUNS COMPLETED"
echo "============================================================"
