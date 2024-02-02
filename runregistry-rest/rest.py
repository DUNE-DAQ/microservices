<<<<<<< HEAD
#!/usr/bin/env python3
=======
__title__ = "NP04 run registry"
__author__ = "Roland Sipos"
__credits__ = [""]
__version__ = "0.0.8"
__maintainers__ = ["Roland Sipos", "Pierre Lasorak", "Tiago Alves"]
__emails__ = ["roland.sipos@cern.ch", "plasorak@cern.ch", "tiago.alves20@imperial.ac.uk"]

import os, io, gzip, tarfile
import flask
import sys

from flask import Flask, render_template, request, redirect, url_for, send_file

from flask_restful import Api, Resource
from flask_httpauth import HTTPBasicAuth
from flask_redis import FlaskRedis
from flask_caching import Cache

from authentication import auth

# postgres = False

# if "-p" in sys.argv or os.environ.get("RGDB", None):
#     import backends.pg_queries as queries
#     import backends.pg_backend as db

#     postgres = True
# else:
#     import backends.ora_queries as queries
#     import backends.ora_backend as db

"""
Specs
"""
# Create an APISpec
# spec = APISpec(
#    title='Swagger Sensors',
#    version='1.0.0',
#    openapi_version='2.0',
#    plugins=[
#        FlaskPlugin(),
#        MarshmallowPlugin(),
#    ],
# )

"""
Main app
"""
app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 32 * 1000 * 1000
app.config["UPLOAD_EXTENSIONS"] = [".gz", ".tgz"]
app.config["UPLOAD_PATH"] = "uploads"
app.config["CACHE_TYPE"] = "simple"
cache = Cache(app)
api = Api(app)

"""
For REDIS cache
"""


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


"""
Append schema to results
"""


def add_schema_as_element(rowres):
    rowres.insert(0, queries.schema)


# $ curl -u fooUsr:barPass -X GET np04-srv-021:5005/runregistry/getRunMeta/2
@api.resource("/runregistry/getRunMeta/<int:runNum>")
class getRunMeta(Resource):
    @auth.login_required
    def get(self, runNum):
        rowRes = []
        try:
            db.perform_query(queries.getRunMeta, {"run_num": runNum}, rowRes)
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
    @auth.login_required
    def get(self, amount):
        rowRes = []
        try:
            db.perform_query(queries.getRunMetaLast, {"amount": amount}, rowRes)
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
    @auth.login_required
    @cache.cached(timeout=0, key_prefix=cache_key, query_string=True)
    def get(self, runNum):
        rowRes = []
        try:
            db.perform_query(queries.getRunBlob, {"run_num": runNum}, rowRes)
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


# $ curl -u fooUsr:barPass -F "file=@sspconf.tar.gz" -F "run_num=4" -F "det_id=foo" -F "run_type=bar" -F "software_version=dunedaq-vX.Y.Z" -X POST http://localhost:5005/runregistry/insertRun/
@api.resource("/runregistry/insertRun/")
class insertRun(Resource):
    @auth.login_required
    def post(self):
        filename = ""
        try:
            # Ensure form fields
            run_num = request.form["run_num"]
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
            query_list = []
            bind_vars = []
            query_list.append(queries.insertRunRegistryMeta)
            query_list.append(queries.insertRunRegistryBlob)
            bind_vars.append(
                {
                    "run_num": run_num,
                    "det_id": det_id,
                    "run_type": run_type,
                    "filename": filename,
                    "software_version": software_version,
                }
            )
            bind_vars.append({"run_num": run_num, "config_blob": data.getvalue()})
            db.perform_transaction_multi(query_list, bind_vars)
            rowRes = []
            db.perform_query(queries.getRunMeta, {"run_num": run_num}, rowRes)
            resp = flask.make_response(flask.jsonify(rowRes))
            # remove uploaded temp file
            os.remove(local_file_name)
            return resp
        except Exception as e:
            print("Exception:", e)
            return flask.make_response(str(e), 400)


@api.resource("/runregistry/updateStopTime/<int:runNum>")
class updateStopTimestamp(Resource):
    @auth.login_required
    def get(self, runNum):
        rowRes = []
        try:
            db.perform_transaction(queries.updateStopTime, {"run_num": runNum})
            db.perform_query(queries.getRunMeta, {"run_num": runNum}, rowRes)
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
>>>>>>> develop
'''
Main app

To control set the following environment variables:
DATABASE_URI - URI for sqlalchemy to use
DEBUG - set to TRUE for flask debugging
'''
import os

from api import app, db

# setenv DEBUG=True to enable debug mode
DEBUG = os.getenv("DEBUG", "False").lower() == "true"

with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5005, debug=DEBUG)
