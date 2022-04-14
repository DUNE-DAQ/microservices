import psycopg2
import credentials

from psycopg2.extensions import AsIs

print("psycopg2 client version: ", str(psycopg2.__version__))
# user, pass, dsn, min, max, increment
db_conn = psycopg2.connect(user=credentials.user,
                                password=credentials.password,
                                host=credentials.dburi,
                                database=credentials.database
                                )
print("Postgres connection:", str(db_conn))

def perform_query(query, bind_variables, resultset):
    connection = db_conn
    cursor = connection.cursor()
    cursor.execute(query, bind_variables)
    print("  -> Perform query done...")
    rowsFetched=0
    while True:
      qres = cursor.fetchmany()
      rowsFetched+=len(qres)
      if not len(qres)==0:
        resultset.append(qres)
      if not qres:
        print("No rows...")
        break
      #rowsFetched=len(resultset)
    print("  -> fetched ", rowsFetched, " rows...")

def perform_transaction(query, bind_variables, autcomm=False):
    connection = db_conn
    #connection.autocommit = autcomm
    cursor = connection.cursor()
    cursor.execute(query, bind_variables)
    print("  -> Perform transaction done...")
    if not autcomm:
        connection.commit()
        print("  -> Committed...")
    cursor.close()

def perform_transaction_multi(queries, bind_variables, autcomm=False):
    print("  -> Multiple queries: ", queries)
    print(" bind vars: ", bind_variables)
    if not type(queries) is list:
      print("  -> Queries expected to be a list!")
      return
    if not type(bind_variables) is list:
      print("  -> Bind variables expected to be a list!")
    connection = db_conn
    connection.autocommit = True
    print("  -> Using connection:", connection)
    cursor = connection.cursor()
    print(queries)
    for i in range(len(queries)):
      cursor.execute(queries[i], bind_variables[i])
    if not autcomm:
        connection.commit()
        print("  -> Committed...")
    print("  -> Perform transaction done...")
    cursor.close()

def perform_query_unpack(args):
    return perform_query(*args)

def lock_db():
    conn = db_pool.acquire()
    cursor = conn.cursor()
    print("lock_db(): beginning execute...")
    cursor.callproc("dbms_lock.sleep", (5,))
    print("lock_db(): done execute...")

