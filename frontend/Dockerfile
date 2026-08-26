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
RUN npm ci --omit=dev
COPY --from=build /app/.next ./.next
COPY --from=build /app/next.config.ts ./
USER node
EXPOSE 3000
CMD ["npx", "next", "start", "-p", "3000"]
