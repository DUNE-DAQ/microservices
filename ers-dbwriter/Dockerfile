FROM dunedaq/c8-minimal

RUN yum -y install python3-pip python3-devel libpq-devel gcc \
 && yum clean all

COPY requirements.txt dbwriter.py /

RUN python3 -m pip install --upgrade pip && python3 -m pip install -r /requirements.txt && pip cache remove *

USER 10000:0
ENTRYPOINT ["python3", "dbwriter.py"]
