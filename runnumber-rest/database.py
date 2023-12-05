from datetime import datetime

from flask_sqlalchemy import SQLAlchemy

__all__ = ["db", "RunNumber"]

db = SQLAlchemy()


class RunNumber(db.Model):
    """
    The run number object in the database

    TODO: how to specify start value for auto increment of run number
    """

    rn = db.Column("rn", db.Integer, primary_key=True, autoincrement=True, nullable=False)
    flag = db.Column("flag", db.Boolean, nullable=False, default=False)
    start_time = Column(
        "start_time", db.TIMESTAMP(6), nullable=False, default=datetime.now
    )
    stop_time = db.Column("stop_time", db.TIMESTAMP(6), nullable=True)
