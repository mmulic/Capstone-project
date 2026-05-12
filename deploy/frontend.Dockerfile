FROM node:20-alpine AS builder

WORKDIR /app

RUN apk add --no-cache python3 make g++ git

COPY . .

RUN rm -rf node_modules package.json package-lock.json && cat > package.json <<'EOF'
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

RUN npm install --no-audit --no-fund --legacy-peer-deps

ARG VITE_API_BASE_URL=""
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL

RUN NODE_OPTIONS="--max-old-space-size=2048" npm run build

FROM nginx:alpine AS runtime

RUN echo 'server { listen 80; server_name _; root /usr/share/nginx/html; index index.html; location / { try_files $uri $uri/ /index.html; } }' > /etc/nginx/conf.d/default.conf

COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
