from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol

from pydantic import TypeAdapter, ValidationError

from app.errors import AppError
from app.schemas import KnowledgeItem


class KnowledgeProvider(Protocol):
    async def retrieve(
        self,
        *,
        group_id: str,
        type_id: str,
        type_name: str,
    ) -> KnowledgeItem | None: ...


class MockKnowledgeProvider:
    def __init__(self, data_path: Path) -> None:
        try:
            raw = json.loads(data_path.read_text(encoding="utf-8"))
            self._items = TypeAdapter(list[dict[str, object]]).validate_python(raw)
        except (OSError, ValueError, ValidationError) as exc:
            raise AppError(
                code="KNOWLEDGE_LOAD_FAILED",
                message="模拟知识数据加载失败",
                status_code=500,
                details={"path": str(data_path)},
            ) from exc

    async def retrieve(
        self,
        *,
        group_id: str,
        type_id: str,
        type_name: str,
    ) -> KnowledgeItem | None:
        raw = next((item for item in self._items if item["type_id"] == type_id), None)
        if raw is None:
            return None
        return KnowledgeItem(
            document_id=str(raw["document_id"]),
            group_id=group_id,
            type_id=type_id,
            type_name=type_name,
            title=str(raw["title"]),
            content=str(raw["content"]),
            source_type="local",
            source_name=str(raw["source_name"]),
            source_version=str(raw.get("source_version") or "mock"),
        )

