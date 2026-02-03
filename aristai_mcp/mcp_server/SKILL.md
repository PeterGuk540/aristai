# AristAI MCP Server Skill

This skill enables voice-operated control of the AristAI classroom forum platform via the Model Context Protocol (MCP).

## Overview

The AristAI MCP Server exposes 35+ tools that allow complete hands-free operation of an AI-assisted classroom forum. Instructors can manage courses, run live sessions, moderate discussions, create polls, and generate reports—all through voice commands.

## Installation

### Prerequisites

- Python 3.11+
- PostgreSQL database
- Redis (for async tasks)
- OpenAI API key (for Whisper ASR) or local Whisper
- ElevenLabs API key (optional, for premium TTS)

### Setup

1. **Install the MCP server:**
   ```bash
   cd aristai
   pip install -e .
   ```

2. **Configure environment:**
   ```bash
   cp .env.example .env
   # Edit .env with your database and API credentials
   ```

3. **Run database migrations:**
   ```bash
   docker compose up -d db redis
   docker compose exec api alembic upgrade head
   ```

4. **Start the MCP server:**
   ```bash
   python -m mcp_server.server
   ```

### Claude Desktop Configuration

Add to your Claude Desktop `claude_desktop_config.json`:

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

## Available Tools

### Course Management

| Tool | Mode | Description |
|------|------|-------------|
| `list_courses` | READ | List all courses in the system |
| `get_course` | READ | Get detailed course information |
| `create_course` | WRITE | Create a new course |
| `generate_session_plans` | WRITE | Generate AI session plans from syllabus |

### Session Management

| Tool | Mode | Description |
|------|------|-------------|
| `list_sessions` | READ | List sessions for a course |
| `get_session` | READ | Get session details |
| `get_session_plan` | READ | Get AI-generated session plan |
| `create_session` | WRITE | Create a new session |
| `update_session_status` | WRITE | Change session status |
| `go_live` | WRITE | Set session to live |
| `end_session` | WRITE | Complete a session |

### Forum & Discussion

| Tool | Mode | Description |
|------|------|-------------|
| `get_session_cases` | READ | Get case studies for a session |
| `post_case` | WRITE | Post a discussion case |
| `get_session_posts` | READ | Get all posts in a discussion |
| `get_latest_posts` | READ | Get recent posts |
| `get_pinned_posts` | READ | Get pinned posts |
| `get_post` | READ | Get a specific post |
| `search_posts` | READ | Search posts by keyword |
| `create_post` | WRITE | Create a new post |
| `reply_to_post` | WRITE | Reply to a post |
| `pin_post` | WRITE | Pin/unpin a post |
| `label_post` | WRITE | Add labels to a post |
| `mark_high_quality` | WRITE | Mark post as high-quality |
| `mark_needs_clarification` | WRITE | Mark post as needing clarification |

### Polls

| Tool | Mode | Description |
|------|------|-------------|
| `get_session_polls` | READ | Get all polls for a session |
| `get_poll_results` | READ | Get poll results with percentages |
| `create_poll` | WRITE | Create a new poll |
| `vote_on_poll` | WRITE | Cast a vote |

### AI Copilot

| Tool | Mode | Description |
|------|------|-------------|
| `get_copilot_status` | READ | Check if copilot is running |
| `get_copilot_suggestions` | READ | Get latest AI suggestions |
| `start_copilot` | WRITE | Start the AI copilot |
| `stop_copilot` | WRITE | Stop the AI copilot |

### Reports

| Tool | Mode | Description |
|------|------|-------------|
| `get_report` | READ | Get the full feedback report |
| `get_report_summary` | READ | Get voice-friendly summary |
| `get_participation_stats` | READ | Get participation metrics |
| `get_student_scores` | READ | Get student answer scores |
| `generate_report` | WRITE | Generate a new report |

### Enrollment

| Tool | Mode | Description |
|------|------|-------------|
| `get_enrolled_students` | READ | List enrolled students |
| `enroll_student` | WRITE | Enroll a student |
| `get_users` | READ | List users by role |

## Voice Command Examples

### Managing a Live Class

**Instructor says:** "Go live with session 5"
```
Tool: go_live
Args: {"session_id": 5}
Response: "Updated session 'Week 3: Ethics Case' from scheduled to live."
```

**Instructor says:** "What's new in the discussion?"
```
Tool: get_latest_posts
Args: {"session_id": 5, "count": 5}
Response: "Latest post from Alice: I think stakeholder theory provides a better framework because..."
```

**Instructor says:** "Pin post 23"
```
Tool: pin_post
Args: {"post_id": 23, "pinned": true}
Response: "Post 23 has been pinned."
```

**Instructor says:** "Create a poll: Which approach is better? Options: Shareholder primacy, Stakeholder theory, Hybrid approach"
```
Tool: create_poll
Args: {"session_id": 5, "question": "Which approach is better?", "options": ["Shareholder primacy", "Stakeholder theory", "Hybrid approach"]}
Response: "Created poll: 'Which approach is better?' Options: 'Shareholder primacy', 'Stakeholder theory', 'Hybrid approach'."
```

**Instructor says:** "What does the copilot suggest?"
```
Tool: get_copilot_suggestions
Args: {"session_id": 5}
Response: "Summary: Discussion is active with 15 posts. Found 2 confusion points. Top issue: confusion between stakeholder vs shareholder concepts. Try asking: Can someone explain the key difference between these two approaches?"
```

### After Class

**Instructor says:** "Generate a report for session 5"
```
Tool: generate_report
Args: {"session_id": 5}
Response: "Started generating report for session 'Week 3: Ethics Case' with 23 posts. Check back in a minute."
```

**Instructor says:** "What was the participation rate?"
```
Tool: get_participation_stats
Args: {"session_id": 5}
Response: "Session 'Week 3: Ethics Case': 18 of 25 students participated (72%). Students who didn't participate: John, Sarah, Mike..."
```

## Confirmation for Write Operations

By default, write operations require confirmation to prevent accidental changes. When a write tool is invoked:

1. The system describes what will happen
2. Asks for confirmation ("Should I proceed?")
3. User says "yes" to confirm or "no" to cancel

This can be disabled in the voice loop configuration if desired.

## Integration with voicemode

For hands-free operation, integrate with the `voicemode` MCP server:

```json
{
  "mcpServers": {
    "aristai": { ... },
    "voicemode": {
      "command": "uvx",
      "args": ["voicemode"],
      "env": {
        "OPENAI_API_KEY": "${OPENAI_API_KEY}"
      }
    }
  }
}
```

This enables:
- Wake-word activation ("Hey AristAI")
- Continuous listening with silence detection
- High-quality voice responses

## Voice Loop Controller

For standalone voice operation without Claude Desktop, use the Voice Loop Controller:

```python
from mcp_server.voice_loop import VoiceLoopController, VoiceConfig, VoiceMode

controller = VoiceLoopController(
    config=VoiceConfig(
        mode=VoiceMode.CONTINUOUS,
        wake_word="hey aristai",
        confirmation_required_for_writes=True,
    )
)

await controller.start()
```

Or via HTTP API:
```bash
# Start voice loop
curl -X POST http://localhost:8000/api/voice/start

# Process a command
curl -X POST http://localhost:8000/api/voice/command \
  -H "Content-Type: application/json" \
  -d '{"transcript": "list all courses"}'

# Get status
curl http://localhost:8000/api/voice/status
```

## Error Handling

All tools return a consistent response format:

**Success:**
```json
{
  "message": "Human-readable summary for TTS",
  "success": true,
  ... additional data ...
}
```

**Error:**
```json
{
  "error": "Description of what went wrong"
}
```

The voice loop gracefully handles errors and provides helpful feedback.

## Best Practices

1. **Be specific with IDs**: Say "session 5" not just "the session"
2. **Use natural language**: "Go live" works as well as "update status to live"
3. **Check before acting**: Use read tools to verify state before writes
4. **Listen to confirmations**: Write operations describe what will happen first

## Troubleshooting

**"No LLM API key configured"**
- Set `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` in environment

**"Session not found"**
- Verify the session ID with `list_sessions`

**"Database connection error"**
- Check `DATABASE_URL` environment variable
- Ensure PostgreSQL is running

**Voice not working**
- Check microphone permissions
- Verify ASR provider configuration
- Test with text input first via `/voice/command` endpoint
