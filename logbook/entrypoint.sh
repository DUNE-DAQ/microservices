#!/bin/bash

cd $(dirname $0)
source ../entrypoint_functions.sh

ensure_required_variables "USERNAME PASSWORD HARDWARE"

mkdir -p ./logfiles
cp ./cern-get-sso-cookie /usr/local/bin

python3 ./logbook.py

