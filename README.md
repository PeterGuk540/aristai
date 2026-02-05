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
- **Role-Based UI**: Different views for instructors vs students
- **Enrollment Management**: Track which students are enrolled in which courses
- **Participation Tracking**: See who participated and who didn't in reports
- **Answer Scoring**: AI scores student responses against best-practice answers

## Architecture

```
┌─────────────────┐      ┌─────────────────┐      ┌─────────────────┐
│  Next.js        │      │  FastAPI        │      │  PostgreSQL     │
│  Frontend       │─────▶│  Backend        │─────▶│  Database       │
│  (Vercel)       │      │  (EC2:8000)     │      │  (EC2)          │
└─────────────────┘      └────────┬────────┘      └─────────────────┘
                                  │
                         ┌────────▼────────┐
                         │  LangGraph      │
                         │  AI Workflows   │
                         │  (Claude API)   │
                         └─────────────────┘

┌─────────────────┐      ┌─────────────────┐
│  MCP Clients    │─────▶│  MCP Server     │
│  (Claude, etc.) │      │  (mcp_server)   │
└─────────────────┘      └────────┬────────┘
                                  │
                         ┌────────▼────────┐
                         │  FastAPI        │
                         │  Backend        │
                         └─────────────────┘
```

## Tech Stack

**Backend:**
- Python 3.11, FastAPI
- PostgreSQL (required - uses PostgreSQL-specific ENUM types)
- Redis + Celery (task queue)
- LangGraph (LLM workflow orchestration)
- Anthropic Claude API (LLM)
- Model Context Protocol (MCP) server for tool-based access

**Frontend:**
- Next.js 14 (App Router)
- TypeScript
- Tailwind CSS
- Deployed on Vercel

**Authentication:**
- AWS Cognito (email/password)
- Google OAuth
- Microsoft OAuth

**Legacy UI:**
- Streamlit (still available at port 8501)

> **Note**: This project requires PostgreSQL. The database migrations use PostgreSQL-specific features (`ENUM` types) and will not work with SQLite or other databases.

---

## Deployment Options

### Option 1: Full Stack on EC2 (Development/Testing)

```bash
# 1. Copy environment file and add your API keys
cp .env.example .env
# Edit .env to add ANTHROPIC_API_KEY

# 2. Start all services
docker compose up --build

# 3. Run database migrations (first time only)
docker compose exec api alembic upgrade head

# Access the services:
# - API: http://localhost:8000
# - API Docs (Swagger): http://localhost:8000/docs
# - Streamlit UI: http://localhost:8501
```

### Option 2: Vercel Frontend + EC2 Backend (Production)

This is the recommended production setup:

**Backend (EC2):**
```bash
# On EC2 instance
docker compose up --build -d
docker compose exec api alembic upgrade head
```

**Frontend (Vercel):**
1. Connect your GitHub repo to Vercel
2. Set **Root Directory** to `frontend`
3. Add environment variable: `BACKEND_API_URL=http://<your-ec2-ip>:8000`
4. Deploy

**EC2 Security Group:**
- Open port 8000 to `0.0.0.0/0` for Vercel access

The frontend uses an API proxy (`/api/proxy/[...path]`) to route requests to the EC2 backend, avoiding CORS and mixed-content issues.

---

## Project Structure

```
aristai/
├── api/                    # FastAPI backend
│   ├── api/               # API routes
│   │   └── routes/        # Endpoint modules
│   ├── core/              # Configuration, database
│   ├── models/            # SQLAlchemy ORM models
│   ├── schemas/           # Pydantic schemas
│   └── services/          # Business logic
├── frontend/              # Next.js frontend (Vercel)
│   ├── src/
│   │   ├── app/           # Pages (App Router)
│   │   │   ├── courses/   # Course management
│   │   │   ├── sessions/  # Session management
│   │   │   ├── forum/     # Discussion forum
│   │   │   ├── console/   # Instructor console
│   │   │   ├── reports/   # Session reports
│   │   │   └── api/proxy/ # API proxy route
│   │   ├── components/    # React components
│   │   ├── lib/           # API client, utilities
│   │   └── types/         # TypeScript types
│   ├── package.json
│   └── tailwind.config.js
├── workflows/             # LangGraph LLM workflows
├── worker/                # Celery worker and tasks
├── ui_streamlit/          # Legacy Streamlit UI
├── mcp_server/            # MCP server (tool registry + voice control)
├── alembic/               # Database migrations
├── tests/                 # Test suite
├── docker-compose.yml     # Docker services
└── requirements.txt       # Python dependencies
```

---

## Frontend Pages

### Courses (`/courses`)
- **Courses Tab**: View all courses with syllabus and objectives
- **Create Tab** (instructor): Create new course, optionally generate AI plans
- **Enrollment Tab** (instructor): Manage student enrollment

### Sessions (`/sessions`)
- View sessions by course
- See AI-generated session plans (topics, goals, case studies, discussion prompts)
- **Instructor**: Create sessions, manage status (draft → scheduled → live → completed)

### Forum (`/forum`)
- **Case Studies Tab**: View posted case studies
- **Discussion Tab**: Threaded posts with replies
- **Instructor**: Pin posts, add labels (insightful, question, misconception, etc.)

### Instructor Console (`/console`) - Instructor Only
- **AI Copilot Tab**: Start/stop live monitoring, view interventions
- **Polls Tab**: Create polls, view real-time results
- **Post Case Tab**: Post new case studies

### Reports (`/reports`)
- **Summary Tab**: Discussion stats, themes, learning objective alignment, misconceptions
- **Participation Tab**: Enrollment stats, participation rate, who participated/didn't
- **Scoring Tab** (instructor): Individual scores, class statistics, feedback

---

## Role-Based Access (Three-Tier System)

AristAI uses a three-tier role system:

| Role | Description |
|------|-------------|
| **Admin** | Full system access. Can approve/reject instructor requests and upload CSV rosters. |
| **Instructor** | Can create courses, manage sessions, enroll students, and use AI copilot features. |
| **Student** | Can view enrolled courses, participate in discussions, and request instructor access. |

### Permissions Matrix

| Feature | Student | Instructor | Admin |
|---------|---------|------------|-------|
| View enrolled courses/sessions | ✓ | ✓ | ✓ |
| Create courses/sessions | ✗ | ✓ | ✓ |
| View forum posts | ✓ | ✓ | ✓ |
| Create posts/replies | ✓ | ✓ | ✓ |
| Pin/label posts | ✗ | ✓ | ✓ |
| Access Instructor Console | ✗ | ✓ | ✓ |
| Start/stop copilot | ✗ | ✓ | ✓ |
| Create polls | ✗ | ✓ | ✓ |
| Vote on polls | ✓ | ✓ | ✓ |
| View reports | ✓ | ✓ | ✓ |
| Generate reports | ✗ | ✓ | ✓ |
| View scoring details | ✗ | ✓ | ✓ |
| Manage enrollment | ✗ | ✓ | ✓ |
| Request instructor access | ✓ | ✗ | ✗ |
| Approve/reject instructor requests | ✗ | ✗ | ✓ |
| Upload CSV roster | ✗ | ✗ | ✓ |

### Instructor Request Workflow

1. **Student requests**: Student clicks "Become Instructor" in Courses page
2. **Admin reviews**: Admin sees pending requests in Console > Instructor Requests tab
3. **Admin approves/rejects**: Request is approved (user promoted to instructor) or rejected

### CSV Roster Upload (Admin Only)

Admins can bulk-enroll students via CSV upload in Console > Roster Upload:
- CSV format: `email,name` (with header row)
- New users are automatically created with `student` role
- Existing users are enrolled without modification

---

## API Endpoints

### Users
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/users/` | List users (optional `?role=`) |
| GET | `/api/users/{id}` | Get user by ID |
| POST | `/api/users/` | Create user |

### Courses
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/courses/` | List courses |
| GET | `/api/courses/{id}` | Get course |
| POST | `/api/courses/` | Create course |
| POST | `/api/courses/{id}/generate_plans` | Generate AI plans |
| GET | `/api/courses/{id}/sessions` | List sessions |

### Enrollments
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/enrollments/course/{id}/students` | Get enrolled students |
| POST | `/api/enrollments/` | Enroll user |
| POST | `/api/enrollments/course/{id}/enroll-all-students` | Bulk enroll |
| DELETE | `/api/enrollments/{id}` | Unenroll |

### Sessions
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/sessions/{id}` | Get session |
| POST | `/api/sessions/` | Create session |
| PATCH | `/api/sessions/{id}/status` | Update status |
| GET | `/api/sessions/{id}/cases` | Get cases |
| POST | `/api/sessions/{id}/case` | Post case |
| POST | `/api/sessions/{id}/start_live_copilot` | Start copilot |
| POST | `/api/sessions/{id}/stop_live_copilot` | Stop copilot |
| GET | `/api/sessions/{id}/copilot_status` | Check copilot |
| GET | `/api/sessions/{id}/interventions` | Get interventions |

### Posts
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/posts/session/{id}` | Get posts |
| POST | `/api/posts/session/{id}` | Create post |
| POST | `/api/posts/{id}/pin` | Pin/unpin post |
| POST | `/api/posts/{id}/label` | Label post |

### Polls
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/polls/session/{id}` | Create poll |
| POST | `/api/polls/{id}/vote` | Vote |
| GET | `/api/polls/{id}/results` | Get results |

### Reports
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/reports/session/{id}/generate` | Generate report |
| GET | `/api/reports/session/{id}` | Get report |

---

## AI Workflows (LangGraph)

### 1. Session Plan Generator
**Trigger:** `POST /api/courses/{id}/generate_plans`

Generates structured session plans from syllabus containing:
- Topics to cover
- Learning goals
- Key concepts
- Discussion prompts
- Case study scenarios
- Checkpoints

### 2. Live Copilot
**Trigger:** `POST /api/sessions/{id}/start_live_copilot`

Runs continuously while active, analyzing discussion for:
- Confusion points (severity: high/medium/low)
- Rolling summary
- Suggested instructor prompts
- Re-engagement activities
- Poll suggestions
- Overall assessment (engagement, understanding, quality)

### 3. Report Generator
**Trigger:** `POST /api/reports/session/{id}/generate`

Produces comprehensive report including:
- Discussion summary and themes
- Learning objective alignment
- Misconceptions identified
- Best-practice answer
- **Participation metrics**: Who participated, who didn't, participation rate
- **Answer scoring**: Individual scores (0-100), feedback, class statistics

---

## MCP Server (Tool Registry + Voice Control)

AristAI ships with a first-party MCP server that exposes classroom operations as tools, enabling voice or agent-driven control without modifying the core API.

**Location:** `mcp_server/`

**Tool execution notes:** Handlers may be defined with or without a `db` argument; database sessions are created inside worker threads to avoid cross-thread session sharing.

**Action protocol:** Write tools now return a planned action with a preview and `action_id`. Execute via the `execute_action` tool after confirmation.

**Context tools:** Resolve courses/sessions/users by natural language and set active context with `resolve_course`, `resolve_session`, `resolve_user`, `set_active_course`, and `set_active_session`.

**UI actions:** Browsers subscribe to `/api/ui-actions/stream` (SSE) for `ui.navigate`, `ui.openTab`, `ui.openModal`, and `ui.toast` messages.

**Tool response schema:** Tools return `{ ok, type, summary, data, ui_actions?, requires_confirmation?, action_id? }` for consistent machine parsing.

**Voice macros:** Use `voice_open_page`, `voice_create_poll`, `voice_generate_report`, and `voice_enroll_students` to resolve context and return planned actions with confirmations.

**Start the server (stdio for Claude Desktop):**
```bash
python -m mcp_server.server
```

**Start the server (SSE for web clients):**
```bash
python -m mcp_server.server --transport sse --port 8080
```

**Claude Desktop config (example):**
```json
{
  "mcpServers": {
    "aristai": {
      "command": "python",
      "args": ["-m", "mcp_server.server"],
      "cwd": "/path/to/aristai",
      "env": {
        "DATABASE_URL": "postgresql+psycopg2://aristai:aristai_dev@localhost:5433/aristai",
        "REDIS_URL": "redis://localhost:6379/0"
      }
    }
  }
}
```

For a detailed breakdown of the internal tool registry structure (categories, handlers, and request flow), see `mcp_server/TOOL_REGISTRY.md`.

---

## Database Models

| Model | Description |
|-------|-------------|
| **User** | id, name, email, role, auth_provider, is_admin, instructor_request_status |
| **Course** | id, title, syllabus_text, objectives_json |
| **Enrollment** | user_id, course_id (tracks enrollment) |
| **Session** | id, course_id, title, status, plan_json |
| **Case** | id, session_id, prompt (case studies) |
| **Post** | id, session_id, user_id, content, parent_post_id, labels_json, pinned |
| **Poll** | id, session_id, question, options_json |
| **PollVote** | poll_id, user_id, option_index |
| **Intervention** | id, session_id, suggestion_json (copilot output) |
| **Report** | id, session_id, report_md, report_json, observability fields |

---

## Environment Variables

### Backend (.env)
| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL connection |
| `REDIS_URL` | Redis connection |
| `ANTHROPIC_API_KEY` | Claude API key |
| `DEBUG` | Enable debug endpoints |

### Frontend (Vercel)
| Variable | Description |
|----------|-------------|
| `BACKEND_API_URL` | EC2 backend URL (e.g., `http://3.85.224.97:8000`) |

---

## Development Commands

```bash
# View logs
docker compose logs -f api worker

# Run migrations
docker compose exec api alembic upgrade head

# Create new migration
docker compose exec api alembic revision --autogenerate -m "Description"

# Access database
docker compose exec db psql -U aristai -d aristai

# Run tests
docker compose exec api pytest

# Restart worker after code changes
docker compose restart worker
```

---

## Typical Workflow

1. **Setup Course** (Courses page)
   - Create course with syllabus and objectives
   - Click "Create & Generate Plans" for AI session plans
   - Enroll students in the course

2. **Start Session** (Sessions page)
   - View AI-generated plan
   - Set session status to "live"

3. **Run Discussion** (Forum page)
   - Post case study for students
   - Students post responses
   - Moderate: pin important posts, add labels

4. **Use Copilot** (Instructor Console)
   - Start live copilot monitoring
   - View real-time suggestions and confusion points
   - Create polls from AI suggestions

5. **Generate Report** (Reports page)
   - Generate post-discussion analysis
   - View participation metrics
   - Review student answer scores

---

## Cost Estimates

Based on Claude API pricing (January 2025):

| Operation | Typical Tokens | Est. Cost |
|-----------|----------------|-----------|
| Session planning | 1,000-2,000 | $0.001-0.003 |
| Copilot iteration | 1,500-3,000 | $0.002-0.005 |
| Report generation | 3,000-5,000 | $0.003-0.008 |

*Costs vary based on discussion length and model choice.*
