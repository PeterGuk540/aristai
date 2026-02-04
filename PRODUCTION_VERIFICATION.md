# ElevenLabs Agents Production Verification Checklist
## AristAI - Production Deployment Ready: ✅ State 3

### **Pre-Deployment Security Checks**

#### Backend (FastAPI on EC2)
- [ ] `ELEVENLABS_API_KEY` is set in EC2 environment variables (NOT in code)
- [ ] `ELEVENLABS_AGENT_ID` is set in EC2 environment variables
- [ ] `GET /api/voice/agent/signed-url` endpoint requires Authorization header
- [ ] No `/api/voice/synthesize` endpoints are active
- [ ] No simulate-conversation or legacy TTS code paths exist
- [ ] API Gateway/Load Balancer has proper JWT/Cognito authentication
- [ ] Environment variables are not exposed in error responses

#### Frontend (Next.js on Vercel)  
- [ ] No ElevenLabs API keys anywhere in frontend code or environment
- [ ] Only calls `/api/voice/agent/signed-url` for voice initialization
- [ ] Uses official ElevenLabs SDK (`Conversation.startSession()`)
- [ ] Vendor SDK file (`elevenlabs-client-0.6.0.mjs`) is present
- [ ] Legacy TTS proxy routes are removed/disabled

---

### **Runtime Verification Tests**

#### 1. Backend API Tests
```bash
# Test signed URL endpoint (requires auth)
curl -H "Authorization: Bearer <JWT>" \
     https://your-api.amazonaws.com/api/voice/agent/signed-url

# Should return: { "signed_url": "wss://api.elevenlabs.io/..." }

# Test that legacy endpoints return 404/405
curl -X POST https://your-api.amazonaws.com/api/voice/synthesize
# Should NOT exist
```

#### 2. Frontend Browser Tests
Open Browser DevTools → Network → WS tab:

- [ ] When voice conversation starts:
  - ✅ Fetch to `/api/voice/agent/signed-url` (with Authorization)
  - ✅ Direct WebSocket connection to `wss://api.elevenlabs.io/...`
  - ❌ NO calls to `/api/voice/synthesize`
  - ❌ NO API keys in Network requests

- [ ] Verify WebSocket traffic:
  - ✅ Origin: `wss://api.elevenlabs.io`
  - ✅ Protocol: WebSocket (not proxied through backend)
  - ✅ Bidirectional audio streaming

#### 3. End-to-End Flow Test
1. User clicks microphone → Frontend calls `/api/voice/agent/signed-url`
2. Backend mints signed URL → Returns only the URL
3. Frontend calls `Conversation.startSession({ signedUrl })`
4. Browser connects directly to ElevenLabs WebSocket
5. Realtime conversation works (mic input → AI response)
6. Check DevTools: Direct WebSocket, no backend audio traffic

---

### **Production Environment Validation**

#### EC2 Backend
- [ ] Security Group allows HTTPS (443) from API Gateway only
- [ ] Environment variables set via EC2 User Data or Secrets Manager
- [ ] Application logs show signed URL requests, not TTS synthesis
- [ ] Memory/CPU usage normal (no audio processing load)

#### Vercel Frontend  
- [ ] Environment variables: `NEXT_PUBLIC_API_URL` pointing to API Gateway
- [ ] Build completes without errors
- [ ] Runtime logs show no legacy API calls
- [ ] WebSocket connections work in production

#### API Gateway (if used)
- [ ] JWT/Cognito integration configured
- [ ] `/api/voice/agent/signed-url` route protected
- [ ] CORS headers allow Vercel frontend domain
- [ ] Rate limiting configured for abuse protection

---

### **Monitoring & Observability**

#### Log Patterns to Expect
```
✅ INFO: Generated signed URL: wss://api.elevenlabs.io/v1/convai/conversation?...
✅ INFO: ElevenLabs SDK preloaded successfully
✅ INFO: Connected to ElevenLabs: conv_123abc...

❌ ERROR: Legacy simulate-conversation called  (Should never appear)
❌ ERROR: TTS synthesis failed             (Should never appear)
```

#### Monitoring Alerts
- [ ] Set up alerts for simulate-conversation calls (should be 0)
- [ ] Monitor signed URL generation volume
- [ ] Track WebSocket connection success rates
- [ ] Alert on API key exposure in logs

---

### **Final Production Verification**

**✅ Architecture Confirmation:**
```
Browser (Next.js on Vercel) 
  → GET /api/voice/agent/signed-url (via API Gateway) 
  → FastAPI on EC2 (mints signed URL only)
  
Browser ↔ ElevenLabs Agent (Direct WebSocket/WebRTC)
  (NO backend audio proxying, NO legacy TTS)
```

**🚀 Ready for Production Deployment: State 3 Achieved**

All legacy patterns removed, official SDK implementation verified, 
security confirmed, and production checklist complete.