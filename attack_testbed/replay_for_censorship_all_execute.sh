#!/usr/bin/env bash
set -euo pipefail

NS="kt-local-eth-testnet"
POD="attack-runner"

LOCAL_DIR="/home/narwhal/eth_overlay/attack_testbed"
REMOTE_DIR="/root/attack_testbed"

echo "=================================================="
echo "[0/8] Starting attack-runner pod..."
echo "=================================================="

kubectl apply -f attack-runner.yaml

echo
echo "Waiting for attack-runner pod to become Ready..."

kubectl wait \
    --for=condition=Ready \
    pod/"$POD" \
    -n "$NS" \
    --timeout=180s

echo
echo "=================================================="
echo "[1/8] Checking attack-runner pod..."
echo "=================================================="

kubectl get pod "$POD" -n "$NS" -o wide


echo
echo "=================================================="
echo "[2/8] Copying attack_testbed into attack-runner..."
echo "=================================================="

# Remove old directory first to avoid nested copies such as:
# /root/attack_testbed/attack_testbed
kubectl exec -n "$NS" "$POD" -- \
    bash -lc "rm -rf '$REMOTE_DIR' && mkdir -p '$REMOTE_DIR'"

kubectl cp \
    "$LOCAL_DIR/." \
    "$NS/$POD:$REMOTE_DIR"


echo
echo "=================================================="
echo "[3/8] Installing system and Python/Node dependencies..."
echo "=================================================="

kubectl exec -n "$NS" "$POD" -- bash -lc '
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive

apt-get update -y

apt-get install -y \
    python3 \
    python3-venv \
    python3-pip \
    vim \
    nodejs \
    npm \
    curl \
    procps

cd /root/attack_testbed

echo
echo "Node version:"
node --version

echo
echo "NPM version:"
npm --version

echo
echo "Python version:"
python3 --version


# --------------------------------------------------
# Node dependencies
# --------------------------------------------------

if [ ! -f package.json ]; then
    npm init -y
fi

npm install solc


# --------------------------------------------------
# Python virtual environment
# --------------------------------------------------

if [ ! -d venv ]; then
    python3 -m venv venv
fi

source venv/bin/activate

python3 -m pip install --upgrade pip

pip install \
    pandas \
    web3 \
    requests \
    openpyxl

echo
echo "Virtual environment:"
which python3

echo
echo "Python:"
python3 --version
'


echo
echo "=================================================="
echo "[4/8] Downloading top-20 smart contracts..."
echo "=================================================="

kubectl exec -n "$NS" "$POD" -- bash -lc '
set -euo pipefail

cd /root/attack_testbed

source venv/bin/activate

echo "Python being used:"
which python3

echo
echo "Starting download_top20_contracts.py..."
echo

python3 download_top20_contracts.py

echo
echo "download_top20_contracts.py completed successfully."
'


echo
echo "=================================================="
echo "[5/8] Deploying downloaded smart contracts..."
echo "=================================================="

kubectl exec -n "$NS" "$POD" -- bash -lc '
set -euo pipefail

cd /root/attack_testbed

source venv/bin/activate

mkdir -p logs

echo
echo "Running Hardhat deployment..."
echo

# Save complete output while also showing it on screen.
npx hardhat run \
    --no-compile \
    scripts/deploy_all20_remaining.ts \
    --network localnet \
    2>&1 | tee logs/deploy_all20_remaining.log

echo
echo "=================================================="
echo "Hardhat deployment completed."
echo "=================================================="
'


echo
echo "=================================================="
echo "[6/8] Extracting deployed address mappings..."
echo "=================================================="

kubectl exec -n "$NS" "$POD" -- bash -lc '
set -euo pipefail

cd /root/attack_testbed

DEPLOY_LOG="logs/deploy_all20_remaining.log"
MAPPING_FILE="logs/final_address_mapping.txt"

if [ ! -f "$DEPLOY_LOG" ]; then
    echo "ERROR: $DEPLOY_LOG does not exist."
    exit 1
fi

# --------------------------------------------------
# Extract lines such as:
#
# 0xdac... -> 0x123...
#
# Also retain FAILED if the deployment script emits:
#
# 0xdac... -> FAILED
# --------------------------------------------------

grep -Ei \
    "^[[:space:]]*0x[a-fA-F0-9]{40}[[:space:]]*->[[:space:]]*(0x[a-fA-F0-9]{40}|FAILED)[[:space:]]*$" \
    "$DEPLOY_LOG" \
    | sed "s/^[[:space:]]*//;s/[[:space:]]*$//" \
    > "$MAPPING_FILE" || true

COUNT=$(wc -l < "$MAPPING_FILE")

echo
echo "Mappings extracted: $COUNT"
echo

cat "$MAPPING_FILE"

if [ "$COUNT" -eq 0 ]; then
    echo
    echo "ERROR: No address mappings were found in Hardhat output."
    echo
    echo "Check:"
    echo "  $DEPLOY_LOG"
    exit 1
fi
'


echo
echo "=================================================="
echo "[7/8] Updating populate_maps.py and running it..."
echo "=================================================="

kubectl exec -n "$NS" "$POD" -- bash -lc '
set -euo pipefail

cd /root/attack_testbed

source venv/bin/activate

MAPPING_FILE="logs/final_address_mapping.txt"

if [ ! -f "$MAPPING_FILE" ]; then
    echo "ERROR: Mapping file missing:"
    echo "  $MAPPING_FILE"
    exit 1
fi

echo
echo "Mapping that will be inserted into populate_maps.py:"
echo "--------------------------------------------------"
cat "$MAPPING_FILE"
echo "--------------------------------------------------"


# ==========================================================
# BACK UP populate_maps.py
# ==========================================================

cp populate_maps.py populate_maps.py.before_mapping.bak


# ==========================================================
# Replace FINAL_ADDRESS_MAPPING = """ ... """
# automatically.
# ==========================================================

python3 - <<'"'"'PY'"'"'
from pathlib import Path
import re

populate_file = Path("populate_maps.py")
mapping_file = Path("logs/final_address_mapping.txt")

text = populate_file.read_text()
mapping = mapping_file.read_text().strip()

if not mapping:
    raise RuntimeError("Address mapping file is empty.")

pattern = re.compile(
    r'"'"'FINAL_ADDRESS_MAPPING\s*=\s*"""[\s\S]*?"""'"'"',
    re.MULTILINE,
)

replacement = (
    '"'"'FINAL_ADDRESS_MAPPING = """\n'"'"'
    + mapping
    + '"'"'\n"""'"'"'
)

updated, count = pattern.subn(
    lambda m: replacement,
    text,
    count=1,
)

if count != 1:
    raise RuntimeError(
        "Could not uniquely locate FINAL_ADDRESS_MAPPING "
        f"in populate_maps.py. Replacements={count}"
    )

populate_file.write_text(updated)

print()
print("SUCCESS: FINAL_ADDRESS_MAPPING updated.")
print()
print("Installed mapping:")
print(mapping)
PY


echo
echo "=================================================="
echo "Running populate_maps.py..."
echo "=================================================="
echo

python3 populate_maps.py

echo
echo "populate_maps.py completed successfully."
'


echo
echo "=================================================="
echo "[8/8] Verifying replay script mappings..."
echo "=================================================="

kubectl exec -n "$NS" "$POD" -- bash -lc '
set -euo pipefail

cd /root/attack_testbed
source venv/bin/activate

echo
echo "Replay smart-contract scripts:"
echo

ls -lh replay_tx_v*_sm.py

echo
echo "Number of replay scripts:"
find . \
    -maxdepth 1 \
    -type f \
    -name "replay_tx_v*_sm.py" \
    | wc -l

echo
echo "CONTRACT_ADDRESS_MAP occurrences:"
echo

for f in replay_tx_v*_sm.py; do
    printf "%-25s : " "$f"

    grep -c "^CONTRACT_ADDRESS_MAP" "$f" || true
done


echo
echo "=================================================="
echo "Current mapping from populate_maps.py"
echo "=================================================="

python3 - <<'"'"'PY'"'"'
from pathlib import Path
import re

text = Path("populate_maps.py").read_text()

match = re.search(
    r'"'"'FINAL_ADDRESS_MAPPING\s*=\s*"""([\s\S]*?)"""'"'"',
    text,
)

if match:
    print(match.group(1).strip())
else:
    print("FINAL_ADDRESS_MAPPING not found.")
PY
'


echo
echo "=================================================="
echo "ALL STEPS COMPLETED SUCCESSFULLY"
echo "=================================================="

echo
echo "Enter attack-runner:"
echo
echo "kubectl exec -it -n $NS $POD -- bash"
echo
echo "Then:"
echo
echo "cd $REMOTE_DIR"
echo "source venv/bin/activate"
echo

echo "Deployment log:"
echo "$REMOTE_DIR/logs/deploy_all20_remaining.log"

echo
echo "Extracted mapping:"
echo "$REMOTE_DIR/logs/final_address_mapping.txt"

echo
echo "=================================================="