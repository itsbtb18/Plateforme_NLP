from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Any

from fastapi import Depends, Header, HTTPException, Request, status
from redis import Redis

from app.config import get_settings

settings = get_settings()


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def verify_jwt_hs256(token: str) -> dict[str, Any]:
    """Minimal HS256 validation to avoid runtime coupling to external JWT libs."""
    try:
        header_b64, payload_b64, sig_b64 = token.split(".")
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc

    signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")
    expected_sig = hmac.new(
        settings.AI_JWT_SECRET.encode("utf-8"),
        signing_input,
        digestmod=hashlib.sha256,
    ).digest()
    provided_sig = _b64url_decode(sig_b64)

    if not hmac.compare_digest(expected_sig, provided_sig):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid signature")

    payload = json.loads(_b64url_decode(payload_b64).decode("utf-8"))
    exp = payload.get("exp")
    if exp is not None and int(exp) < int(time.time()):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    return payload


async def require_jwt(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    if settings.AI_JWT_OPTIONAL and not authorization:
        return {"sub": "anonymous", "roles": ["public"]}

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")

    token = authorization.removeprefix("Bearer ").strip()
    return verify_jwt_hs256(token)


def _client_identifier(request: Request, claims: dict[str, Any]) -> str:
    if claims.get("sub"):
        return str(claims["sub"])
    return request.client.host if request.client else "unknown"


async def enforce_rate_limit(
    request: Request,
    claims: dict[str, Any] = Depends(require_jwt),
) -> dict[str, Any]:
    client_id = _client_identifier(request, claims)
    key = f"rate:ai:{client_id}:{int(time.time() // 60)}"

    redis_client = Redis.from_url(settings.REDIS_URL, decode_responses=True)
    current = redis_client.incr(key)
    if current == 1:
        redis_client.expire(key, 90)

    if current > settings.AI_RATE_LIMIT_PER_MINUTE:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Rate limit exceeded")

    return claims
