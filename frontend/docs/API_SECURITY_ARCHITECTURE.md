# AristAI API Security Architecture

## Overview

This document describes how the AristAI frontend connects to the backend API with JWT authentication to protect against unauthorized access.

---

## Security Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              BROWSER (Client)                                │
│                                                                             │
│  localStorage:                                                              │
│  ├─ CognitoIdentityServiceProvider.{clientId}.LastAuthUser                 │
│  ├─ CognitoIdentityServiceProvider.{clientId}.{user}.accessToken  ◄─ JWT   │
│  ├─ CognitoIdentityServiceProvider.{clientId}.{user}.idToken               │
│  └─ CognitoIdentityServiceProvider.{clientId}.{user}.refreshToken          │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                    API Request with: Authorization: Bearer <JWT>
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         VERCEL (Next.js Frontend)                           │
│                                                                             │
│  PUBLIC URL: https://aristai-frontend.vercel.app                           │
│                                                                             │
│  /api/proxy/[...path]  ◄─── Server-side proxy (hides backend URL)          │
│       │                                                                     │
│       │  Forwards: Authorization header + request body                      │
│       │  BACKEND_URL is SERVER-SIDE ONLY (not exposed to browser)          │
│       ▼                                                                     │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                    Request to: API Gateway (hidden URL)
                    Header: Authorization: Bearer <JWT>
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         API GATEWAY (AWS us-east-1)                         │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                      JWT AUTHORIZER                                  │   │
│  │                                                                      │   │
│  │  Validates JWT against:                                             │   │
│  │  • Issuer: Cognito User Pool (us-east-2)                           │   │
│  │  • Audience: App Client ID                                          │   │
│  │                                                                      │   │
│  │  Checks performed:                                                  │   │
│  │  ✓ RS256 signature verification                                     │   │
│  │  ✓ Token expiration (exp claim)                                     │   │
│  │  ✓ Issuer validation (iss claim)                                    │   │
│  │  ✓ Audience validation (aud claim)                                  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                      │                                      │
│                          VALID TOKEN │ INVALID → 401 Unauthorized           │
│                                      ▼                                      │
│                              Backend Lambda                                 │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Security Layers

| Layer | Protection | Details |
|-------|------------|---------|
| **1. Proxy Hiding** | Backend URL not exposed | `BACKEND_URL` is hardcoded server-side, never sent to browser |
| **2. JWT Required** | API Gateway rejects unauthorized | All `/api/*` routes require valid JWT |
| **3. JWT Signature** | Token cannot be forged | RS256 signature verified against Cognito's public keys |
| **4. Token Expiration** | Short-lived access | Access tokens expire (typically 1 hour) |
| **5. Issuer Check** | Only Cognito tokens accepted | JWT must be from the configured User Pool |
| **6. HTTPS Only** | Encrypted in transit | All endpoints use TLS |

---

## Authentication Flow

### 1. User Login
```
User clicks "Sign In"
       │
       ▼
Redirect to Cognito Hosted UI
       │
       ▼
User enters credentials (or uses Google)
       │
       ▼
Cognito redirects to /callback with authorization code
       │
       ▼
Frontend exchanges code for tokens via /oauth2/token
       │
       ▼
Tokens stored in localStorage
```

### 2. API Request
```
Frontend calls api.getCourses()
       │
       ▼
fetchApi() retrieves accessToken from localStorage
       │
       ▼
Request sent to /api/proxy/courses/ with Authorization header
       │
       ▼
Next.js proxy forwards to API Gateway (server-side)
       │
       ▼
API Gateway validates JWT
       │
       ▼
Backend processes request and returns data
```

---

## What Attackers Can See (Browser DevTools)

```javascript
// Network tab shows:
Request URL: https://aristai-frontend.vercel.app/api/proxy/courses/
Authorization: Bearer eyJraWQiOiJ...  // JWT token (visible but not forgeable)

// Decoded JWT payload (public information):
{
  "sub": "user-uuid",
  "email": "user@example.com",
  "exp": 1706123456,
  "iss": "https://cognito-idp.us-east-2.amazonaws.com/..."
}
```

---

## What Attackers Cannot Do

| Attack Vector | Why It Fails |
|---------------|--------------|
| **Discover backend URL** | Hidden in server-side proxy code, not in browser bundle |
| **Forge JWT token** | Requires Cognito's private RSA signing key |
| **Reuse expired token** | API Gateway validates `exp` claim |
| **Use token from another app** | Audience (`aud`) must match configured Client ID |
| **Brute force login** | Cognito has built-in rate limiting and account lockout |
| **Token replay** | Tokens are short-lived and tied to specific user |

---

## Key Files

| File | Purpose |
|------|---------|
| `src/lib/auth.tsx` | Cognito authentication, token storage/retrieval |
| `src/lib/api.ts` | API client, attaches JWT to requests |
| `src/app/api/proxy/[...path]/route.ts` | Server-side proxy, hides backend URL |
| `src/app/callback/page.tsx` | OAuth callback, exchanges code for tokens |

---

## Token Storage Format

Tokens are stored in localStorage using Cognito's standard format:

```
CognitoIdentityServiceProvider.{clientId}.LastAuthUser = "username"
CognitoIdentityServiceProvider.{clientId}.{username}.accessToken = "..."
CognitoIdentityServiceProvider.{clientId}.{username}.idToken = "..."
CognitoIdentityServiceProvider.{clientId}.{username}.refreshToken = "..."
```

---

## API Response Examples

### Without Token
```bash
curl https://api-gateway-url/api/courses/
# Response: {"message":"Unauthorized"}
```

### With Invalid Token
```bash
curl -H "Authorization: Bearer fake-token" https://api-gateway-url/api/courses/
# Response: {"message":"Unauthorized"}
```

### With Valid Token
```bash
curl -H "Authorization: Bearer valid-jwt" https://api-gateway-url/api/courses/
# Response: [{"id": 1, "title": "Course 1", ...}]
```

---

## Security Checklist

- [x] Backend URL hidden via server-side proxy
- [x] JWT authentication enforced at API Gateway
- [x] Authorization code flow (more secure than implicit)
- [x] Tokens stored in localStorage (standard practice)
- [x] HTTPS enforced on all endpoints
- [x] Token expiration validated
- [x] Issuer and audience validation configured

---

## Infrastructure Summary

| Component | Location | Purpose |
|-----------|----------|---------|
| Cognito User Pool | AWS us-east-2 | User authentication, JWT issuance |
| API Gateway | AWS us-east-1 | JWT validation, request routing |
| Backend Lambda | AWS us-east-1 | Business logic |
| Frontend | Vercel | User interface, API proxy |

---

*Last updated: January 2026*
