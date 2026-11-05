# syntax=docker/dockerfile:1
# Preuve web image (Phase 5D): Next.js standalone server, non-root.
# PREUVE_API_INTERNAL_URL is compiled into the build (rewrites are part of the build output),
# so build with the API's address as the web container sees it.

ARG NODE_IMAGE=node:22-alpine

# ---------- dependencies from the lockfile (pnpm's supply-chain checks stay on) ----------
FROM ${NODE_IMAGE} AS deps
WORKDIR /srv/web
RUN corepack enable
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile

# ---------- build ----------
FROM deps AS build
COPY . .
ARG PREUVE_API_INTERNAL_URL=http://api:8000
ENV PREUVE_API_INTERNAL_URL=${PREUVE_API_INTERNAL_URL} \
    NEXT_OUTPUT=standalone \
    NEXT_TELEMETRY_DISABLED=1
RUN mkdir -p public && pnpm build

# ---------- runtime ----------
FROM ${NODE_IMAGE} AS runtime
RUN addgroup -S -g 10001 preuve && adduser -S -u 10001 -G preuve -h /srv/web preuve
WORKDIR /srv/web
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    HOSTNAME=0.0.0.0 \
    PORT=3000
COPY --from=build --chown=preuve:preuve /srv/web/.next/standalone ./
COPY --from=build --chown=preuve:preuve /srv/web/.next/static ./.next/static
COPY --from=build --chown=preuve:preuve /srv/web/public ./public
USER preuve
EXPOSE 3000
HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=5 \
  CMD wget -q -O /dev/null http://127.0.0.1:3000/login || exit 1
CMD ["node", "server.js"]
