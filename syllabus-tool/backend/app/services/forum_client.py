"""HTTP client for communicating with the forum API."""

import logging
from typing import Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

TIMEOUT = 15  # seconds


async def resolve_cognito_sub(cognito_sub: str) -> Optional[dict]:
    """Look up a forum user by Cognito sub. Returns {id, name, email} or None."""
    if not settings.FORUM_API_URL:
        logger.debug("FORUM_API_URL not configured, skipping cognito_sub resolution")
        return None

    url = f"{settings.FORUM_API_URL}/api/users/by-cognito-sub/{cognito_sub}"
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, timeout=TIMEOUT)
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            data = resp.json()
            return {"id": data["id"], "name": data.get("name", ""), "email": data.get("email", "")}
    except Exception as exc:
        logger.warning(f"Failed to resolve cognito_sub {cognito_sub}: {exc}")
        return None


async def create_course(data: dict) -> dict:
    """Create a course in the forum. Returns the created course dict.

    data should contain: title, syllabus_text, syllabus_json, objectives_json, created_by
    """
    if not settings.FORUM_API_URL:
        raise RuntimeError("FORUM_API_URL not configured")

    url = f"{settings.FORUM_API_URL}/api/courses/"
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json=data, timeout=30)
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPStatusError as exc:
        logger.error(f"Forum create_course HTTP error: {exc.response.status_code} {exc.response.text}")
        raise
    except Exception as exc:
        logger.error(f"Forum create_course error: {exc}")
        raise
