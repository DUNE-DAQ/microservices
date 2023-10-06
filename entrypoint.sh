#!/bin/bash


cd $(dirname $0)
source ./entrypoint_functions.sh

ensure_required_variables "MICROSERVICE"

microservice_dir=$(dirname $0)/$MICROSERVICE

if [[ ! -e ${microservice_dir}/entrypoint.sh ]]; then
    echo "This script sees the MICROSERVICE environment variable set to \"$MICROSERVICE\" but is unable to find the corresponding entrypoint script \"${microservice_dir}/entrypoint.sh\"" >&2
    exit 2
fi

cd $microservice_dir

./entrypoint.sh

retval=$?
echo "Return value of call to ${microservice_dir}/entrypoint.sh is $retval"

exit $retval
