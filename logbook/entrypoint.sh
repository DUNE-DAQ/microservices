#!/bin/bash

mkdir -p ./logfiles
cp ./cern-get-sso-cookie /usr/local/bin

git clone https://github.com/DUNE-DAQ/elisa_client_api

python3 ./logbook.py
