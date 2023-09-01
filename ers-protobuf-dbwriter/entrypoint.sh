#!/bin/bash

source $DAQ_RTE

pip3 install -r requirements.txt

python /dbwriter.py 
