# Step-by-Step ElevenLabs MCP Configuration

## 🎯 **Immediate Action Plan**

Follow these exact steps to configure your ElevenLabs Agent with a single MCP delegate tool:

---

## **Step 1: Open Your Agent**
1. Go to: https://elevenlabs.io/app/agents/agent_6401kgkknwfnf7gvmgqb94hbmy4z
2. Click **"Edit Agent"**
3. Scroll down to **"Functions"** section
4. Click **"Add Function"**

---

## **Step 2: Add the Only Function (Delegate to MCP)**

Copy and paste this entire configuration:

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
      "Authorization": "Bearer dummy-token",
      "Content-Type": "application/json"
    }
  }
}
```

Click **"Save"** or **"Add"** for this function.

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

## **Step 6: Update the System Instruction**

Set the agent system instruction to:

```
You are a real-time voice interface.
Do not interpret user intent or make decisions.
Always delegate understanding and actions to the MCP backend.
Speak only the response provided by MCP.
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
1. Check webhook URL is accessible: `curl https://your-api-domain.com/api/voice/agent/delegate`
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
2. Configure production HTTPS and authentication
3. Monitor webhook calls and user feedback

**Start with Step 1 now!** This should take about 10 minutes to configure the single tool and system prompt.
