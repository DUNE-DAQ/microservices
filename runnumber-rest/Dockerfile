FROM cern/cc7-base

RUN yum clean all \
 && yum -y install python3-pip \
 && yum -y install python3-devel \
 && yum --enablerepo=cernonly -y install oracle-instantclient12.1-devel \
 && yum --enablerepo=cernonly -y install oracle-instantclient-tnsnames.ora \
 && yum clean all

COPY authentication.py /
COPY credentials.py /
COPY rest.py /
COPY ./backends/. /backends/
COPY requirements.txt /

RUN pip3 install --upgrade pip
RUN pip3 install -r /requirements.txt

ENV LD_LIBRARY_PATH=/usr/lib/oracle/12.1/client64/lib/

COPY entrypoint.sh /
RUN ["chmod", "+x", "/entrypoint.sh"]
ENTRYPOINT ["/entrypoint.sh"]
