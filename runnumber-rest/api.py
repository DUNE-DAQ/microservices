"""
Variables for Webpage
"""

__title__ = "NP04 run number"
__author__ = "Roland Sipos"
__credits__ = [""]
__version__ = "0.0.1"
__maintainers__ = ["Roland Sipos", "Pierre Lasorak", "Tiago Alves"]
__emails__ = [
    "roland.sipos@cern.ch",
    "plasorak@cern.ch",
    "tiago.alves20@imperial.ac.uk",
]

import os
from datetime import datetime

import flask
from flask_restful import Api, Resource
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func

__all__ = ["app", "api", "db"]

app = flask.Flask(__name__)

app.config.update(
    SQLALCHEMY_DATABASE_URI=os.environ.get(
        "DATABASE_URI", "sqlite:////tmp/test.sqlite"
    ),
    DEPLOYMENT_ENV=os.environ.get("DEPLOYMENT_ENV", "DEV"),
    RUN_START=int(os.getenv("RUN_START", "1000")),
    SQLALCHEMY_ECHO=False,
)

uri = app.config["SQLALCHEMY_DATABASE_URI"]
db = SQLAlchemy(app)
api = Api(app)

from urllib.parse import urlparse

from authentication import auth
from database import RunNumber

PARSED_URI = urlparse(app.config["SQLALCHEMY_DATABASE_URI"])
DB_TYPE = PARSED_URI.scheme


# $ curl -u fooUsr:barPass -X GET np04-srv-021:30016//runnumber/get
@api.resource("/runnumber/get")
class getRunNumber(Resource):
    """
    returns the run number of the previous run
    if no previous run number, returns in format: Null
    otherwise returns the last run number in format: [[[1000]]]

    """

    @auth.login_required
    def get(self):
        print("getNewRunNumber: no args")
        try:
            max_run_number = db.session.query(func.max(RunNumber.rn)).scalar()
            # maybe find consumers to see if we can drop the extra nesting
            print(f"getRunNumber: result {[[[max_run_number]]]}")
            return flask.make_response(flask.jsonify([[max_run_number]]))
        except Exception as err_obj:
            print(f"Exception:{err_obj}")
            return flask.make_response(flask.jsonify({"Exception": f"{err_obj}"}))


# $ curl -u fooUsr:barPass -X GET np04-srv-021:30016//runnumber/getnew
@api.resource("/runnumber/getnew")
class getNewtRunNumber(Resource):
    """
    create a new run in the database with a new run number which is previous run number +1
    if no previous run number, returns: [[[1000]]]
    otherwise return the run number in format: [[[1001]]]
    """

    @auth.login_required
    def get(self):
        rowRes = []
        try:
            # if we start at a higher number
            # the primary key sequence may not match
            current_max_run = None
            with db.session.begin():
                current_max_run = (
                    db.session.query(func.max(RunNumber.rn)).scalar()
                    or app.config["RUN_START"]
                ) + 1
                run = RunNumber(rn=current_max_run)
                db.session.add(run)
            print(f"getNewtRunNumber: result {[current_max_run]}")
            return flask.make_response(flask.jsonify([current_max_run]))
        except Exception as err_obj:
            print(f"Exception:{err_obj}")
            return flask.make_response(flask.jsonify({"Exception": f"{err_obj}"}))


# $ curl -u fooUsr:barPass -X GET np04-srv-021:30016/runnumber/updatestop/<int:runNum>
@api.resource("/runnumber/updatestop/<int:runNum>")
class updateStopTimestamp(Resource):
    """
    set and record the stop time for the run into the database
    should return the start and stop times in format: [[["Thu, 14 Dec 2023 15:12:03 GMT","Thu, 14 Dec 2023 15:12:32 GMT"]]]
    """

    @auth.login_required
    def get(self, runNum):
        print(f"updateStopTimestamp: arg {runNum}")
        try:
            run = None
            with db.session.begin():
                run = db.session.query(RunNumber).filter_by(rn=runNum).one()
                run.stop_time = datetime.now()
            print(f"updateStopTimestamp: result {[run.start_time, run.stop_time]}")
            return flask.make_response(flask.jsonify([[run.start_time, run.stop_time]]))
        except Exception as err_obj:
            print(f"Exception:{err_obj}")
            return flask.make_response(flask.jsonify({"Exception": f"{err_obj}"}))


@app.route("/")
def index():
    root_text = f"""
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
    """
    return root_text
