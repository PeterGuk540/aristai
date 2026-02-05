#!/bin/bash

# ElevenLabs MCP Integration Setup Script
# This script helps configure your ElevenLabs agent with MCP functions

echo "🔧 ElevenLabs MCP Integration Setup"
echo "=================================="
echo ""

# Check if we have the agent ID
AGENT_ID="agent_6401kgkknwfnf7gvmgqb94hbmy4z"
BACKEND_URL="http://ec2-13-219-204-7.compute-1.amazonaws.com:8000"

echo "📋 Configuration Summary:"
echo "Agent ID: $AGENT_ID"
echo "Backend URL: $BACKEND_URL"
echo ""

echo "🔍 Testing MCP Backend Connection..."
echo "===================================="

# Test the MCP execute endpoint
echo "Testing list_courses tool..."
RESPONSE=$(curl -s -X POST "$BACKEND_URL/api/mcp/execute" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer dummy-token" \
  -d '{"tool": "list_courses", "arguments": {}}')

if echo "$RESPONSE" | grep -q '"ok":true'; then
    echo "✅ MCP Backend is working correctly!"
    echo "Sample response: $(echo "$RESPONSE" | head -c 200)..."
else
    echo "❌ MCP Backend test failed"
    echo "Response: $RESPONSE"
    exit 1
fi

echo ""
echo "🎯 Next Steps - Manual Configuration Required:"
echo "=============================================="
echo ""
echo "1. Go to ElevenLabs Console:"
echo "   https://elevenlabs.io/app/agents/$AGENT_ID"
echo ""
echo "2. Click 'Edit Agent' then scroll to 'Functions/Tools'"
echo ""
echo "3. Add these functions one by one:"
echo ""

# Generate function definitions for key tools
echo "📝 Function Definitions to Add:"
echo "==============================="

cat << 'EOF'

### 1. Navigate to Page
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
  },
  "webhook": {
    "url": "http://ec2-13-219-204-7.compute-1.amazonaws.com:8000/api/mcp/execute",
    "method": "POST",
    "headers": {
      "Authorization": "Bearer dummy-token",
      "Content-Type": "application/json"
    }
  }
}
```

### 2. List Courses
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
  },
  "webhook": {
    "url": "http://ec2-13-219-204-7.compute-1.amazonaws.com:8000/api/mcp/execute",
    "method": "POST",
    "headers": {
      "Authorization": "Bearer dummy-token",
      "Content-Type": "application/json"
    }
  }
}
```

### 3. Create Poll
```json
{
  "name": "create_poll",
  "description": "Create a new poll in a session",
  "parameters": {
    "type": "object",
    "properties": {
      "session_id": {"type": "integer", "description": "The session ID"},
      "question": {"type": "string", "description": "The poll question"},
      "options": {
        "type": "array",
        "items": {"type": "string"},
        "description": "List of answer options"
      }
    },
    "required": ["session_id", "question", "options"]
  },
  "webhook": {
    "url": "http://ec2-13-219-204-7.compute-1.amazonaws.com:8000/api/mcp/execute",
    "method": "POST",
    "headers": {
      "Authorization": "Bearer dummy-token",
      "Content-Type": "application/json"
    }
  }
}
```

### 4. Start Copilot
```json
{
  "name": "start_copilot",
  "description": "Start the AI copilot for a session",
  "parameters": {
    "type": "object",
    "properties": {
      "session_id": {"type": "integer", "description": "The session ID"}
    },
    "required": ["session_id"]
  },
  "webhook": {
    "url": "http://ec2-13-219-204-7.compute-1.amazonaws.com:8000/api/mcp/execute",
    "method": "POST",
    "headers": {
      "Authorization": "Bearer dummy-token",
      "Content-Type": "application/json"
    }
  }
}
```

### 5. Get Available Pages
```json
{
  "name": "get_available_pages",
  "description": "Get list of all available pages for navigation",
  "parameters": {
    "type": "object",
    "properties": {},
    "required": []
  },
  "webhook": {
    "url": "http://ec2-13-219-204-7.compute-1.amazonaws.com:8000/api/mcp/execute",
    "method": "POST",
    "headers": {
      "Authorization": "Bearer dummy-token",
      "Content-Type": "application/json"
    }
  }
}
```

EOF

echo ""
echo "⚠️  Important Notes:"
echo "===================="
echo "• Replace 'dummy-token' with proper JWT authentication in production"
echo "• Use HTTPS for production webhook URLs"
echo "• Test each function after adding it"
echo "• You can add more functions from your 44 available MCP tools"
echo ""

echo "🧪 Quick Test Commands:"
echo "========================"
echo "After configuration, test these voice commands:"
echo "• 'Show my courses' → Should call list_courses"
echo "• 'Go to forum' → Should call navigate_to_page"
echo "• 'Create a poll' → Should call create_poll (may need session ID)"
echo "• 'Start copilot' → Should call start_copilot"
echo ""

echo "🔗 Useful Links:"
echo "================"
echo "• ElevenLabs Agent: https://elevenlabs.io/app/agents/$AGENT_ID"
echo "• Your Backend API: $BACKEND_URL/docs"
echo "• MCP Tools List: Run 'python -c \"from mcp_server.server import TOOL_REGISTRY; print(list(TOOL_REGISTRY.keys()))\"'"
echo ""

echo "✅ Setup script complete!"
echo "Now manually configure the functions in ElevenLabs console."