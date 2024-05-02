FROM alpine:latest
RUN apk add --no-cache privoxy && mv /etc/privoxy/config.new /etc/privoxy/config
CMD ["privoxy", "--no-daemon", "/etc/privoxy/config"]