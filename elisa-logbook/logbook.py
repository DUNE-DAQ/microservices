__author__ = "Jonathan Hancock"
__credits__ = ["J.Bracinik", "P.Lasorak"]
__version__ = "1.1.0"
__maintainer__ = "Jonathan Hancock"
__email__ = "jonathan.hancock@cern.ch"

import json
import os
import re
import traceback
from pathlib import Path

from authentication import auth
from credmgr import CERNSessionHandler, credentials
from elisa import ElisaLogbook
from flask import Flask, jsonify, make_response, request
from flask_caching import Cache
from flask_restful import Api

# Sets up the app and processes command line inputs
app = Flask(__name__)
cache = Cache(app)
api = Api(app)

# Converts the config json into a dictionary, and gets a list of the keys
with Path("elisaconf.json").open() as json_file:
    elisaconf = json.load(json_file)

keylist = elisaconf.keys()
hardware_string = "Please choose from one of the following options:"
for key in keylist:
    hardware_string += " "
    hardware_string += key


# We use environment variables to pass data
def get_required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Required environment variable {name} is not set")
    return value.rstrip("\n")


hard_var = get_required_env("HARDWARE")
app.config["PATH"] = os.getenv("APP_DATA", "./logfiles").rstrip("\n")
app.config["USER"] = get_required_env("USERNAME")
app.config["PASSWORD"] = get_required_env("PASSWORD")

try:
    app.config["HARDWARECONF"] = elisaconf[hard_var]
except KeyError as exc:
    raise KeyError(f"{hard_var} is not a valid choice!{hardware_string}") from exc

Path(app.config["PATH"]).mkdir(parents=True, exist_ok=True)
if not os.access(app.config["PATH"], os.W_OK):
    raise PermissionError(
        f"Error: Permission denied to access the file at {app.config['PATH']}"
    )

credentials.add_login("elisa", app.config["USER"], app.config["PASSWORD"], "CERN.CH")
cern_auth = CERNSessionHandler(username=app.config["USER"])

logbook = ElisaLogbook(app.config["HARDWARECONF"], cern_auth)


# Helper function to sanitize run_type to prevent path traversal
def sanitize_run_type(run_type: str) -> str:
    """
    Sanitize run_type to prevent path traversal attacks.
    Only allows alphanumeric characters, hyphens, and underscores.
    The first character must be alphanumeric to avoid interpretation as command-line flags.
    """
    if not run_type or not re.match(r"^[a-zA-Z0-9][a-zA-Z0-9_-]*$", run_type):
        raise ValueError(
            "Invalid run_type: must start with alphanumeric and contain only alphanumeric characters, hyphens, or underscores"
        )
    return run_type


# Main app
# The general principle is to replace the methods of each class with API methods
# The first type of logging is fileLogbook, which writes logs to a given file in the current working directory.


@app.route("/")
def index():
    return "<h1>Welcome to the logbook API!</h1>"


# $ curl --user fooUsr:barPass -d "author=jsmith&message=foo&run_num=1&run_type=test" -X POST http://localhost:5005/v1/fileLogbook/message_on_start/
@app.route("/v1/fileLogbook/message_on_start/", methods=["POST"])
@auth.login_required
def Fmessage_on_start():
    try:
        run_number = int(request.json["run_num"])
    except (ValueError, TypeError, KeyError):
        error = "Run number is not an integer!"
        return error, 400

    try:
        # Security: Sanitize run_type to prevent path traversal
        run_type = sanitize_run_type(request.json["run_type"])

        base_path = Path(app.config["PATH"])
        file_path = base_path / f"_{run_number}_{run_type}.txt"

        # Security: Verify the resolved path is within the base directory
        try:
            file_path.resolve().relative_to(base_path.resolve())
        except ValueError:
            return "Invalid file path", 400

        with file_path.open("w") as f:
            f.write(
                f"-- User {request.json['author']} started a run {run_number}, of type {run_type} --\n"
            )
            f.write(request.json["author"] + ": " + request.json["message"] + "\n")
        rstring = "Logfile started at " + str(file_path) + "\n"
        return rstring, 201
    except Exception as e:
        return str(e), 400


# $ curl --user fooUsr:barPass -d "author=jsmith&message=foo&run_num=1&run_type=test" -X PUT http://localhost:5005/v1/fileLogbook/add_message/
@app.route("/v1/fileLogbook/add_message/", methods=["PUT"])
@auth.login_required
def Fadd_message():
    try:
        run_number = int(request.json["run_num"])
    except (ValueError, TypeError, KeyError):
        error = "Run number is not an integer!"
        return error, 400

    try:
        # Security: Sanitize run_type to prevent path traversal
        run_type = sanitize_run_type(request.json["run_type"])

        base_path = Path(app.config["PATH"])
        file_path = base_path / f"_{run_number}_{run_type}.txt"

        # Security: Verify the resolved path is within the base directory
        try:
            file_path.resolve().relative_to(base_path.resolve())
        except ValueError:
            return "Invalid file path", 400
    except Exception as e:
        return str(e), 400

    if not file_path.exists():
        error = "File not found!"
        return error, 404

    with file_path.open("a") as f:
        f.write(request.json["author"] + ": " + request.json["message"] + "\n")

    rstring = "Logfile updated at " + str(file_path) + "\n"
    return rstring, 200


# $ curl --user fooUsr:barPass -d "author=jsmith&message=foo&run_num=1&run_type=test" -X PUT http://localhost:5005/v1/fileLogbook/message_on_stop/
@app.route("/v1/fileLogbook/message_on_stop/", methods=["PUT"])
@auth.login_required
def Fmessage_on_stop():
    try:
        run_num = int(request.json["run_num"])
    except (ValueError, TypeError, KeyError):
        error = "Run number is not an integer!"
        return error, 400

    try:
        # Security: Sanitize run_type to prevent path traversal
        run_type = sanitize_run_type(request.json["run_type"])

        base_path = Path(app.config["PATH"])
        file_path = base_path / f"_{run_num}_{run_type}.txt"

        # Security: Verify the resolved path is within the base directory
        try:
            file_path.resolve().relative_to(base_path.resolve())
        except ValueError:
            return "Invalid file path", 400
    except Exception as e:
        return str(e), 400

    if not file_path.exists():
        error = "File not found!"
        return error, 404

    with file_path.open("a") as f:
        f.write(
            f"-- User {request.json['author']} stopped the run {run_num}, of type {run_type} --\n"
        )
        f.write(request.json["author"] + ": " + request.json["message"] + "\n")

    rstring = "Log stopped at " + str(file_path) + "\n"
    return rstring, 200


# The second (preferred) type of logging is elisaLogbook, which sends the logs off to an external database.


# $ curl --user fooUsr:barPass -H "Content-Type: application/json" -d '{"author":"jhancock", "title":"Test", "body":"Testing the microservice", "command":"start", "systems":["daq"]}'  -X POST http://localhost:5005/v1/elisaLogbook/new_message/
@app.route("/v1/elisaLogbook/new_message/", methods=["POST"])
@auth.login_required
def new_message():
    print(request.json)
    if (
        request.json.get("body", "") == ""
        or request.json.get("title", "") == ""
        or request.json.get("command", "") == ""
        or request.json.get("author", "") == ""
    ):
        resp = make_response(
            jsonify(
                response="Body, title, command, author cannot be empty!",
                sent_data=request.json,
            )
        )
        resp.status = 400
        resp.headers["mimetype"] = "application/json"
        return resp
    try:
        sys_list = request.json.get(
            "system", ["DAQ"]
        )  # Defaults to DAQ since that's the most likely use case
        thread_id = logbook.start_new_thread(
            subject=request.json["title"],
            body=request.json["body"],
            command=request.json["command"],
            author=request.json["author"],
            systems=sys_list,
        )
    except Exception:
        traceback.print_exc()
        stack = traceback.format_exc().split("\n")
        resp = make_response(jsonify(stacktrace=stack))
        resp.status = 500
        resp.headers["mimetype"] = "application/json"
        return resp

    resp = make_response(
        jsonify(response="Message thread started successfully", thread_id=thread_id)
    )
    resp.status = 201
    resp.headers["mimetype"] = "application/json"
    return resp


# $ curl --user fooUsr:barPass -H "Content-Type: application/json" -d '{"author":"jsmith", "body":"Testing the microservice", "command":"start", "systems":["daq"], "id": 9999}'  -X PUT http://localhost:5005/v1/elisaLogbook/reply_to_message/
@app.route("/v1/elisaLogbook/reply_to_message/", methods=["PUT"])
@auth.login_required
def reply_to_message():
    if (
        request.json.get("body", "") == ""
        or request.json.get("title", "") == ""
        or request.json.get("command", "") == ""
        or request.json.get("author", "") == ""
        or request.json.get("id", "") == ""
    ):
        resp = make_response(
            jsonify(
                response="Body, title, command, author or id cannot be empty!",
                sent_data=request.json,
            )
        )
        resp.status = 400
        resp.headers["mimetype"] = "application/json"
        return resp
    try:
        sys_list = request.json.get("system", ["DAQ"])
        thread_id = logbook.reply(
            body=request.json["body"],
            command=request.json["command"],
            author=request.json["author"],
            systems=sys_list,
            id=request.json["id"],
        )
    except Exception:
        traceback.print_exc()
        stack = traceback.format_exc().split("\n")
        resp = make_response(jsonify(stacktrace=stack))
        resp.status = 500
        resp.headers["mimetype"] = "application/json"
        return resp

    resp = make_response(
        jsonify(response="Message replied successfully", thread_id=thread_id)
    )
    resp.status = 201
    resp.headers["mimetype"] = "application/json"
    return resp


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5005, debug=True)
