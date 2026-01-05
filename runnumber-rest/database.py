import datetime

from api import db

__all__ = ["RunNumber"]


def utc_now():
    return datetime.datetime.now(datetime.timezone.utc)


class RunNumber(db.Model):
    rn = db.Column(
        "rn", db.Integer, primary_key=True, autoincrement=True, nullable=False
    )
    flag = db.Column("flag", db.Boolean, nullable=False, default=False)
    start_time = db.Column(
        "start_time", db.TIMESTAMP(6), nullable=False, default=utc_now
    )
    stop_time = db.Column("stop_time", db.TIMESTAMP(6), nullable=True)
