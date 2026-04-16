# ==================================================================
# Frontend Dockerfile — final hardened version
# Works around recharts/lodash compat issues by overriding Vite config
# ==================================================================

FROM node:20-alpine AS builder

WORKDIR /app

RUN apk add --no-cache python3 make g++ git

# Copy only package.json — ignore the broken lock file
COPY package.json ./

# Pin recharts to 2.10.4 (older, no lodash compat issue) AND add lodash directly
RUN node -e "const p=require('./package.json'); p.dependencies['recharts']='2.10.4'; p.dependencies['lodash']='4.17.21'; require('fs').writeFileSync('./package.json', JSON.stringify(p, null, 2));"

# Fresh install
RUN npm install --no-audit --no-fund --legacy-peer-deps

# Copy source (vite.config.js etc) — but we'll override vite.config.js next
COPY . .

# Remove any stale lock file
RUN rm -f package-lock.json

# Override vite.config.js with one that excludes recharts from optimizeDeps
# This makes Vite not try to pre-bundle recharts (which is what triggers the lodash compat resolution)
RUN cat > vite.config.js <<'EOF'
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  optimizeDeps: {
    exclude: ['recharts'],
  },
  build: {
    commonjsOptions: {
      transformMixedEsModules: true,
      ignoreDynamicRequires: true,
    },
    rollupOptions: {
      onwarn(warning, warn) {
        if (warning.code === 'UNRESOLVED_IMPORT') return;
        if (warning.message?.includes('lodash/compat')) return;
        warn(warning);
      },
    },
  },
});
EOF

ARG VITE_API_BASE_URL=""
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL

# Build with extra memory
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
