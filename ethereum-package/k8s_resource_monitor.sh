#!/bin/bash

LOG_FILE="./k8s_resource_alert.log"
INTERVAL=10   # seconds

echo "Starting Kubernetes resource monitor..." | tee -a "$LOG_FILE"

while true; do
    TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

    echo "===============================" >> "$LOG_FILE"
    echo "Timestamp: $TIMESTAMP" >> "$LOG_FILE"

    ############################
    # NODE CHECK
    ############################
    kubectl top nodes --no-headers | while read -r node cpu mem cpu_pct mem_pct; do
        
        # remove m / Mi / % signs
        CPU_VAL=$(echo "$cpu_pct" | tr -d '%')
        MEM_VAL=$(echo "$mem_pct" | tr -d '%')

        if [[ "$CPU_VAL" =~ ^[0-9]+$ ]] && [[ "$CPU_VAL" -ge 90 ]]; then
            echo "[ALERT] NODE HIGH CPU: $node CPU=$cpu_pct MEM=$mem_pct at $TIMESTAMP" >> "$LOG_FILE"
        fi

        if [[ "$MEM_VAL" =~ ^[0-9]+$ ]] && [[ "$MEM_VAL" -ge 90 ]]; then
            echo "[ALERT] NODE HIGH MEMORY: $node CPU=$cpu_pct MEM=$mem_pct at $TIMESTAMP" >> "$LOG_FILE"
        fi
    done

    ############################
    # POD CHECK
    ############################
    kubectl top pods -A --no-headers | while read -r ns pod cpu mem; do
        
        # convert CPU (m) → number
        CPU_NUM=$(echo "$cpu" | tr -d 'm')

        # convert memory (Mi)
        MEM_NUM=$(echo "$mem" | tr -d 'Mi')

        # simple threshold logic (adjust as needed)
        # NOTE: pod % not directly available, so we approximate using raw values

        if [[ "$CPU_NUM" =~ ^[0-9]+$ ]] && [[ "$CPU_NUM" -ge 900 ]]; then
            echo "[ALERT] POD HIGH CPU: $ns/$pod CPU=${cpu} MEM=${mem} at $TIMESTAMP" >> "$LOG_FILE"
        fi

        if [[ "$MEM_NUM" =~ ^[0-9]+$ ]] && [[ "$MEM_NUM" -ge 900 ]]; then
            echo "[ALERT] POD HIGH MEMORY: $ns/$pod CPU=${cpu} MEM=${mem} at $TIMESTAMP" >> "$LOG_FILE"
        fi

    done

    sleep $INTERVAL
done
