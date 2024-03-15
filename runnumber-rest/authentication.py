from flask_httpauth import HTTPBasicAuth

auth = HTTPBasicAuth()

__all__ = [
    "auth",
]

# This is reset by the image creation
APP_PASS = {"fooUsr": "barPass"}


@auth.verify_password
def verify(username, password):
    if username and password:
        return APP_PASS.get(username) == password
    return False
