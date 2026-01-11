# AristAI - AI-Assisted Classroom Forum

An AI-powered platform for synchronous classroom discussions with instructor copilot features.

## Features

- **Course Setup**: Upload syllabus and learning objectives
- **Session Planning**: AI generates session plans with topics, readings, cases, and checkpoints
- **Forum**: Instructor posts cases, students discuss in real-time
- **Live Copilot**: Real-time suggestions for instructors during discussions
- **Feedback Reports**: Post-discussion analysis with themes, contributions, and misconceptions
- **Polls**: Interactive checkpoints with AI-suggested questions

## Tech Stack

- **Backend**: Python 3.11, FastAPI
- **Database**: PostgreSQL (required - see note below)
- **Task Queue**: Redis + Celery
- **LLM Workflows**: LangGraph
- **UI**: Streamlit (MVP)

> **Note**: This project requires PostgreSQL. The database migrations use PostgreSQL-specific features (`ENUM` types) and will not work with SQLite or other databases.

## Quick Start

```bash
# 1. Copy environment file and add your API keys
cp .env.example .env
# Edit .env to add OPENAI_API_KEY or ANTHROPIC_API_KEY

# 2. Start all services (this installs all dependencies including email-validator)
docker compose up --build

# 3. Run database migrations (first time only)
# An initial migration is provided in alembic/versions/001_initial_migration.py
docker compose exec api alembic upgrade head

# Access the services:
# - API: http://localhost:8000
# - API Docs (Swagger): http://localhost:8000/docs
# - Streamlit UI: http://localhost:8501
```

> **Important**: If running outside Docker, ensure you `pip install -r requirements.txt` first. The `email-validator` package is required for `/api/users/` endpoints to work (used by `pydantic.EmailStr`).

## Development with Hot Reload

```bash
# Use dev compose for hot reload (slower on Windows/macOS)
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build

# Or stable mode (no reload)
docker compose up --build
```

## Project Structure

```
aristai/
├── app/                    # FastAPI application
│   ├── api/               # API routes
│   │   └── routes/        # Endpoint modules (courses, sessions, posts, polls, reports)
│   ├── core/              # Configuration, database
│   ├── models/            # SQLAlchemy ORM models
│   ├── schemas/           # Pydantic request/response schemas
│   ├── services/          # Business logic (future)
│   └── workflows/         # LangGraph LLM workflows (planning, copilot, report)
├── worker/                # Celery worker and tasks
├── ui/                    # Streamlit UI
├── alembic/               # Database migrations
├── tests/                 # Test suite
├── docker-compose.yml     # Production-like compose
├── docker-compose.dev.yml # Dev overrides (hot reload)
├── Dockerfile             # API + Worker image
├── Dockerfile.streamlit   # UI image
├── requirements.txt       # Backend dependencies
└── requirements-ui.txt    # UI dependencies
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| POST | `/api/users/` | Create a user |
| GET | `/api/users/` | List users (optional role filter) |
| GET | `/api/users/{id}` | Get user |
| PATCH | `/api/users/{id}` | Update user |
| DELETE | `/api/users/{id}` | Delete user |
| POST | `/api/courses/` | Create a course |
| GET | `/api/courses/` | List courses |
| GET | `/api/courses/{id}` | Get course |
| POST | `/api/courses/{id}/generate_plans` | Generate session plans (async) |
| POST | `/api/sessions/` | Create a session |
| GET | `/api/sessions/{id}` | Get session |
| POST | `/api/sessions/{id}/case` | Post a case |
| POST | `/api/sessions/{id}/start_live_copilot` | Start copilot (async) |
| POST | `/api/sessions/{id}/stop_live_copilot` | Stop copilot |
| GET | `/api/sessions/{id}/copilot_status` | Check copilot status |
| GET | `/api/sessions/{id}/interventions` | Get interventions |
| GET | `/api/posts/session/{id}` | Get posts |
| POST | `/api/posts/session/{id}` | Create post |
| POST | `/api/posts/{id}/label` | Label a post |
| POST | `/api/polls/session/{id}` | Create poll |
| POST | `/api/polls/{id}/vote` | Vote on poll |
| GET | `/api/polls/{id}/results` | Get poll results |
| POST | `/api/reports/session/{id}/generate` | Generate report (async) |
| GET | `/api/reports/session/{id}` | Get report |

Debug endpoints (only when DEBUG=true):
- `GET /api/debug/db_check` - Check database
- `POST /api/debug/enqueue_test_task` - Test Celery
- `GET /api/debug/task_status/{id}` - Check task status

## Development Commands

```bash
# View logs
docker compose logs -f api worker

# Run migrations
docker compose exec api alembic revision --autogenerate -m "Description"
docker compose exec api alembic upgrade head

# Access database
docker compose exec db psql -U aristai -d aristai

# Run tests
docker compose exec api pytest

# Restart worker after code changes (if not using dev mode)
docker compose restart worker
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| DATABASE_URL | db:5432 (docker) | PostgreSQL connection |
| REDIS_URL | redis:6379 (docker) | Redis connection |
| OPENAI_API_KEY | - | OpenAI API key |
| ANTHROPIC_API_KEY | - | Anthropic API key |
| DEBUG | true (.env.example) | Enable debug endpoints |
| API_URL | http://api:8000 (docker) | API URL for Streamlit UI |

Note: For local dev outside Docker, use `localhost:5433` for DB and `localhost:6379` for Redis. See `.env.example` for details.

## Smoke Test Checklist

After `docker compose up --build`:

1. **Health check**: `curl http://localhost:8000/health` → `{"status":"ok"}`
2. **Swagger docs**: Open http://localhost:8000/docs
3. **Database**: `curl http://localhost:8000/api/debug/db_check` → `{"status":"ok","database":"connected"}`
4. **Celery**: `curl -X POST http://localhost:8000/api/debug/enqueue_test_task` → returns task_id
5. **Streamlit**: Open http://localhost:8501
