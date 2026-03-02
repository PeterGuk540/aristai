"""Proxy endpoints that forward syllabus CRUD requests to the syllabus-tool backend."""

import logging
from fastapi import APIRouter, HTTPException, Query
from typing import Optional
import httpx

from api.core.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/")
async def list_syllabi(instructor_id: Optional[int] = Query(None)):
    """List syllabi, optionally filtered by instructor_id."""
    settings = get_settings()
    params = {}
    if instructor_id is not None:
        params["instructor_id"] = instructor_id

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
