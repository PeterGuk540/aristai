#!/bin/bash

echo "🔐 Setting up SSH tunnels to EC2 for MCP server..."
echo "📍 EC2: ec2-13-219-204-7.compute-1.amazonaws.com"
echo "👤 User: ubuntu"
echo "🔑 Key: //wsl.localhost/Ubuntu/home/aojie_ju/aristai-key.pem"
echo ""
echo "This will create SSH tunnels for:"
echo "  - Local port 15432 → EC2 PostgreSQL (5432)"
echo "  - Local port 16379 → EC2 Redis (6379)"
echo ""
echo "Press Ctrl+C to stop tunnels"
echo "========================="

# Ensure key permissions and copy to temp location
cp "//wsl.localhost/Ubuntu/home/aojie_ju/aristai-key.pem" "/tmp/aristai-key.pem"
chmod 600 "/tmp/aristai-key.pem"

# Check if we have SSH key for EC2
echo "🔑 Checking SSH access..."
ssh -i "/tmp/aristai-key.pem" \
    -o StrictHostKeyChecking=no \
    -o ConnectTimeout=10 \
    -o BatchMode=yes \
    ubuntu@ec2-13-219-204-7.compute-1.amazonaws.com "echo 'SSH access: SUCCESS'" || {
    echo "❌ SSH access failed. Please ensure:"
    echo "   1. You have SSH access to ubuntu@ec2-13-219-204-7.compute-1.amazonaws.com"
    echo "   2. Your SSH key is at: //wsl.localhost/Ubuntu/home/aojie_ju/aristai-key.pem"
    echo "   3. The EC2 instance allows SSH access"
    exit 1
}

echo "✅ SSH access confirmed"
echo ""

# Create SSH tunnels
echo "🚀 Creating SSH tunnels..."
echo "PostgreSQL: localhost:5432 → ec2-13-219-204-7.compute-1.amazonaws.com:5432"
echo "Redis: localhost:6379 → ec2-13-219-204-7.compute-1.amazonaws.com:6379"
echo ""

# SSH tunnel command with both ports
ssh -i "/tmp/aristai-key.pem" \
    -o StrictHostKeyChecking=no \
    -L 15432:localhost:5432 \
    -L 16379:localhost:6379 \
    -N \
    ubuntu@ec2-13-219-204-7.compute-1.amazonaws.com

echo ""
echo "🛑 SSH tunnels stopped"