from __future__ import annotations

import json
import re
from pathlib import Path

from app.errors import AppError
from app.schemas import EngineeringType, MatchCandidate


def _normalize(text: str) -> str:
    return re.sub(r"[^0-9a-zA-Z\u4e00-\u9fff]+", "", text).lower()


def load_engineering_types(path: Path) -> list[EngineeringType]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        items = [EngineeringType.model_validate(item) for item in raw]
    except (OSError, ValueError) as exc:
        raise AppError(
            code="ENGINEERING_TYPES_LOAD_FAILED",
            message="标准工程标签加载失败",
            status_code=500,
            details={"path": str(path)},
        ) from exc
    enabled = [item for item in items if item.enabled]
    if not enabled:
        raise AppError(
            code="ENGINEERING_TYPES_EMPTY",
            message="没有可用的标准工程标签",
            status_code=500,
        )
    return enabled


class KeywordMatcher:
    def __init__(
        self,
        engineering_types: list[EngineeringType],
        *,
        top_k: int,
        threshold: int,
    ) -> None:
        self.engineering_types = engineering_types
        self.top_k = top_k
        self.threshold = threshold

    def _score(
        self, description: str, engineering_type: EngineeringType
    ) -> tuple[int, list[str]]:
        normalized = _normalize(description)
        type_name = _normalize(engineering_type.type_name)
        aliases = [_normalize(alias) for alias in engineering_type.aliases]

        matched_keywords = [
            keyword
            for keyword in engineering_type.keywords
            if _normalize(keyword) and _normalize(keyword) in normalized
        ]

        if type_name and type_name in normalized:
            return 100, matched_keywords
        if any(alias and alias in normalized for alias in aliases):
            return 95, matched_keywords
        if not engineering_type.keywords:
            return 0, []

        keyword_coverage = len(matched_keywords) / len(engineering_type.keywords)
        score = round(keyword_coverage * 100)
        return score, matched_keywords

    def match(self, description: str) -> list[MatchCandidate]:
        ranked: list[MatchCandidate] = []
        for engineering_type in self.engineering_types:
            score, matched_keywords = self._score(description, engineering_type)
            ranked.append(
                MatchCandidate(
                    type_id=engineering_type.type_id,
                    type_name=engineering_type.type_name,
                    match_score=score,
                    above_threshold=score >= self.threshold,
                    matched_keywords=matched_keywords,
                )
            )
        ranked.sort(key=lambda item: (-item.match_score, item.type_name))
        return ranked[: self.top_k]

    def has_type(self, type_id: str) -> bool:
        return any(item.type_id == type_id for item in self.engineering_types)

