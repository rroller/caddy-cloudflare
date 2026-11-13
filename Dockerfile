ARG CADDY_BUILDER_IMAGE=caddy:2.11.9-builder
ARG CADDY_RUNTIME_IMAGE=caddy:2.11.9
FROM ${CADDY_BUILDER_IMAGE} AS builder
ARG CADDY_VERSION=2.11.9
ARG CLOUDFLARE_VERSION=v0.2.4
RUN xcaddy build "v${CADDY_VERSION}" \
    --with "github.com/caddy-dns/cloudflare@${CLOUDFLARE_VERSION}"

FROM ${CADDY_RUNTIME_IMAGE}
COPY --from=builder /usr/bin/caddy /usr/bin/caddy
