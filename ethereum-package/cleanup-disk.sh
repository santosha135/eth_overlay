#!/usr/bin/env bash
#
# AlmaLinux / RHEL-compatible safe disk cleanup
#
# Default: REPORT ONLY
# Apply cleanup:
#   sudo bash cleanup-disk.sh --apply
#
# Recommended on:
#   10.10.0.23
#   10.10.0.28
#   10.10.0.29
#   10.10.0.30
#   10.10.0.21
#

set -u

MODE="report"

if [[ "${1:-}" == "--apply" ]]; then
    MODE="apply"
fi

if [[ $EUID -ne 0 ]]; then
    echo "ERROR: Run as root:"
    echo "  sudo bash $0 --apply"
    exit 1
fi

HOST="$(hostname -s)"
DATE="$(date '+%Y-%m-%d %H:%M:%S')"

echo
echo "============================================================"
echo " Disk Cleanup - $HOST"
echo " $DATE"
echo " Mode: $MODE"
echo "============================================================"
echo

###############################################################################
# Helper functions
###############################################################################

run_cmd() {
    echo
    echo "+ $*"

    if [[ "$MODE" == "apply" ]]; then
        "$@"
    fi
}

show_size() {
    local path="$1"

    if [[ -e "$path" ]]; then
        du -sh "$path" 2>/dev/null || true
    fi
}

###############################################################################
# 1. Current filesystem usage
###############################################################################

echo "### CURRENT FILESYSTEM USAGE"
df -hT
echo

###############################################################################
# 2. Find the biggest directories on /
###############################################################################

echo "### TOP DIRECTORIES UNDER /"
echo "This is REPORT ONLY."
echo

du -xhd1 / 2>/dev/null | sort -h | tail -20

echo

###############################################################################
# 3. Find large files on root filesystem
###############################################################################

echo "### LARGE FILES (>500 MB) ON /"
echo "This is REPORT ONLY."
echo

find / \
    -xdev \
    -type f \
    -size +500M \
    -printf '%s %p\n' \
    2>/dev/null |
    sort -nr |
    head -50 |
    numfmt --field=1 --to=iec 2>/dev/null || true

echo

###############################################################################
# 4. systemd journal cleanup
###############################################################################

echo "### SYSTEMD JOURNAL"

if command -v journalctl >/dev/null 2>&1; then

    journalctl --disk-usage 2>/dev/null || true

    echo
    echo "Keeping journal logs from the last 7 days."

    if [[ "$MODE" == "apply" ]]; then
        journalctl --vacuum-time=7d
    else
        echo "DRY RUN: journalctl --vacuum-time=7d"
    fi

fi

###############################################################################
# 5. DNF/YUM package cache
###############################################################################

echo
echo "### DNF PACKAGE CACHE"

if command -v dnf >/dev/null 2>&1; then
    run_cmd dnf clean all
fi

if command -v yum >/dev/null 2>&1; then
    if ! command -v dnf >/dev/null 2>&1; then
        run_cmd yum clean all
    fi
fi

###############################################################################
# 6. /var/cache
###############################################################################

echo
echo "### /var/cache"

show_size /var/cache

if [[ "$MODE" == "apply" ]]; then

    # Clean only old cache files, not the directory itself.
    find /var/cache \
        -xdev \
        -type f \
        -mtime +14 \
        -delete \
        2>/dev/null || true

else
    echo "DRY RUN: old /var/cache files (>14 days) would be removed."
fi

###############################################################################
# 7. Temporary files
###############################################################################

echo
echo "### TEMPORARY FILES"

show_size /tmp
show_size /var/tmp

echo

if [[ "$MODE" == "apply" ]]; then

    # Do NOT rm -rf the entire /tmp.
    # Remove files that have not been touched for 7 days.
    find /tmp \
        -xdev \
        -type f \
        -mtime +7 \
        -delete \
        2>/dev/null || true

    find /tmp \
        -xdev \
        -type l \
        -mtime +7 \
        -delete \
        2>/dev/null || true

    # /var/tmp is traditionally retained across reboots,
    # so use a longer retention period.
    find /var/tmp \
        -xdev \
        -type f \
        -mtime +14 \
        -delete \
        2>/dev/null || true

    find /var/tmp \
        -xdev \
        -type l \
        -mtime +14 \
        -delete \
        2>/dev/null || true

else

    echo "DRY RUN:"
    echo "  /tmp     files older than 7 days"
    echo "  /var/tmp files older than 14 days"

fi

###############################################################################
# 8. Crash dumps
###############################################################################

echo
echo "### CRASH DUMPS"

if [[ -d /var/crash ]]; then
    show_size /var/crash

    if [[ "$MODE" == "apply" ]]; then
        find /var/crash \
            -xdev \
            -type f \
            -mtime +14 \
            -delete \
            2>/dev/null || true
    else
        echo "DRY RUN: crash files older than 14 days would be removed."
    fi
fi

###############################################################################
# 9. Old rotated logs
###############################################################################

echo
echo "### OLD ROTATED LOGS"

echo "Files older than 30 days:"
find /var/log \
    -xdev \
    -type f \
    \( \
        -name '*.log.*' \
        -o -name '*.gz' \
        -o -name '*.old' \
    \) \
    -mtime +30 \
    -printf '%s %p\n' \
    2>/dev/null |
    sort -nr |
    head -50 |
    numfmt --field=1 --to=iec 2>/dev/null || true

echo

if [[ "$MODE" == "apply" ]]; then

    find /var/log \
        -xdev \
        -type f \
        \( \
            -name '*.log.*' \
            -o -name '*.gz' \
            -o -name '*.old' \
        \) \
        -mtime +30 \
        -delete \
        2>/dev/null || true

else

    echo "DRY RUN: rotated logs older than 30 days would be removed."

fi


###############################################################################
# Kurtosis logs
###############################################################################

echo
echo "### KURTOSIS LOGS"

if compgen -G "/var/log/kurtosis*" >/dev/null 2>&1; then

    echo
    echo "Kurtosis log directories/files:"
    du -sh /var/log/kurtosis* 2>/dev/null || true

    echo
    echo "Deleted Kurtosis files still held open:"
    if command -v lsof >/dev/null 2>&1; then
        lsof +L1 2>/dev/null | grep '/var/log/kurtosis' || true
    else
        echo "lsof is not installed."
    fi

    if [[ "$MODE" == "apply" ]]; then

        echo
        echo "Removing contents of /var/log/kurtosis..."
        rm -rf /var/log/kurtosis/*

        echo
        echo "Kurtosis logs AFTER cleanup:"
        du -sh /var/log/kurtosis* 2>/dev/null || true

        echo
        echo "Deleted Kurtosis files still held open AFTER cleanup:"
        lsof +L1 2>/dev/null | grep '/var/log/kurtosis' || true

    else

        echo
        echo "DRY RUN:"
        echo "  rm -rf /var/log/kurtosis/*"

    fi

else
    echo "/var/log/kurtosis* does not exist."
fi

###############################################################################
# 10. Snap old revisions
###############################################################################

echo
echo "### SNAP"

if command -v snap >/dev/null 2>&1; then

    echo "Installed snap revisions:"
    snap list --all 2>/dev/null || true

    echo
    echo "Looking for disabled/old snap revisions..."

    if [[ "$MODE" == "apply" ]]; then

        snap list --all 2>/dev/null |
        awk '/disabled/{print $1, $3}' |
        while read -r snapname revision; do

            if [[ -n "${snapname:-}" && -n "${revision:-}" ]]; then
                echo "Removing old snap: $snapname revision $revision"

                snap remove "$snapname" \
                    --revision="$revision" \
                    2>/dev/null || true
            fi

        done

    else

        echo "DRY RUN: disabled snap revisions would be removed."

    fi

else
    echo "snap is not installed."
fi

###############################################################################
# 11. systemd persistent journal size
###############################################################################

echo
echo "### JOURNAL DIRECTORY"

show_size /var/log/journal

###############################################################################
# 12. Deleted files still held open
###############################################################################

echo
echo "### DELETED FILES STILL OPEN"

echo "These files consume disk even though they were deleted."

if command -v lsof >/dev/null 2>&1; then

    lsof +L1 2>/dev/null |
        head -100 || true

else

    echo "lsof is not installed."
    echo "Install with:"
    echo "  sudo dnf install lsof"
fi

###############################################################################
# 13. IMPORTANT: Kubernetes/container data
###############################################################################

echo
echo "============================================================"
echo " KUBERNETES / CONTAINER DATA"
echo "============================================================"

echo
echo "DO NOT automatically delete these:"
echo
echo "  /var/lib/containerd"
echo "  /var/lib/docker"
echo "  /var/lib/kubelet"
echo "  /var/lib/containers"
echo "  /var/lib/etcd"
echo "  /home"
echo
echo "These may contain active Kubernetes/container/Ethereum data."

###############################################################################
# 14. Container runtime information
###############################################################################

echo
echo "### CONTAINER RUNTIME USAGE"

if command -v crictl >/dev/null 2>&1; then
    echo
    echo "--- crictl images ---"
    crictl images 2>/dev/null || true

    echo
    echo "--- crictl containers ---"
    crictl ps -a 2>/dev/null || true
fi

if command -v podman >/dev/null 2>&1; then
    echo
    echo "--- podman disk usage ---"
    podman system df 2>/dev/null || true
fi

if command -v docker >/dev/null 2>&1; then
    echo
    echo "--- docker disk usage ---"
    docker system df 2>/dev/null || true
fi

###############################################################################
# 15. Kubernetes disk locations
###############################################################################

echo
echo "### KUBERNETES DIRECTORIES"

for d in \
    /var/lib/kubelet \
    /var/lib/containerd \
    /var/lib/docker \
    /var/lib/containers \
    /var/lib/etcd
do
    if [[ -d "$d" ]]; then
        printf "%-30s " "$d"
        du -sh "$d" 2>/dev/null || true
    fi
done

###############################################################################
# Docker cleanup
###############################################################################

echo
echo "============================================================"
echo " DOCKER CLEANUP"
echo "============================================================"

if command -v docker >/dev/null 2>&1; then

    echo
    echo "Docker usage BEFORE cleanup:"
    docker system df || true

    if [[ "$MODE" == "apply" ]]; then

        echo
        echo "Removing stopped Docker containers..."
        docker container prune -f || true

        echo
        echo "Removing unused Docker images..."
        docker image prune -a -f || true

        echo
        echo "Removing unused Docker networks..."
        docker network prune -f || true

        echo
        echo "Removing Docker build cache..."
        docker builder prune -a -f || true

    else
        echo
        echo "DRY RUN:"
        echo "  docker container prune -f"
        echo "  docker image prune -a -f"
        echo "  docker network prune -f"
        echo "  docker builder prune -a -f"
    fi

    echo
    echo "Docker usage AFTER cleanup:"
    docker system df || true

fi


###############################################################################
# K3s / containerd imported-image cleanup
###############################################################################

echo
echo "============================================================"
echo " K3S / CONTAINERD IMAGE CLEANUP"
echo "============================================================"

if command -v crictl >/dev/null 2>&1; then

    echo
    echo "Containerd/Kubernetes images BEFORE cleanup:"
    crictl images || true

    if [[ "$MODE" == "apply" ]]; then

        echo
        echo "Removing unused containerd/K3s images..."

        crictl rmi --prune || true

    else
        echo
        echo "DRY RUN:"
        echo "  crictl rmi --prune"
    fi

    echo
    echo "Containerd/Kubernetes images AFTER cleanup:"
    crictl images || true

fi

###############################################################################
# 16. Final filesystem usage
###############################################################################

echo
echo "============================================================"
echo " FINAL FILESYSTEM USAGE"
echo "============================================================"

df -hT

echo
echo "============================================================"
echo " CLEANUP COMPLETE"
echo "============================================================"

if [[ "$MODE" != "apply" ]]; then
    echo
    echo "Nothing was deleted."
    echo
    echo "If the report looks safe, run:"
    echo
    echo "  sudo bash $0 --apply"
    echo
fi
