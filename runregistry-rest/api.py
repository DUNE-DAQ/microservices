import os, io
import flask
from flask_restful import Api, Resource
from flask_caching import Cache
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import desc, func

__all__ = ["app", "api", "db"]

app = flask.Flask(__name__)

app.config["MAX_CONTENT_LENGTH"] = 32 * 1000 * 1000
app.config["UPLOAD_EXTENSIONS"] = [".gz", ".tgz"]
app.config["UPLOAD_PATH"] = "uploads"
app.config["CACHE_TYPE"] = "simple"
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
    "DATABASE_URI", "sqlite:////tmp/test.sqlite"
)
cache = Cache(app)
db = SQLAlchemy(app)
api = Api(app)

from authentication import auth
from database import RunRegistryMeta, RunRegistryConfig


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


def add_schema_as_element(rowres):
    rowres.insert(0, queries.schema)


# $ curl -u fooUsr:barPass -X GET np04-srv-021:30015/runregistry/getRunMeta/2
@api.resource("/runregistry/getRunMeta/<int:runNum>")
class getRunMeta(Resource):
    """
    returns the meta data for the specified runumber
    should return the RunMeta in format: [1000, "Thu, 14 Dec 2023 15:12:03 GMT", "Thu, 14 Dec 2023 15:12:32 GMT", 1, "Don't know what goes here", "config.json", dunedaq-v4.2.0]
    """

    @auth.login_required
    def get(self, runNum):
        rowRes = []
        try:
            rowRes.append(
                db.session.execute(db.select(func.max(RunRegistryMeta.rn))).scalar_one()
            )
        except Exception as e:
            (err_obj,) = e.args
            print("Exception:", err_obj.message)
            resp = flask.make_response(flask.jsonify({"Exception": err_obj.message}))
            return resp
        # print(rowRes)
        add_schema_as_element(rowRes)
        resp = flask.make_response(flask.jsonify(rowRes))
        return resp


# $ curl -u fooUsr:barPass -X GET np04-srv-021:30015/runregistry/getRunMetaLast/100
@api.resource("/runregistry/getRunMetaLast/<int:amount>")
class getRunMetaLast(Resource):
    """
    returns the meta data for the number of runs specific to the number chosen in the curl
    should return the RunMeta in format: [[1000, "Thu, 14 Dec 2023 15:12:03 GMT", "Thu, 14 Dec 2023 15:12:32 GMT", 1, "Don't know what goes here", "config.json", dunedaq-v4.2.0],[1001, "Thu, 14 Dec 2023 15:12:03 GMT", "Thu, 14 Dec 2023 15:12:32 GMT", 5, "Don't know what goes here", "config2.json", dunedaq-v4.2.0]]
    """

    @auth.login_required
    def get(self, amount):
        rowRes = []
        try:
            rowRes.append(
                db.session.query(RunRegistryMeta.rn)
                .order_by(desc(RunRegistryMeta.rn))
                .limit(amount)
            )
        except Exception as e:
            (err_obj,) = e.args
            print("Exception:", err_obj.message)
            resp = flask.make_response(flask.jsonify({"Exception": err_obj.message}))
            return resp
        # print(rowRes)
        add_schema_as_element(rowRes)
        resp = flask.make_response(flask.jsonify(rowRes))
        return resp


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
        rowRes = []
        try:
            rowRes.append(
                db.session.execute(
                    db.select(
                        RunRegistryMeta.filename, RunRegistryConfig.configuration
                    ).join(
                        RunRegistryConfig, RunRegistryConfig.rn == RunRegistryMeta.rn
                    )
                )
            )
        except Exception as e:
            (err_obj,) = e.args
            print("Exception:", err_obj.message)
            resp = flask.make_response(flask.jsonify({"Exception": err_obj.message}))
            return resp
        filename = rowRes[0][0][0]
        print("returning " + filename)
        blob = rowRes[0][0][1]
        resp = (
            flask.make_response(bytes(blob))
            if postgres
            else flask.make_response(blob.read())
        )
        resp.headers["Content-Type"] = "application/octet-stream"
        resp.headers["Content-Disposition"] = "attachment; filename=%s" % filename
        return resp


# $ curl -u fooUsr:barPass -F "file=@sspconf.tar.gz" -F "rn=1000" -F "det_id=foo" -F "run_type=bar" -F "software_version=dunedaq-vX.Y.Z" -X POST np04-srv-021:30015/runregistry/insertRun/
@api.resource("/runregistry/insertRun/")
class insertRun(Resource):
    """
    adds a run with the specified data given in the curl command
    should return the inserted meta data in the format: [1000, "foo", "bar", "dunedaq-vX.Y.Z", "@sspconf.tar.gz"]
    """

    @auth.login_required
    def post(self):
        filename = ""
        try:
            # Ensure form fields
            rn = flask.request.form["rn"]
            stop_time = None
            det_id = flask.request.form["det_id"]
            run_type = flask.request.form["run_type"]
            software_version = flask.request.form["software_version"]
            uploaded_file = flask.request.files["file"]
            filename = uploaded_file.filename

            # Save uploaded file temporarily
            if filename != "":
                file_ext = os.path.splitext(filename)[1]
                if file_ext not in app.config["UPLOAD_EXTENSIONS"]:
                    error = "Unknown file extension! File needs to be .tar.gz or .tgz file! \n"
                    return flask.make_response(error, 400)
                local_file_name = os.path.join(app.config["UPLOAD_PATH"], filename)
                if os.path.isfile(local_file_name):
                    error = "BLOB insert is ongoing with the same file name! Try again a bit later."
                    return flask.make_response(error, 400)
                uploaded_file.save(local_file_name)
            else:
                error = "Expected file (conf blob) name is missing in form! \n"
                return flask.make_response(error, 400)

            # Read in file to memory
            with open(local_file_name, "rb") as fin:
                data = io.BytesIO(fin.read())

            # Perform insert
            run_config = RunRegistryConfig(rn=rn, configuration=data.getvalue())
            run_meta = RunRegistryMeta(
                rn=rn,
                detector_id=det_id,
                run_type=run_type,
                filename=filename,
                software_version=software_version,
            )
            db.session.add(run_config)
            db.session.add(run_meta)
            db.session.commit()
            resp = flask.make_response(flask.jsonify(rowRes))
            # remove uploaded temp file
            os.remove(local_file_name)
            return resp
        except Exception as e:
            print("Exception:", e)
            return flask.make_response(str(e), 400)


# $ curl -u fooUsr:barPass -X GET np04-srv-021:30015/runregistry/updatestop/<int:runNum>
@api.resource("/runregistry/updateStopTime/<int:runNum>")
class updateStopTimestamp(Resource):
    """
    set and record the stop time for the run into the database
    should return the start and stop times in format: ["Thu, 14 Dec 2023 15:12:03 GMT","Thu, 14 Dec 2023 15:12:32 GMT"]
    """

    @auth.login_required
    def get(self, runNum):
        rowRes = []
        try:
            rowRes.append(
                db.session.query(RunRegistryMeta)
                .filter(
                    RunRegistryMeta.rn == runNum, RunRegistryMeta.stop_time.is_(None)
                )
                .update({RunRegistryMeta.stop_time: datetime.now()})
            )
        except Exception as e:
            (err_obj,) = e.args
            print("Exception:", str(e))
            resp = flask.make_response(flask.jsonify({"Exception": err_obj.message}))
            return resp
        print(rowRes)
        resp = flask.make_response(flask.jsonify(rowRes))
        return resp


@app.route("/")
def index():
    return "Best thing since sliced bread!"
