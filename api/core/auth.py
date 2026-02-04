from typing import Optional

from fastapi import Header, HTTPException, status


async def require_auth(authorization: Optional[str] = Header(default=None, alias="Authorization")) -> str:
    """Require an Authorization header for protected endpoints.

    TODO: Validate Cognito JWTs (or API Gateway JWT authorizer tokens) here.
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header required",
        )
    return authorization
