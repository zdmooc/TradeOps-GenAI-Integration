FROM node:22-alpine AS build
WORKDIR /src
COPY frontend/tradeops-ui/package.json ./package.json
RUN npm install --no-audit --no-fund
COPY frontend/tradeops-ui/ ./
RUN npm run build

FROM nginxinc/nginx-unprivileged:1.27-alpine
COPY --from=build /src/dist /usr/share/nginx/html
COPY frontend/tradeops-ui/nginx.conf /etc/nginx/templates/default.conf.template
ENV NGINX_ENVSUBST_FILTER="MCP_AGENT_TOKEN|MCP_REVIEWER_TOKEN"
USER 0
RUN chgrp -R 0 /usr/share/nginx/html /etc/nginx/templates /etc/nginx/conf.d /var/cache/nginx /var/run \
    && chmod -R g=u /usr/share/nginx/html /etc/nginx/templates /etc/nginx/conf.d /var/cache/nginx /var/run
USER 101
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 CMD wget -q -O - http://127.0.0.1:8080/healthz || exit 1
