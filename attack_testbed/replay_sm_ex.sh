#!/usr/bin/env bash
set -euo pipefail

NS="kt-local-eth-testnet"
POD="attack-runner"
LOCAL_DIR="/home/narwhal/eth_overlay/attack_testbed"
REMOTE_DIR="/root/attack_testbed"


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