import cx_Oracle
import threading
import credentials

print("cx_Oracle client version: ", str(cx_Oracle.clientversion()))
# user, pass, dsn, min, max, increment
db_pool = cx_Oracle.SessionPool(credentials.user,
                                credentials.password,
                                credentials.dburi,
                                2, 4, 1, threaded=True)
print("cx_Oracle SessionPool:", str(db_pool))

def perform_query(query, bind_variables, resultset):
    print("THREAD ", threading.current_thread().name)
    connection = db_pool.acquire()
    print("  -> Using connection from pool:", connection)
    cursor = connection.cursor()
#    cursor.arraysize = 25000
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
    print("THREAD ", threading.current_thread().name)
    connection = db_pool.acquire()
    connection.autocommit = autcomm
    print("  -> Using connection from pool:", connection)
    cursor = connection.cursor()
    cursor.execute(query, bind_variables)
    print("  -> Perform transaction done...")
    if not autcomm:
        connection.commit()
        print("  -> Committed...")
    cursor.close()

def perform_query_unpack(args):
    return perform_query(*args)

def lock_db():
    conn = db_pool.acquire()
    cursor = conn.cursor()
    print("lock_db(): beginning execute...")
    cursor.callproc("dbms_lock.sleep", (5,))
    print("lock_db(): done execute...")

