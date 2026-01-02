#!/bin/bash

cd $(dirname $0)
source ../entrypoint_functions.sh

ensure_required_variables "USERNAME PASSWORD HARDWARE"

python3 ./logbook.py
