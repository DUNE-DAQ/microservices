#!/bin/bash

exec gunicorn -b 0.0.0.0:5000 --workers=1 --worker-class=gthread --threads=2 --timeout 5000000000 --log-level=debug connection-service.connection-flask:app
