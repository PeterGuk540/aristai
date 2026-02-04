#!/bin/bash

# ElevenLabs Agent Setup Script for AristAI
# This script helps configure ElevenLabs Agent for optimal voice assistant performance

echo "=== AristAI ElevenLabs Agent Setup ==="
echo ""
echo "This script will help you configure ElevenLabs Agent for significantly faster voice responses."
echo ""

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "❌ Error: .env file not found. Please copy .env.example to .env first."
    exit 1
fi

echo "📋 Current Configuration:"
echo "========================"
grep "ELEVENLABS_" .env | grep -v "^#"
echo ""

# Check if required fields are set
API_KEY_SET="true"
AGENT_ID_SET="true"

if [ "" = "false" ] || [ "" = "false" ]; then
    echo "⚠️  Configuration needed. Please provide the following:"
    echo ""
    
    if [ "" = "false" ]; then
        echo "🔑 1. Get your ElevenLabs API Key:"
        echo "   - Go to https://elevenlabs.io/app/settings/api-keys"
        echo "   - Create a new API key"
        echo "   - Copy it here:"
        read -p "   Enter your ElevenLabs API Key: " API_KEY
        
        if [ ! -z "" ]; then
            sed -i "s/ELEVENLABS_API_KEY=.*/ELEVENLABS_API_KEY=/" .env
            echo "   ✅ API Key saved"
        fi
        echo ""
    fi
    
    if [ "" = "false" ]; then
        echo "🤖 2. Create your ElevenLabs Agent:"
        echo "   - Go to https://elevenlabs.io/app/agents"
        echo "   - Create a new agent with:"
        echo "     * Voice: Adam (or your preferred voice)"
        echo "     * Model: GPT-4 or similar"
        echo "     * Language: English"
        echo "   - Copy the Agent ID from the URL or agent details"
        echo "   - Paste it here:"
        read -p "   Enter your ElevenLabs Agent ID: " AGENT_ID
        
        if [ ! -z "" ]; then
            sed -i "s/ELEVENLABS_AGENT_ID=.*/ELEVENLABS_AGENT_ID=/" .env
            echo "   ✅ Agent ID saved"
        fi
        echo ""
    fi
else
    echo "✅ ElevenLabs configuration appears to be complete!"
fi

echo "🎯 Performance Benefits:"
echo "======================="
echo "• Response Time: 200-500ms (vs 1-2s with traditional TTS)"
echo "• Better Conversation Flow: Natural turn-taking and interruptions"
echo "• Integrated Pipeline: ASR + LLM + TTS in one optimized service"
echo "• Lower Infrastructure Complexity: Single API endpoint"
echo ""

echo "🚀 Next Steps:"
echo "===============
