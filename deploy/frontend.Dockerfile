# ==================================================================
# Frontend Dockerfile — surgical fix
# Removes MetricsPage (the only file using recharts) so the broken
# transitive deps never get pulled in. Frontend still has Map, Chat,
# Landing, Overview pages — fully demoable.
# ==================================================================

FROM node:20-alpine AS builder

WORKDIR /app

RUN apk add --no-cache python3 make g++ git

# Copy only package.json (NOT lock file)
COPY package.json ./

# Strip recharts entirely from package.json — no longer needed
RUN node -e "const p=require('./package.json'); delete p.dependencies['recharts']; require('fs').writeFileSync('./package.json', JSON.stringify(p, null, 2));"

# Fresh install with no broken deps
RUN npm install --no-audit --no-fund --legacy-peer-deps

# Copy source
COPY . .

# Remove broken lock file
RUN rm -f package-lock.json

# ─── Surgical removal of MetricsPage ──────────────────────
# 1. Delete the MetricsPage file
RUN rm -f src/pages/MetricsPage.jsx

# 2. Patch App.jsx to remove import + usage
RUN sed -i '/import MetricsPage/d' src/App.jsx && \
    sed -i 's|{currentPage === "metrics"[^}]*&& <MetricsPage />}|{currentPage === "metrics" \&\& <div className="flex-1 flex items-center justify-center text-gray-500">Metrics page coming soon</div>}|g' src/App.jsx

ARG VITE_API_BASE_URL=""
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL

# Build
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
