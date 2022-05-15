FROM cern/cc7-base

RUN yum clean all \
 && yum install epel-release -y \
 && yum update -y

RUN yum groupinstall "Development Tools" -y \
 && yum install openssl-devel libffi-devel bzip2-devel -y \
 && yum install wget -y

RUN wget https://www.python.org/ftp/python/3.9.10/Python-3.9.10.tgz \
 && tar xvf Python-3.9.10.tgz 

WORKDIR /Python-3.9.10
RUN ./configure --enable-optimizations \
 && make altinstall \
 && /usr/local/bin/python3.9 -m pip install --upgrade pip
WORKDIR /

RUN yum install perl -y \
 && yum install perl-Authen-Krb5.x86_64 -y \
 && yum install perl-WWW-CERNSSO-Auth.noarch -y 

COPY authentication.py /
COPY elisaconf.json /
COPY logbook.py /
COPY credmgr.py /
COPY elisa.py /
COPY requirements.txt /
COPY elisa_client_api /elisa_client_api
COPY cern-get-sso-cookie /usr/local/bin

RUN pip install -r /requirements.txt
RUN pip install ./elisa_client_api
RUN mkdir -p ./logfiles

EXPOSE 5005
CMD ["python3.9", "logbook.py"]
