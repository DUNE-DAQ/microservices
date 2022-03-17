"""
 Copyright (C) 2019-2021 CERN
 
 DAQling is free software: you can redistribute it and/or modify
 it under the terms of the GNU Lesser General Public License as published by
 the Free Software Foundation, either version 3 of the License, or
 (at your option) any later version.
 
 DAQling is distributed in the hope that it will be useful,
 but WITHOUT ANY WARRANTY; without even the implied warranty of
 MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 GNU Lesser General Public License for more details.
 
 You should have received a copy of the GNU Lesser General Public License
 along with DAQling. If not, see <http://www.gnu.org/licenses/>.
"""

import cx_Oracle
import threading
import ctypes
import logging

db_pool = None
logger = logging.getLogger('archiver_logger.backend')

def init(config): 
    logger.debug("cx_Oracle client version: " + str(cx_Oracle.clientversion()))
    global db_pool
    try:
      db_pool = cx_Oracle.SessionPool(str(config["ora_acc"]), str(config["ora_pass"]), str(config["ora_name"]), 2, 4, 1, threaded=True)
    except:
      logger.error("cx_Oracle SessionPool: Failed to init the pool!!! Please check connection details!")
      raise IOError
    finally:
      logger.debug("cx_Oracle SessionPool:" + str(db_pool))

def strip_single(rowRes):
    return rowRes[0][0][0]

def perform_query(query, bind_variables, resultset):
    logger.debug("THREAD " + threading.current_thread().name)
    connection = db_pool.acquire()
    logger.debug("  -> Using connection from pool:" + str(connection))
    cursor = connection.cursor()
    #cursor.arraysize = 25000
    cursor.execute(query, bind_variables)
    logger.debug("  -> Perform query done...")
    rowsFetched=0
    while True:
      qres = cursor.fetchmany()
      rowsFetched+=len(qres)
      if not len(qres)==0:
        resultset.append(qres)
      if not qres:
        logger.debug("No rows...")
        break;
      #rowsFetched=len(resultset)
    logger.debug("  -> fetched " + str(rowsFetched) + " rows...")

def perform_query_unpack(args):
    return perform_query(*args)


def perform_query_rows(query, bind_variables, resultset):
    logger.debug(bind_variables)
    logger.debug("THREAD ", threading.current_thread().name)
    connection = db_pool.acquire()
    logger.debug("  -> Using connection from pool:" + str(connection))
    logger.debug("  -> ADDR: resultset: " + id(resultset))

    bv = bind_variables
    cursor = connection.cursor()
    cursor.execute(query, bv)
    logger.debug("  -> Perform query done...")
    rowsFetched=0
    rows = []
    while True:
      qres = cursor.fetchmany()
      if not len(qres)==0:
        rowsFetched+=len(qres)
        for row in qres:
          rows.append(row)
      if not qres:
        logger.debug("No rows...")
        break;
    for r in reversed(rows):
      resultset.append(r)
    logger.debug("  -> fetched " + str(rowsFetched) + " rows...")

def perform_query_rows_unpack(args):
    return perform_query_rows(*args)


def lock_db():
    conn = db_pool.acquire()
    cursor = conn.cursor()
    logger.debug("lock_db(): beginning execute...")
    cursor.callproc("dbms_lock.sleep", (5,))
    logger.debug("lock_db(): done execute...")

