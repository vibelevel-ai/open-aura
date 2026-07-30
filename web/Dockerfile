# syntax=docker/dockerfile:1.7
# Open Aura viewer — Next.js host that renders @vibelevel/aura-ui. The build
# context is the REPO ROOT (it's an npm workspace: packages/aura-ui + web).
#   docker build -f web/Dockerfile .
FROM node:20-alpine AS build
WORKDIR /app
# Lockfile + workspace manifests first, for cached installs.
COPY package.json package-lock.json ./
COPY packages/aura-ui/package.json ./packages/aura-ui/package.json
COPY web/package.json ./web/package.json
RUN --mount=type=cache,target=/root/.npm \
    npm ci \
      --prefer-offline \
      --no-audit \
      --no-fund \
      --fetch-retries=5 \
      --fetch-retry-mintimeout=10000 \
      --fetch-retry-maxtimeout=60000 \
      --fetch-timeout=120000
# Sources, then build the web workspace.
COPY packages ./packages
COPY web ./web
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build -w open-aura-web

FROM node:20-alpine AS run
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1
COPY --from=build /app/node_modules ./node_modules
COPY --from=build /app/package.json ./package.json
COPY --from=build /app/packages ./packages
COPY --from=build /app/web ./web
EXPOSE 3000
WORKDIR /app/web
CMD ["npx", "next", "start", "-p", "3000"]
