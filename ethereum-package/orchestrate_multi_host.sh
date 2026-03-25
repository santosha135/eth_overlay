#!/usr/bin/env bash
set -Eeuo pipefail

########################################
# CONFIG
########################################

# Remote SSH user
REMOTE_USER="narwhal"

# Target hosts / computers
HOSTS=(
  "10.10.0.23"
  "10.10.0.30"
  
)

# Base directories on LOCAL machine
LOCAL_ETH_OVERLAY="/home/narwhal/eth_overlay"
LOCAL_ATTACK_TESTBED="/home/narwhal/attack_testbed"

# Base directories on REMOTE machines
REMOTE_HOME="/home/${REMOTE_USER}"
REMOTE_ETH_OVERLAY="${REMOTE_HOME}/eth_overlay"
REMOTE_ATTACK_TESTBED="${REMOTE_HOME}/attack_testbed"

# Paths inside eth_overlay
REMOTE_GETH_REPO="${REMOTE_ETH_OVERLAY}/go-ethereum"
REMOTE_ETHEREUM_PACKAGE="${REMOTE_ETH_OVERLAY}/ethereum-package"
REMOTE_GETH_BIN="${REMOTE_GETH_REPO}/build/bin/geth"
REMOTE_DOCKER_GETH_PATH="${REMOTE_ETHEREUM_PACKAGE}/docker/geth-overlay/geth"

# Kurtosis settings
ENCLAVE_NAME="local-eth-testnet"
KURTOSIS_ARGS_FILE="network_params.yaml"

# Monitoring
MONITOR_SCRIPT="./geth_proc_usage.sh"
MONITOR_LOG="geth_proc_usage.log"

# Post-processing
POST_PROCESS_SCRIPT="post_process_script.mjs"

# SSH options
SSH_OPTS=(
  -o BatchMode=yes
  -o StrictHostKeyChecking=no
  -o ConnectTimeout=10
)

# Parallel jobs
MAX_PARALLEL=3

########################################
# HELPERS
########################################

timestamp() {
  date '+%Y-%m-%d %H:%M:%S'
}

log() {
  echo "[$(timestamp)] $*"
}

run_for_host() {
  local host="$1"

  log "========== START: ${host} =========="

  log "[${host}] Creating remote directories"
  ssh "${SSH_OPTS[@]}" "${REMOTE_USER}@${host}" "
    mkdir -p '${REMOTE_ETH_OVERLAY}' '${REMOTE_ATTACK_TESTBED}'
  "

  log "[${host}] Syncing eth_overlay"
  rsync -az --delete \
    -e "ssh ${SSH_OPTS[*]}" \
    "${LOCAL_ETH_OVERLAY}/" \
    "${REMOTE_USER}@${host}:${REMOTE_ETH_OVERLAY}/"

  log "[${host}] Syncing attack_testbed"
  rsync -az --delete \
    -e "ssh ${SSH_OPTS[*]}" \
    "${LOCAL_ATTACK_TESTBED}/" \
    "${REMOTE_USER}@${host}:${REMOTE_ATTACK_TESTBED}/"

  log "[${host}] Running remote build/orchestration"
  ssh "${SSH_OPTS[@]}" "${REMOTE_USER}@${host}" bash -s <<EOF
set -Eeuo pipefail

echo "[\$(date '+%Y-%m-%d %H:%M:%S')] Host: ${host}"

echo "[STEP 1] Build geth"
cd "${REMOTE_GETH_REPO}"
make geth

echo "[STEP 2] Copy built geth into docker overlay path"
cp "${REMOTE_GETH_BIN}" "${REMOTE_DOCKER_GETH_PATH}"
chmod +x "${REMOTE_DOCKER_GETH_PATH}"

echo "[STEP 3] Build docker image"
cd "${REMOTE_ETHEREUM_PACKAGE}"
docker build -t geth-overlay:local docker/geth-overlay

echo "[STEP 4] Run Kurtosis"
kurtosis clean -a
kurtosis run --enclave "${ENCLAVE_NAME}" . --args-file "${KURTOSIS_ARGS_FILE}"

echo "[STEP 5] Start monitoring script in background"
cd "${REMOTE_ETHEREUM_PACKAGE}"
pkill -f "geth_proc_usage.sh" || true
nohup bash -lc '${MONITOR_SCRIPT}' > "${MONITOR_LOG}" 2>&1 &

echo "[STEP 6] Run post process script"
cd "${REMOTE_ATTACK_TESTBED}"
node "${POST_PROCESS_SCRIPT}"

echo "[DONE] ${host}"
EOF

  log "[${host}] Collecting quick status"
  ssh "${SSH_OPTS[@]}" "${REMOTE_USER}@${host}" "
    echo '--- docker images ---'
    docker images | grep geth-overlay || true
    echo '--- kurtosis enclaves ---'
    kurtosis enclave ls || true
    echo '--- monitoring process ---'
    pgrep -af geth_proc_usage.sh || true
  "

  log "========== END: ${host} =========="
}

########################################
# MAIN
########################################

main() {
  local pids=()
  local count=0

  mkdir -p logs

  for host in "${HOSTS[@]}"; do
    (
      run_for_host "${host}"
    ) > "logs/${host}.log" 2>&1 &

    pids+=("$!")
    ((count+=1))

    if (( count % MAX_PARALLEL == 0 )); then
      wait
    fi
  done

  wait

  log "All hosts completed."
  log "Per-host logs are in ./logs/"
}

main "$@"`
