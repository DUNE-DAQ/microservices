#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")" || exit 2
if [[ ! -f ../entrypoint_functions.sh ]]; then
    echo "Error: entrypoint_functions.sh not found" >&2
    exit 2
fi
source ../entrypoint_functions.sh

ensure_required_variables "OPMON_DBWRITER_KAFKA_BOOTSTRAP_SERVER OPMON_DBWRITER_KAFKA_GROUP OPMON_DBWRITER_SUBSCRIBER_TIMEOUT_MS OPMON_DBWRITER_TOPIC DATABASE_URI OPMON_DBWRITER_BATCH_SIZE_MS"

exec python3 ./dbwriter.py --subscriber-bootstrap "${OPMON_DBWRITER_KAFKA_BOOTSTRAP_SERVER}" \
    --subscriber-group "${OPMON_DBWRITER_KAFKA_GROUP}" \
    --subscriber-timeout "${OPMON_DBWRITER_SUBSCRIBER_TIMEOUT_MS}" \
    --subscriber-topic "${OPMON_DBWRITER_TOPIC}" \
    --influxdb-uri "${DATABASE_URI}" \
    --influxdb-timeout "${OPMON_DBWRITER_BATCH_SIZE_MS}" \
    --influxdb-create True \
    --health-port "${HEALTH_PORT:-}" \
    --debug False
