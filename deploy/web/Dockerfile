FROM nginxinc/nginx-unprivileged:1.27.4-alpine
COPY deploy/nginx.conf /etc/nginx/conf.d/default.conf
COPY --chown=101:101 . /usr/share/nginx/html
RUN rm -f /usr/share/nginx/html/deploy/Dockerfile
EXPOSE 8080
USER 101
