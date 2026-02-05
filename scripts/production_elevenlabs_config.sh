#!/bin/bash

# Production ElevenLabs Agent Configuration
# Use this after getting your HTTPS and authentication setup

echo "🔧 Production ElevenLabs Configuration"
echo "======================================"
echo ""

BACKEND_URL="https://your-api-domain.com"  # Replace with your HTTPS domain
AUTH_TOKEN="your-jwt-token-here"          # Replace with real JWT auth

echo "📝 Production Webhook Template:"
echo "==============================="
echo ""

cat << EOF
{
  "webhook": {
    "url": "$BACKEND_URL/api/mcp/execute",
    "method": "POST",
    "headers": {
      "Authorization": "Bearer $AUTH_TOKEN",
      "Content-Type": "application/json"
    },
    "timeout": 30000
  }
}
EOF

echo ""
echo "🔐 Security Notes:"
echo "=================="
echo "• Use HTTPS URLs in production"
echo "• Implement proper JWT authentication"
echo "• Set up rate limiting on your backend"
echo "• Monitor webhook calls for abuse"
echo ""

echo "🚀 Additional Functions to Add:"
echo "================================"
echo "After testing the first 3 functions, add these:"
echo ""
echo "• create_poll"
echo "• start_copilot" 
echo "• stop_copilot"
echo "• get_enrolled_students"
echo "• generate_report"
echo "• post_case"
echo "• get_session_posts"
echo ""

echo "📋 All 44 MCP Tools Available:"
echo "=============================="
echo "Run this to see all tools:"
echo "cd /home/aojie_ju/aristai && ./scripts/list_mcp_tools.sh"