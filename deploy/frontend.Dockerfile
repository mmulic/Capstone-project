# ==================================================================
# Frontend Dockerfile (Vite + React + Tailwind)
# Hardened against frontend dependency issues.
# ==================================================================

# ─── Stage 1: Build ───────────────────────────────────────────────
FROM node:20-alpine AS builder

WORKDIR /app

# Install python+make for any node-gyp transitive deps
RUN apk add --no-cache python3 make g++ git

# Copy package.json only (NOT lock file — it's broken)
COPY package.json ./

# Pin recharts to a known-working version BEFORE install to override their version
# 2.12.7 is the last version without the lodash/compat import bug
RUN node -e "const p=require('./package.json'); p.dependencies['recharts']='2.12.7'; require('fs').writeFileSync('./package.json', JSON.stringify(p, null, 2));"

# Fresh install — generates a working lock file
RUN npm install --no-audit --no-fund --legacy-peer-deps

# Copy source and build
COPY . .

# Remove the old broken lock file if it got copied over
RUN rm -f package-lock.json

ARG VITE_API_BASE_URL=""
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL

# Build with extra memory in case of OOM
RUN NODE_OPTIONS="--max-old-space-size=2048" npm run build


# ─── Stage 2: Serve ───────────────────────────────────────────────
FROM nginx:alpine AS runtime

RUN echo 'server { \
    listen 80; \
    server_name _; \
    root /usr/share/nginx/html; \
    index index.html; \
    location / { \
        try_files $uri $uri/ /index.html; \
    } \
}' > /etc/nginx/conf.d/default.conf

COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
