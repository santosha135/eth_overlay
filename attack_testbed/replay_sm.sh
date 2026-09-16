#!/usr/bin/env bash
set -euo pipefail

NS="kt-local-eth-testnet"
POD="attack-runner"
LOCAL_DIR="/home/narwhal/eth_overlay/attack_testbed"
REMOTE_DIR="/root/attack_testbed"

echo "[0/6] Starting attack-runner pod..."
kubectl apply -f attack-runner.yaml

echo "Waiting 5 seconds for the pod to start..."
sleep 5

echo "[1/6] Checking attack-runner pod..."
kubectl get pod "$POD" -n "$NS"

echo "[2/6] Copying local attack_testbed to attack-runner..."
kubectl cp "$LOCAL_DIR" "$NS/$POD:$REMOTE_DIR"

echo "[3/6] Installing packages inside attack-runner..."
kubectl exec -n "$NS" "$POD" -- bash -lc '
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive

apt-get update -y
apt-get install -y python3 python3-venv python3-pip vim nodejs npm curl procps && npm install solc

cd /root/attack_testbed

python3 -m venv venv
source venv/bin/activate

pip install --upgrade pip
pip install pandas web3 requests openpyxl
'

echo "[4/6] Checking replay scripts..."
kubectl exec -n "$NS" "$POD" -- bash -lc '
set -euo pipefail
cd /root/attack_testbed

for i in $(seq 1 10); do
  test -f "replay_tx_v${i}_sm.py" || {
    echo "Missing replay_tx_v${i}_sm.py"
    exit 1
  }
done

echo "All replay_tx_v1_sm.py ... replay_tx_v10_sm.py exist."
'

echo "[5/6] Running replay_tx_v1.py to replay_tx_v10.py in parallel..."
kubectl exec -n "$NS" "$POD" -- bash -lc '
set -euo pipefail
cd /root/attack_testbed
source venv/bin/activate

mkdir -p logs outputs

for i in $(seq 1 10); do
  script="replay_tx_v${i}_sm.py"
  log="logs/replay_tx_v${i}_sm.log"

  echo "[START] $script"
  nohup python3 "$script" > "$log" 2>&1 &
  # nohup ./venv/bin/python -u "$script" > "$log" 2>&1 &
  echo $! > "logs/replay_tx_v${i}_sm.pid"
done

echo "Started all 10 replay scripts."
echo "PIDs:"
cat logs/*.pid
'

echo "[6/6] Follow logs with:"
echo "kubectl exec -it -n $NS $POD -- bash"
echo "cd $REMOTE_DIR && tail -f logs/replay_tx_v*_sm.log"