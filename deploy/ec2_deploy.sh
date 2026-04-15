#!/bin/bash
# ============================================================
# EC2 Full-Stack Deployment Script
# ============================================================
# Deploys frontend + backend + database on a single EC2 instance.
#
# Usage:
#   ssh -i key.pem ubuntu@YOUR_EC2_IP
#   wget https://raw.githubusercontent.com/mmulic/Capstone-project/ahmad/deploy/ec2_deploy.sh
#   chmod +x ec2_deploy.sh
#   ./ec2_deploy.sh
# ============================================================

set -e

REPO_URL="https://github.com/mmulic/Capstone-project.git"
BACKEND_BRANCH="ahmad"
FRONTEND_BRANCH="frontend"
WORK_DIR="$HOME/capstone"

echo ""
echo "🚀 Disaster Assessment Full-Stack Deployment"
echo "============================================"
echo ""

# ─── 1. System update ─────────────────────────────────────
echo "[1/7] Updating system packages..."
sudo apt-get update -qq
sudo apt-get upgrade -y -qq

# ─── 2. Install Docker ────────────────────────────────────
if command -v docker &> /dev/null; then
    echo "[2/7] Docker already installed"
else
    echo "[2/7] Installing Docker..."
    sudo apt-get install -y -qq ca-certificates curl gnupg
    sudo install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | \
        sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    sudo chmod a+r /etc/apt/keyrings/docker.gpg
    echo \
        "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
        https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
        sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
    sudo apt-get update -qq
    sudo apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    sudo usermod -aG docker $USER
fi

# ─── 3. Install Git ───────────────────────────────────────
if ! command -v git &> /dev/null; then
    echo "[3/7] Installing Git..."
    sudo apt-get install -y -qq git
else
    echo "[3/7] Git already installed"
fi

# ─── 4. Set up working directory ──────────────────────────
mkdir -p $WORK_DIR
cd $WORK_DIR

# ─── 5. Clone backend (from ahmad branch) ─────────────────
if [ -d "disaster-assessment-backend" ]; then
    echo "[4/7] Backend repo exists — pulling latest..."
    cd disaster-assessment-backend
    git fetch origin
    git checkout $BACKEND_BRANCH
    git pull origin $BACKEND_BRANCH
    cd ..
else
    echo "[4/7] Cloning backend ($BACKEND_BRANCH branch)..."
    git clone --branch $BACKEND_BRANCH $REPO_URL disaster-assessment-backend
fi

# ─── 6. Clone frontend (from frontend branch) ─────────────
if [ -d "frontend" ]; then
    echo "[5/7] Frontend repo exists — pulling latest..."
    cd frontend
    git fetch origin
    git checkout $FRONTEND_BRANCH
    git pull origin $FRONTEND_BRANCH
    # Frontend code is in /frontend folder of repo
    cd ..
else
    echo "[5/7] Cloning frontend ($FRONTEND_BRANCH branch)..."
    git clone --branch $FRONTEND_BRANCH $REPO_URL frontend-repo
    # Symlink the actual frontend folder so docker-compose paths work
    ln -sf frontend-repo/frontend frontend
fi

# ─── 7. Set up environment file ──────────────────────────
cd $WORK_DIR/disaster-assessment-backend
if [ ! -f .env ]; then
    echo "[6/7] Creating .env from template..."
    cp .env.example .env

    # Generate strong JWT secret
    JWT_SECRET=$(openssl rand -base64 32 | tr -d '\n')
    sed -i "s|JWT_SECRET_KEY=.*|JWT_SECRET_KEY=$JWT_SECRET|" .env

    echo "  ✓ .env created with random JWT secret"
    echo ""
    echo "  ⚠️  Edit .env to add:"
    echo "      - SUPABASE_DB_DSN (from ML teammate)"
    echo "      - GEMINI_API_KEY (when ML teammate provides it)"
    echo "      Run: nano $WORK_DIR/disaster-assessment-backend/.env"
else
    echo "[6/7] .env already exists — skipping"
fi

# ─── 8. Build and start ───────────────────────────────────
echo "[7/7] Building and starting full stack..."
sudo docker compose -f docker-compose.prod.yml up -d --build

echo ""
echo "⏳ Waiting for services to start..."
sleep 20

# Get public IP
PUBLIC_IP=$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4 2>/dev/null || echo "YOUR_PUBLIC_IP")

echo ""
echo "================================================"
echo "✅ Full-Stack Deployment Complete!"
echo "================================================"
echo ""
echo "🌐 Frontend (React app):    http://$PUBLIC_IP"
echo "📡 Backend API:              http://$PUBLIC_IP:8000"
echo "📖 Swagger docs:             http://$PUBLIC_IP:8000/docs"
echo "❤️  Health check:            http://$PUBLIC_IP:8000/health"
echo "🧠 ML bridge health:         http://$PUBLIC_IP:8000/api/ml/health"
echo ""
echo "🔍 Useful commands:"
echo "   sudo docker compose -f docker-compose.prod.yml logs -f         # All logs"
echo "   sudo docker compose -f docker-compose.prod.yml logs -f app     # Backend only"
echo "   sudo docker compose -f docker-compose.prod.yml logs -f frontend # Frontend only"
echo "   sudo docker compose -f docker-compose.prod.yml ps              # Container status"
echo "   sudo docker compose -f docker-compose.prod.yml restart         # Restart everything"
echo "   sudo docker compose -f docker-compose.prod.yml down            # Stop everything"
echo ""
echo "🔄 To update after pushing new code:"
echo "   cd $WORK_DIR/disaster-assessment-backend && git pull"
echo "   cd $WORK_DIR/frontend-repo && git pull"
echo "   cd $WORK_DIR/disaster-assessment-backend && sudo docker compose -f docker-compose.prod.yml up -d --build"
echo ""
