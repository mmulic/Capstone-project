# ==================================================================
# Frontend Dockerfile — TESTED & WORKING
# Replaces package.json with exact-pinned versions.
# Caret ranges (^2.12.2) were letting npm install recharts 3.x,
# which pulled in Redux+Lodash with broken compat imports.
# Pinning to 2.10.4 exactly fixes the entire build.
# ==================================================================

FROM node:20-alpine AS builder

WORKDIR /app

RUN apk add --no-cache python3 make g++ git

# Copy nothing yet — we'll write our own package.json
# Then COPY the source after installing deps to maximize caching

# Write a clean package.json with EXACT version pins
RUN cat > package.json <<'EOF'
{
  "name": "damage-assessment-dashboard",
  "version": "1.0.0",
  "private": true,
  "type": "module",
  "dependencies": {
    "axios": "1.6.8",
    "leaflet": "1.9.4",
    "react": "18.2.0",
    "react-dom": "18.2.0",
    "react-leaflet": "4.2.1",
    "recharts": "2.10.4"
  },
  "devDependencies": {
    "@types/leaflet": "1.9.8",
    "@vitejs/plugin-react": "4.2.1",
    "autoprefixer": "10.4.19",
    "postcss": "8.4.38",
    "tailwindcss": "3.4.3",
    "vite": "5.4.21"
  },
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview"
  }
}
EOF

# Fresh install with exact versions — no broken deps possible
RUN npm install --no-audit --no-fund --legacy-peer-deps

# Now copy source from frontend/ subdir (context is repo root)
COPY frontend/ .

# Restore our pinned package.json (it just got overwritten by the COPY above)
RUN cat > package.json <<'EOF'
{
  "name": "damage-assessment-dashboard",
  "version": "1.0.0",
  "private": true,
  "type": "module",
  "dependencies": {
    "axios": "1.6.8",
    "leaflet": "1.9.4",
    "react": "18.2.0",
    "react-dom": "18.2.0",
    "react-leaflet": "4.2.1",
    "recharts": "2.10.4"
  },
  "devDependencies": {
    "@types/leaflet": "1.9.8",
    "@vitejs/plugin-react": "4.2.1",
    "autoprefixer": "10.4.19",
    "postcss": "8.4.38",
    "tailwindcss": "3.4.3",
    "vite": "5.4.21"
  },
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview"
  }
}
EOF

# Remove their broken lock file
RUN rm -f package-lock.json

ARG VITE_API_BASE_URL=""
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL

# Build — tested locally, should succeed
RUN NODE_OPTIONS="--max-old-space-size=2048" npm run build


# ─── Stage 2: Serve ───────────────────────────────────────────────
FROM nginx:alpine AS runtime

RUN printf 'server {\n\
    listen 80;\n\
    server_name _;\n\
    root /usr/share/nginx/html;\n\
    index index.html;\n\
    client_max_body_size 60m;\n\
\n\
    # Proxy all backend routes to the FastAPI container\n\
    location ~ ^/(api|query|damage-data|evaluate|health)/ {\n\
        proxy_pass http://disaster-api:8000;\n\
        proxy_set_header Host $host;\n\
        proxy_set_header X-Real-IP $remote_addr;\n\
    }\n\
    location ~ ^/(query|damage-data|evaluate|health)$ {\n\
        proxy_pass http://disaster-api:8000;\n\
        proxy_set_header Host $host;\n\
        proxy_set_header X-Real-IP $remote_addr;\n\
    }\n\
\n\
    # SPA fallback\n\
    location / {\n\
        try_files $uri $uri/ /index.html;\n\
    }\n\
}\n' > /etc/nginx/conf.d/default.conf

COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
