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
- **UI**: Streamlit

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

## Streamlit UI Guide

The Streamlit UI provides a complete interface for managing courses, sessions, discussions, and reports. Access it at **http://localhost:8501** after running `docker compose up`.

### Pages Overview

| Page | Purpose |
|------|---------|
| **Courses** | Create courses with syllabus + objectives, trigger plan generation |
| **Sessions** | View session plans, create sessions, manage status (draft→live→completed) |
| **Forum** | Post cases, view discussion thread, post replies, moderate posts |
| **Instructor Console** | Live copilot suggestions, poll management, quick actions |
| **Reports** | Generate reports, view formatted/raw markdown, export, observability panel |

### Typical Workflow

1. **Setup Course** (Courses page)
   - Paste syllabus text
   - Add learning objectives (one per line)
   - Click "Create & Generate Plans" to auto-generate session plans

2. **Start a Session** (Sessions page)
   - Load a session by ID
   - View the AI-generated plan (topics, goals, case study, discussion prompts)
   - Click "Go Live" to start the session

3. **Run Discussion** (Forum page)
   - Post a case study for students
   - Students post replies (use different user IDs)
   - Moderate: pin important posts, label as high-quality or needs-clarification

4. **Use Copilot** (Instructor Console)
   - Click "Start Copilot" to begin real-time analysis (runs every 90 seconds)
   - View suggestions: rolling summary, confusion points, instructor prompts
   - Create polls from AI suggestions with one click
   - Monitor poll results in real-time

5. **Generate Report** (Reports page)
   - Click "Generate Report" after discussion ends
   - View formatted report with themes, misconceptions, best practices
   - Export as markdown
   - Check observability panel: model name, prompt version, execution time

### Instructor Console Features

The Instructor Console provides real-time support during live sessions:

**Live Copilot Tab:**
- Start/Stop copilot (runs every 90 seconds)
- View rolling discussion summary
- See confusion points with severity (🔴 high / 🟡 medium / 🟢 low)
- Get 2-3 actionable instructor prompts
- Suggested re-engagement activities
- One-click poll creation from AI suggestions
- Overall assessment: engagement, understanding, discussion quality

**Polls Tab:**
- Create polls manually
- View poll results with bar charts
- See vote counts and percentages

**Quick Actions Tab:**
- Go Live / End Session buttons
- Generate feedback report

### Report Observability Panel

Each report includes an observability summary showing:
- **Model**: Which LLM generated the report (gpt-4o-mini, claude-3-haiku, or fallback)
- **Prompt Version**: Version of prompts used
- **Execution Time**: How long report generation took
- **Report ID**: Database identifier

If you see "fallback" mode, it means no LLM API key was configured and default responses were used.

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

### Milestone 5: Poll Results as Classroom Evidence

**Acceptance Criteria**: Poll results are automatically included in reports as classroom state evidence.

**Validation Steps**:

```bash
# 1. Create a poll during a live session
curl -X POST http://localhost:8000/api/polls/session/1 \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Which ML approach is best for customer churn prediction?",
    "options_json": ["Logistic Regression", "Random Forest", "Neural Network", "Unsupervised Clustering"]
  }'
# Note the poll ID returned

# 2. Cast some votes
curl -X POST http://localhost:8000/api/polls/1/vote \
  -H "Content-Type: application/json" \
  -d '{"user_id": 2, "option_index": 0}'

curl -X POST http://localhost:8000/api/polls/1/vote \
  -H "Content-Type: application/json" \
  -d '{"user_id": 3, "option_index": 1}'

# 3. Check poll results
curl http://localhost:8000/api/polls/1/results
# Expected: {"poll_id": 1, "question": "...", "options": [...], "vote_counts": [...], "total_votes": 2}

# 4. Generate report (polls are automatically included)
curl -X POST http://localhost:8000/api/reports/session/1/generate

# 5. Wait and fetch report
sleep 60
curl http://localhost:8000/api/reports/session/1
# Expected: report_json contains "poll_results" section with:
# - question
# - total_votes
# - options (with votes, percentage)
# - interpretation (AI-generated analysis)

# 6. Verify in UI
# Open Reports page, go to "JSON Data" tab
# Expand "Poll Results (Embedded)" section
```

**Poll Evidence Structure**:

```json
{
  "poll_results": [
    {
      "poll_id": 1,
      "question": "Which ML approach is best for customer churn prediction?",
      "total_votes": 25,
      "options": [
        {"text": "Logistic Regression", "votes": 12, "percentage": 48.0},
        {"text": "Random Forest", "votes": 8, "percentage": 32.0},
        {"text": "Neural Network", "votes": 3, "percentage": 12.0},
        {"text": "Unsupervised Clustering", "votes": 2, "percentage": 8.0}
      ],
      "interpretation": "Class strongly favors Logistic Regression, showing good understanding of supervised classification approaches."
    }
  ]
}
```

### Milestone 6: Observability & Evaluation

**Acceptance Criteria**: All LLM calls track execution time, tokens, cost. Rolling summary controls token usage. Golden set evaluation available.

#### Observability Fields

All workflows (reports, copilot, session planning) now track:

| Field | Description |
|-------|-------------|
| `execution_time_seconds` | Time taken to generate response |
| `total_tokens` | Total tokens used (prompt + completion) |
| `prompt_tokens` | Tokens in the prompt |
| `completion_tokens` | Tokens in the response |
| `estimated_cost_usd` | Estimated cost based on model pricing |
| `error_message` | Error description if generation failed |
| `retry_count` | Number of retry attempts |
| `used_fallback` | 1 if fallback mode was used (no LLM) |

**Validation Steps**:

```bash
# 1. Generate a report
curl -X POST http://localhost:8000/api/reports/session/1/generate
sleep 60

# 2. Check observability fields
curl http://localhost:8000/api/reports/session/1
# Expected response includes:
# - execution_time_seconds
# - total_tokens
# - prompt_tokens
# - completion_tokens
# - estimated_cost_usd
# - model_name
# - used_fallback

# 3. Check intervention observability
curl http://localhost:8000/api/sessions/1/interventions
# Each intervention includes observability fields

# 4. Verify in UI
# Open Reports page, check "Observability Summary" panel
# Shows: Model, Execution Time, Tokens Used, Estimated Cost
```

#### Token Control: Rolling Summary

For long discussions, the system uses rolling summary to control token usage:

- **Recent posts**: Last N posts (configurable, default 20) are included in full
- **Older posts**: Summarized into a brief context paragraph
- **Benefit**: Prevents token explosion while maintaining context

This is automatically applied in both copilot and report workflows.

#### Golden Set Evaluation

A golden set evaluation harness is provided for testing LLM output quality.

**Location**: `tests/golden_sets/`

**Files**:
- `sample_data.py` - Sample inputs and expected output structures
- `evaluator.py` - Evaluation harness with scoring logic
- `test_workflows.py` - pytest integration tests

**Sample Categories**:

| Workflow | Samples | Purpose |
|----------|---------|---------|
| Session Planning | 3 | Test plan generation quality |
| Live Copilot | 3 | Test real-time intervention quality |
| Report Generation | 2 | Test report structure and evidence |

**Running Evaluations**:

```bash
# Run offline evaluation (validates test structure)
python -m tests.golden_sets.evaluator

# Run with verbose output
python -m tests.golden_sets.evaluator --verbose

# Evaluate specific workflow
python -m tests.golden_sets.evaluator --workflow copilot

# Evaluate specific sample
python -m tests.golden_sets.evaluator --sample-id planning_001

# Run pytest unit tests
pytest tests/golden_sets/test_workflows.py -v
```

**Evaluation Metrics**:

Each sample is scored on:

1. **Structure Score (60%)**: Required keys present, minimum counts met
2. **Quality Score (40%)**: Keyword presence, evidence citation, appropriate responses

**Pass threshold**: 70% overall score

**Sample Output**:

```
============================================================
GOLDEN SET EVALUATION REPORT
============================================================
Timestamp: 2025-01-11T12:00:00
Mode: offline

OVERALL METRICS
----------------------------------------
Total Samples:       8
Passed:              8 (100.0%)
Failed:              0

Avg Structure Score: 100.0%
Avg Quality Score:   100.0%
Avg Overall Score:   100.0%

SESSION_PLANNING WORKFLOW
----------------------------------------
  [PASS] planning_001: Ethics Case Discussion
         Structure: 100.0% | Quality: 100.0% | Overall: 100.0%
  [PASS] planning_002: Healthcare Decision Making
         Structure: 100.0% | Quality: 100.0% | Overall: 100.0%
  ...
============================================================
```

**Extending Golden Sets**:

To add new test cases, edit `tests/golden_sets/sample_data.py`:

```python
{
    "id": "copilot_004",
    "name": "New Test Case",
    "input": {
        "session_title": "...",
        "session_plan": {...},
        "posts": [...]
    },
    "expected_structure": {
        "required_keys": ["rolling_summary", "confusion_points"],
        "confusion_points_min_count": 1,
    },
    "quality_criteria": {
        "should_cite_evidence": True,
    }
}
```

---

## Cost Estimates

Based on model pricing (as of January 2025):

| Model | Prompt (per 1M tokens) | Completion (per 1M tokens) |
|-------|------------------------|---------------------------|
| gpt-4o-mini | $0.15 | $0.60 |
| gpt-4o | $2.50 | $10.00 |
| claude-3-haiku | $0.25 | $1.25 |
| claude-3-5-sonnet | $3.00 | $15.00 |

**Typical costs per operation**:
- Session planning: ~1,000-2,000 tokens → $0.001-0.003
- Copilot iteration: ~1,500-3,000 tokens → $0.002-0.005
- Report generation: ~3,000-5,000 tokens → $0.003-0.008

*Note: Actual costs vary based on discussion length and model choice.*
