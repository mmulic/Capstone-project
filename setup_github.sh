#!/bin/bash
# ============================================
# GitHub Setup Script
# Run this ONCE after unzipping the project
# ============================================
#
# BEFORE RUNNING:
# 1. Create a new repo on GitHub:
#    - Go to https://github.com/new
#    - Name it: disaster-assessment-backend
#    - Set to Private
#    - Do NOT add README, .gitignore, or license (we have them already)
#    - Click "Create repository"
#
# 2. Copy your repo URL (looks like):
#    https://github.com/YOUR_USERNAME/disaster-assessment-backend.git
#
# 3. Run this script:
#    chmod +x setup_github.sh
#    ./setup_github.sh https://github.com/YOUR_USERNAME/disaster-assessment-backend.git
#
# ============================================

set -e

REPO_URL=$1

if [ -z "$REPO_URL" ]; then
    echo ""
    echo "❌ Please provide your GitHub repo URL"
    echo ""
    echo "Usage: ./setup_github.sh https://github.com/YOUR_USERNAME/disaster-assessment-backend.git"
    echo ""
    exit 1
fi

echo ""
echo "🚀 Setting up GitHub repo..."
echo "   Remote: $REPO_URL"
echo ""

# Initialize git
git init
git branch -M main

# Create .env from example (so it's not committed)
if [ ! -f .env ]; then
    cp .env.example .env
    echo "✅ Created .env from .env.example"
fi

# Stage all files
git add -A

# Initial commit
git commit -m "feat: Sprint 1 + Sprint 2 — Backend foundation and data ingestion pipeline

Sprint 1 (19 pts):
- FastAPI project structure (routers/models/services/schemas)
- PostgreSQL + PostGIS database (8 tables, Alembic migrations)
- S3 service with local filesystem fallback
- Docker + docker-compose local dev stack
- Pydantic schemas and SQLAlchemy models (full API contract)
- ML integration interfaces (PredictionService, LLMService)

Sprint 2 (21 pts):
- Image upload endpoint (POST /api/ingest) with full preprocessing
- Image preprocessing service (EXIF/GPS extraction, normalization, pair matching)
- GeoJSON generation service (GET /api/geojson with PostGIS spatial filtering)
- Batch ingest endpoint (POST /api/ingest/batch — ZIP upload with job tracking)

Total: 40 story points across 9 stories"

# Add remote and push
git remote add origin "$REPO_URL"
git push -u origin main

echo ""
echo "✅ Done! Your code is now on GitHub."
echo ""
echo "📋 Next steps:"
echo "   1. Go to $REPO_URL to verify"
echo "   2. Add your teammates as collaborators:"
echo "      Repo → Settings → Collaborators → Add people"
echo "   3. Set up branch protection (optional but recommended):"
echo "      Settings → Branches → Add rule → 'main'"
echo "      ✓ Require pull request reviews"
echo "      ✓ Require status checks (CI)"
echo ""
