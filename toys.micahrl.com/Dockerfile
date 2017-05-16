FROM httpd:2.4-alpine
LABEL maintainer "me@micahrl.com"
COPY ["httpd.conf", "/usr/local/apache2/conf/httpd.conf"]
EXPOSE 80
CMD ["httpd-foreground"]
