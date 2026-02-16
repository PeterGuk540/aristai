# AristAI - AI-Powered Discussion Forum for Education

## Project Overview

AristAI is an AI-enhanced educational discussion platform that helps instructors manage courses, facilitate live class discussions, and integrate with external LMS systems (Canvas, UPP).

## Tech Stack

- **Frontend**: Next.js 14 (App Router), TypeScript, Tailwind CSS
- **Backend**: FastAPI (Python 3.11+), SQLAlchemy, Pydantic
- **Database**: PostgreSQL
- **Task Queue**: Celery + Redis
- **LLM**: OpenAI GPT-4o-mini (primary), with fallback support
- **Voice**: ElevenLabs Agent for voice UI control
- **Deployment**: Docker Compose on AWS EC2

## Project Structure

```
aristai/
├── api/                    # FastAPI backend
│   ├── api/routes/         # API endpoints
│   ├── models/             # SQLAlchemy models
│   ├── schemas/            # Pydantic schemas
│   ├── services/           # Business logic
│   │   └── integrations/   # LMS providers (Canvas, UPP)
│   └── core/               # Database, config
├── frontend/               # Next.js frontend
│   ├── src/app/            # App router pages
│   ├── src/components/     # React components
│   │   ├── ui/             # Base UI components
│   │   ├── voice/          # Voice UI controller
│   │   └── instructor/     # Instructor features
│   └── src/lib/            # Utilities, API client
├── workflows/              # LangGraph workflows
│   ├── planning.py         # Session plan generation
│   ├── report.py           # Post-session reports
│   ├── copilot.py          # Live AI copilot
│   └── canvas_push.py      # Push summaries to Canvas
├── worker/                 # Celery background tasks
├── alembic/                # Database migrations
└── docker-compose.yml      # Container orchestration
```

## Key Features

### 1. Course & Session Management
- Instructors create courses with syllabus
- AI generates session plans from syllabus (LangGraph workflow)
- Sessions have statuses: draft → scheduled → live → completed

### 2. Live Discussion Forum
- Students post and reply during live sessions
- Instructors can pin posts, create polls
- AI Copilot monitors discussion and provides suggestions

### 3. LMS Integrations
- **Canvas**: OAuth-based, sync materials, push announcements/assignments
- **UPP**: Web scraping-based, import courses and sessions

### 4. Voice UI Controller
- Natural language voice commands via ElevenLabs
- LLM-based intent classification (`USE_LLM_INTENT_DETECTION = True`)
- Controls navigation, form filling, button clicks
- Bilingual: English and Spanish

### 5. Instructor Enhancement Features
- Engagement heatmap
- Smart facilitation suggestions
- Pre-class insights
- Post-class summaries
- Student progress tracking
- Breakout groups
- Session timers

### 6. Enhanced AI Features (NEW - Feb 2026)

Ten advanced AI-powered features for educational enhancement:

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

## Database Models (Key Tables)

- `users` - User accounts (role: instructor/student, is_admin)
- `courses` - Courses with syllabus, join_code, created_by
- `sessions` - Class sessions with plan_json, status
- `posts` - Discussion posts
- `polls` / `poll_votes` - In-session polls
- `enrollments` - Student-course relationships
- `integration_provider_connections` - LMS API connections
- `integration_course_mappings` - External to local course mapping
- `integration_canvas_pushes` - Track Canvas push operations

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

## Common Development Tasks

### Run migrations
```bash
docker compose exec api alembic upgrade head
```

### Restart services
```bash
docker compose restart api frontend worker
```

### Check logs
```bash
docker compose logs api --tail=100
docker compose logs worker --tail=100
```

### Voice Controller
- Frontend: `frontend/src/components/voice/VoiceUIController.tsx`
- Backend: `api/api/voice_converse_router.py`
- State: `api/services/voice_conversation_state.py`

### Adding new voice commands
1. Add button with `data-voice-id="your-id"` in React component
2. Add to `PAGE_STRUCTURES` in `voice_conversation_state.py`
3. Add patterns in `ACTION_PATTERNS` in `voice_converse_router.py`
4. Add button mapping in `voice_converse_router.py`

## API Conventions

- Endpoints use `user_id` query param for auth (simplified)
- Admin users (`is_admin=True`) bypass ownership checks
- Instructors can only see/edit their own courses (`created_by` field)

## Recent Changes (Feb 2026)

- Session edit/delete with ownership verification
- Push to Canvas feature (announcements/assignments)
- UPP course name extraction improvements
- Voice commands for edit/delete sessions
- Session plan generation updates existing imported sessions
- **10 Enhanced AI Features** (see section 6 above):
  - Database models: `api/models/enhanced_features.py`
  - API routes: `api/api/routes/enhanced_features.py`
  - Celery tasks: `worker/tasks.py` (generate_live_summary_task, etc.)
  - Workflows: `workflows/enhanced_features.py`
  - Frontend components: `frontend/src/components/enhanced/`
  - Voice commands added for all features

## API Endpoints for Enhanced Features

All enhanced features use the `/api/v1/enhanced` prefix:

### Live Summary
- `GET /enhanced/sessions/{id}/live-summary` - Get latest summary
- `POST /enhanced/sessions/{id}/live-summary/generate` - Generate new

### Student Groups
- `POST /enhanced/sessions/{id}/groups/generate` - Create AI groups
- `GET /enhanced/sessions/{id}/groups` - List groups

### Personalized Followups
- `POST /enhanced/sessions/{id}/followups/generate` - Generate
- `GET /enhanced/sessions/{id}/followups` - List followups
- `POST /enhanced/followups/{id}/send` - Send to student

### Question Bank
- `POST /enhanced/sessions/{id}/questions/generate` - Generate
- `GET /enhanced/courses/{id}/question-bank` - List questions

### Participation Insights
- `GET /enhanced/courses/{id}/participation` - Course summary
- `GET /enhanced/sessions/{id}/participation` - Session details
- `POST /enhanced/courses/{id}/participation/analyze` - Run analysis

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
- `POST /enhanced/peer-reviews/{id}/submit` - Submit review

### Multi-Language
- `POST /enhanced/posts/{id}/translate` - Translate post
- `GET /enhanced/users/{id}/language-preference` - Get preference
- `PUT /enhanced/users/{id}/language-preference` - Update preference

## Voice Commands for Enhanced Features

New voice commands supported:
- "show the live summary" / "generate a summary" / "mostrar resumen"
- "create AI groups" / "split students by AI" / "crear grupos con IA"
- "generate followups" / "create personalized feedback" / "generar seguimientos"
- "generate quiz questions" / "build question bank" / "generar preguntas"
- "show participation insights" / "analyze participation" / "ver participacion"
- "ask the AI assistant" / "preguntar al asistente"
- "show objective coverage" / "check learning objectives" / "cobertura de objetivos"
- "create peer reviews" / "set up peer review" / "crear revisiones de pares"
- "translate the posts" / "translate to Spanish" / "traducir publicaciones"
