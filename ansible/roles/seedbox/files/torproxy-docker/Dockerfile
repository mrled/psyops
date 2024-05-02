FROM debian:latest
RUN apt-get update && apt-get install -y \
    tor \
    && rm -rf /var/lib/apt/lists/*
EXPOSE 9050
USER debian-tor
CMD ["/usr/bin/tor", "-f", "/etc/tor/torrc"]
