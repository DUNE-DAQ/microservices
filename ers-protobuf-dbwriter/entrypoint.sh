#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")" || exit 2
if [[ ! -f ../entrypoint_functions.sh ]]; then
    echo "Error: entrypoint_functions.sh not found" >&2
    exit 2
fi
source ../entrypoint_functions.sh

ensure_required_variables "ERS_DBWRITER_KAFKA_BOOTSTRAP_SERVER ERS_DBWRITER_KAFKA_TIMEOUT_MS ERS_DBWRITER_KAFKA_GROUP ERS_DBWRITER_DB_URI ERS_DBWRITER_DB_TABLENAME"

exec python3 ./dbwriter.py --subscriber-bootstrap "${ERS_DBWRITER_KAFKA_BOOTSTRAP_SERVER}" \
                      --subscriber-group "${ERS_DBWRITER_KAFKA_GROUP}" \
                      --subscriber-timeout "${ERS_DBWRITER_KAFKA_TIMEOUT_MS}" \
                      --db-uri "${ERS_DBWRITER_DB_URI}" \
                      --db-table "${ERS_DBWRITER_DB_TABLENAME}" \
                      --debug False
