from __future__ import annotations

import asyncio
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any


class InMemoryWorkflowStore:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._matches: dict[str, dict[str, Any]] = {}
        self._confirmations: dict[str, dict[str, Any]] = {}
        self._issues: dict[str, dict[str, Any]] = {}
        self._retrievals: dict[str, dict[str, Any]] = {}

    async def save_match(self, request_id: str, data: dict[str, Any]) -> None:
        async with self._lock:
            self._matches[request_id] = {
                **deepcopy(data),
                "created_at": datetime.now(UTC).isoformat(),
            }

    async def get_match(self, request_id: str) -> dict[str, Any] | None:
        async with self._lock:
            value = self._matches.get(request_id)
            return deepcopy(value) if value else None

    async def save_confirmation(self, request_id: str, data: dict[str, Any]) -> None:
        async with self._lock:
            self._confirmations[request_id] = {
                **deepcopy(data),
                "confirmed_at": datetime.now(UTC).isoformat(),
            }

    async def get_confirmation(self, request_id: str) -> dict[str, Any] | None:
        async with self._lock:
            value = self._confirmations.get(request_id)
            return deepcopy(value) if value else None

    async def save_issue(self, report_id: str, data: dict[str, Any]) -> None:
        async with self._lock:
            self._issues[report_id] = {
                **deepcopy(data),
                "status": "pending",
                "created_at": datetime.now(UTC).isoformat(),
            }

    async def get_issue(self, report_id: str) -> dict[str, Any] | None:
        async with self._lock:
            value = self._issues.get(report_id)
            return deepcopy(value) if value else None

    async def save_retrieval(self, request_id: str, data: dict[str, Any]) -> None:
        async with self._lock:
            self._retrievals[request_id] = {
                **deepcopy(data),
                "retrieved_at": datetime.now(UTC).isoformat(),
            }

    async def get_retrieval(self, request_id: str) -> dict[str, Any] | None:
        async with self._lock:
            value = self._retrievals.get(request_id)
            return deepcopy(value) if value else None
