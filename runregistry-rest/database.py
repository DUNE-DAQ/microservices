from datetime import datetime

from api import db

__all__ = ["RunNumber", "RunRegistryConfig", "RunRegistryMeta"]


class RunNumber(db.Model):
    run_number = db.Column(
        "run_number",
        db.Integer,
        primary_key=True,
        autoincrement=True,
        nullable=False,
        index=True,
    )
    flag = db.Column("flag", db.Boolean, nullable=False, default=False)
    start_time = db.Column(
        "start_time", db.TIMESTAMP(6), nullable=False, default=datetime.now
    )
    stop_time = db.Column("stop_time", db.TIMESTAMP(6), nullable=True)


class RunRegistryConfig(db.Model):
    run_number = db.Column(
        "run_number",
        db.Integer,
        db.ForeignKey(RunNumber.run_number),
        primary_key=True,
        autoincrement=True,
        nullable=False,
        index=True,
    )
    configuration = db.Column("configuration", db.LargeBinary, nullable=False)


class RunRegistryMeta(db.Model):
    run_number = db.Column(
        "run_number",
        db.Integer,
        db.ForeignKey(RunNumber.run_number),
        primary_key=True,
        autoincrement=True,
        nullable=False,
        index=True,
    )
    detector_id = db.Column("detector_id", db.String(40))
    run_type = db.Column("run_type", db.String(40))
    filename = db.Column("filename", db.String(100))
    software_version = db.Column("software_version", db.String(40))
