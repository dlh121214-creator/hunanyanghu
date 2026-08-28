from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _load_env_file() -> None:
    """加载项目根目录的 .env，已有系统环境变量优先。"""
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if not env_path.is_file():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        os.environ.setdefault(key, value)


def _as_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _as_int(value: str | None, default: int) -> int:
    if value is None:
        return default
    return int(value)


@dataclass(frozen=True, slots=True)
class Settings:
    app_name: str
    app_version: str
    environment: str
    cors_origins: tuple[str, ...]
    top_k: int
    match_threshold: int
    judge_model_provider: str
    judge_model_base_url: str | None
    judge_model_api_key: str | None
    judge_model_name: str
    judge_model_timeout_seconds: int
    compose_model_provider: str
    compose_model_base_url: str | None
    compose_model_api_key: str | None
    compose_model_name: str
    compose_model_timeout_seconds: int
    local_knowledge_enabled: bool
    knowledge_provider: str
    knowledge_file_path: str | None
    network_search_enabled: bool
    network_search_fallback_enabled: bool
    network_search_provider: str
    network_search_base_url: str | None
    network_search_api_key: str | None
    network_search_timeout_seconds: int
    multi_project_compose_enabled: bool
    compose_failure_degrade_enabled: bool
    issue_report_enabled: bool


def load_settings() -> Settings:
    _load_env_file()
    origins = tuple(
        item.strip()
        for item in os.getenv(
            "CORS_ORIGINS",
            "http://localhost:3000,http://localhost:5173,http://127.0.0.1:8000",
        ).split(",")
        if item.strip()
    )
    return Settings(
        app_name="湖南养护工程施工交底参考系统智能体服务",
        app_version="0.1.0",
        environment=os.getenv("APP_ENV", "development"),
        cors_origins=origins,
        top_k=_as_int(os.getenv("TOP_K"), 3),
        match_threshold=_as_int(os.getenv("MATCH_THRESHOLD"), 70),
        judge_model_provider=os.getenv("JUDGE_MODEL_PROVIDER", "mock"),
        judge_model_base_url=os.getenv("JUDGE_MODEL_BASE_URL"),
        judge_model_api_key=os.getenv("JUDGE_MODEL_API_KEY"),
        judge_model_name=os.getenv("JUDGE_MODEL_NAME", "qwen3-8b"),
        judge_model_timeout_seconds=_as_int(
            os.getenv("JUDGE_MODEL_TIMEOUT_SECONDS"), 30
        ),
        compose_model_provider=os.getenv("COMPOSE_MODEL_PROVIDER", "mock"),
        compose_model_base_url=os.getenv("COMPOSE_MODEL_BASE_URL"),
        compose_model_api_key=os.getenv("COMPOSE_MODEL_API_KEY"),
        compose_model_name=os.getenv("COMPOSE_MODEL_NAME", "qwen3-8b"),
        compose_model_timeout_seconds=_as_int(
            os.getenv("COMPOSE_MODEL_TIMEOUT_SECONDS"), 120
        ),
        local_knowledge_enabled=_as_bool(
            os.getenv("LOCAL_KNOWLEDGE_ENABLED"), False
        ),
        knowledge_provider=os.getenv("KNOWLEDGE_PROVIDER", "mock"),
        knowledge_file_path=os.getenv("KNOWLEDGE_FILE_PATH"),
        network_search_enabled=_as_bool(
            os.getenv("NETWORK_SEARCH_ENABLED"), False
        ),
        network_search_fallback_enabled=_as_bool(
            os.getenv("NETWORK_SEARCH_FALLBACK_ENABLED"), True
        ),
        network_search_provider=os.getenv("NETWORK_SEARCH_PROVIDER", "mock"),
        network_search_base_url=os.getenv("NETWORK_SEARCH_BASE_URL"),
        network_search_api_key=os.getenv("NETWORK_SEARCH_API_KEY"),
        network_search_timeout_seconds=_as_int(
            os.getenv("NETWORK_SEARCH_TIMEOUT_SECONDS"), 30
        ),
        multi_project_compose_enabled=_as_bool(
            os.getenv("MULTI_PROJECT_COMPOSE_ENABLED"), True
        ),
        compose_failure_degrade_enabled=_as_bool(
            os.getenv("COMPOSE_FAILURE_DEGRADE_ENABLED"), True
        ),
        issue_report_enabled=_as_bool(os.getenv("ISSUE_REPORT_ENABLED"), True),
    )
