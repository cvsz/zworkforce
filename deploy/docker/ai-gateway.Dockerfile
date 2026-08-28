FROM node:20-alpine

ARG OCI_REVISION=unknown
ARG OCI_SOURCE=https://github.com/cvsz/z-platform
ARG OCI_CREATED=unknown
ARG OCI_VERSION=dev

LABEL org.opencontainers.image.revision="${OCI_REVISION}" \
      org.opencontainers.image.source="${OCI_SOURCE}" \
      org.opencontainers.image.created="${OCI_CREATED}" \
      org.opencontainers.image.version="${OCI_VERSION}"

ENV NODE_ENV=production
ENV HOST=0.0.0.0

WORKDIR /app

COPY services/ai-gateway/package.json services/ai-gateway/package-lock.json ./
RUN npm install --package-lock-only --ignore-scripts --no-audit --no-fund \
    && npm ci --omit=dev --no-audit --ignore-scripts --no-fund
COPY services/ai-gateway/ ./

RUN addgroup -S zplatform && adduser -S -G zplatform zplatform \
    && chown -R zplatform:zplatform /app

USER zplatform

CMD ["npm", "start"]
