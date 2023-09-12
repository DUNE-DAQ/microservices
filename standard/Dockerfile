FROM cern/alma9-base

# libaio and libnsl are needed when rpm is called on the Oracle client software 

RUN yum clean all \
  && yum -y install gcc make git libaio libnsl libpq-devel libffi-devel python3-pip python3-wheel \
  && yum clean all

RUN curl -O https://download.oracle.com/otn_software/linux/instantclient/1919000/oracle-instantclient19.19-basic-19.19.0.0.0-1.el9.x86_64.rpm \
  && rpm -iv oracle-instantclient19.19-basic-19.19.0.0.0-1.el9.x86_64.rpm

COPY requirements.txt /
RUN python3 -m pip install --upgrade setuptools && \
  python3 -m pip install -r requirements.txt && \
  python3 -m pip cache remove \*

# elisa_client_api needed by the logbook microservice
RUN git clone https://github.com/DUNE-DAQ/elisa_client_api.git && python3 -m pip install --upgrade setuptools && python3 -m pip install ./elisa_client_api 

# This ensures the container will run as non-root by default. Hat tip Pat Riehecky.
# [Commented out so various entrypoint.sh scripts as of Sep-12-2023 continue to work, to be addressed later]
# USER 60000:0

