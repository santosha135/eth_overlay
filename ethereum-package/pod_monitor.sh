#!/bin/bash

LOG_FILE="./pod_termination.log"
NAMESPACE="--all-namespaces"

echo "Starting pod monitor... Logging to $LOG_FILE"

# keep last seen pod status in memory
declare -A POD_STATUS

while true; do
    kubectl get pods $NAMESPACE --no-headers 2>/dev/null | while read line; do

        NS=$(echo "$line" | awk '{print $1}')
        POD=$(echo "$line" | awk '{print $2}')
        READY=$(echo "$line" | awk '{print $3}')
        STATUS=$(echo "$line" | awk '{print $4}')

        KEY="$NS/$POD"

        # detect termination states
        if [[ "$STATUS" == "Failed"  || "$STATUS" == "Succeeded" || "$STATUS" == "Unknown" ]]; then

            REASON=$(kubectl get pod -n "$NS" "$POD" -o jsonpath='{.status.reason}' 2>/dev/null)

            if [[ -z "$REASON" ]]; then
                REASON=$(kubectl describe pod -n "$NS" "$POD" | grep -i "Reason:" | head -1 | awk -F":" '{print $2}')
            fi

            TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

            echo "$TIMESTAMP | $NS | $POD | STATUS=$STATUS | REASON=$REASON" >> "$LOG_FILE"
        fi

    done

    sleep 5
done
