"""
app.services.router — query routing.

Public API:
  - QueryRouter, get_query_router
  - RoutingResult (dataclass)
"""
from app.services.router.engine import (
    QueryRouter,
    RoutingResult,
    get_query_router,
)

__all__ = [
    "QueryRouter",
    "RoutingResult",
    "get_query_router",
]
