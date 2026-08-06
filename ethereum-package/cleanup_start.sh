#!/usr/bin/env bash

set -euo pipefail

echo "========================================"
echo "Cleaning old Kurtosis resources..."
echo "========================================"

# Remove old enclave (ignore if it doesn't exist)
kurtosis enclave rm -f local-eth-testnet || true

# Clean all Kurtosis resources
kurtosis clean -a || true

# Stop and restart the Kurtosis engine
kurtosis engine stop || true
kurtosis engine start

echo "Waiting 5 seconds for the engine to initialize..."
sleep 5

echo "========================================"
echo "Starting local-eth-testnet..."
echo "========================================"

# Clean again before starting and run the enclave
kurtosis clean -a && \
kurtosis run --enclave local-eth-testnet . --args-file network_params.yaml

echo "Done."
