FROM docker.io/dbeaver/cloudbeaver:latest

WORKDIR /opt/cloudbeaver

EXPOSE 8978

VOLUME ["/opt/cloudbeaver/work"]

# Restrict the server to loopback only
COPY cloudbeaver.conf /opt/cloudbeaver/conf/cloudbeaver.conf

