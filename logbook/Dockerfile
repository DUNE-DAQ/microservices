FROM cern/cc7-base AS builder

EXPOSE 5005

RUN yum clean all \
 && yum update -y

#Some utilities needed to compile python
RUN yum install gcc -y \
 && yum install make -y \
 && yum install openssl-devel libffi-devel bzip2-devel -y

RUN curl https://www.python.org/ftp/python/3.9.10/Python-3.9.10.tgz > Python-3.9.10.tgz
RUN tar -zxvf Python-3.9.10.tgz 

WORKDIR /Python-3.9.10
RUN ./configure --enable-optimizations \
 && make altinstall \
 && /usr/local/bin/python3.9 -m pip install --upgrade pip
WORKDIR /

RUN yum install perl-Authen-Krb5.x86_64 -y \
 && yum install perl-WWW-CERNSSO-Auth.noarch -y 

COPY *.py elisaconf.json requirements.txt /
COPY elisa_client_api /elisa_client_api
COPY cern-get-sso-cookie /usr/local/bin

RUN pip install -r /requirements.txt \
 && pip install ./elisa_client_api \
 && mkdir -p ./logfiles
 && pip cache remove *

USER 10000:0
CMD ["python3.9", "logbook.py"]
