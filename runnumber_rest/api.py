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

PARSED_URI = urlparse(uri)
db_type = PARSED_URI.scheme
print(db_type)

from runregistry_rest.authentication import auth
from runregistry_rest.database import RunNumber

# $ curl -u fooUsr:barPass -X GET np04-srv-021:30016//runnumber/get
@api.resource("/runnumber/get") ## Keep this for now 
class getRunNumber(Resource):
    """
    returns the run number of the previous run
    if no previous run number, returns in format: Null
    otherwise returns the last run number in format: [[[1000]]]

    """

    @auth.login_required
    def get(self):
        rowRes = []
        try:
            rowRes.append(
                db.session.execute(db.select(func.max(RunNumber.rn))).scalar_one()
            )
        except Exception as err_obj:
            print(f"Exception:{err_obj}")
            resp = flask.make_response(flask.jsonify({"Exception": f"{err_obj}"}))
            return resp
        print(f"getRunNumber: result {rowRes}")
        resp = flask.make_response(flask.jsonify([[rowRes]]))
        return resp


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
            current_max_run = db.session.execute(
                db.select(func.max(RunNumber.rn))
            ).scalar()
            if current_max_run is None:
                current_max_run = current_max_run = int(os.getenv("RUN_START", "1000"))
            else:
                current_max_run += 1
            run = RunNumber(rn=current_max_run)
            db.session.add(run)
            db.session.commit()
            rowRes.append(current_max_run)
        except Exception as err_obj:
            print(f"Exception:{err_obj}")
            resp = flask.make_response(flask.jsonify({"Exception": f"{err_obj}"}))
            return resp
        print(f"getNewtRunNumber: result {rowRes}")
        resp = flask.make_response(flask.jsonify([[rowRes]]))
        return resp


# $ curl -u fooUsr:barPass -X GET np04-srv-021:30016/runnumber/updatestop/<int:runNum>
@api.resource("/runnumber/updatestop/<int:runNum>")
class updateStopTimestamp(Resource):
    """
    set and record the stop time for the run into the database
    should return the start and stop times in format: ["Thu, 14 Dec 2023 15:12:03 GMT","Thu, 14 Dec 2023 15:12:32 GMT"]
    """

    @auth.login_required
    def get(self, runNum):
        rowRes = []
        print(f"updateStopTimestamp: arg {runNum}")
        try:
            run = db.session.execute(
                db.select(RunNumber).filter_by(rn=runNum)
            ).scalar_one()
            run.stop_time = datetime.now()
            db.session.commit()
            rowRes.extend((run.start_time, run.stop_time))
        except Exception as err_obj:
            print(f"Exception:{err_obj}")
            resp = flask.make_response(flask.jsonify({"Exception": f"{err_obj}"}))
            return resp
        print(f"updateStopTimestamp: result {rowRes}")
        resp = flask.make_response(flask.jsonify([[rowRes]]))
        return resp


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
    <h3>GET <a href="/runregistry/get">/runregistry/get</a></h3>
    <p>Gets the current or last run number.</p>
    <p>Example:</p>
    <p style="font-family:courier;">$ curl -u user:password -X GET http://host:port/runregistry/get</p>
    </div>
    <p></p>

    <div style="border: 1px solid black">
    <h3>GET <a href="/runregistry/getnew">/runregistry/getnew</a></h3>
    <p>Get a new unique run number.</p>
    <p>Example:</p>
    <p style="font-family:courier;">$ curl -u user:password -X GET http://host:port/runregistry/getnew</p>
    </div>
    <p></p>

    <div style="border: 1px solid black">
    <h3>GET <a href="/runregistry/updatestop/">/runregistry/updatestop/</a>&lt;run_num&gt;</h3>
    <p>Update the stop time of the specified run number (replace &lt;run_num&gt; with the run number you want).</p>
    <p>Example:</p>
    <p style="font-family:courier;">$ curl -u user:password -X GET http://host:port//runregistry/updatestop/2</p>
    </div>
    <p></p>

    <div style="border: 1px solid black">
    <h3>GET <a href="/runregistry/getRunMeta/">/runregistry/getRunMeta/</a>&lt;run_num&gt;</h3>
    <p>Gets the run metadata for the specified run number (replace &lt;run_num&gt; with the run number you want).</p>
    <p>Example:</p>
    <p style="font-family:courier;">$ curl -u user:password -X GET http://host:port/runregistry/getRunMeta/2</p>
    </div>
    <p></p>

    <div style="border: 1px solid black">
    <h3>GET <a href="/runregistry/getRunMetaLast/">/runregistry/getRunMetaLast/</a>&lt;how_many_runs&gt;</h3>
    <p>Get the run metadata for the last runs (replace &lt;how_many_runs&gt; by the number of runs you want to go in the past).</p>
    <p>Example:</p>
    <p style="font-family:courier;">$ curl -u user:password -X GET http://host:port/runregistry/getRunMetaLast/100</p>
    </div>
    <p></p>

    <div style="border: 1px solid black">
    <h3>GET <a href="/runregistry/getRunBlob/">/runregistry/getRunBlob</a>/&lt;run_num&gt;</h3>
    <p>Get the run configuration blob (tar.gz of some folders structure containing json) for the specified run number (replace <run_num> by the run number you want).</p>
    <p>Example:</p>
    <p style="font-family:courier;">$ curl -u user:password -X GET -O -J http://host:port/runregistry/getRunBlob/2</p>
    </div>
    <p></p>

    <div style="border: 1px solid black">
    <h3>POST /runregistry/insertRun/</h3>
    <p>Insert a new run in the database. The post request should have the fields:</p>
    <ul>
        <li> "file": a file containing the configuration to save
        <li> "run_num": the run number
        <li> "det_id": the id of the detector
        <li> "run_type": the type of run (either PROD of TEST)
        <li> 'software_version": the version of dunedaq.
    </ul>
    <p>Example:</p>
    <p style="font-family:courier;">$ curl -u user:password -F "file=@sspconf.tar.gz" -F "run_num=4" -F "det_id=foo" -F "run_type=bar" -F "software_version=dunedaq-vX.Y.Z" -X POST http://host:port/runregistry/insertRun/</p>
    </div>
    <p></p>

    </body>
    </html>
    """

    return root_text
