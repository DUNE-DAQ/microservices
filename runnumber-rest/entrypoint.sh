#!/bin/bash

sed -i "s/dbhost\='Secret from Kubernetes\!'/dbhost\='${RNURI}'/g" /credentials.py
sed -i "s/username\='Secret from Kubernetes\!'/username\='${RNUSER}'/g" /credentials.py
sed -i "s/password\='Secret from Kubernetes\!'/password\='${RNPASS}'/g" /credentials.py
sed -i "s/port\='Secret from Kubernetes\!'/port\='${RNPORT}'/g" /credentials.py
sed -i "s/database\='Secret from Kubernetes\!'/database\='${RNDBNAME}'/g" /credentials.py


exec gunicorn -b 0.0.0.0:5000 --workers=1 --worker-class=gevent --timeout 5000000000 --log-level=debug rest:app
