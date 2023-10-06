#!/bin/bash

cd $(dirname $0)
source ../entrypoint_functions.sh

ensure_required_variables ""

python3 ./kafka-to-influx.py
