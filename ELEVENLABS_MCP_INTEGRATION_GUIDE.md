# ElevenLabs Agent MCP Integration Guide

## Problem Identified
Your ElevenLabs Agent (`agent_6401kgkknwfnf7gvmgqb94hbmy4z`) is a generic conversational agent that doesn't have access to your MCP functions (navigation, course management, polling, etc.).

## Solution Options

### Option 1: Configure ElevenLabs Agent with MCP Tools (Recommended)

1. **Go to ElevenLabs Console**: https://elevenlabs.io/app/agents
2. **Select your agent**: `agent_6401kgkknwfnf7gvmgqb94hbmy4z`
3. **Add Custom Functions** in the agent configuration:
   - Navigate to "Tools" or "Functions" section
   - Add your MCP tools as custom functions

#### Required Function Definitions for Key Tools:

**Navigation Function:**
```json
{
  "name": "navigate_to_page",
  "description": "Navigate to a specific page in the AristAI interface",
  "parameters": {
    "type": "object",
    "properties": {
      "page": {
        "type": "string",
        "enum": ["courses", "sessions", "forum", "reports", "console", "dashboard", "home", "settings"],
        "description": "The page to navigate to"
      }
    },
    "required": ["page"]
  }
}
```

**List Courses Function:**
```json
{
  "name": "list_courses",
  "description": "List all available courses in the system",
  "parameters": {
    "type": "object",
    "properties": {
      "skip": {"type": "integer", "default": 0},
      "limit": {"type": "integer", "default": 100}
    },
    "required": []
  }
}
```

**Create Poll Function:**
```json
{
  "name": "create_poll",
  "description": "Create a new poll in a session",
  "parameters": {
    "type": "object",
    "properties": {
      "session_id": {"type": "integer"},
      "question": {"type": "string"},
      "options": {
        "type": "array",
        "items": {"type": "string"},
        "description": "List of answer options"
      }
    },
    "required": ["session_id", "question", "options"]
  }
}
```

**Function Endpoint Configuration:**
For each function, configure:
- **Webhook URL**: `https://your-api-domain.com/api/mcp/execute`
- **Headers**: `Authorization: Bearer YOUR_JWT_TOKEN`
- **Method**: POST

### Option 2: Use Built-in Tool Calling via Backend API

Modify your voice assistant to use the `/api/mcp/execute` endpoint directly from the frontend (already implemented).

### Option 3: Create Custom ElevenLabs Agent with MCP Integration

Create a new agent specifically configured for AristAI with all MCP tools pre-configured.

## Step-by-Step Fix Process

### 1. Test MCP Integration Locally First
```bash
# Test your MCP server is working
cd /home/aojie_ju/aristai/mcp_server
python server.py

# In another terminal, test a tool
curl -X POST http://localhost:8000/api/mcp/execute \
  -H "Content-Type: application/json" \
  -d '{"tool": "list_courses", "arguments": {}}'
```

### 2. Configure ElevenLabs Agent Functions

1. Go to: https://elevenlabs.io/app/agents/agent_6401kgkknwfnf7gvmgqb94hbmy4z
2. Click "Edit Agent"
3. Scroll to "Functions" or "Tools"
4. Add each MCP function with proper JSON schema
5. Set webhook URL to: `http://ec2-13-219-204-7.compute-1.amazonaws.com:8000/api/mcp/execute`
6. Save and test

### 3. Update Frontend Integration (If Needed)

Your frontend already has the MCP execution logic in `ConversationalVoice.tsx`. Ensure it's calling the right endpoint:

```typescript
// This should work if MCP is configured in ElevenLabs
const response = await fetch('/api/mcp/execute', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ tool: toolName, arguments: args }),
});
```

### 4. Test End-to-End

1. Deploy updated configuration
2. Test voice commands:
   - "Show my courses"
   - "Navigate to forum"
   - "Create a poll"
3. Verify MCP tools are executed via your backend

## Critical Configuration Details

### Security Headers
Configure your ElevenLabs agent to include proper authentication:
```json
{
  "headers": {
    "Authorization": "Bearer YOUR_JWT_TOKEN",
    "Content-Type": "application/json"
  }
}
```

### Error Handling
Ensure your MCP endpoints return proper error responses that ElevenLabs can understand.

### Rate Limiting
Configure appropriate rate limits in your backend to prevent abuse.

## Verification

After configuration, test these commands:
- ✅ "Show my courses" → Should call `list_courses`
- ✅ "Go to forum" → Should call `navigate_to_page` with `page: "forum"`
- ✅ "Create a poll" → Should call `create_poll` (may need additional parameters)

## Alternative: Direct Integration

If ElevenLabs function calling is complex, use your existing frontend pattern:
1. Voice → ElevenLabs transcription
2. Frontend parses intent
3. Frontend calls your MCP API directly
4. Results back to user

This approach is already implemented in your `ConversationalVoice.tsx` component.