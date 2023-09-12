#!/bin/bash

mkdir -p ./logfiles
cp ./cern-get-sso-cookie /usr/local/bin

if [[ ! -d ./elisa_client_api ]]; then
  git clone https://github.com/DUNE-DAQ/elisa_client_api.git
fi

pip3 install --upgrade setuptools
pip3 install ./elisa_client_api 

python3 ./logbook.py

