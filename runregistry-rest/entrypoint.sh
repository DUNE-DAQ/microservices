#!/bin/bash

sed -i "s/dburi\='Secret from Kubernetes\!'/dburi\='${RGURI}'/g" /credentials.py
sed -i "s/user\='Secret from Kubernetes\!'/user\='${RGUSER}'/g" /credentials.py
sed -i "s/password\='Secret from Kubernetes\!'/password\='${RGPASS}'/g" /credentials.py

exec gunicorn -b 0.0.0.0:5005 --workers=1 --worker-class=gevent --timeout 5000000000 --log-level=debug rest:app
