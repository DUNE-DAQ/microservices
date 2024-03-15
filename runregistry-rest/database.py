from datetime import datetime

from api import db

__all__ = ['RunRegistryConfig', 'RunRegistryMeta']


class RunRegistryMeta(db.Model):
    run_number = db.Column(
        'run_number', db.Integer, primary_key=True, autoincrement=True, nullable=False
    )
    start_time = db.Column(
        'start_time', db.TIMESTAMP(6), nullable=False, default=datetime.now
    )
    stop_time = db.Column(
        'stop_time', db.TIMESTAMP(6), nullable=True
    )
    detector_id = db.Column(
        'detector_id', db.String(40)
    )
    run_type = db.Column(
        'run_type', db.String(40)
    )
    filename = db.Column(
        'filename', db.String(100)
    )
    software_version = db.Column(
        'software_version', db.String(40)
    )

class RunRegistryConfigs(db.Model):
    run_number = db.Column(
        'run_number', db.Integer,  primary_key=True, autoincrement=True, nullable=False
    )
    configuration = db.Column(
        'configuration', db.LargeBinary, nullable=False
    )