"""
ElevenLabs Agent service for realtime conversation support.

Provides signed URLs for direct browser-to-ElevenLabs WebSocket connections.
"""
import logging
from typing import Optional

import httpx
from api.core.config import get_settings

logger = logging.getLogger(__name__)


async def get_signed_url() -> str:
    """
    Get a signed WebSocket URL from ElevenLabs for realtime agent conversation.
    
    Returns:
        str: WebSocket URL (wss://...) for direct browser connection
        
    Raises:
        ValueError: If required environment variables are missing
        httpx.HTTPError: If the ElevenLabs API request fails
    """
    settings = get_settings()
    
    # Validate required environment variables
    if not settings.elevenlabs_api_key:
        raise ValueError("ELEVENLABS_API_KEY environment variable is required")
    
    if not settings.elevenlabs_agent_id:
        raise ValueError("ELEVENLABS_AGENT_ID environment variable is required")
    
    # Call the official ElevenLabs endpoint
    url = f"https://api.elevenlabs.io/v1/convai/conversation/get-signed-url?agent_id={settings.elevenlabs_agent_id}"
    
    headers = {
        "xi-api-key": settings.elevenlabs_api_key,
        "Content-Type": "application/json",
    }
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, headers=headers)
            
            # Handle non-200 responses
            if response.status_code != 200:
                logger.error(f"ElevenLabs API error {response.status_code}: {response.text}")
                raise httpx.HTTPStatusError(
                    f"ElevenLabs API returned {response.status_code}",
                    request=response.request,
                    response=response
                )
            
            # Parse and return the signed URL
            data = response.json()
            signed_url = data.get("signed_url")
            
            if not signed_url:
                raise ValueError("ElevenLabs API response missing signed_url field")
            
            logger.info(f"✅ Generated signed URL: {signed_url[:50]}...")
            return signed_url
            
    except httpx.HTTPError as e:
        logger.error(f"ElevenLabs API request failed: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error getting signed URL: {e}")
        raise