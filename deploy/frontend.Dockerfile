# ==================================================================
# Frontend Dockerfile (Vite + React + Tailwind)
# Stage 1: Build the production bundle with Vite
# Stage 2: Serve via Nginx
# ==================================================================
# This file lives in the frontend/ folder, copied here for reference.
# When deploying via docker-compose, the build context points to ./frontend.

# ─── Stage 1: Build ───────────────────────────────────────────────
FROM node:20-alpine AS builder

WORKDIR /app

# Install deps first (cached layer)
COPY package.json package-lock.json* ./
RUN npm ci --no-audit --no-fund

# Copy source and build
COPY . .

# VITE_API_BASE_URL can be set as a build arg
ARG VITE_API_BASE_URL=""
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL

RUN npm run build


# ─── Stage 2: Serve ───────────────────────────────────────────────
FROM nginx:alpine AS runtime

# Custom nginx config for SPA routing (all routes → index.html)
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
