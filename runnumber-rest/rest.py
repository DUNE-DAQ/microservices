#!/usr/bin/env python3

import flask
from flask import Flask

from flask_restful import Api, Resource
from flask_httpauth import HTTPBasicAuth


"""
Main app

To control set the following environment variables:
DATABASE_URI - URI for sqlalchemy to use
DEBUG - set to TRUE for flask debugging
RUN_START - set to your starting run number, does not need to be changed after first launching as run number will be iterated from this initial value
"""
import os

from api import app, db
with app.app_context():
    db.create_all()


if __name__ == '__main__':
    # As a testserver.
    # app.run(host='0.0.0.0', port=5000, debug=True)

    # Normally spawned by gunicorn
    app.run(host= '0.0.0.0', port=5000, debug=False)
