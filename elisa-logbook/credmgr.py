import logging
import os
import subprocess
import sys
from getpass import getpass
from pathlib import Path
from typing import Optional


def which(program):
    # https://stackoverflow.com/a/377028
    def is_exe(fpath):
        fpath_obj = Path(fpath)
        return fpath_obj.is_file() and os.access(fpath, os.X_OK)

    fpath, _fname = os.path.split(program)
    if fpath:
        if is_exe(program):
            print("Found1", program)
            return program
    else:
        for path in os.environ.get("PATH", "").split(os.pathsep):
            exe_file = Path(path) / program
            if is_exe(exe_file):
                print("Found2", program)
                return str(exe_file)

    return None


def env_for_kerberos(ticket_dir):
    ticket_dir = Path(ticket_dir).expanduser()
    return {"KRB5CCNAME": f"DIR:{ticket_dir}"}


def new_kerberos_ticket(
    user: str, realm: str, password: Optional[str] = None, ticket_dir: str = "~/"
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

        if password is None:
            print(f"Password for {user}@{realm}:")
            try:
                password = getpass()

            except KeyboardInterrupt:
                print()
                return False

        stdout_data, stderr_data = p.communicate(password.encode())

        # Display stderr if present (where kinit typically sends output)
        if stderr_data:
            print(stderr_data.decode())
        elif stdout_data:
            print(stdout_data.decode())

        if not password_provided:
            password = None

        success = p.returncode == 0

        if not success and password_provided:
            error_msg = stderr_data.decode() if stderr_data else stdout_data.decode()
            raise RuntimeError(
                f"Authentication error for {user}@{realm}. The password provided (likely in configuration file) is incorrect\n{error_msg}"
            )

    return True


def get_kerberos_user(silent=False, ticket_dir: str = "~/"):
    log = logging.getLogger("get_kerberos_user")

    env = env_for_kerberos(ticket_dir)
    args = [
        "klist"
    ]  # on my mac, I can specify --json and that gives everything nicely in json format... but...

    proc = subprocess.run(args, check=False, capture_output=True, text=True, env=env)
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
    if kerb_user != against_user:  # we enforce the user is the same
        if not silent:
            log.info("Another user is logged in")
        return False
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
        self.log = logging.getLogger(self.__class__.__name__)

    def generate_cern_sso_cookie(self, website, kerberos_directory, output_directory):
        env = {"KRB5CCNAME": f"DIR:{kerberos_directory}"}

        import sh

        executable = sh.Command("auth-get-sso-cookie")

        try:
            executable(
                "-u", website, "-o", output_directory, _env=env, _new_session=False
            )
        except sh.ErrorReturnCode as error:
            self.log.exception(
                f"Couldn't get SSO cookie! {error.stdout=} {error.stderr=}"
            )
            raise RuntimeError(
                f"Couldn't get SSO cookie! {error.stdout=} {error.stderr=}"
            ) from error

        return output_directory


class CredentialManager:
    def __init__(self):
        self.log = logging.getLogger(self.__class__.__name__)
        self.authentications = []
        self.user = None

    def add_login(self, service: str, user: str, password: str, realm: str = "CERN.CH"):
        self.authentications.append(
            ServiceAccountWithKerberos(service, user, password, realm)
        )

    def add_login_from_file(self, service: str, file: str):
        cwd = Path.cwd()
        file_path = cwd / f"{file}.py"
        if not file_path.is_file():
            self.log.error(f"Couldn't find file {file} in PWD")
            raise FileNotFoundError(f"Couldn't find file {file} in PWD")

        sys.path.append(str(cwd))
        i = __import__(file, fromlist=[""])
        self.add_login(service, i.user, i.password)
        self.log.info(f"Added login data from file: {file}")

    def get_login(self, service: str, user: Optional[str] = None):
        for auth in self.authentications:
            if service == auth.service:
                if user is None or user == auth.username:
                    return auth

        if user:
            self.log.error(f"Couldn't find login for service: {service}, user: {user}")
            raise ValueError(
                f"Couldn't find login for service: {service}, user: {user}"
            )
        self.log.error(f"Couldn't find login for service: {service}")
        raise ValueError(f"Couldn't find login for service: {service}")

    def rm_login(self, service: str, user: str):
        for auth in self.authentications:
            if service == auth.service and user == auth.username:
                self.authentications.remove(auth)
                return

    def new_kerberos_ticket(self):
        for a in self.authentications:
            if a.username == self.user:
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
        return Path("/tmp/.nanorc_elisakerbcache")

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

        if not elisa_kerb_cache.is_dir():
            elisa_kerb_cache.mkdir()

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
