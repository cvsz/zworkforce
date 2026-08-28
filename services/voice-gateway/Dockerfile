FROM node:22.16.0-alpine3.22

ARG OCI_REVISION=unknown
ARG OCI_SOURCE=https://github.com/cvsz/z-platform
ARG OCI_CREATED=unknown
ARG OCI_VERSION=dev

LABEL org.opencontainers.image.revision="${OCI_REVISION}" \
      org.opencontainers.image.source="${OCI_SOURCE}" \
      org.opencontainers.image.created="${OCI_CREATED}" \
      org.opencontainers.image.version="${OCI_VERSION}"

ENV NODE_ENV=production \
    HOST=0.0.0.0 \
    PORT=8450

WORKDIR /app
COPY --chown=node:node index.mjs ./index.mjs

USER node
EXPOSE 8450
CMD ["node", "index.mjs"]
