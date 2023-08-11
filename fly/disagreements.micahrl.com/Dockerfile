# Dockerfile for running Remark42 on Fly.io with auto backups to S3

FROM umputun/remark42:latest

COPY start.sh /usr/local/bin/start.sh
COPY supervisord.conf /etc/supervisord.conf
COPY backup.sh /usr/local/bin/backup.sh

USER root
RUN true \
    && apk add --no-cache aws-cli supervisor \
    && mkdir -p /etc/backup.sh.d \
    && touch /etc/backup.sh.d/backup.env \
    && chown root:root /etc/backup.sh.d /etc/backup.sh.d/backup.env \
    && chmod 0700 /etc/backup.sh.d /etc/backup.sh.d/backup.env \
    && chmod 755 /usr/local/bin/start.sh /usr/local/bin/backup.sh \
    && echo "0 0 * * * /usr/local/bin/backup.sh" | crontab - \
    && true

ENTRYPOINT []
CMD ["/usr/local/bin/start.sh"]