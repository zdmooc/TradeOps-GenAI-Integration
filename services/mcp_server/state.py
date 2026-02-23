"""Minimal in-memory state for the MCP server.

Tracks the current correlation_id and a simple tool-call counter.
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional


class MCPState:
    """Lightweight state container for the MCP server."""

    def __init__(self) -> None:
        self._correlation_id: Optional[str] = None
        self._call_count: int = 0
        self._started_at: str = datetime.now(timezone.utc).isoformat()

    def set_correlation_id(self, cid: str) -> None:
        self._correlation_id = cid
        self._call_count += 1

    @property
    def correlation_id(self) -> Optional[str]:
        return self._correlation_id

    @property
    def call_count(self) -> int:
        return self._call_count

    def to_dict(self) -> Dict[str, Any]:
        return {
            "current_correlation_id": self._correlation_id,
            "total_calls": self._call_count,
            "started_at": self._started_at,
        }
