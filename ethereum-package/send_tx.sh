#!/usr/bin/env bash
set -Eeuo pipefail

########################################
# CONFIG
########################################

REMOTE_USER="narwhal"

HOSTS=(
  "10.10.0.30"
)

REMOTE_HOME="/home/${REMOTE_USER}"
REMOTE_REPO_DIR="${REMOTE_HOME}/eth_overlay"

REMOTE_ETHEREUM_PACKAGE="${REMOTE_REPO_DIR}/ethereum-package"
REMOTE_ATTACK_TESTBED="${REMOTE_REPO_DIR}/attack_testbed"

ENCLAVE_NAME="local-eth-testnet"

# Monitoring script stays in ethereum-package
MONITOR_SCRIPT="${REMOTE_ETHEREUM_PACKAGE}/geth_proc_usage.sh"
MONITOR_LOG_DIR="${REMOTE_ETHEREUM_PACKAGE}/logs"

# All tx scripts are in same place as post_process_script.mjs
NORMAL_TX_SCRIPT="${REMOTE_ATTACK_TESTBED}/send_normal_transaction.mjs"
RESOURCE_ATTACK_SCRIPT="${REMOTE_ATTACK_TESTBED}/send_resource_exhaust_attack.mjs"
MEMPURGE_ATTACK_SCRIPT="${REMOTE_ATTACK_TESTBED}/send_mempurge_attack.mjs"
CENSORSHIP_TEST_SCRIPT="${REMOTE_ATTACK_TESTBED}/send_censorship_test.mjs"

SSH_OPTS=(
  -o BatchMode=yes
  -o StrictHostKeyChecking=no
  -o ConnectTimeout=10
)

MAX_PARALLEL=2

########################################
# HELPERS
########################################

timestamp() {
  date '+%Y-%m-%d %H:%M:%S'
}

log() {
  echo "[$(timestamp)] $*"
}

choose_mode() {
  echo
  echo "Choose transaction mode:"
  echo "1. send normal transaction"
  echo "2. send resource exhaust attack"
  echo "3. mempurge attack"
  echo "4. censorship test"
  echo

  read -rp "Enter choice [1-4]: " TX_CHOICE

  case "${TX_CHOICE}" in
    1)
      TX_MODE_NAME="normal"
      TX_SCRIPT_PATH="${NORMAL_TX_SCRIPT}"
      ;;
    2)
      TX_MODE_NAME="resource_exhaust"
      TX_SCRIPT_PATH="${RESOURCE_ATTACK_SCRIPT}"
      ;;
    3)
      TX_MODE_NAME="mempurge"
      TX_SCRIPT_PATH="${MEMPURGE_ATTACK_SCRIPT}"
      ;;
    4)
      TX_MODE_NAME="censorship"
      TX_SCRIPT_PATH="${CENSORSHIP_TEST_SCRIPT}"
      ;;
    *)
      echo "Invalid choice: ${TX_CHOICE}"
      exit 1
      ;;
  esac

  echo
  echo "Selected mode : ${TX_MODE_NAME}"
  echo "Remote script : ${TX_SCRIPT_PATH}"
  echo
}

run_for_host() {
  local host="$1"

  log "========== START TX RUN: ${host} =========="

  ssh "${SSH_OPTS[@]}" "${REMOTE_USER}@${host}" \
    "REMOTE_USER='${REMOTE_USER}' \
     REMOTE_ETHEREUM_PACKAGE='${REMOTE_ETHEREUM_PACKAGE}' \
     REMOTE_ATTACK_TESTBED='${REMOTE_ATTACK_TESTBED}' \
     MONITOR_SCRIPT='${MONITOR_SCRIPT}' \
     MONITOR_LOG_DIR='${MONITOR_LOG_DIR}' \
     TX_MODE_NAME='${TX_MODE_NAME}' \
     TX_SCRIPT_PATH='${TX_SCRIPT_PATH}' \
     ENCLAVE_NAME='${ENCLAVE_NAME}' \
     bash -s" <<'EOF'
set -Eeuo pipefail

timestamp() {
  date '+%Y-%m-%d %H:%M:%S'
}

log() {
  echo "[$(timestamp)] $*"
}

have_cmd() {
  command -v "$1" >/dev/null 2>&1
}

get_kurtosis_rpc_url() {
  local inspect_output
  inspect_output="$(kurtosis enclave inspect "${ENCLAVE_NAME}" 2>/dev/null || true)"

  if [ -z "${inspect_output}" ]; then
    log "ERROR: kurtosis enclave inspect returned no output"
    return 1
  fi

  awk '
    BEGIN { in_target=0 }
    /^[0-9a-f]+[[:space:]]+el-.*geth/ { in_target=1; next }
    /^[0-9a-f]+[[:space:]]+/ { in_target=0 }
    in_target && /rpc:[[:space:]]*8545\/tcp[[:space:]]*->[[:space:]]*(http:\/\/)?127\.0\.0\.1:/ {
      if (match($0, /127\.0\.0\.1:[0-9]+/)) {
        print "http://" substr($0, RSTART, RLENGTH)
        exit
      }
    }
  ' <<< "${inspect_output}"
}

if ! have_cmd node; then
  log "ERROR: node is not installed on remote host"
  exit 1
fi

if ! have_cmd kurtosis; then
  export PATH="$HOME/.kurtosis/bin:/usr/local/bin:/usr/bin:$PATH"
fi

mkdir -p "${MONITOR_LOG_DIR}"

MONITOR_LOG="${MONITOR_LOG_DIR}/geth_proc_usage_${TX_MODE_NAME}.log"
TX_RUN_LOG="${MONITOR_LOG_DIR}/tx_run_${TX_MODE_NAME}.log"

log "Using monitor script : ${MONITOR_SCRIPT}"
log "Using tx script      : ${TX_SCRIPT_PATH}"
log "Monitor log          : ${MONITOR_LOG}"
log "TX run log           : ${TX_RUN_LOG}"

########################################
# START MONITORING IN BACKGROUND
########################################

pkill -f "geth_proc_usage.sh" || true

if [ ! -f "${MONITOR_SCRIPT}" ]; then
  log "ERROR: monitor script not found: ${MONITOR_SCRIPT}"
  exit 1
fi

chmod +x "${MONITOR_SCRIPT}" || true

log "Starting monitoring script in background"
setsid nohup bash "${MONITOR_SCRIPT}" >> "${MONITOR_LOG}" 2>&1 < /dev/null &
MONITOR_PID=$!

sleep 2

if ps -p "${MONITOR_PID}" >/dev/null 2>&1; then
  log "Monitoring started with PID ${MONITOR_PID}"
else
  log "ERROR: monitoring script failed to stay running"
  [ -f "${MONITOR_LOG}" ] && tail -50 "${MONITOR_LOG}" || true
  exit 1
fi

########################################
# VERIFY TX SCRIPT
########################################

if [ ! -f "${TX_SCRIPT_PATH}" ]; then
  log "ERROR: transaction script not found: ${TX_SCRIPT_PATH}"
  exit 1
fi

########################################
# OPTIONAL: AUTO-DETECT RPC URL
########################################

RPC_URL="$(get_kurtosis_rpc_url || true)"
if [ -n "${RPC_URL}" ]; then
  log "Detected RPC URL: ${RPC_URL}"
else
  log "WARNING: could not auto-detect RPC URL; tx script must handle it itself"
fi

########################################
# RUN TRANSACTION SCRIPT
########################################

cd "${REMOTE_ATTACK_TESTBED}"

log "Running transaction script"
if [ -n "${RPC_URL}" ]; then
  RPC_URL="${RPC_URL}" node "${TX_SCRIPT_PATH}" 2>&1 | tee -a "${TX_RUN_LOG}"
else
  node "${TX_SCRIPT_PATH}" 2>&1 | tee -a "${TX_RUN_LOG}"
fi

log "Transaction script completed"

########################################
# CONFIRM MONITOR STILL RUNNING
########################################

if pgrep -af geth_proc_usage.sh >/dev/null 2>&1; then
  log "Monitor is still running after tx execution"
else
  log "WARNING: monitor is no longer running"
fi

log "DONE"
EOF

  log "[${host}] Collecting status"

  ssh "${SSH_OPTS[@]}" "${REMOTE_USER}@${host}" "
    export PATH=\"\$HOME/.kurtosis/bin:/usr/local/bin:/usr/bin:\$PATH\"
    echo '--- kurtosis enclaves ---'
    kurtosis enclave ls || true
    echo '--- monitor process ---'
    pgrep -af geth_proc_usage.sh || true
    echo '--- monitor logs ---'
    ls -l '${MONITOR_LOG_DIR}' || true
  "

  log "========== END TX RUN: ${host} =========="
}

main() {
  choose_mode

  mkdir -p logs
  local count=0
  local failed=0
  local -a pids=()

  for host in "${HOSTS[@]}"; do
    (
      run_for_host "${host}"
    ) > "logs/${host}_${TX_MODE_NAME}.log" 2>&1 &

    pids+=("$!")
    ((count+=1))

    if (( count % MAX_PARALLEL == 0 )); then
      for pid in "${pids[@]}"; do
        if ! wait "${pid}"; then
          failed=1
        fi
      done
      pids=()
    fi
  done

  for pid in "${pids[@]}"; do
    if ! wait "${pid}"; then
      failed=1
    fi
  done

  if (( failed )); then
    log "One or more hosts failed."
    log "Logs are in ./logs/"
    exit 1
  fi

  log "All hosts completed successfully."
  log "Logs are in ./logs/"
}

main "$@"