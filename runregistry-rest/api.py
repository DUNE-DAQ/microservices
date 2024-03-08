"""
Variables for Webpage
"""

__title__ = "NP04 run registry"
__author__ = "Roland Sipos"
__credits__ = [""]
__version__ = "0.0.8"
__maintainers__ = ["Roland Sipos", "Pierre Lasorak", "Tiago Alves"]
__emails__ = [
    "roland.sipos@cern.ch",
    "plasorak@cern.ch",
    "tiago.alves20@imperial.ac.uk",
]

import io
import os

import flask
from flask_caching import Cache
from flask_restful import Api, Resource
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import desc, func

__all__ = ["app", "api", "db"]

app = flask.Flask(__name__)

app.config.update(
    MAX_CONTENT_LENGTH=32 * 1000 * 1000,
    UPLOAD_EXTENSIONS={".gz", ".tgz"},
    UPLOAD_PATH="",
    CACHE_TYPE="simple",
    SQLALCHEMY_DATABASE_URI=os.environ.get(
        "DATABASE_URI", "sqlite:////tmp/test.sqlite"
    ),
    DEPLOYMENT_ENV=os.environ.get("DEPLOYMENT_ENV", "DEV"),
    RUN_START=int(os.getenv("RUN_START", "1000")),
    SQLALCHEMY_ECHO=False,
)

cache = Cache(app)
db = SQLAlchemy(app)
api = Api(app)

import datetime
import urllib
from urllib.parse import urlparse

from authentication import auth
from database import RunRegistryConfig, RunRegistryMeta

PARSED_URI = urlparse(app.config["SQLALCHEMY_DATABASE_URI"])
DB_TYPE = PARSED_URI.scheme


def cache_key():
    args = flask.request.args
    key = (
        flask.request.path
        + "?"
        + urllib.urlencode(
            [(k, v) for k in sorted(args) for v in sorted(args.getlist(k))]
        )
    )
    return key


# $ curl -u fooUsr:barPass -X GET np04-srv-021:30015/runregistry/getRunMeta/2
@api.resource("/runregistry/getRunMeta/<int:runNum>")
class getRunMeta(Resource):
    """
    returns the meta data for the specified runumber
    should return the RunMeta in format: [["RUN_NUMBER", "START_TIME", "STOP_TIME", "DETECTOR_ID", "RUN_TYPE", "SOFTWARE_VERSION"],[[1000, "Thu, 14 Dec 2023 15:12:03 GMT", "Thu, 14 Dec 2023 15:12:32 GMT", 1, "Don't know what goes here", "config.json", dunedaq-v4.2.0]]]
    """

    @auth.login_required
    def get(self, runNum):
        rowRes = []
        try:
            result = (
                db.session.query(
                    RunRegistryMeta.run_number,
                    RunRegistryMeta.start_time,
                    RunRegistryMeta.stop_time,
                    RunRegistryMeta.detector_id,
                    RunRegistryMeta.run_type,
                    RunRegistryMeta.filename,
                    RunRegistryMeta.software_version,
                )
                .filter(RunRegistryMeta.run_number == runNum)
                .one()
            )
            print(f"getRunMeta: result {result}")
            return flask.make_response(flask.jsonify([result.keys()], [[result]]))
        except Exception as err_obj:
            print(f"Exception:{err_obj}")
            return flask.make_response(flask.jsonify({"Exception": f"{err_obj}"}))


# $ curl -u fooUsr:barPass -X GET np04-srv-021:30015/runregistry/getRunMetaLast/100
@api.resource("/runregistry/getRunMetaLast/<int:amount>")
class getRunMetaLast(Resource):
    """
    returns the meta data for the number of runs specific to the number chosen in the curl
    should return the RunMeta in format: [[1000, "Thu, 14 Dec 2023 15:12:03 GMT", "Thu, 14 Dec 2023 15:12:32 GMT", 1, "Don't know what goes here", "config.json", dunedaq-v4.2.0],[1001, "Thu, 14 Dec 2023 15:12:03 GMT", "Thu, 14 Dec 2023 15:12:32 GMT", 5, "Don't know what goes here", "config2.json", dunedaq-v4.2.0]]
    """

    @auth.login_required
    def get(self, amount):
        try:
            result = (
                db.session.query(
                        RunRegistryMeta.run_number,
                        RunRegistryMeta.start_time,
                        RunRegistryMeta.stop_time,
                        RunRegistryMeta.detector_id,
                        RunRegistryMeta.run_type,
                        RunRegistryMeta.filename,
                        RunRegistryMeta.software_version,
                )
                .order_by(desc(RunRegistryMeta.run_number))
                .limit(amount)
                .all()
            )
            print(f"getRunMetaLast: result {result}")
            column_names = RunRegistryMeta.__table__.columns.keys()
            return flask.make_response(flask.jsonify([column_names], [[result]]))
        except Exception as err_obj:
            resp = flask.make_response(flask.jsonify({"Exception": f"{err_obj}"}))


# $ curl -u fooUsr:barPass -X GET -O -J np04-srv-021:30015/runregistry/getRunBlob/2
@api.resource("/runregistry/getRunBlob/<int:runNum>")
class getRunBlob(Resource):
    """
    returns the nanorc configuration of the run number specified
    should return the configuration in a json format
    """

    @auth.login_required
    @cache.cached(timeout=0, key_prefix=cache_key, query_string=True)
    def get(self, runNum):
        print(f"getRunBlob: arg {runNum}")
        try:
            blob = (
                db.session.query(RunRegistryConfig.configuration)
                .filter(RunRegistryConfig.run_number == runNum)
                .scalar()
            )
            filename = (
                db.session.query(RunRegistryMeta.filename)
                .filter(RunRegistryMeta.run_number == runNum)
                .scalar()
            )
            print("returning " + filename)
            resp.headers["Content-Type"] = "application/octet-stream"
            resp.headers["Content-Disposition"] = f"attachment; filename={filename}"
            resp = (
                flask.make_response(bytes(blob))
                ### FIXME
                if DB_TYPE == "postgresql"
                else flask.make_response(blob.read())
            )
            return resp
        except Exception as err_obj:
            print(f"Exception:{err_obj}")
            return flask.make_response(flask.jsonify({"Exception": f"{err_obj}"}))

# $ curl -u fooUsr:barPass -F "run_number=1000" -F "det_id=foo" -F "run_type=bar" -F "software_version=dunedaq-vX.Y.Z" -F "file=@sspconf.tar.gz" -X POST np04-srv-021:30015/runregistry/insertRun/
@api.resource("/runregistry/insertRun/")
class insertRun(Resource):
    """
    adds a run with the specified data given in the curl command
    should return the inserted meta data in the format: [[[1000, "foo", "bar", "dunedaq-vX.Y.Z", "@sspconf.tar.gz"]]]
    """

    @auth.login_required
    def post(self):
        rowRes = []
        filename = ""
        local_file_name = None
        try:
            # Ensure form fields
            run_number = flask.request.form.get("run_number")
            det_id = flask.request.form.get("det_id")
            run_type = flask.request.form.get("run_type")
            software_version = flask.request.form.get("software_version")
            uploaded_file = flask.request.files.get("file")
            if not all([run_number, det_id, run_type, software_version, uploaded_file]):
                return flask.make_response("Missing required form fields", 400)

            filename = uploaded_file.filename
            if (
                not filename
                or os.path.splitext(filename)[1] not in app.config["UPLOAD_EXTENSIONS"]
            ):
                return flask.make_response("Invalid file or extension", 400)

            local_file_name = os.path.join(app.config["UPLOAD_PATH"], filename)
            if os.path.isfile(local_file_name):
                return flask.make_response(
                    "File with the same name is already being processed. Try again later.",
                    400,
                )

            uploaded_file.save(local_file_name)

            with open(local_file_name, "rb") as file_in:
                data = io.BytesIO(file_in.read())

            with db.session.begin():
                run_meta = RunRegistryMeta(
                    run_number=run_number,
                    detector_id=det_id,
                    run_type=run_type,
                    filename=filename,
                    software_version=software_version,
                )
                run_config = RunRegistryConfig(
                    run_number=run_number, configuration=data.getvalue()
                )

                db.session.add(run_meta)
                db.session.add(run_config)

            resp_data = [run_number, det_id, run_type, software_version, filename]
            return flask.make_response(flask.jsonify([[[resp_data]]]))
        except Exception as err_obj:
            print(f"Exception:{err_obj}")
            return flask.make_response(str(err_obj), 400)
        finally:
            if local_file_name and os.path.exists(local_file_name):
                os.remove(local_file_name)


# $ curl -u fooUsr:barPass -X GET np04-srv-021:30015/runregistry/updatestop/<int:runNum>
@api.resource("/runregistry/updatestop/<int:runNum>")
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
                run = db.session.query(RunRegistryMeta).filter_by(run_number=runNum).one()
                run.stop_time = datetime.now()
            print(f"updateStopTimestamp: result {[run.start_time, run.stop_time]}")
            return flask.make_response(flask.jsonify([[[run.start_time, run.stop_time]]]))
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
    <h3>GET /runregistry/getRunMeta/<run_num></h3>
    <p>Gets the run metadata for the specified run number (replace <run_num> with the run number you want).</p>
    <p>Example:</p>
    <p style="font-family:courier;">$ curl -u user:password -X GET http://host:port/runregistry/getRunMeta/2</p>
    </div>
    <p></p>

    <div style="border: 1px solid black">
    <h3>GET /runregistry/getRunMetaLast/<how_many_runs></h3>
    <p>Get the run metadata for the last runs (replace <how_many_runs> by the number of runs you want to go in the past).</p>
    <p>Example:</p>
    <p style="font-family:courier;">$ curl -u user:password -X GET http://host:port/runregistry/getRunMetaLast/100</p>
    </div>
    <p></p>

    <div style="border: 1px solid black">
    <h3>GET /runregistry/getRunBlob/<run_num></h3>
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

    <div style="border: 1px solid black">
    <h3>GET /runregistry/updateStopTime/<run_num></h3>
    <p>Update the stop time of the specified run number (replace <run_num> with the run number you want).</p>
    <p>Example:</p>
    <p style="font-family:courier;">$ curl -u user:password -X GET http://host:port/runregistry/updateStopTime/2</p>
    </div>
    <p></p>

    </body>
    </html>
    """

    return root_text
