# Step-by-Step ElevenLabs MCP Configuration

## 🎯 **Immediate Action Plan**

Follow these exact steps to configure your ElevenLabs Agent with MCP functions:

---

## **Step 1: Open Your Agent**
1. Go to: https://elevenlabs.io/app/agents/agent_6401kgkknwfnf7gvmgqb94hbmy4z
2. Click **"Edit Agent"**
3. Scroll down to **"Functions"** section
4. Click **"Add Function"**

---

## **Step 2: Add First Function (Navigation)**

Copy and paste this entire configuration:

```json
{
  "name": "navigate_to_page",
  "description": "Navigate to a specific page in the AristAI educational platform. Use this when user asks to go to pages like courses, forum, reports, dashboard, console, sessions, etc.",
  "parameters": {
    "type": "object",
    "properties": {
      "page": {
        "type": "string",
        "enum": ["courses", "sessions", "forum", "reports", "console", "dashboard", "home", "settings"],
        "description": "The target page to navigate to"
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

Click **"Save"** or **"Add"** for this function.

---

## **Step 3: Add Second Function (List Courses)**

Click **"Add Function"** again, then add:

```json
{
  "name": "list_courses",
  "description": "List all available courses for the user. Use this when user asks to see their courses, what courses they have, or show my courses.",
  "parameters": {
    "type": "object",
    "properties": {
      "skip": {"type": "integer", "default": 0, "description": "Number of courses to skip for pagination"},
      "limit": {"type": "integer", "default": 100, "description": "Maximum number of courses to return"}
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

Click **"Save"**.

---

## **Step 4: Add Third Function (Help/Available Pages)**

Add this helper function:

```json
{
  "name": "get_available_pages",
  "description": "Get list of all available pages for navigation and provide help. Use this when user asks for help or what they can do.",
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

Click **"Save"**.

---

## **Step 5: Test the Configuration**

1. Save your agent changes
2. Go to your AristAI application
3. Start voice assistant
4. Try these commands:

   **Test Commands:**
   - "Show my courses"
   - "Go to forum" 
   - "What pages can I navigate to?"
   - "Take me to the courses page"

---

## **Step 6: Add More Functions (After Testing Works)**

Once basic functions work, add these:

### **Create Poll Function:**
```json
{
  "name": "create_poll",
  "description": "Create a new poll in a session for student engagement",
  "parameters": {
    "type": "object",
    "properties": {
      "session_id": {"type": "integer", "description": "The session ID to create poll in"},
      "question": {"type": "string", "description": "The poll question"},
      "options": {
        "type": "array",
        "items": {"type": "string"},
        "description": "List of answer options (minimum 2)"
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

### **Start Copilot Function:**
```json
{
  "name": "start_copilot",
  "description": "Start the AI copilot for a session to monitor discussions and provide suggestions",
  "parameters": {
    "type": "object",
    "properties": {
      "session_id": {"type": "integer", "description": "The session ID to start copilot for"}
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

---

## **Step 7: Production Upgrades**

For production deployment:

1. **Replace URLs:** Change `http://ec2-...` to your production HTTPS URL
2. **Update Authentication:** Replace `dummy-token` with real JWT tokens
3. **Add Error Handling:** Configure proper error responses

---

## **🚨 Troubleshooting**

### **If functions don't trigger:**
1. Check webhook URL is accessible: `curl http://ec2-13-219-204-7.compute-1.amazonaws.com:8000/api/mcp/execute`
2. Verify JSON syntax is correct
3. Check ElevenLabs function calling is enabled

### **If authentication fails:**
1. Verify your backend accepts `Authorization: Bearer dummy-token`
2. Check CORS settings allow ElevenLabs requests
3. Ensure MCP endpoint is working

### **If voice commands not recognized:**
1. Test the agent's understanding first (without functions)
2. Check function descriptions are clear
3. Verify parameter names match exactly

---

## **🎉 Expected Results**

After successful configuration:

✅ **"Show my courses"** → Lists your 3 courses  
✅ **"Go to forum"** → Navigates to forum page  
✅ **"Take me to reports"** → Opens reports section  
✅ **"Create a poll"** → Opens poll creation (with session)  
✅ **"Start copilot"** → Activates AI assistant  

---

## **🔗 Quick Links**

- **Your Agent:** https://elevenlabs.io/app/agents/agent_6401kgkknwfnf7gvmgqb94hbmy4z
- **Backend API:** http://ec2-13-219-204-7.compute-1.amazonaws.com:8000/docs
- **Test MCP:** `curl http://ec2-13-219-204-7.compute-1.amazonaws.com:8000/api/mcp/execute -X POST -H "Content-Type: application/json" -d '{"tool":"list_courses","arguments":{}}'`

---

## **📞 Next Steps After Configuration**

1. Test basic navigation and course listing
2. Add poll and copilot functions  
3. Configure production HTTPS and authentication
4. Add remaining 39 MCP tools as needed
5. Monitor webhook calls and user feedback

**Start with Step 1 now!** This should take about 15-20 minutes to configure the first 3 functions.