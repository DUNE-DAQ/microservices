incrementRunNum = "insert into RUN_NUMBER (RN, START_TIME, FLAG, STOP_TIME) select RN+1, CURRENT_TIMESTAMP, 0, CURRENT_TIMESTAMP from RUN_NUMBER where rownum=1 order by RN DESC"

getRunNum = "select RN from RUN_NUMBER where rownum=1 order by RN DESC"

getRunTime = "select START_TIME, STOP_TIME from RUN_NUMBER where RN=:runNum"

updateStopTimestamp = "update RUN_NUMBER set STOP_TIME=CURRENT_TIMESTAMP where RN=:runNum"

