FROM cern/cc7-base

RUN yum clean all \
    && yum -y install git \
    && yum -y install python3-pip \
    && yum -y install python3-devel \
    && yum  --enablerepo=cernonly -y install perl-Authen-Krb5.x86_64 \
    && yum  --enablerepo=cernonly -y install perl-WWW-CERNSSO-Auth.noarch \
    && yum clean all

COPY *.py elisaconf.json requirements.txt /
COPY get_ticket_np04daq.sh /

RUN pip3 install --upgrade pip
RUN pip3 install -r /requirements.txt
RUN mkdir -p ./logfiles
RUN git clone https://github.com/DUNE-DAQ/elisa_client_api.git
RUN pip3 install ./elisa_client_api

# EXPOSE 5005

COPY entrypoint.sh /
RUN ["chmod", "+x", "/entrypoint.sh"]
ENTRYPOINT ["/entrypoint.sh"]
