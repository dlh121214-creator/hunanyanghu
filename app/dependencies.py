from __future__ import annotations

from pathlib import Path

from app.config import Settings
from app.errors import AppError
from app.providers.model import OpenAICompatibleModelClient
from app.providers.knowledge import MockKnowledgeProvider
from app.services.judge import JudgeService, build_mock_judge_client
from app.services.matcher import KeywordMatcher, load_engineering_types
from app.services.composer import ComposeService, build_mock_compose_client
from app.providers.search import (
    HttpNetworkSearchProvider,
    MockNetworkSearchProvider,
    NetworkSearchProvider,
)


def build_judge_service(settings: Settings) -> JudgeService:
    if settings.judge_model_provider == "mock":
        return JudgeService(build_mock_judge_client())
    if settings.judge_model_provider == "api":
        return JudgeService(
            OpenAICompatibleModelClient(
                base_url=settings.judge_model_base_url,
                api_key=settings.judge_model_api_key,
                model_name=settings.judge_model_name,
                timeout_seconds=settings.judge_model_timeout_seconds,
            )
        )
    raise AppError(
        code="MODEL_CONFIG_ERROR",
        message="不支持的判断模型提供者",
        status_code=503,
        details={"provider": settings.judge_model_provider},
    )


def build_keyword_matcher(settings: Settings) -> KeywordMatcher:
    data_path = Path(__file__).resolve().parent.parent / "data" / "engineering_types.json"
    return KeywordMatcher(
        load_engineering_types(data_path),
        top_k=settings.top_k,
        threshold=settings.match_threshold,
    )


def build_knowledge_provider(settings: Settings) -> MockKnowledgeProvider:
    if settings.knowledge_provider != "mock":
        raise AppError(
            code="KNOWLEDGE_CONFIG_ERROR",
            message="正式知识库尚未接入，当前仅支持mock提供者",
            status_code=503,
            details={"provider": settings.knowledge_provider},
        )
    data_path = Path(__file__).resolve().parent.parent / "data" / "mock_knowledge.json"
    return MockKnowledgeProvider(data_path)


def build_compose_service(settings: Settings) -> ComposeService:
    if settings.compose_model_provider == "mock":
        client = build_mock_compose_client()
    elif settings.compose_model_provider == "api":
        client = OpenAICompatibleModelClient(
            base_url=settings.compose_model_base_url,
            api_key=settings.compose_model_api_key,
            model_name=settings.compose_model_name,
            timeout_seconds=settings.compose_model_timeout_seconds,
        )
    else:
        raise AppError(
            code="MODEL_CONFIG_ERROR",
            message="不支持的整合模型提供者",
            status_code=503,
            details={"provider": settings.compose_model_provider},
        )
    return ComposeService(
        client,
        degrade_on_failure=settings.compose_failure_degrade_enabled,
    )


def build_network_search_provider(settings: Settings) -> NetworkSearchProvider:
    if settings.network_search_provider == "mock":
        return MockNetworkSearchProvider()
    if settings.network_search_provider == "api":
        return HttpNetworkSearchProvider(
            base_url=settings.network_search_base_url,
            api_key=settings.network_search_api_key,
            timeout_seconds=settings.network_search_timeout_seconds,
        )
    raise AppError(
        code="NETWORK_SEARCH_CONFIG_ERROR",
        message="不支持的网络搜索提供者",
        status_code=503,
        details={"provider": settings.network_search_provider},
    )
