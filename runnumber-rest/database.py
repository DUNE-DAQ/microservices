from datetime import datetime

from api import db

__all__ = ["RunNumber"]


class RunNumber(db.Model):
    """
    The run number object in the database

    TODO: how to specify start value for auto increment of run number
    """

    rn = db.Column(
        "rn", db.Integer, primary_key=True, autoincrement=True, nullable=False
    )
    flag = db.Column(
        "flag", db.Boolean, nullable=False, default=False
        )
    start_time = db.Column(
        "start_time", db.TIMESTAMP(6), nullable=False, default=datetime.now
    )
    stop_time = db.Column(
        "stop_time", db.TIMESTAMP(6), nullable=True
        )
