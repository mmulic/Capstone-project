# Disaster Assessment Backend

Backend API for the **Automated Disaster Damage Assessment** system. Built with FastAPI, PostgreSQL/PostGIS, and designed to integrate with Google Gemini Vision for damage classification.

## Architecture

```
app/
├── main.py              # FastAPI app entry point
├── core/
│   ├── config.py        # Pydantic settings (env vars)
│   └── database.py      # Async SQLAlchemy engine + session
├── models/
│   └── models.py        # SQLAlchemy ORM models (all tables)
├── schemas/
│   └── schemas.py       # Pydantic request/response schemas
├── services/
│   ├── s3_service.py    # S3 file storage (with local fallback)
│   ├── prediction_service.py  # ML interface (mock + abstract)
│   └── llm_service.py   # Chatbot LLM interface (mock + abstract)
├── routers/
│   ├── health.py        # GET /health
│   ├── ingest.py        # POST /api/ingest
│   └── stubs.py         # Future endpoints (visible in Swagger)
alembic/                 # Database migrations
docker-compose.yml       # Local dev stack
Dockerfile
```

## Quick Start

### Prerequisites
- Docker & Docker Compose

### Setup (< 5 minutes)

```bash
# 1. Clone and enter the project
git clone <repo-url>
cd disaster-assessment-backend

# 2. Create your .env file
cp .env.example .env

# 3. Start everything
docker-compose up --build

# 4. Open Swagger docs
open http://localhost:8000/docs
```

That's it. PostgreSQL + PostGIS starts automatically. No AWS account needed for local dev.

### Run Migrations

```bash
docker-compose exec app alembic upgrade head
```

### Generate a New Migration

```bash
docker-compose exec app alembic revision --autogenerate -m "description"
```

## API Endpoints

| Method | Endpoint | Status | Sprint |
|--------|----------|--------|--------|
| GET | `/health` | ✅ Done | 1 |
| POST | `/api/ingest` | ✅ Done | 1-2 |
| POST | `/api/ingest/batch` | ✅ Done | 2 |
| GET | `/api/ingest/{job_id}/status` | ✅ Done | 2 |
| GET | `/api/geojson` | ✅ Done | 2 |
| POST | `/api/predict` | 🔲 Stub | 3 |
| GET | `/api/results` | 🔲 Stub | 3 |
| GET | `/api/properties/{id}` | 🔲 Stub | 3 |
| GET | `/api/stats` | 🔲 Stub | 4 |
| POST | `/api/chat` | 🔲 Stub | 4 |
| GET | `/api/evaluate` | 🔲 Stub | 5 |
| POST | `/api/auth/login` | 🔲 Stub | 5 |
| POST | `/api/auth/register` | 🔲 Stub | 5 |

## ML Integration

The backend defines two abstract interfaces for the ML person to implement:

### PredictionService (`app/services/prediction_service.py`)
```python
class BasePredictionService(ABC):
    async def predict(self, pre_image: bytes, post_image: bytes) -> PredictionResult:
        ...
```

### LLMService (`app/services/llm_service.py`)
```python
class BaseLLMService(ABC):
    async def generate_response(self, message: str, context: str, history: list) -> str:
        ...
```

Both have mock implementations for development. Swap to real Gemini implementations by changing the singleton at the bottom of each file.

## Tech Stack

- **FastAPI** — async Python web framework
- **PostgreSQL 16 + PostGIS** — spatial database
- **SQLAlchemy 2.0** — async ORM
- **Alembic** — database migrations
- **boto3** — AWS S3 (with local filesystem fallback)
- **Docker** — containerized development
