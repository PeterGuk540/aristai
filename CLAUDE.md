# AristAI - AI-Powered Discussion Forum for Education

## Project Overview

AristAI is an AI-enhanced educational discussion platform that helps instructors manage courses, facilitate live class discussions, and integrate with external LMS systems (Canvas, UPP). The platform features voice-controlled UI, real-time AI assistance, and comprehensive analytics.

## Tech Stack

- **Frontend**: Next.js 14 (App Router), TypeScript, Tailwind CSS, Zustand (state)
- **Backend**: FastAPI (Python 3.11+), SQLAlchemy 2.0, Pydantic v2
- **Database**: PostgreSQL 15
- **Task Queue**: Celery + Redis
- **AI/LLM**: OpenAI GPT-4o-mini (primary), LangGraph for orchestration
- **Voice**: ElevenLabs Agent for voice UI control
- **MCP**: Model Context Protocol server for AI tool integration
- **Deployment**: Docker Compose on AWS EC2

## Project Structure

```
aristai/
├── api/                         # FastAPI backend
│   ├── api/                     # API layer
│   │   ├── routes/              # Endpoint modules
│   │   │   ├── auth.py          # Authentication
│   │   │   ├── courses.py       # Course management
│   │   │   ├── sessions.py      # Session management
│   │   │   ├── posts.py         # Discussion posts
│   │   │   ├── polls.py         # Polling system
│   │   │   ├── materials.py     # Course materials
│   │   │   ├── admin.py         # Admin operations
│   │   │   ├── integrations.py  # LMS integrations
│   │   │   └── enhanced_features.py  # AI features
│   │   ├── voice_converse_router.py  # Voice command processing
│   │   └── deps.py              # Dependency injection
│   ├── models/                  # SQLAlchemy ORM models
│   │   ├── user.py              # User model
│   │   ├── course.py            # Course, Enrollment
│   │   ├── session.py           # Session model
│   │   ├── post.py              # Post, Reply models
│   │   ├── poll.py              # Poll, PollVote
│   │   ├── material.py          # CourseMaterial
│   │   ├── integration.py       # LMS integration models
│   │   └── enhanced_features.py # AI feature models
│   ├── schemas/                 # Pydantic schemas
│   ├── services/                # Business logic
│   │   ├── ai/                  # AI services
│   │   │   ├── copilot.py       # Live AI copilot
│   │   │   └── enhanced.py      # Enhanced AI features
│   │   ├── integrations/        # LMS providers
│   │   │   ├── canvas.py        # Canvas LMS
│   │   │   └── upp.py           # UPP scraper
│   │   └── voice_conversation_state.py  # Voice state
│   └── core/                    # Core utilities
│       ├── database.py          # DB connection
│       ├── config.py            # Settings
│       └── security.py          # Auth utilities
├── frontend/                    # Next.js frontend
│   ├── src/
│   │   ├── app/                 # App Router pages
│   │   │   ├── (auth)/          # Auth pages (login, register)
│   │   │   ├── (dashboard)/     # Protected dashboard
│   │   │   │   ├── courses/     # Course management
│   │   │   │   ├── sessions/    # Session management
│   │   │   │   ├── discussions/ # Live discussions
│   │   │   │   ├── analytics/   # Analytics dashboard
│   │   │   │   └── admin/       # Admin panel
│   │   │   └── page.tsx         # Home page
│   │   ├── components/
│   │   │   ├── ui/              # Base UI components (Button, Card, etc.)
│   │   │   ├── voice/           # Voice UI controller
│   │   │   ├── instructor/      # Instructor features
│   │   │   │   ├── BreakoutGroups.tsx
│   │   │   │   ├── EngagementHeatmap.tsx
│   │   │   │   ├── FacilitationSuggestions.tsx
│   │   │   │   ├── PreClassInsights.tsx
│   │   │   │   ├── ProgressTracker.tsx
│   │   │   │   └── SessionTimer.tsx
│   │   │   └── enhanced/        # Enhanced AI feature components
│   │   │       ├── LiveSummary.tsx
│   │   │       ├── QuestionBank.tsx
│   │   │       ├── PeerReviewPanel.tsx
│   │   │       ├── ParticipationInsights.tsx
│   │   │       └── ObjectiveCoverage.tsx
│   │   ├── lib/
│   │   │   ├── api.ts           # API client (70+ endpoints)
│   │   │   ├── utils.ts         # Utility functions
│   │   │   └── auth.ts          # Auth utilities
│   │   └── stores/              # Zustand stores
│   └── public/                  # Static assets
├── workflows/                   # LangGraph AI workflows
│   ├── planning.py              # Session plan generation
│   ├── report.py                # Post-session reports
│   ├── copilot.py               # Live AI copilot
│   ├── canvas_push.py           # Push summaries to Canvas
│   └── enhanced_features.py     # Enhanced AI workflows
├── worker/                      # Celery background tasks
│   ├── tasks.py                 # Task definitions
│   └── celery_app.py            # Celery configuration
├── mcp_server/                  # MCP server for AI tools
│   ├── server.py                # MCP server implementation
│   └── tools.py                 # Tool definitions
├── alembic/                     # Database migrations
│   └── versions/                # Migration files
├── docker-compose.yml           # Container orchestration
├── docker-compose.prod.yml      # Production config
└── .env.example                 # Environment template
```

## Key Features

### 1. Course & Session Management
- Instructors create courses with syllabus
- AI generates session plans from syllabus (LangGraph workflow)
- Sessions have statuses: draft → scheduled → live → completed
- Join codes for student enrollment

### 2. Live Discussion Forum
- Real-time posts and replies during live sessions
- Instructors can pin posts, create polls
- AI Copilot monitors discussion and provides suggestions
- Threaded replies with author attribution

### 3. LMS Integrations
- **Canvas**: OAuth-based, sync materials, push announcements/assignments
- **UPP**: Web scraping-based, import courses and sessions
- Bidirectional sync capabilities

### 4. Voice UI Controller
- Natural language voice commands via ElevenLabs
- LLM-based intent classification (`USE_LLM_INTENT_DETECTION = True`)
- Controls navigation, form filling, button clicks
- Bilingual: English and Spanish
- Custom event dispatch for tab switching

### 5. Instructor Enhancement Features
- Engagement heatmap (visual participation tracking)
- Smart facilitation suggestions
- Pre-class insights (student preparation analysis)
- Post-class summaries
- Student progress tracking
- Breakout groups (manual and AI-generated)
- Session timers with visual countdown

### 6. Enhanced AI Features (10 Features)

1. **Smart Discussion Summarization (Real-time)**
   - Rolling summaries during live sessions
   - Key themes extraction, unanswered questions detection
   - Misconception identification with corrections
   - Engagement pulse monitoring (high/medium/low)

2. **AI-Powered Student Grouping**
   - Debate groups (opposing viewpoints)
   - Mixed participation (balance engagement levels)
   - Learning gap groups (similar gaps together)
   - Jigsaw mode (topic-based expert groups)

3. **Personalized Follow-up Generator**
   - AI-generated personalized feedback per student
   - Identifies strengths, improvements, key takeaways
   - Suggests resources based on participation
   - Send via Canvas/email/in-app

4. **Question Bank Builder**
   - AI generates quiz questions from discussion
   - MCQ, short answer, essay, true/false types
   - Difficulty levels (easy/medium/hard)
   - Links to learning objectives
   - Approval workflow (draft → approved → archived)

5. **Attendance & Participation Insights**
   - Real-time participation snapshots
   - At-risk student detection with risk factors
   - Quality scores for contributions
   - Automated alerts for low engagement

6. **AI Teaching Assistant Mode**
   - Students can ask questions to AI assistant
   - AI uses course materials as context
   - Instructor approval workflow
   - Confidence scoring for responses

7. **Session Recording & Transcript Analysis**
   - Upload audio/video recordings
   - Automatic transcription (Whisper integration ready)
   - Key moments extraction
   - Link transcript to discussion posts

8. **Learning Objective Alignment Dashboard**
   - Track objective coverage across sessions
   - Identify gaps in curriculum coverage
   - Generate recommendations for future sessions
   - Visual progress indicators

9. **Peer Review Workflow**
   - AI-matched reviewer assignments
   - Structured feedback templates (rating, strengths, areas)
   - Quality scoring for feedback
   - Flexible assignment modes

10. **Multi-Language Support**
    - Auto-detect source language
    - Translate posts on demand
    - User language preferences
    - Batch translate entire sessions

## Database Models (45 Tables)

### Core Tables
- `users` - User accounts (role: instructor/student, is_admin)
- `courses` - Courses with syllabus, join_code, created_by
- `sessions` - Class sessions with plan_json, status
- `posts` - Discussion posts (content, is_pinned, author_id)
- `polls` / `poll_votes` - In-session polls
- `enrollments` - Student-course relationships
- `course_materials` - Uploaded course materials

### Integration Tables
- `integration_provider_connections` - LMS API connections
- `integration_course_mappings` - External to local course mapping
- `integration_canvas_pushes` - Track Canvas push operations
- `integration_sync_logs` - Sync history

### Enhanced AI Features Tables
- `live_summaries` - Rolling discussion summaries
- `student_groups` / `student_group_members` - AI-generated breakout groups
- `personalized_followups` - Student follow-up messages
- `question_bank_items` - AI-generated quiz questions
- `participation_snapshots` / `participation_alerts` - Engagement tracking
- `ai_assistant_messages` - AI TA interactions
- `session_recordings` / `transcript_post_links` - Recording analysis
- `objective_coverage` - Learning objective tracking
- `peer_review_assignments` / `peer_review_feedback` - Peer review workflow
- `post_translations` / `user_language_preferences` - Multi-language support

## API Routes (70+ Endpoints)

### Authentication (`/api/v1/auth`)
- `POST /auth/login` - User login
- `POST /auth/register` - User registration
- `POST /auth/logout` - User logout
- `GET /auth/me` - Current user info

### Courses (`/api/v1/courses`)
- `GET /courses` - List courses (filtered by user)
- `POST /courses` - Create course
- `GET /courses/{id}` - Get course details
- `PUT /courses/{id}` - Update course
- `DELETE /courses/{id}` - Delete course
- `POST /courses/{id}/join` - Join course via code
- `POST /courses/{id}/generate-plan` - Generate AI session plan

### Sessions (`/api/v1/sessions`)
- `GET /sessions` - List sessions
- `POST /sessions` - Create session
- `GET /sessions/{id}` - Get session details
- `PUT /sessions/{id}` - Update session
- `DELETE /sessions/{id}` - Delete session
- `POST /sessions/{id}/start` - Start live session
- `POST /sessions/{id}/end` - End session

### Posts (`/api/v1/posts`)
- `GET /posts` - List posts (with filters)
- `POST /posts` - Create post
- `PUT /posts/{id}` - Update post
- `DELETE /posts/{id}` - Delete post
- `POST /posts/{id}/pin` - Pin/unpin post
- `POST /posts/{id}/reply` - Reply to post

### Polls (`/api/v1/polls`)
- `POST /polls` - Create poll
- `GET /sessions/{id}/polls` - List session polls
- `POST /polls/{id}/vote` - Submit vote
- `GET /polls/{id}/results` - Get results

### Materials (`/api/v1/materials`)
- `POST /courses/{id}/materials` - Upload material
- `GET /courses/{id}/materials` - List materials
- `DELETE /materials/{id}` - Delete material

### Integrations (`/api/v1/integrations`)
- `POST /integrations/canvas/connect` - Connect Canvas
- `GET /integrations/canvas/courses` - List Canvas courses
- `POST /integrations/canvas/import` - Import course
- `POST /integrations/canvas/push` - Push to Canvas
- `POST /integrations/upp/connect` - Connect UPP
- `POST /integrations/upp/import` - Import from UPP

### Admin (`/api/v1/admin`)
- `GET /admin/users` - List all users
- `PUT /admin/users/{id}` - Update user
- `DELETE /admin/users/{id}` - Delete user
- `GET /admin/stats` - Platform statistics

### Enhanced Features (`/api/v1/enhanced`)
See "API Endpoints for Enhanced Features" section below.

### Voice (`/api/v1/voice`)
- `POST /voice/converse` - Process voice command
- `GET /voice/page-structure` - Get page structure for voice

## API Endpoints for Enhanced Features

All enhanced features use the `/api/v1/enhanced` prefix:

### Live Summary
- `GET /enhanced/sessions/{id}/live-summary` - Get latest summary
- `POST /enhanced/sessions/{id}/live-summary/generate` - Generate new

### Student Groups
- `POST /enhanced/sessions/{id}/groups/generate` - Create AI groups
- `GET /enhanced/sessions/{id}/groups` - List groups
- `DELETE /enhanced/groups/{id}` - Delete group

### Personalized Followups
- `POST /enhanced/sessions/{id}/followups/generate` - Generate
- `GET /enhanced/sessions/{id}/followups` - List followups
- `POST /enhanced/followups/{id}/send` - Send to student
- `PUT /enhanced/followups/{id}` - Update followup

### Question Bank
- `POST /enhanced/sessions/{id}/questions/generate` - Generate
- `GET /enhanced/courses/{id}/question-bank` - List questions
- `PUT /enhanced/questions/{id}` - Update question
- `DELETE /enhanced/questions/{id}` - Delete question

### Participation Insights
- `GET /enhanced/courses/{id}/participation` - Course summary
- `GET /enhanced/sessions/{id}/participation` - Session details
- `POST /enhanced/courses/{id}/participation/analyze` - Run analysis
- `GET /enhanced/courses/{id}/at-risk-students` - At-risk list

### AI Teaching Assistant
- `POST /enhanced/sessions/{id}/ai-assistant/ask` - Ask question
- `GET /enhanced/sessions/{id}/ai-assistant/messages` - List messages
- `POST /enhanced/ai-assistant/messages/{id}/review` - Approve/reject

### Learning Objective Coverage
- `GET /enhanced/courses/{id}/objective-coverage` - Get report
- `POST /enhanced/courses/{id}/objective-coverage/analyze` - Analyze

### Peer Review
- `POST /enhanced/sessions/{id}/peer-reviews/create` - Create assignments
- `GET /enhanced/sessions/{id}/peer-reviews` - List assignments
- `GET /enhanced/peer-reviews/{id}` - Get assignment details
- `POST /enhanced/peer-reviews/{id}/submit` - Submit review

### Multi-Language
- `POST /enhanced/posts/{id}/translate` - Translate post
- `GET /enhanced/users/{id}/language-preference` - Get preference
- `PUT /enhanced/users/{id}/language-preference` - Update preference
- `POST /enhanced/sessions/{id}/batch-translate` - Translate all posts

## MCP Server Tools

The MCP server (`mcp_server/`) provides AI tools for external integrations:

- `get_courses` - List available courses
- `get_sessions` - List sessions for a course
- `get_discussion_posts` - Get posts from a session
- `create_post` - Create a new discussion post
- `generate_summary` - Generate AI summary
- `get_analytics` - Get course analytics
- `translate_text` - Translate text

## Voice Commands

### Navigation
- "go to courses" / "ir a cursos"
- "go to sessions" / "ir a sesiones"
- "go to analytics" / "ver analiticas"
- "go to admin" / "ir a admin"
- "take me to the AI features tab"
- "switch to materials tab"

### Actions
- "create a new course" / "crear curso"
- "start the session" / "iniciar sesion"
- "end the session" / "terminar sesion"
- "delete session" / "eliminar sesion"
- "edit session" / "editar sesion"

### Enhanced AI Commands
- "show the live summary" / "generate a summary" / "mostrar resumen"
- "create AI groups" / "split students by AI" / "crear grupos con IA"
- "generate followups" / "create personalized feedback" / "generar seguimientos"
- "generate quiz questions" / "build question bank" / "generar preguntas"
- "show participation insights" / "analyze participation" / "ver participacion"
- "ask the AI assistant" / "preguntar al asistente"
- "show objective coverage" / "check learning objectives" / "cobertura de objetivos"
- "create peer reviews" / "set up peer review" / "crear revisiones de pares"
- "translate the posts" / "translate to Spanish" / "traducir publicaciones"

## Common Development Tasks

### Run migrations
```bash
docker compose exec api alembic upgrade head
```

### Create new migration
```bash
docker compose exec api alembic revision --autogenerate -m "description"
```

### Restart services
```bash
docker compose restart api frontend worker
```

### Rebuild services
```bash
docker compose build api frontend
docker compose up -d
```

### Check logs
```bash
docker compose logs api --tail=100
docker compose logs worker --tail=100
docker compose logs frontend --tail=100
```

### Run frontend locally
```bash
cd frontend && npm run dev
```

### Run backend locally
```bash
cd api && uvicorn api.main:app --reload
```

### Run Celery worker locally
```bash
cd worker && celery -A celery_app worker --loglevel=info
```

## Key Configuration Files

### Voice Controller
- Frontend: `frontend/src/components/voice/VoiceUIController.tsx`
- Backend: `api/api/voice_converse_router.py`
- State: `api/services/voice_conversation_state.py`

### Adding new voice commands
1. Add button with `data-voice-id="your-id"` in React component
2. Add to `PAGE_STRUCTURES` in `voice_conversation_state.py`
3. Add patterns in `ACTION_PATTERNS` in `voice_converse_router.py`
4. Add button mapping in `voice_converse_router.py`

### Adding voice tab switching
In page components, add tab mapping in `handleVoiceSelectTab`:
```typescript
const tabMap: Record<string, string> = {
  'aifeatures': 'ai-features',  // normalized → actual
  'ai-features': 'ai-features',
};
const mappedTab = tabMap[tab.toLowerCase()] || tab;
```

### Environment Variables
Key variables in `.env`:
- `DATABASE_URL` - PostgreSQL connection
- `REDIS_URL` - Redis for Celery
- `OPENAI_API_KEY` - OpenAI API key
- `ELEVENLABS_API_KEY` - Voice API key
- `CANVAS_CLIENT_ID/SECRET` - Canvas OAuth
- `SECRET_KEY` - JWT signing key

## API Conventions

- Endpoints use `user_id` query param for auth (simplified auth)
- Admin users (`is_admin=True`) bypass ownership checks
- Instructors can only see/edit their own courses (`created_by` field)
- Standard response format: `{ "data": ..., "message": "..." }`
- Error format: `{ "detail": "error message" }`
- Pagination: `?skip=0&limit=20`

## Testing

### Run backend tests
```bash
docker compose exec api pytest
```

### Run frontend tests
```bash
cd frontend && npm test
```

### Run type checking
```bash
cd frontend && npm run type-check
cd api && mypy .
```

## Deployment

### Production deployment
```bash
docker compose -f docker-compose.prod.yml up -d
```

### SSL/HTTPS
- Nginx reverse proxy handles SSL termination
- Let's Encrypt certificates via Certbot

### Monitoring
- Docker health checks
- Celery flower for task monitoring
- Application logs in `/var/log/aristai/`

## Recent Changes (Feb 2026)

- Session edit/delete with ownership verification
- Push to Canvas feature (announcements/assignments)
- UPP course name extraction improvements
- Voice commands for edit/delete sessions
- Session plan generation updates existing imported sessions
- **10 Enhanced AI Features** implemented:
  - Database models: `api/models/enhanced_features.py`
  - API routes: `api/api/routes/enhanced_features.py`
  - Celery tasks: `worker/tasks.py`
  - Workflows: `workflows/enhanced_features.py`
  - Frontend components: `frontend/src/components/enhanced/`
  - Voice commands for all features
- AI Features tab in Sessions page
- AI Insights tab in Courses page
- Voice tab switching fixes for hyphenated tab names
