#!/usr/bin/env bash
set -euo pipefail

ENCLAVE="local-eth-testnet"
SERVICE="el-1-geth-lighthouse"
INTERVAL="${1:-2}"

kexec() {
  kurtosis service exec "$ENCLAVE" "$SERVICE" "$1"
}

get_geth_pid() {
  kexec 'sh -lc '"'"'
for f in /proc/[0-9]*/comm; do
  [ -r "$f" ] || continue
  read -r name < "$f" || continue
  if [ "$name" = "geth" ]; then
    pid="${f#/proc/}"
    pid="${pid%/comm}"
    echo "$pid"
    exit 0
  fi
done
exit 1
'"'"'' 2>/dev/null | awk '/^[0-9]+$/ {print; exit}'
}

read_sample() {
  local pid="$1"
  kexec "sh -lc '
    [ -r /proc/$pid/stat ] || exit 1
    [ -r /proc/$pid/status ] || exit 1
    [ -r /proc/stat ] || exit 1
    [ -r /proc/meminfo ] || exit 1

    PROC=\$(awk \"{print \\\$14 + \\\$15}\" /proc/$pid/stat)
    TOTAL=\$(awk \"/^cpu / {sum=0; for (i=2; i<=NF; i++) sum+=\\\$i; print sum}\" /proc/stat)
    RSS=\$(awk \"/^VmRSS:/ {print \\\$2}\" /proc/$pid/status)
    MEMTOTAL=\$(awk \"/^MemTotal:/ {print \\\$2}\" /proc/meminfo)

    NCPU=1
    if [ -r /proc/stat ]; then
      NCPU=\$(awk \"/^cpu[0-9]+ / {n++} END {if (n>0) print n; else print 1}\" /proc/stat)
    fi

    echo \"\$PROC \$TOTAL \$RSS \$MEMTOTAL \$NCPU\"
  '" 2>/dev/null | awk 'NF==5 {print; exit}'
}

PID="$(get_geth_pid || true)"

if [[ -z "$PID" ]]; then
  echo "No running geth process found in $SERVICE"
  echo "Trying raw /proc listing for debug..."
  kexec 'sh -lc '"'"'
for f in /proc/[0-9]*/comm; do
  [ -r "$f" ] || continue
  pid="${f#/proc/}"
  pid="${pid%/comm}"
  read -r name < "$f" || continue
  echo "$pid $name"
done | sed -n "1,40p"
'"'"'' || true
  exit 1
fi

echo "Monitoring geth process only"
echo "Enclave : $ENCLAVE"
echo "Service : $SERVICE"
echo "PID     : $PID"
echo "Interval: ${INTERVAL}s"
echo

printf "%-20s %-8s %-12s %-12s %-12s\n" "timestamp" "pid" "cpu(%)" "rss(MiB)" "mem(%)"

while true; do
  SAMPLE1="$(read_sample "$PID" || true)"
  if [[ -z "$SAMPLE1" ]]; then
    echo "geth process not accessible"
    exit 1
  fi
  read -r PROC1 TOTAL1 RSS1 MEMTOTAL1 NCPU1 <<<"$SAMPLE1"

  sleep "$INTERVAL"

  SAMPLE2="$(read_sample "$PID" || true)"
  if [[ -z "$SAMPLE2" ]]; then
    echo "geth process exited or is unavailable"
    exit 1
  fi
  read -r PROC2 TOTAL2 RSS2 MEMTOTAL2 NCPU2 <<<"$SAMPLE2"

  DPROC=$((PROC2 - PROC1))
  DTOTAL=$((TOTAL2 - TOTAL1))

  CPU_PCT="$(awk -v dp="$DPROC" -v dt="$DTOTAL" -v ncpu="$NCPU2" '
    BEGIN {
      if (dt <= 0) { printf "0.00"; exit }
      printf "%.2f", (dp / dt) * 100 * ncpu
    }
  ')"

  RSS_MIB="$(awk -v rss="$RSS2" 'BEGIN { printf "%.2f", rss / 1024 }')"
  MEM_PCT="$(awk -v rss="$RSS2" -v mt="$MEMTOTAL2" '
    BEGIN {
      if (mt <= 0) { printf "0.00"; exit }
      printf "%.2f", (rss / mt) * 100
    }
  ')"

  printf "%-20s %-8s %-12s %-12s %-12s\n" \
    "$(date '+%Y-%m-%d %H:%M:%S')" "$PID" "$CPU_PCT" "$RSS_MIB" "$MEM_PCT"
done