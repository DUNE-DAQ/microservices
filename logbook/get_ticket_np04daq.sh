#!/bin/bash
export KRB5CCNAME=/tmp/krb
kinit -k -t /kerb/np04daq.keytab np04daq@CERN.CH
