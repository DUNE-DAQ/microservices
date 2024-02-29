import io
import os
import urllib
from datetime import datetime
from urllib.parse import urlparse

import flask
from flask_caching import Cache
from flask_restful import Api, Resource
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import desc, func

from authentication import auth

__all__ = ["app", "api", "db", "cache"]

app = flask.Flask(__name__)

app.config.update(
    MAX_CONTENT_LENGTH=32 * 1000 * 1000,
    UPLOAD_EXTENSIONS={".gz", ".tgz"},
    UPLOAD_PATH="uploads",
    CACHE_TYPE="simple",
    SQLALCHEMY_DATABASE_URI=os.environ.get(
        "DATABASE_URI", "sqlite:////tmp/test.sqlite"
    ),
    DEPLOYMENT_ENV=os.environ.get("DEPLOYMENT_ENV", "DEV"),
    RUN_START=int(os.getenv("RUN_START", "1000")),
    SQLALCHEMY_ECHO=False,
)

uri = app.config["SQLALCHEMY_DATABASE_URI"]
cache = Cache(app)
db = SQLAlchemy(app)
api = Api(app)

from database import RunNumber, RunRegistryConfig, RunRegistryMeta

PARSED_URI = urlparse(uri)
print(f" * Detected database connection type->{PARSED_URI.scheme}")
print(f" * Detected hostname for database->{PARSED_URI.hostname}")
print(f" * Detected path for database->{PARSED_URI.path}")

DB_TYPE = PARSED_URI.scheme  ### IS THIS NEEDED?

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


# $ curl -u fooUsr:barPass -X GET np04-srv-021:30015//runregistry/get
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
            max_run_number = db.session.query(func.max(RunNumber.run_number)).scalar()
            # maybe find consumers to see if we can drop the extra nesting
            print(f"getRunNumber: result {[[result]]}")
            return flask.make_response(flask.jsonify([[max_run_number]]))
        except Exception as err_obj:
            print(f"Exception:{err_obj}")
            return flask.make_response(flask.jsonify({"Exception": f"{err_obj}"}))


api.add_resource(getRunNumber, *["/runregistry/get", "/runnumber/get"])


# $ curl -u fooUsr:barPass -X GET np04-srv-021:30015//runregistry/getnew
class getNewRunNumber(Resource):
    """
    create a new run in the database with a new run number which is previous run number +1
    if no previous run number, returns: [1000]
    otherwise return the run number in format: [1001]
    """

    @auth.login_required
    def get(self):
        print("getNewRunNumber: no args")
        try:
            # if we start at a higher number
            # the primary key sequence may not match
            current_max_run = (
                db.session.query(func.max(RunNumber.run_number)).scalar()
                or app.config["RUN_START"]
            ) + 1
            run = RunNumber(run_number=current_max_run)
            db.session.add(run)
            db.session.commit()
            print(f"getNewtRunNumber: result {[current_max_run]}")
            return flask.make_response(flask.jsonify([current_max_run]))
        except Exception as err_obj:
            print(f"Exception:{err_obj}")
            return flask.make_response(flask.jsonify({"Exception": f"{err_obj}"}))


api.add_resource(getNewRunNumber, *["/runregistry/getnew", "/runnumber/getnew"])


# $ curl -u fooUsr:barPass -X GET np04-srv-021:30015/runregistry/updatestop/<int:runNum>
class updateStopTimestamp(Resource):
    """
    set and record the stop time for the run into the database
    should return the start and stop times in format: ["Thu, 14 Dec 2023 15:12:03 GMT","Thu, 14 Dec 2023 15:12:32 GMT"]
    """

    @auth.login_required
    def get(self, runNum):
        print(f"updateStopTimestamp: arg {runNum}")
        try:
            run = db.session.query(RunNumber).filter_by(run_number=runNum).one()
            run.stop_time = datetime.now()
            db.session.commit()
            print(f"updateStopTimestamp: result {[run.start_time, run.stop_time]}")
            return flask.make_response(flask.jsonify([run.start_time, run.stop_time]))
        except Exception as err_obj:
            print(f"Exception:{err_obj}")
            return flask.make_response(flask.jsonify({"Exception": f"{err_obj}"}))


api.add_resource(
    updateStopTimestamp,
    *["/runregistry/updatestop/<int:runNum>", "/runnumber/updatestop/<int:runNum>"],
)


# $ curl -u fooUsr:barPass -X GET np04-srv-021:30015/runregistry/getRunMeta/2
@api.resource("/runregistry/getRunMeta/<int:runNum>")
class getRunMeta(Resource):
    """
    returns the meta data for the specified runumber
    should return the RunMeta in format: [1000, "Thu, 14 Dec 2023 15:12:03 GMT", "Thu, 14 Dec 2023 15:12:32 GMT", 1, "Don't know what goes here", "config.json", dunedaq-v4.2.0]
    """

    @auth.login_required
    def get(self, runNum):
        print(f"getRunMeta: arg {runNum}")
        try:
            result = (
                db.session.query(
                    RunNumber.run_number,
                    RunNumber.start_time,
                    RunNumber.stop_time,
                    RunRegistryMeta.detector_id,
                    RunRegistryMeta.run_type,
                    RunRegistryMeta.filename,
                    RunRegistryMeta.software_version,
                )
                .filter(RunNumber.run_number == RunRegistryMeta.run_number)
                .filter(RunNumber.run_number == runNum)
                .one()
            )
            print(f"getRunMeta: result {result}")
            return flask.make_response(flask.jsonify([[result.keys()], [[result]]]))
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
        print(f"getRunMeta: arg {amount}")
        try:
            result = (
                db.session.query(
                    RunNumber.run_number,
                    RunNumber.start_time,
                    RunNumber.stop_time,
                    RunRegistryMeta.detector_id,
                    RunRegistryMeta.run_type,
                    RunRegistryMeta.filename,
                    RunRegistryMeta.software_version,
                )
                .filter(RunNumber.run_number == RunRegistryMeta.run_number)
                .order_by(desc(RunNumber.run_number))
                .limit(amount)
                .scalar()
            )
            print(f"getRunMetaLast: result {result}")
            return flask.make_response(flask.jsonify(result))
        except Exception as err_obj:
            print(f"Exception:{err_obj}")
            return flask.make_response(flask.jsonify({"Exception": f"{err_obj}"}))


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
            run_config = (
                db.session.query(RunRegistryConfig)
                .where(RunRegistryConfig.run_number == runNum)
                .one()
            )
            filename, blob = run_config[0][0], run_config[0][1]
            print("returning " + filename)
            resp = (
                make_response(bytes(blob))
                ### FIXME
                if DB_TYPE == "postgresql"
                else flask.make_response(blob.read())
            )
            resp.headers["Content-Type"] = "application/octet-stream"
            resp.headers["Content-Disposition"] = f"attachment; filename={filename}"
            return resp
        except Exception as err_obj:
            print(f"Exception:{err_obj}")
            return flask.make_response(flask.jsonify({"Exception": f"{err_obj}"}))


# $ curl -u fooUsr:barPass -F "file=@sspconf.tar.gz" -F "run_number=1000" -F "det_id=foo" -F "run_type=bar" -F "software_version=dunedaq-vX.Y.Z" -X POST np04-srv-021:30015/runregistry/insertRun/
@api.resource("/runregistry/insertRun/")
class insertRun(Resource):
    """
    adds a run with the specified data given in the curl command
    should return the inserted meta data in the format: [1000, "foo", "bar", "dunedaq-vX.Y.Z", "@sspconf.tar.gz"]
    """

    @auth.login_required
    def post(self):
        try:
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

            with open(local_file_name, "rb") as fin:
                data = io.BytesIO(fin.read())

            run_config = RunRegistryConfig(
                run_number=run_number, configuration=data.getvalue()
            )
            run_meta = RunRegistryMeta(
                run_number=run_number,
                detector_id=det_id,
                run_type=run_type,
                filename=filename,
                software_version=software_version,
            )

            db.session.add(run_config)
            db.session.add(run_meta)
            db.session.commit()

            resp_data = [run_number, det_id, run_type, software_version, filename]
            return flask.make_response(flask.jsonify(resp_data))
        except Exception as err_obj:
            print(f"Exception:{err_obj}")
            return flask.make_response(str(err_obj), 400)
        finally:
            if local_file_name and os.path.exists(local_file_name):
                os.remove(local_file_name)


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
