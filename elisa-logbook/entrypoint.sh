#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")" || exit 2
if [[ ! -f ../entrypoint_functions.sh ]]; then
    echo "Error: entrypoint_functions.sh not found" >&2
    exit 2
fi
source ../entrypoint_functions.sh

ensure_required_variables "USERNAME PASSWORD HARDWARE"

exec gunicorn -b 0.0.0.0:5005 --workers=1 --worker-class=gevent --timeout 9000 --log-level=debug logbook:app
