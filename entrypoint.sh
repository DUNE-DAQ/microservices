#!/bin/bash

if [[ ! -e ./entrypoint_functions.sh ]]; then
    echo "This script should be run from the top of the microservices repo" >&2
    exit 2
fi
source ./entrypoint_functions.sh

ensure_required_variables "MICROSERVICE"

# Validate MICROSERVICE is a safe directory name
if [[ ! "${MICROSERVICE}" =~ ^[a-zA-Z0-9_-]+$ ]]; then
    echo "ERROR: MICROSERVICE must contain only alphanumeric characters, hyphens, and underscores" >&2
    exit 2
fi

microservice_dir="$(pwd)/${MICROSERVICE}"

# Verify entrypoint.sh exists in target service
if [[ ! -e "${microservice_dir}/entrypoint.sh" ]]; then
    echo "This script sees the MICROSERVICE environment variable set to \"${MICROSERVICE}\" but is unable to find the corresponding entrypoint script \"${microservice_dir}/entrypoint.sh\"" >&2
    exit 2
fi

# Verify entrypoint.sh is executable
if [[ ! -x "${microservice_dir}/entrypoint.sh" ]]; then
    echo "${microservice_dir}/entrypoint.sh is not executable" >&2
    exit 2
fi

cd "${microservice_dir}" || exit 2

"$(pwd)/entrypoint.sh"

retval=$?
echo "Return value of call to ${microservice_dir}/entrypoint.sh is:${retval}"

exit $retval
