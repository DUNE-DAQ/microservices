#!/bin/bash
set -euo pipefail

if [[ ! -e ./entrypoint_functions.sh ]]; then
    echo "This script should be run from the top of the microservices repo" >&2
    exit 2
fi
source ./entrypoint_functions.sh

ensure_required_variables "MICROSERVICE"

microservice_dir="$(pwd)/${MICROSERVICE}"

if [[ ! -e ${microservice_dir}/entrypoint.sh ]]; then
    echo "This script sees the MICROSERVICE environment variable set to \"${MICROSERVICE}\" but is unable to find the corresponding entrypoint script \"${microservice_dir}/entrypoint.sh\"" >&2
    exit 2
fi

cd "${microservice_dir}" || exit 2

exec "${microservice_dir}/entrypoint.sh"
