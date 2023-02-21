from setuptools import setup

setup(name="connection-service",
     install_requires=[
       "Flask",
       "gevent",
       "gunicorn",
       "Werkzeug"
     ]
  )

