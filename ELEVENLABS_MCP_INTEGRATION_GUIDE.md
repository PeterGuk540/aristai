# ElevenLabs Agent MCP Integration Guide

## Problem Identified
Your ElevenLabs Agent (`agent_6401kgkknwfnf7gvmgqb94hbmy4z`) is configured with multiple domain-specific tools. That makes it behave like a “brain,” but in this architecture **MCP must be the only brain**. The ElevenLabs agent should only forward transcripts and speak whatever MCP returns.

## Solution Options

### Option 1: Single “Delegate to MCP” Tool (Recommended)

**Goal:** Keep ElevenLabs as the real-time voice interface only. MCP handles intent and actions.

1. **Go to ElevenLabs Console**: https://elevenlabs.io/app/agents  
2. **Select your agent**: `agent_6401kgkknwfnf7gvmgqb94hbmy4z`  
3. In the **Tools / Functions** section, delete any existing tools.  
4. **Add exactly one tool**:

```json
{
  "name": "delegate_to_mcp",
  "description": "Delegate all user intent understanding and action planning to the MCP backend.",
  "parameters": {
    "type": "object",
    "properties": {
      "transcript": { "type": "string" },
      "current_page": { "type": "string" },
      "user_id": { "type": "integer" }
    },
    "required": ["transcript"]
  },
  "webhook": {
    "url": "https://your-api-domain.com/api/voice/agent/delegate",
    "method": "POST",
    "headers": {
      "Authorization": "Bearer YOUR_JWT_TOKEN",
      "Content-Type": "application/json"
    }
  }
}
```

### Option 2: Client Tool Calling (SDK)

If you prefer to keep the tool call on the client, define a single `delegate_to_mcp` client tool that POSTs to `/api/voice/agent/delegate` and returns the MCP response string for the agent to speak.

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

### 2. Configure ElevenLabs Agent Tool

1. Go to: https://elevenlabs.io/app/agents/agent_6401kgkknwfnf7gvmgqb94hbmy4z  
2. Click **"Edit Agent"**  
3. Scroll to **"Functions"** or **"Tools"**  
4. Add the single `delegate_to_mcp` tool (above)  
5. Set webhook URL to: `https://your-api-domain.com/api/voice/agent/delegate`  
6. Save and test  

### 3. Configure System Instructions (Short)

Set the ElevenLabs agent **system instruction** to:

```
You are a real-time voice interface.
Do not interpret user intent or make decisions.
Always delegate understanding and actions to the MCP backend.
Speak only the response provided by MCP.
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
- ✅ "Show my courses" → `delegate_to_mcp` → MCP runs `list_courses`
- ✅ "Go to forum" → `delegate_to_mcp` → MCP returns `ui.navigate`
- ✅ "Create a poll" → `delegate_to_mcp` → MCP plans/executed tool
