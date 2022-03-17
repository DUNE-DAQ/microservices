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


'''
Configuration schema. (Maybe it's an overkill, but looks sufficient as a first go.)

-----------------------------------------------------
| COLUMN_NAME    |  DATA_TYPE          |  NULLABLE  |
-----------------------------------------------------
| OBJECTID       |  VARCHAR2(24 BYTE)  |  No        |
| NAME           |  VARCHAR2(200 BYTE) |  No        | 
| INSERTION_TIME |  NUMBER             |  No        |
| ALTERED_TIME   |  NUMBER             |  No        |
| FLAG	         |  VARCHAR2(20 BYTE)  |  No        |
| CONFIGURATION  |  CLOB               |  No        |
-----------------------------------------------------

  CREATE TABLE "<SCHEMA_NAME>"."<TABLE_NAME>" 
  ( 
    "OBJECTID" VARCHAR2(24 BYTE) NOT NULL ENABLE, 
    "NAME" VARCHAR2(200 BYTE) NOT NULL ENABLE, 
    "INSERTION_TIME" NUMBER NOT NULL ENABLE, 
    "ALTERED_TIME" NUMBER NOT NULL ENABLE, 
    "FLAG" VARCHAR2(20 BYTE) NOT NULL ENABLE, 
    "CONFIGURATION" CLOB NOT NULL ENABLE, 
    CONSTRAINT "<TABLE_NAME>_PK" PRIMARY KEY ("OBJECTID", "NAME")
  )

'''

class SqlQueries(object):
  def __init__(self):
    schema = ""
    table = ""
    fullname = schema + '.' + table
    insertConfig = ""
    retrieveExactConfig = ""
    retrieveConfigsLike = ""
    getLastInsert = ""  

  def init(self, config):
    if not config:
      raise IOError
    elif not config['ora_schema'] or not config['ora_table']:
      raise IOError
    else:
      self.schema = config['ora_schema']
      self.table = config['ora_table']
      self.fullname = self.schema + '.' + self.table
      self.insertConfig = "insert into " + self.fullname 
      self.insertConfig += " (OBJECTID, NAME, INSERTION_TIME, ALTERED_TIME, FLAG, CONFIGURATION)"
      self.insertConfig += " values (:objId, :cName, :insTime, :altTime, :cFlag, :confClob)"
      self.retrieveExactConfig = "select CONFIGURATION from " + self.fullname + " where NAME=:cName"
      self.retrieveConfigsLike = "select CONFIGURATION from " + self.fullname + " where NAME like :cName"
      self.getLastInsert = "select * from (select INSERTION_TIME from " + self.fullname
      self.getLastInsert += " order by INSERTION_TIME desc) where rownum <= 1"

