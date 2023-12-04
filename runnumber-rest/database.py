from datetime import datetime

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Column, Integer, LargeBinary, TIMESTAMP, String

__all__ = ["db", "RunNumber"]

db = SQLAlchemy()


class RunNumber(db.Model):
    """
    The run number object in the database

    TODO: how to specify start value for auto increment of run number
    """

    rn = Column("rn", Integer, primary_key=True, autoincrement=True, nullable=False)
    flag = Column("flag", Boolean, nullable=False, default=False)
    start_time = Column(
        "start_time", TIMESTAMP(6), nullable=False, default=datetime.now
    )
    stop_time = Column("stop_time", TIMESTAMP(6), nullable=True)
