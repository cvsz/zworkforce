FROM postgres:17-alpine

LABEL org.opencontainers.image.title="zwf/zpostgresql" \
      org.opencontainers.image.description="PostgreSQL 17 for zWorkforce ecosystem - global database image" \
      org.opencontainers.image.source="https://github.com/cvsz/zworkforce" \
      org.opencontainers.image.vendor="cvsz"

# Thailand timezone and minimal production tools
RUN apk add --no-cache tzdata curl && \
    ln -sf /usr/share/zoneinfo/Asia/Bangkok /etc/localtime && \
    echo "Asia/Bangkok" > /etc/timezone

# Production PostgreSQL configuration
COPY docker/postgres/postgresql.conf /etc/postgresql/postgresql.conf.production
COPY docker/postgres/pg_hba.conf /etc/postgresql/pg_hba.conf.production

# Database initialization scripts
COPY docker/postgres/docker-entrypoint-initdb.d/ /docker-entrypoint-initdb.d/

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
  CMD pg_isready -U "${POSTGRES_USER:-postgres}" -d "${POSTGRES_DB:-postgres}"

EXPOSE 5432
VOLUME ["/var/lib/postgresql/data"]
