from datetime import datetime

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Column, Integer, LargeBinary, TIMESTAMP, String

__all__ = ["db", "RunRegistryConfig", "RunRegistryMeta"]

db = SQLAlchemy()

class RunRegistryConfig(db.Model):
    rn = Column("rn", Integer, primary_key=True, autoincrement=True, nullable=False)
    configuration = Column("configuration", LargeBinary, nullable=False)

class RunRegistryMeta(db.Model):
    rn = Column("rn", Integer, primary_key=True, autoincrement=True, nullable=False)
    start_time = Column("start_time", TIMESTAMP(6), nullable=False, default=datetime.now)
    stop_time = Column("stop_time", TIMESTAMP(6), nullable=True)
    detector_id = Column("detector_id", String(40))
    run_type = Column("run_type", String(40))
    filename = Column("filename", String(100))
    software_version = Column("software_version", String(40))



