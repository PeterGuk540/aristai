#!/bin/bash

echo "🚀 AristAI MCP Server - Complete EC2 Setup via SSH Tunnels"
echo "============================================================"
echo ""

# Step 1: Start SSH tunnels
echo "Step 1: Starting SSH tunnels to EC2..."
cd "//wsl.localhost/Ubuntu/home/aojie_ju/aristai"

# Copy key and set permissions
cp "//wsl.localhost/Ubuntu/home/aojie_ju/aristai-key.pem" "/tmp/aristai-key.pem"
chmod 600 "/tmp/aristai-key.pem"

# Start SSH tunnels in background (use different local ports to avoid Windows conflicts)
ssh -i "/tmp/aristai-key.pem" \
    -o StrictHostKeyChecking=no \
    -L 15432:localhost:5432 \
    -L 16379:localhost:6379 \
    -N \
    -f \
    ubuntu@ec2-13-219-204-7.compute-1.amazonaws.com

# Wait for tunnels to establish
sleep 3

# Check if tunnels are running
if netstat -an | grep -q ":15432.*LISTEN" && netstat -an | grep -q ":16379.*LISTEN"; then
    echo "✅ SSH tunnels established successfully"
else
    echo "❌ Failed to establish SSH tunnels"
    exit 1
fi

echo ""

# Step 2: Test database connections
echo "Step 2: Testing database connections via tunnels..."

python -c "
import sys
sys.path.insert(0, '.')
from api.core.database import SessionLocal
from sqlalchemy import text

# Test PostgreSQL
try:
    db = SessionLocal()
    result = db.execute(text('SELECT version()')).scalar()
    print(f'✅ PostgreSQL: SUCCESS')
    db.close()
except Exception as e:
    print(f'❌ PostgreSQL: FAILED - {e}')
    exit(1)

# Test Redis
try:
    import redis
    from api.core.config import get_settings
    settings = get_settings()
    redis_client = redis.from_url(settings.redis_url)
    redis_client.ping()
    print(f'✅ Redis: SUCCESS')
except Exception as e:
    print(f'❌ Redis: FAILED - {e}')
    exit(1)

print('🎉 All database connections working!')
"

if [ $? -ne 0 ]; then
    echo "❌ Database connection tests failed"
    exit 1
fi

echo ""

# Step 3: Start MCP server
echo "Step 3: Starting MCP server..."
echo "📋 MCP Server will register 44 tools across 8 categories"
echo "🔌 Ready to accept MCP client connections"
echo ""
echo "Press Ctrl+C to stop MCP server"
echo "========================="

# Start MCP server
cd mcp_server
python server.py

# Cleanup when stopped
echo ""
echo "🛑 Stopping SSH tunnels..."
pkill -f "ssh.*ec2-13-219-204-7.compute-1.amazonaws.com"
echo "✅ Cleanup complete"