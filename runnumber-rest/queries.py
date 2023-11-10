incrementRunNum = "insert into RUN_NUMBER (RN, START_TIME, FLAG, STOP_TIME) select RN+1, CURRENT_TIMESTAMP, 0, CURRENT_TIMESTAMP from RUN_NUMBER where rownum=1 order by RN DESC"

getRunNum = "select RN from RUN_NUMBER where rownum=1 order by RN DESC"

getRunTime = "select START_TIME, STOP_TIME from RUN_NUMBER where RN=:runNum"

updateStopTimestamp = "update RUN_NUMBER set STOP_TIME=CURRENT_TIMESTAMP where RN=:runNum"



# from sqlalchemy import create_engine, Column, Integer, DateTime
# from sqlalchemy.orm import sessionmaker
# from sqlalchemy.ext.declarative import declarative_base
# from sqlalchemy.sql import func

# incrementRunNum = session.query(
#     (incrementRunNumQ.c.func.max(RunNumber.RN) + 1).label('new_rn'),
#     func.current_timestamp(),
#     0,
#     func.current_timestamp()
# ).filter(RunNumber.RN == increment_run_num_query.c.func.max(RunNumber.RN)).statement

# getRunNum = session.query(RunNumber.RN).order_by(RunNumber.RN.desc()).limit(1).statement

# getRunTime = session.query(RunNumber.START_TIME, RunNumber.STOP_TIME).filter(RunNumber.RN == ':runNum')

# updateStopTimestamp = session.query(RunNumber).filter(RunNumber.RN == ':runNum').update({'STOP_TIME': func.current_timestamp()})


