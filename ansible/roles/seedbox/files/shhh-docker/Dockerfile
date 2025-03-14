FROM debian:latest
VOLUME ["/config"]
RUN apt-get update && apt-get install -y \
    curl \
    libicu72 \
    python3 \
    python3-pip \
    sqlite3 \
    tzdata \
    wget \
    && true
RUN true \
    && cd /opt \
    && W="$(echo Juvfcnee | tr 'A-Za-z' 'N-ZA-Mn-za-m')" \
    && wget --content-disposition "http://$W.servarr.com/v1/update/nightly/updatefile?os=linux&runtime=netcore&arch=x64" \
    && tar -xvzf ${W}*.linux*.tar.gz \
    && rm ${W}*.linux*.tar.gz \
    && mv ${W} Juvfcnee \
    && true
RUN true \
    && cd /opt/Juvfcnee \
    && ln -s /config .config \
    && true
COPY "entrypoint.sh" "/usr/local/sbin/entrypoint.sh"
ENTRYPOINT ["/usr/local/sbin/entrypoint.sh"]

