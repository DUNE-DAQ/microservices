from flask_httpauth import HTTPBasicAuth

auth = HTTPBasicAuth()

APP_PASS = {"fooUsr": "barPass"}


@auth.verify_password
def verify(username, password):
    if not (username and password):
        return False
    return APP_PASS.get(username) == password
