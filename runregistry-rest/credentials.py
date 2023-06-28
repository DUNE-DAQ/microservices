import os

if os.environ.get("RGDB", None) == "postgres":
    dbhost = os.environ.get("DB_HOSTNAME", "localhost")
    port = os.environ.get("DB_PORT", 5432)
    database = os.environ.get("DB_NAME", "runregistry")

    username = os.environ.get("DB_USERNAME", "")
    password = os.environ.get("DB_PASSWORD", "")
else:  # is oracle?
    dburi = "FIX ME to be a Secret from Kubernetes with good defaults!"
    port = os.environ.get("DB_PORT", 1521)
    database = "set default database name here"

    username = os.environ.get("DB_USERNAME", "")
    password = os.environ.get("DB_PASSWORD", "")
