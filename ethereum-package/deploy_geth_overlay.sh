#!/bin/bash

set -euo pipefail

# Configuration
IMAGE_NAME="geth-overlay:local"
IMAGE_TAR="geth-overlay-local.tar"
GETH_SRC="/home/narwhal/eth_overlay/go-ethereum/build/bin/geth"
GETH_DST="docker/geth-overlay/geth"

# Nodes to deploy
NODES=(
    "10.10.0.30"
    "10.10.0.28"
    "10.10.0.29"
    "10.10.0.21"
)

echo "======================================="
echo "Copying geth binary..."
echo "======================================="
cp "$GETH_SRC" "$GETH_DST"
chmod +x "$GETH_DST"

echo "======================================="
echo "Building Docker image..."
echo "======================================="
docker build --no-cache -t "$IMAGE_NAME" docker/geth-overlay/

echo "======================================="
echo "Saving Docker image..."
echo "======================================="
docker save "$IMAGE_NAME" -o "$IMAGE_TAR"

echo "======================================="
echo "Importing image into local k3s..."
echo "======================================="
sudo k3s ctr images import "$IMAGE_TAR"
sudo k3s ctr images ls | grep geth-overlay

echo "======================================="
echo "Deploying image to remote nodes..."
echo "======================================="

for NODE in "${NODES[@]}"; do
    echo "---------------------------------------"
    echo "Deploying to $NODE"
    echo "---------------------------------------"

    scp "$IMAGE_TAR" "narwhal@$NODE:/home/narwhal/"

    ssh "narwhal@$NODE" <<EOF
sudo /usr/local/bin/k3s ctr images import /home/narwhal/$IMAGE_TAR
sudo /usr/local/bin/k3s ctr images ls | grep geth-overlay
EOF

done

echo "======================================="
echo "Verifying image on all nodes..."
echo "======================================="

VERIFY_NODES=(
    "10.10.0.30"
    "10.10.0.28"
    "10.10.0.29"
    "10.10.0.21"
)

for NODE in "${VERIFY_NODES[@]}"; do
    echo "===== $NODE ====="
    ssh "narwhal@$NODE" \
        'sudo /var/lib/rancher/k3s/data/current/bin/ctr -n k8s.io images ls | grep geth-overlay || sudo k3s ctr images ls | grep geth-overlay'
done

echo
echo "======================================="
echo "Deployment completed successfully."
echo "======================================="
