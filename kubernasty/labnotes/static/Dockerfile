# Dockerfile for building a container that serves the labnotes.
# Assumes that it will be run from public/ after running "hugo build".
FROM nginx:latest
LABEL maintainer "me@micahrl.com"
ADD . /usr/share/nginx/html
