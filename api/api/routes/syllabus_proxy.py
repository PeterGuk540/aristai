"""Proxy endpoints that forward syllabus CRUD requests to the syllabus-tool backend."""

import logging
from fastapi import APIRouter, HTTPException, Query
from typing import Optional
import httpx

from api.core.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/")
async def list_syllabi(
    instructor_id: Optional[int] = Query(None),
    cognito_sub: Optional[str] = Query(None),
):
    """List syllabi, optionally filtered by instructor_id and/or cognito_sub."""
    settings = get_settings()
    params = {}
    if instructor_id is not None:
        params["instructor_id"] = instructor_id
    if cognito_sub is not None:
        params["cognito_sub"] = cognito_sub

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{settings.syllabus_tool_url}/api/v1/syllabi/",
                params=params,
                timeout=30,
            )
            resp.raise_for_status()
            return resp.json()
    except Exception as exc:
        logger.error(f"Syllabus proxy list error: {exc}")
        raise HTTPException(status_code=502, detail=f"Syllabus tool unavailable: {exc}")


@router.get("/{syllabus_id}")
async def get_syllabus(syllabus_id: int):
    """Get a single syllabus by ID."""
    settings = get_settings()

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{settings.syllabus_tool_url}/api/v1/syllabi/{syllabus_id}",
                timeout=30,
            )
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail=exc.response.text)
    except Exception as exc:
        logger.error(f"Syllabus proxy get error: {exc}")
        raise HTTPException(status_code=502, detail=f"Syllabus tool unavailable: {exc}")


@router.delete("/{syllabus_id}")
async def delete_syllabus(syllabus_id: int):
    """Delete a syllabus by ID."""
    settings = get_settings()

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.delete(
                f"{settings.syllabus_tool_url}/api/v1/syllabi/{syllabus_id}",
                timeout=30,
            )
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail=exc.response.text)
    except Exception as exc:
        logger.error(f"Syllabus proxy delete error: {exc}")
        raise HTTPException(status_code=502, detail=f"Syllabus tool unavailable: {exc}")


@router.post("/{syllabus_id}/push-to-forum")
async def push_syllabus_to_forum(
    syllabus_id: int,
    instructor_id: Optional[int] = Query(None),
    cognito_sub: Optional[str] = Query(None),
):
    """Push a syllabus to the forum as a new course. Proxied to syllabus-tool."""
    settings = get_settings()
    params = {}
    if instructor_id is not None:
        params["instructor_id"] = instructor_id
    if cognito_sub is not None:
        params["cognito_sub"] = cognito_sub

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{settings.syllabus_tool_url}/api/v1/syllabi/{syllabus_id}/push-to-forum",
                params=params,
                timeout=60,
            )
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail=exc.response.text)
    except Exception as exc:
        logger.error(f"Syllabus proxy push-to-forum error: {exc}")
        raise HTTPException(status_code=502, detail=f"Syllabus tool unavailable: {exc}")
