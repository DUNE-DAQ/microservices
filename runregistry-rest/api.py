import os, io, gzip, tarfile
import flask
import sys

from flask import Flask, render_template, request, redirect, url_for, send_file

from flask_restful import Api, Resource
from flask_httpauth import HTTPBasicAuth
from flask_redis import FlaskRedis
from flask_caching import Cache
from flask_sqlalchemy import SQLAlchemy

from sqlalchemy import desc, func

from authentication import auth

__all__ = ["app", "api", "db"]

app = Flask(__name__)

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


# $ curl -u fooUsr:barPass -X GET np04-srv-021:5005/runregistry/getRunMeta/2
@api.resource("/runregistry/getRunMeta/<int:runNum>")
class getRunMeta(Resource):
    """
    Get XYZ
    should return the RunMeta in format: XXXXXX
    """

    @auth.login_required
    def get(self, runNum):
        rowRes = []
        try:
            rowRes.append(
                db.session.execute(
                    db.select(func.max(RunRegistryMeta.rn))
                ).scalar_one()
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


# $ curl -u fooUsr:barPass -X GET np04-srv-021:5005/runregistry/getRunMetaLast/100
@api.resource("/runregistry/getRunMetaLast/<int:amount>")
class getRunMetaLast(Resource):
    """
    Get XYZ
    should return the RunMeta in format: XXXXXX
    """

    @auth.login_required
    def get(self, amount):
        rowRes = []
        try:
            rowRes.append(
                db.session.query(RunRegistryMeta.rn).order_by(desc(RunRegistryMeta.rn)).limit(amount)
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


# $ curl -u fooUsr:barPass -X GET -O -J np04-srv-021:5005/runregistry/getRunBlob/2
@api.resource("/runregistry/getRunBlob/<int:runNum>")
class getRunBlob(Resource):
    """
    Get XYZ
    should return the ZYX in format: XXXXXX
    """
    @auth.login_required
    @cache.cached(timeout=0, key_prefix=cache_key, query_string=True)
    def get(self, runNum):
        rowRes = []
        try:
            rowRes.append(db.session.execute(db.select(RunRegistryMeta.filename, RunRegistryConfig.configuration).join(RunRegistryConfig, RunRegistryConfig.rn == RunRegistryMeta.rn)))
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


# $ curl -u fooUsr:barPass -F "file=@sspconf.tar.gz" -F "rn=4" -F "det_id=foo" -F "run_type=bar" -F "software_version=dunedaq-vX.Y.Z" -X POST http://localhost:5005/runregistry/insertRun/
@api.resource("/runregistry/insertRun/")
class insertRun(Resource):
    """
    Get XYZ
    should return the XYZ in format: XXXXXX
    """
    @auth.login_required
    def post(self):
        filename = ""
        try:
            # Ensure form fields
            rn = request.form["rn"]
            stop_time = None
            det_id = request.form["det_id"]
            run_type = request.form["run_type"]
            software_version = request.form["software_version"]
            uploaded_file = request.files["file"]
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
            run_meta = RunRegistryMeta(rn=rn, detector_id=det_id, run_type=run_type, filename=filename, software_version=software_version)
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


@api.resource("/runregistry/updateStopTime/<int:runNum>")
class updateStopTimestamp(Resource):
    """
    Get XYZ
    should return the times in format: XXXXXX
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
