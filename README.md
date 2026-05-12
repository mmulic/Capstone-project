# Disaster Assessment Backend

Production-grade backend for the **Automated Disaster Damage Assessment** system. Built with FastAPI, PostgreSQL/PostGIS, and integrates with Google Gemini Vision for AI-powered damage classification from aerial imagery.

**Status:** ✅ All 6 sprints complete (29/29 stories, 130/130 story points)

## What This Does

1. **Ingests** pre/post disaster aerial image pairs with EXIF/GPS extraction
2. **Classifies** damage using Google Gemini Vision (no_damage / minor / major / destroyed)
3. **Stores** geospatial data in PostgreSQL with PostGIS spatial indexing
4. **Serves** results via REST API with bounding-box queries for map overlay
5. **Powers** a chatbot using RAG retrieval over the prediction database
6. **Evaluates** model accuracy against FEMA ground-truth labels
7. **Deploys** to AWS ECS Fargate with auto-scaling and CloudWatch monitoring

## Architecture

```
app/
├── main.py                 # FastAPI entry — all routers + middleware
├── core/
│   ├── config.py           # Pydantic settings from .env
│   ├── database.py         # Async SQLAlchemy
│   ├── rate_limit.py       # Sliding window rate limiter
│   └── logging_config.py   # Structured JSON logging for CloudWatch
├── models/
│   └── models.py           # 8 SQLAlchemy tables
├── schemas/
│   └── schemas.py          # All Pydantic request/response types
├── services/
│   ├── s3_service.py            # S3 with local fallback
│   ├── image_preprocessor.py    # EXIF, normalization, pair matching
│   ├── prediction_service.py    # Abstract interface (ML implements)
│   ├── prediction_orchestrator.py  # Job queue, retries, concurrency
│   ├── geojson_service.py       # FeatureCollection builder
│   ├── rag_service.py           # 4-strategy RAG retrieval
│   ├── llm_service.py           # Abstract LLM interface (ML implements)
│   ├── fema_import.py           # CSV/JSON ground truth import
│   ├── evaluation_service.py    # Accuracy, F1, confusion matrix
│   └── auth_service.py          # JWT + bcrypt
└── routers/
    ├── health.py           # GET /health
    ├── ingest.py           # POST /api/ingest
    ├── batch_ingest.py     # POST /api/ingest/batch
    ├── geojson.py          # GET /api/geojson
    ├── predict.py          # POST /api/predict
    ├── results.py          # GET /api/results, /api/properties/{id}
    ├── chat.py             # POST /api/chat
    ├── stats.py            # GET /api/stats
    ├── evaluate.py         # POST /api/evaluate/import, GET /api/evaluate
    └── auth.py             # POST /api/auth/{register,login,refresh,me}

tests/
├── conftest.py             # Pytest fixtures
├── test_api.py             # Endpoint smoke tests
├── test_services.py        # Unit tests for services
├── test_rag.py             # RAG retrieval tests
└── integration/
    └── test_e2e.py         # End-to-end pipeline test

deploy/
└── ecs-task-definition.json    # AWS ECS Fargate task template

docs/
└── AWS_SETUP.md            # AWS provisioning guide

.github/workflows/
└── ci.yml                  # CI/CD: lint → test → build → push → deploy
```

## Quick Start

### Prerequisites
- Docker Desktop
- Git

### Local Setup (~3 minutes)

```bash
git clone https://github.com/mmulic/Capstone-project.git
cd Capstone-project
cp .env.example .env
docker-compose up --build
```

Open http://localhost:8000/docs for the interactive Swagger UI.

PostgreSQL + PostGIS starts automatically. **No AWS account needed for local dev** — S3 falls back to local filesystem storage.

### Run Migrations

```bash
docker-compose exec app alembic upgrade head
```

### Run Tests

```bash
docker-compose exec app pytest tests/ -v
```

### End-to-End Integration Test

```bash
docker-compose exec app python tests/integration/test_e2e.py http://localhost:8000
```

## API Endpoints

All 15 endpoints implemented:

| Method | Endpoint | Sprint | Description |
|--------|----------|--------|-------------|
| GET | `/health` | 1 | Health check |
| POST | `/api/ingest` | 2 | Upload pre/post image pair |
| POST | `/api/ingest/batch` | 2 | Bulk ZIP upload |
| GET | `/api/ingest/{job_id}/status` | 2 | Poll batch job |
| GET | `/api/geojson` | 2 | Damage data as GeoJSON |
| POST | `/api/predict` | 3 | Trigger VLM inference |
| GET | `/api/predict/{job_id}` | 3 | Poll prediction job |
| GET | `/api/results` | 3 | Query results with filters |
| GET | `/api/properties/{id}` | 3 | Property detail |
| POST | `/api/chat` | 4 | Chatbot query |
| GET | `/api/chat/{session_id}/history` | 4 | Chat history |
| GET | `/api/stats` | 4 | Dashboard stats |
| POST | `/api/evaluate/import` | 5 | Upload FEMA labels |
| GET | `/api/evaluate` | 5 | Run evaluation metrics |
| POST | `/api/auth/register` | 5 | Register user |
| POST | `/api/auth/login` | 5 | Get JWT tokens |
| POST | `/api/auth/refresh` | 5 | Refresh access token |
| GET | `/api/auth/me` | 5 | Current user info |

## ML Integration

The backend defines two abstract interfaces. The ML teammate implements them with Google Gemini.

### PredictionService
```python
# app/services/prediction_service.py
class BasePredictionService(ABC):
    async def predict(self, pre_image: bytes, post_image: bytes) -> PredictionResult:
        ...
```
Backend: orchestration, retries, DB storage, /api/predict
ML: Gemini Vision API client, prompt engineering

### LLMService
```python
# app/services/llm_service.py
class BaseLLMService(ABC):
    async def generate_response(self, message: str, context: str, history: list) -> str:
        ...
```
Backend: RAG retrieval, session management, /api/chat
ML: Gemini text generation, prompt construction

Both have working **mock implementations** so the entire backend runs without a Gemini API key. To integrate the real Gemini code: change one line at the bottom of each file.

## Production Deployment

See [`docs/AWS_SETUP.md`](docs/AWS_SETUP.md) for AWS provisioning steps.

### Required GitHub Secrets

For the CI/CD pipeline to deploy to AWS, set these in your repo's Settings → Secrets:

- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`

### Deploy Pipeline

Pushes to `main` automatically:
1. Run `ruff` linter
2. Run `pytest` against PostgreSQL
3. Build production Docker image
4. Push to Amazon ECR
5. Deploy to ECS Fargate (zero-downtime rolling update)

### Production Stack

| Service | Resource |
|---------|----------|
| Compute | ECS Fargate (2 tasks, auto-scaling) |
| Database | RDS PostgreSQL 16 + PostGIS, db.t4g.micro, Multi-AZ |
| Storage | S3 with versioning + lifecycle to Glacier (90 days) |
| Secrets | AWS Secrets Manager |
| Logging | CloudWatch Logs (14-day retention) |
| Monitoring | CloudWatch metrics + SNS alerts |
| CI/CD | GitHub Actions → ECR → ECS |

## Tech Stack

- **FastAPI** 0.115 — async Python web framework
- **PostgreSQL 16 + PostGIS** — spatial database
- **SQLAlchemy 2.0** — async ORM
- **Alembic** — database migrations
- **boto3** — AWS S3 with local filesystem fallback
- **Pillow** — image preprocessing + EXIF
- **python-jose + passlib** — JWT auth + bcrypt password hashing
- **pytest + httpx** — testing
- **Docker + docker-compose** — containerized dev

## Development

### Lint
```bash
ruff check app/
```

### Run a single test
```bash
pytest tests/test_services.py::test_haversine_distance -v
```

### Generate a new migration
```bash
docker-compose exec app alembic revision --autogenerate -m "description"
```

## Project Stats

- **29 stories** delivered across 6 sprints
- **130 story points** completed
- **24 Python source files**
- **~3,500 lines of code**
- **18 API endpoints**
- **8 database tables**
- **30+ unit tests**
