#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")" || exit 2
if [[ ! -f ../entrypoint_functions.sh ]]; then
    echo "Error: entrypoint_functions.sh not found" >&2
    exit 2
fi
source ../entrypoint_functions.sh

ensure_required_variables "DATABASE_URI APP_DATA"

exec gunicorn -b 0.0.0.0:5005 --timeout 9000 --log-level=debug rest:app
