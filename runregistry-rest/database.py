from datetime import datetime

from api import db

__all__ = ["RunNumber", "RunRegistryConfig", "RunRegistryMeta"]


class RunNumber(db.Model):
    run_number = db.Column(
        db.Integer, primary_key=True, autoincrement=True, nullable=False, index=True
    )
    flag = db.Column(db.Boolean, nullable=False, default=False)
    start_time = db.Column(db.TIMESTAMP(6), nullable=False, default=datetime.now)
    stop_time = db.Column(db.TIMESTAMP(6), nullable=True)


class RunRegistryConfig(db.Model):
    run_number = db.Column(
        db.Integer,
        db.ForeignKey(RunNumber.run_number),
        primary_key=True,
        autoincrement=True,
        nullable=False,
        index=True,
    )
    configuration = db.Column(db.LargeBinary, nullable=False)


class RunRegistryMeta(db.Model):
    run_number = db.Column(
        db.Integer,
        db.ForeignKey(RunNumber.run_number),
        primary_key=True,
        autoincrement=True,
        nullable=False,
        index=True,
    )
    detector_id = db.Column(db.String(40))
    run_type = db.Column(db.String(40))
    filename = db.Column(db.String(100))
    software_version = db.Column(db.String(40))
