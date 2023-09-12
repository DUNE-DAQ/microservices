#!/bin/bash

mkdir -p ./logfiles
cp ./cern-get-sso-cookie /usr/local/bin

python3 ./logbook.py

