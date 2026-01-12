# AristAI - AI-Assisted Classroom Forum

An AI-powered platform for synchronous classroom discussions with instructor copilot features.

## Features

- **Course Setup**: Upload syllabus and learning objectives
- **Session Planning**: AI generates session plans with topics, readings, cases, and checkpoints
- **Session Management**: Control session lifecycle (draft -> scheduled -> live -> completed)
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
├── api/                    # FastAPI application
│   ├── api/               # API routes
│   │   └── routes/        # Endpoint modules (courses, sessions, posts, polls, reports)
│   ├── core/              # Configuration, database
│   ├── models/            # SQLAlchemy ORM models
│   ├── schemas/           # Pydantic request/response schemas
│   └── services/          # Business logic (future)
├── workflows/             # LangGraph LLM workflows (planning, copilot, report)
├── worker/                # Celery worker and tasks
├── ui_streamlit/          # Streamlit UI
├── infra/                 # Infrastructure documentation
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
| PATCH | `/api/sessions/{id}/status` | Update session status (publish) |
| POST | `/api/sessions/{id}/case` | Post a case |
| POST | `/api/sessions/{id}/start_live_copilot` | Start copilot (async) |
| POST | `/api/sessions/{id}/stop_live_copilot` | Stop copilot |
| GET | `/api/sessions/{id}/copilot_status` | Check copilot status |
| GET | `/api/sessions/{id}/interventions` | Get interventions |
| GET | `/api/posts/session/{id}` | Get posts |
| POST | `/api/posts/session/{id}` | Create post |
| POST | `/api/posts/{id}/label` | Label a post |
| POST | `/api/posts/{id}/pin` | Pin/unpin a post |
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

---

## Milestone Validation

### Milestone 0: Project Skeleton & Runnable Environment

**Acceptance Criteria**: `docker compose up` runs everything; API health check OK.

**Validation Steps**:

```bash
# 1. Start all services
docker compose up --build -d

# 2. Wait for services to be ready (about 30 seconds)
sleep 30

# 3. Check API health
curl http://localhost:8000/health
# Expected: {"status":"ok"}

# 4. Run database migrations
docker compose exec api alembic upgrade head

# 5. Check database connection
curl http://localhost:8000/api/debug/db_check
# Expected: {"status":"ok","database":"connected"}

# 6. Test Celery worker
curl -X POST http://localhost:8000/api/debug/enqueue_test_task
# Expected: {"task_id":"<uuid>","message":"Test task queued"}

# 7. Verify Streamlit UI loads
curl -s http://localhost:8501 | grep -q "AristAI" && echo "UI OK"

# 8. Check OpenAPI docs
curl -s http://localhost:8000/docs | grep -q "swagger" && echo "Docs OK"
```

### Milestone 1: Course Setup + Planning Workflow

**Acceptance Criteria**: Given a syllabus, system generates N session plans aligned to objectives.

**Validation Steps**:

```bash
# 1. Create a course with syllabus
curl -X POST http://localhost:8000/api/courses/ \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Introduction to Machine Learning",
    "syllabus_text": "Week 1: Introduction to ML\nWeek 2: Supervised Learning\nWeek 3: Unsupervised Learning\nWeek 4: Neural Networks",
    "objectives_json": ["Understand ML fundamentals", "Apply supervised learning", "Implement clustering"]
  }'
# Note the course ID returned

# 2. Generate session plans (async)
curl -X POST http://localhost:8000/api/courses/1/generate_plans
# Returns task_id

# 3. Check task status (if DEBUG=true)
curl http://localhost:8000/api/debug/task_status/<task_id>

# 4. Verify session plans in UI
# Open http://localhost:8501, go to Sessions page, fetch session by ID
```

### Milestone 2: Forum Capture

**Acceptance Criteria**: A session contains a case and a stored discussion thread.

**Validation Steps**:

```bash
# 1. Create a user (instructor)
curl -X POST http://localhost:8000/api/users/ \
  -H "Content-Type: application/json" \
  -d '{"name": "Dr. Smith", "email": "smith@example.com", "role": "instructor"}'

# 2. Create a user (student)
curl -X POST http://localhost:8000/api/users/ \
  -H "Content-Type: application/json" \
  -d '{"name": "Alice", "email": "alice@example.com", "role": "student"}'

# 3. Create a session
curl -X POST http://localhost:8000/api/sessions/ \
  -H "Content-Type: application/json" \
  -d '{"course_id": 1, "title": "Week 1 Discussion"}'

# 4. Update session status to live (PUBLISH)
curl -X PATCH http://localhost:8000/api/sessions/1/status \
  -H "Content-Type: application/json" \
  -d '{"status": "live"}'
# Expected: Session with status "live"

# 5. Post a case
curl -X POST http://localhost:8000/api/sessions/1/case \
  -H "Content-Type: application/json" \
  -d '{"prompt": "A company wants to predict customer churn. What ML approach would you recommend?"}'

# 6. Post student replies
curl -X POST http://localhost:8000/api/posts/session/1 \
  -H "Content-Type: application/json" \
  -d '{"user_id": 2, "content": "I would use logistic regression for binary classification."}'

curl -X POST http://localhost:8000/api/posts/session/1 \
  -H "Content-Type: application/json" \
  -d '{"user_id": 2, "content": "Random Forest could also work well for this problem."}'

# 7. Pin/label posts (moderation)
curl -X POST http://localhost:8000/api/posts/1/pin \
  -H "Content-Type: application/json" \
  -d '{"pinned": true}'

curl -X POST http://localhost:8000/api/posts/1/label \
  -H "Content-Type: application/json" \
  -d '{"labels": ["high-quality"]}'

# 8. Verify posts
curl http://localhost:8000/api/posts/session/1

# 9. Complete session
curl -X PATCH http://localhost:8000/api/sessions/1/status \
  -H "Content-Type: application/json" \
  -d '{"status": "completed"}'
```

### Milestone 3: Post-Discussion Feedback Report

**Acceptance Criteria**: One click generates instructor + student summaries with evidence references.

**Validation Steps**:

```bash
# 1. Ensure session has posts (from Milestone 2)

# 2. Generate report (async)
curl -X POST http://localhost:8000/api/reports/session/1/generate
# Returns task_id

# 3. Wait for report generation (may take 30-60 seconds with LLM)
sleep 60

# 4. Get the report
curl http://localhost:8000/api/reports/session/1
# Expected: JSON with report_md, report_json containing themes, misconceptions, etc.

# 5. Verify in UI
# Open http://localhost:8501, go to Reports page, enter session ID, click "View Latest Report"
```

### Milestone 4: Live Instructor Copilot

**Acceptance Criteria**: While students post, instructor sees live prompts/flags/activities tied to current discussion.

**Validation Steps**:

```bash
# 1. Ensure session is live with some posts (from Milestone 2)
curl -X PATCH http://localhost:8000/api/sessions/1/status \
  -H "Content-Type: application/json" \
  -d '{"status": "live"}'

# 2. Start the live copilot (async)
curl -X POST http://localhost:8000/api/sessions/1/start_live_copilot
# Returns: {"task_id": "<uuid>", "status": "copilot_started"}

# 3. Add more student posts to trigger analysis
curl -X POST http://localhost:8000/api/posts/session/1 \
  -H "Content-Type: application/json" \
  -d '{"user_id": 2, "content": "I think neural networks are the same as decision trees."}'

curl -X POST http://localhost:8000/api/posts/session/1 \
  -H "Content-Type: application/json" \
  -d '{"user_id": 2, "content": "Can we use clustering for classification problems?"}'

# 4. Wait for copilot iteration (runs every 90 seconds)
sleep 100

# 5. Check copilot status
curl http://localhost:8000/api/sessions/1/copilot_status
# Expected: {"session_id": 1, "copilot_active": true, "task_id": "<uuid>"}

# 6. Fetch interventions
curl http://localhost:8000/api/sessions/1/interventions
# Expected: JSON array with structured suggestions containing:
# - rolling_summary
# - confusion_points (with evidence_post_ids)
# - instructor_prompts
# - reengagement_activity
# - poll_suggestion (optional)
# - overall_assessment

# 7. Stop copilot
curl -X POST http://localhost:8000/api/sessions/1/stop_live_copilot
# Expected: {"session_id": 1, "status": "stop_requested", "was_active": true}

# 8. Verify in UI
# Open http://localhost:8501, go to Forum page, click "View Interventions"
```

**Intervention Structure**:

Each intervention contains:
- `rolling_summary`: 2-3 sentence summary of recent discussion
- `confusion_points`: Array of identified misconceptions with `evidence_post_ids`
- `instructor_prompts`: 2-3 actionable prompts for the instructor
- `reengagement_activity`: Suggested activity (poll, quick write, think-pair-share)
- `poll_suggestion`: Optional poll question with 3-5 options
- `overall_assessment`: Engagement level, understanding level, discussion quality

## Smoke Test Checklist

After `docker compose up --build`:

1. **Health check**: `curl http://localhost:8000/health` returns `{"status":"ok"}`
2. **Swagger docs**: Open http://localhost:8000/docs - interactive API documentation
3. **Database**: `curl http://localhost:8000/api/debug/db_check` returns `{"status":"ok","database":"connected"}`
4. **Celery**: `curl -X POST http://localhost:8000/api/debug/enqueue_test_task` returns task_id
5. **Streamlit**: Open http://localhost:8501 - AristAI UI loads

## Session Status Lifecycle

Sessions follow this lifecycle:

```
draft -> scheduled -> live -> completed
  ^__________________________|
```

- **draft**: Initial state, session is being prepared
- **scheduled**: Session is ready but not yet live
- **live**: Discussion is active, students can post
- **completed**: Discussion ended, ready for report generation

Use `PATCH /api/sessions/{id}/status` or the Streamlit UI to transition between states.
