FROM node:22.22.2-alpine AS dependencies

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

FROM node:22.22.2-alpine AS builder

WORKDIR /app
COPY --from=dependencies /app/node_modules ./node_modules
COPY . .
RUN npm run lint && npm run typecheck && npm run test -- --run && npm run build

FROM node:22.22.2-alpine AS runner

ENV NODE_ENV=production
ENV HOSTNAME="0.0.0.0"
WORKDIR /app

COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static

EXPOSE 3000

CMD ["node", "server.js"]
