from setuptools import setup

setup(name="connection-service",
     install_requires=[
       "Flask==2.0.3",
       "gevent==22.10.2",
       "gunicorn==20.1.0",
       "Werkzeug==2.0.3"
     ]
  )

