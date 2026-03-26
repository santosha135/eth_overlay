#!/usr/bin/env bash
set -Eeuo pipefail

########################################
# CONFIG
########################################

REMOTE_USER="narwhal"

HOSTS=(
  "10.10.0.23"
  "10.10.0.30"
)

GIT_REPO_URL="https://github.com/santosha135/eth_overlay.git"
GIT_BRANCH="main"

REMOTE_HOME="/home/${REMOTE_USER}"
REMOTE_REPO_DIR="${REMOTE_HOME}/eth_overlay"

REMOTE_GETH_REPO="${REMOTE_REPO_DIR}/go-ethereum"
REMOTE_ETHEREUM_PACKAGE="${REMOTE_REPO_DIR}/ethereum-package"
REMOTE_ATTACK_TESTBED="${REMOTE_REPO_DIR}/attack_testbed"

REMOTE_GETH_BIN="${REMOTE_GETH_REPO}/build/bin/geth"
REMOTE_DOCKER_GETH_PATH="${REMOTE_ETHEREUM_PACKAGE}/docker/geth-overlay/geth"

ENCLAVE_NAME="local-eth-testnet"
KURTOSIS_ARGS_FILE="network_params.yaml"

MONITOR_SCRIPT="./geth_proc_usage.sh"
MONITOR_LOG="geth_proc_usage.log"

POST_PROCESS_SCRIPT="post_process_script.mjs"

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

run_for_host() {
  local host="$1"

  log "========== START: ${host} =========="

  ssh "${SSH_OPTS[@]}" "${REMOTE_USER}@${host}" bash -s <<EOF
set -Eeuo pipefail

log() {
  echo "[\$(date '+%Y-%m-%d %H:%M:%S')] \$*"
}

have_cmd() {
  command -v "\$1" >/dev/null 2>&1
}

SUDO=""
if have_cmd sudo; then
  if sudo -n true 2>/dev/null; then
    SUDO="sudo"
  else
    log "ERROR: passwordless sudo is required for automation on this host"
    exit 1
  fi
fi

########################################
# OS CHECK
########################################

if [ ! -f /etc/redhat-release ]; then
  log "This script is intended for RHEL-like systems."
  exit 1
fi

if have_cmd dnf; then
  PKG="dnf"
elif have_cmd yum; then
  PKG="yum"
else
  log "Neither dnf nor yum found."
  exit 1
fi

ARCH="\$(uname -m)"
log "Detected architecture: \$ARCH"
log "Using package manager: \$PKG"

pkg_update() {
  if [ "\$PKG" = "dnf" ]; then
    \$SUDO dnf -y makecache
  else
    \$SUDO yum -y makecache
  fi
}

pkg_install() {
  if [ "\$PKG" = "dnf" ]; then
    \$SUDO dnf -y install "\$@"
  else
    \$SUDO yum -y install "\$@"
  fi
}

########################################
# REQUIRED TOOLS
########################################

install_base_tools() {
  log "Installing base packages"
  pkg_install git curl wget tar which ca-certificates gnupg2 dnf-plugins-core yum-utils rsync make gcc gcc-c++
}

install_node() {
  if have_cmd node; then
    log "node already installed: \$(node --version || true)"
    return
  fi

  log "Installing nodejs and npm"
  pkg_install nodejs npm || true

  if ! have_cmd node && have_cmd nodejs; then
    \$SUDO ln -sf "\$(command -v nodejs)" /usr/local/bin/node || true
  fi

  if have_cmd node; then
    log "node installed: \$(node --version || true)"
  else
    log "node install failed"
    exit 1
  fi
}

install_go() {
  if have_cmd go; then
    log "go already installed: \$(go version || true)"
    return
  fi

  log "Installing golang"
  pkg_install golang || pkg_install go-toolset || true

  if ! have_cmd go; then
    log "go was not installed by package manager"
    exit 1
  fi

  log "go installed: \$(go version || true)"
}

install_docker_engine() {
  if have_cmd docker; then
    log "docker already installed: \$(docker --version || true)"
  else
    log "Installing Docker Engine repo and packages"
    if have_cmd dnf; then
      \$SUDO dnf -y install dnf-plugins-core
      \$SUDO dnf config-manager --add-repo https://download.docker.com/linux/rhel/docker-ce.repo
      \$SUDO dnf -y install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    else
      \$SUDO yum -y install yum-utils
      \$SUDO yum-config-manager --add-repo https://download.docker.com/linux/rhel/docker-ce.repo
      \$SUDO yum -y install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    fi
  fi

  \$SUDO systemctl enable --now docker

  if getent group docker >/dev/null 2>&1; then
    \$SUDO usermod -aG docker "${REMOTE_USER}" || true
  fi

  log "docker version: \$(docker --version || true)"
  log "docker compose version: \$(docker compose version || true)"
}

install_kurtosis() {
  export PATH="\$HOME/.kurtosis/bin:/usr/local/bin:/usr/bin:\$PATH"

  if have_cmd kurtosis; then
    log "kurtosis already installed: \$(kurtosis version || true)"
    return
  fi

  log "Installing Kurtosis repo"
  cat <<'REPO' | \$SUDO tee /etc/yum.repos.d/kurtosis.repo >/dev/null
[kurtosis]
name=Kurtosis
baseurl=https://sdk.kurtosis.com/kurtosis-cli-release-artifacts/rpm/
enabled=1
gpgcheck=0
REPO

  if [ "\$PKG" = "dnf" ]; then
    \$SUDO dnf -y makecache
    \$SUDO dnf -y install kurtosis-cli
  else
    \$SUDO yum -y makecache
    \$SUDO yum -y install kurtosis-cli
  fi

  export PATH="\$HOME/.kurtosis/bin:/usr/local/bin:/usr/bin:\$PATH"

  if ! have_cmd kurtosis; then
    log "kurtosis installation failed"
    exit 1
  fi

  log "kurtosis version: \$(kurtosis version || true)"
}

verify_tools() {
  log "Verifying required tools"
  git --version || true
  curl --version 2>/dev/null | sed -n '1p' || true
  rsync --version 2>/dev/null | sed -n '1p' || true
  make --version 2>/dev/null | sed -n '1p' || true
  go version || true
  docker --version || true
  docker compose version || true
  kurtosis version || true
  node --version || true
  npm --version || true
}

install_attack_testbed_deps() {
  cd "${REMOTE_ATTACK_TESTBED}"

  if [ ! -f package.json ]; then
    log "package.json not found, initializing npm project"
    npm init -y
  fi

  if ! npm list web3 >/dev/null 2>&1; then
    log "Installing npm dependency: web3"
    npm install web3
  else
    log "npm dependency web3 already installed"
  fi
}

########################################
# INSTALL FLOW
########################################

log "Refreshing package metadata"
pkg_update

install_base_tools
install_node
install_go
install_docker_engine
install_kurtosis
verify_tools

log "Tool verification completed"

########################################
# GIT PULL / CLONE
########################################

mkdir -p "${REMOTE_HOME}"

log "Checking repository at ${REMOTE_REPO_DIR}"
if [ ! -d "${REMOTE_REPO_DIR}/.git" ]; then
  log "Cloning repository"
  git clone --branch "${GIT_BRANCH}" "${GIT_REPO_URL}" "${REMOTE_REPO_DIR}"
else
  log "Repository exists, refreshing from origin/${GIT_BRANCH}"
  cd "${REMOTE_REPO_DIR}"
  git fetch --all
  git reset --hard "origin/${GIT_BRANCH}"
  git clean -fd
fi

log "Repository ready"
cd "${REMOTE_REPO_DIR}"
git rev-parse --abbrev-ref HEAD || true
git rev-parse HEAD || true

########################################
# BUILD + RUN
########################################

#log "STEP 1: make geth"
#cd "${REMOTE_GETH_REPO}"
#make geth

log "STEP 2: copy built geth binary"
cp "${REMOTE_GETH_BIN}" "${REMOTE_DOCKER_GETH_PATH}"
chmod +x "${REMOTE_DOCKER_GETH_PATH}"

log "STEP 3: build docker image"
cd "${REMOTE_ETHEREUM_PACKAGE}"
docker build -t geth-overlay:local docker/geth-overlay

log "STEP 4: run kurtosis"
kurtosis clean -a
kurtosis run --enclave "${ENCLAVE_NAME}" . --args-file "${KURTOSIS_ARGS_FILE}"

log "STEP 5: start monitoring script"
cd "${REMOTE_ETHEREUM_PACKAGE}"
pkill -f "geth_proc_usage.sh" || true
nohup bash -lc '${MONITOR_SCRIPT}' > "${MONITOR_LOG}" 2>&1 &

log "STEP 6: install attack_testbed dependencies"
install_attack_testbed_deps

log "STEP 7: run post process script"
cd "${REMOTE_ATTACK_TESTBED}"
node "${POST_PROCESS_SCRIPT}"

log "DONE on ${host}"
EOF

  log "[${host}] Collecting status"
  ssh "${SSH_OPTS[@]}" "${REMOTE_USER}@${host}" "
    export PATH=\"\$HOME/.kurtosis/bin:/usr/local/bin:/usr/bin:\$PATH\"
    echo '--- repo ---'
    cd '${REMOTE_REPO_DIR}' && git rev-parse --abbrev-ref HEAD && git rev-parse HEAD || true
    echo '--- versions ---'
    go version || true
    make --version 2>/dev/null | sed -n '1p' || true
    docker --version || true
    docker compose version || true
    kurtosis version || true
    node --version || true
    rsync --version 2>/dev/null | sed -n '1p' || true
    echo '--- docker image ---'
    docker images | grep geth-overlay || true
    echo '--- kurtosis enclaves ---'
    kurtosis enclave ls || true
    echo '--- monitor ---'
    pgrep -af geth_proc_usage.sh || true
  "

  log "========== END: ${host} =========="
}

main() {
  mkdir -p logs
  local count=0
  local failed=0
  local -a pids=()

  for host in "${HOSTS[@]}"; do
    (
      run_for_host "${host}"
    ) > "logs/${host}.log" 2>&1 &

    pids+=("$!")
    ((count+=1))

    if (( count % MAX_PARALLEL == 0 )); then
      for pid in "${pids[@]}"; do
        if ! wait "$pid"; then
          failed=1
        fi
      done
      pids=()
    fi
  done

  for pid in "${pids[@]}"; do
    if ! wait "$pid"; then
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