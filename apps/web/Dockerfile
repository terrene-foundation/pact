# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
#
# CARE Platform — Next.js web frontend
# Multi-stage build: deps → builder → runner
# Requires next.config.js to have output: "standalone"

# ── Stage 1: deps ────────────────────────────────────────────────────────────
FROM node:20-alpine AS deps

# Install libc compatibility for native modules on Alpine
RUN apk add --no-cache libc6-compat

WORKDIR /app

# Copy dependency manifests only — leverages Docker layer cache
COPY package.json package-lock.json* ./

RUN npm ci --omit=dev

# ── Stage 2: builder ─────────────────────────────────────────────────────────
FROM node:20-alpine AS builder

WORKDIR /app

# Copy production deps from previous stage
COPY --from=deps /app/node_modules ./node_modules

# Copy full source for build
COPY . .

# Build the Next.js application
# NEXT_TELEMETRY_DISABLED suppresses telemetry during CI/container builds
ENV NEXT_TELEMETRY_DISABLED=1

RUN npm run build

# ── Stage 3: runner ──────────────────────────────────────────────────────────
FROM node:20-alpine AS runner

WORKDIR /app

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

# Create non-root user for security
RUN addgroup --system --gid 1001 nodejs \
    && adduser --system --uid 1001 nextjs

# Copy the standalone output produced by next build (requires output: "standalone")
# Public assets and static files are copied separately
COPY --from=builder /app/public ./public

# Adjust permissions on the .next directory for the nextjs user
RUN mkdir .next && chown nextjs:nodejs .next

COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs

# Expose the frontend port
EXPOSE 3000

# Health check — polls the Next.js server root
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD wget -qO- http://localhost:3000/ > /dev/null || exit 1

ENV PORT=3000
ENV HOSTNAME=0.0.0.0

# Run the standalone Next.js server (no next binary needed in this stage)
CMD ["node", "server.js"]
