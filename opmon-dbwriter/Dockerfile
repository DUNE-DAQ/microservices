FROM dunedaq/c8-minimal

RUN yum -y install python3-pip python3-devel libpq-devel gcc \
 && yum clean all

COPY requirements.txt /
COPY kafka-to-influx.py /

RUN pip3 install -r requirements.txt

ENTRYPOINT ["python3", "kafka-to-influx.py"]
