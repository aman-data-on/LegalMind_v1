# LegalMind frontend — locked Step 39 (Next.js + TypeScript) and 55.1.
#
# Locked 38.22 / 52.1 r1: the frontend never touches the database. This image
# therefore carries no database driver and no connection string, and reaches the API
# over HTTP only.

FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY tsconfig.json next.config.ts vitest.config.ts ./
COPY src ./src
RUN npm run build

FROM node:22-alpine AS runtime
# Same reason as the backend image: the base tag floats behind Alpine's security
# fixes, and CI job 14 scans the built image. Upgrade at build time so the gate
# measures the image against today's fixes, not the tag's build date.
RUN apk upgrade --no-cache
WORKDIR /app
ENV NODE_ENV=production
COPY package.json package-lock.json ./
# Install, then REMOVE the package managers. The runtime needs `node` and nothing
# else to serve a built Next app, and npm/yarn each bundle their own dependency
# trees inside the base image — CI job 14's first frontend scan (2026-08-26) found
# 9 CRITICAL/HIGH there (node-tar gzip bomb, sigstore certificate acceptance,
# brace-expansion/picomatch ReDoS), none of them ours and none visible to
# `npm audit`, which only sees the lockfile. A package manager in a serving image
# is attack surface with no job; deleting it removes the whole finding class
# rather than chasing versions.
#
# The Playwright trio survives `--omit=dev` because Next declares `@playwright/test`
# as an OPTIONAL PEER and the root lists it as a devDependency — npm records the
# union as `devOptional`, which only `--omit=optional` would drop, and that flag
# would also strip Next's own SWC and sharp platform binaries. Removed by name
# instead: a browser-automation framework has no place in a serving image, and it
# is not required by Next at run time (optional peer).
RUN npm ci --omit=dev \
    && rm -rf node_modules/@playwright node_modules/playwright node_modules/playwright-core \
    && rm -rf /usr/local/lib/node_modules/npm /usr/local/bin/npm /usr/local/bin/npx \
              /opt/yarn* /usr/local/bin/yarn /usr/local/bin/yarnpkg \
    && rm -rf /root/.npm
COPY --from=build /app/.next ./.next
COPY --from=build /app/next.config.ts ./
USER node
EXPOSE 3000
# Direct `node` invocation of Next's own bin — no npx, since npm is gone.
CMD ["node", "node_modules/next/dist/bin/next", "start", "-p", "3000"]
