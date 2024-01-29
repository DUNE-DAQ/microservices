#!/usr/bin/env python3
__title__ = "NP04 run number"
__author__ = "Roland Sipos"
__credits__ = [""]
__version__ = "0.0.1"
__maintainers__ = ["Roland Sipos", "Pierre Lasorak", "Tiago Alves", "Pat Riehecky"]
__emails__ = ["roland.sipos@cern.ch", "plasorak@cern.ch", "tiago.alves20@imperial.ac.uk", "riehecky@fnal.gov"]


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

# setenv DEBUG=True to enable debug mode
DEBUG = os.getenv("DEBUG", "False").lower() == "true"

with app.app_context():
    db.create_all()

@app.route('/')
def index():
    root_text =f'''
    <!DOCTYPE html>
    <html>
    <body>
    <h1>{__title__}</h1>
    
    <ul>
        <li>author: {__author__}</li>
        <li>credits: {__credits__}</li>
        <li>version: {__version__}</li>
        <li>maintainers: {__maintainers__}</li>
        <li>emails: {__emails__}</li>
    </ul>
    
    <h2>Endpoints</h2>
    <div style="border: 1px solid black">
    <h3>GET /runnumber/get</h3>
    <p>Gets the current or last run number.</p>
    <p>Example:</p>
    <p style="font-family:courier;">$ curl -u user:password -X GET http://host:port/runnumber/get</p>
    </div>
    <p></p>
    
    <div style="border: 1px solid black">
    <h3>GET /runnumber/getnew</h3>
    <p>Get a new unique run number.</p>
    <p>Example:</p>
    <p style="font-family:courier;">$ curl -u user:password -X GET http://host:port/runnumber/getnew</p>
    </div>
    <p></p>
    
    <div style="border: 1px solid black">
    <h3>GET /runnumber/updatestop/<run_num></h3>
    <p>Update the stop time of the specified run number (replace <run_num> with the run number you want).</p>
    <p>Example:</p>
    <p style="font-family:courier;">$ curl -u user:password -X GET http://host:port//runnumber/updatestop/2</p>
    </div>
    <p></p>
    
    </body>
    </html>
    '''
    return root_text


if __name__ == '__main__':
    # As a testserver.
    # app.run(host='0.0.0.0', port=5000, debug=True)

    # Normally spawned by gunicorn
    app.run(host= '0.0.0.0', port=5000, debug=False)
