import logging
import os
import subprocess
import sys
from getpass import getpass
from pathlib import Path


def which(program):
    # https://stackoverflow.com/a/377028
    def is_exe(fpath):
        return os.path.isfile(fpath) and os.access(fpath, os.X_OK)

    fpath, fname = os.path.split(program)
    if fpath:
        if is_exe(program):
            print("Found1", program)
            return program
    else:
        for path in os.environ.get("PATH", "").split(os.pathsep):
            exe_file = os.path.join(path, program)
            if is_exe(exe_file):
                print("Found2", program)
                return exe_file

    return None


def env_for_kerberos(ticket_dir):
    ticket_dir = os.path.expanduser(ticket_dir)
    env = {"KRB5CCNAME": f"DIR:{ticket_dir}"}
    return env


def new_kerberos_ticket(
    user: str, realm: str, password: str = None, ticket_dir: str = "~/"
):
    env = env_for_kerberos(ticket_dir)
    success = False
    password_provided = password is not None

    while not success:

        p = subprocess.Popen(
            ["kinit", f"{user}@{realm}"],
            stdout=subprocess.PIPE,
            stdin=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )

        if p.poll() is not None and p.returncode != 0:
            raise RuntimeError(f"Could not execute kinit {user}@{realm}")

        if password is None:
            print(f"Password for {user}@{realm}:")
            try:

                password = getpass()

            except KeyboardInterrupt:
                print()
                return False

        stdout_data = p.communicate(password.encode())
        print(stdout_data[-1].decode())

        if not password_provided:
            password = None

        success = p.returncode == 0

        if not success and password_provided:
            raise RuntimeError(
                f"Authentication error for {user}@{realm}. The password provided (likely in configuration file) is incorrect"
            )

    return True


def get_kerberos_user(silent=False, ticket_dir: str = "~/"):

    log = logging.getLogger("get_kerberos_user")

    env = env_for_kerberos(ticket_dir)
    args = [
        "klist"
    ]  # on my mac, I can specify --json and that gives everything nicely in json format... but...

    proc = subprocess.run(args, capture_output=True, text=True, env=env)
    raw_kerb_info = proc.stdout.split("\n")

    if not silent:
        log.info(proc.stdout)

    kerb_user = None
    for line in raw_kerb_info:
        split_line = line.split(" ")
        split_line = [x for x in split_line if x != ""]
        find_princ = line.find("Default principal")
        if find_princ != -1:
            kerb_user = split_line[2]
            kerb_user = kerb_user.split("@")[0]

        if kerb_user:
            return kerb_user
    return None


def check_kerberos_credentials(against_user: str, silent=False, ticket_dir: str = "~/"):

    log = logging.getLogger("check_kerberos_credentials")

    env = env_for_kerberos(ticket_dir)

    kerb_user = get_kerberos_user(silent=silent, ticket_dir=ticket_dir)

    if not silent:
        if kerb_user:
            log.info(f"Detected kerberos ticket for user: '{kerb_user}'")
        else:
            log.info("No kerberos ticket found")

    if not kerb_user:
        if not silent:
            log.info("No kerberos ticket")
        return False
    elif kerb_user != against_user:  # we enforce the user is the same
        if not silent:
            log.info("Another user is logged in")
        return False
    else:

        ticket_is_valid = subprocess.call(["klist", "-s"], env=env) == 0
        if not silent and not ticket_is_valid:
            log.info("Kerberos ticket is expired")
        return ticket_is_valid


class ServiceAccountWithKerberos:
    def __init__(self, service: str, username: str, password: str, realm: str):
        self.service = service
        self.username = username
        self.password = password
        self.realm = realm

    def generate_cern_sso_cookie(self, website, kerberos_directory, output_directory):
        env = os.environ.copy()
        env["KRB5CCNAME"] = f"DIR:{kerberos_directory}"

        try:
            proc = subprocess.run(
                ["auth-get-sso-cookie", "-u", website, "-o", output_directory],
                env=env,
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as error:
            self.log.error(error)
            raise RuntimeError(
                f"Couldn't get SSO cookie! stdout={error.stdout!r} stderr={error.stderr!r}"
            ) from error

        return output_directory


class CredentialManager:
    def __init__(self):
        self.log = logging.getLogger(self.__class__.__name__)
        self.authentications = []

    def add_login(self, service: str, user: str, password: str, realm: str):
        self.authentications.append(
            ServiceAccountWithKerberos(service, user, password, realm)
        )

    def add_login_from_file(self, service: str, file: str):
        if not os.path.isfile(os.getcwd() + "/" + file + ".py"):
            self.log.error(f"Couldn't find file {file} in PWD")
            raise

        sys.path.append(os.getcwd())
        i = __import__(file, fromlist=[""])
        self.add_login(service, i.user, i.password)
        self.log.info(f"Added login data from file: {file}")

    def get_login(self, service: str, user: str | None = None):
        for auth in self.authentications:
            if auth.service != service:
                continue
            if user is None or auth.user == user:
                return auth

        if user:
            self.log.error(f"Couldn't find login for service: {service}, user: {user}")
        else:
            self.log.error(f"Couldn't find login for service: {service}")

    def rm_login(self, service: str, user: str):
        for auth in self.authentications:
            if service == auth.service and user == auth.user:
                self.authentications.remove(auth)
                return

    def new_kerberos_ticket(self):
        for a in self.authentications:
            if a.user == self.user:
                password = a.password
                break

        p = subprocess.Popen(
            ["kinit", self.user + "@CERN.CH"],
            stdout=subprocess.PIPE,
            stdin=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        stdout_data = p.communicate(password.encode())
        print(stdout_data[-1].decode())
        return True


credentials = CredentialManager()


class CERNSessionHandler:
    def __init__(self, username: str):

        self.log = logging.getLogger(self.__class__.__name__)
        self.elisa_username = username

        if not self.elisa_user_is_authenticated():
            self.authenticate_elisa_user()

    @staticmethod
    def __get_elisa_kerberos_cache_path():

        return Path(os.path.expanduser("/tmp/.nanorc_elisakerbcache"))

    def elisa_user_is_authenticated(self):
        elisa_user = credentials.get_login("elisa")
        return check_kerberos_credentials(
            against_user=elisa_user.username,
            silent=True,
            ticket_dir=CERNSessionHandler.__get_elisa_kerberos_cache_path(),
        )

    def authenticate_elisa_user(self):
        elisa_user = credentials.get_login("elisa")
        elisa_kerb_cache = CERNSessionHandler.__get_elisa_kerberos_cache_path()

        if not os.path.isdir(elisa_kerb_cache):
            os.mkdir(elisa_kerb_cache)

        if self.elisa_user_is_authenticated():
            # we're authenticated, stop here
            return True

        return new_kerberos_ticket(
            user=elisa_user.username,
            realm=elisa_user.realm,
            password=elisa_user.password,
            ticket_dir=elisa_kerb_cache,
        )

    def generate_elisa_cern_cookie(self, website, cookie_dir):
        elisa_user = credentials.get_login("elisa")
        elisa_kerb_cache = CERNSessionHandler.__get_elisa_kerberos_cache_path()

        self.authenticate_elisa_user()

        return elisa_user.generate_cern_sso_cookie(
            website,
            elisa_kerb_cache,
            cookie_dir,
        )
