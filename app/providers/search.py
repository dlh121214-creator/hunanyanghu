from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Protocol

import httpx

from app.errors import AppError
from app.schemas import KnowledgeItem
from app.services.composer import NETWORK_WARNING


class NetworkSearchProvider(Protocol):
    async def search(self, *, group_id: str, query: str) -> KnowledgeItem | None: ...


class MockNetworkSearchProvider:
    async def search(self, *, group_id: str, query: str) -> KnowledgeItem | None:
        return KnowledgeItem(
            document_id=f"network_mock_{group_id}",
            group_id=group_id,
            type_name=query,
            title=f"{query}网络参考资料（Mock）",
            content=f"【模拟网络数据】关于“{query}”的网络参考内容，仅用于验证兜底流程。",
            source_type="network",
            source_name="开发阶段模拟网络搜索",
            source_url="https://example.com/mock-maintenance-reference",
            retrieved_at=datetime.now(UTC).isoformat(),
            warning=NETWORK_WARNING,
        )


class HttpNetworkSearchProvider:
    """通用HTTP搜索适配器。

    上游请求格式：{"query": str, "top_k": 1}
    上游响应格式：{"results": [{"title", "content", "source_name", "url"}]}
    若实际服务格式不同，只需替换本适配器，不影响业务接口。
    """

    def __init__(
        self,
        *,
        base_url: str | None,
        api_key: str | None,
        timeout_seconds: int,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        if not base_url:
            raise AppError(
                code="NETWORK_SEARCH_CONFIG_ERROR",
                message="网络搜索API地址未配置",
                status_code=503,
            )
        self.base_url = base_url
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.transport = transport

    async def search(self, *, group_id: str, query: str) -> KnowledgeItem | None:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        try:
            async with httpx.AsyncClient(
                timeout=self.timeout_seconds, transport=self.transport
            ) as client:
                response = await client.post(
                    self.base_url,
                    headers=headers,
                    json={"query": query, "top_k": 1},
                )
                response.raise_for_status()
                body: dict[str, Any] = response.json()
        except httpx.TimeoutException as exc:
            raise AppError(
                code="NETWORK_SEARCH_TIMEOUT",
                message="网络搜索API调用超时",
                status_code=504,
            ) from exc
        except (httpx.HTTPError, ValueError) as exc:
            raise AppError(
                code="NETWORK_SEARCH_UNAVAILABLE",
                message="网络搜索API调用失败",
                status_code=502,
                details={"reason": type(exc).__name__},
            ) from exc

        results = body.get("results")
        if not isinstance(results, list) or not results:
            return None
        result = results[0]
        required = {"title", "content", "source_name", "url"}
        if not isinstance(result, dict) or not required.issubset(result):
            raise AppError(
                code="NETWORK_SEARCH_RESPONSE_INVALID",
                message="网络搜索API响应缺少来源字段",
                status_code=502,
            )
        return KnowledgeItem(
            document_id=f"network_{group_id}",
            group_id=group_id,
            type_name=query,
            title=str(result["title"]),
            content=str(result["content"]),
            source_type="network",
            source_name=str(result["source_name"]),
            source_url=str(result["url"]),
            retrieved_at=datetime.now(UTC).isoformat(),
            warning=NETWORK_WARNING,
        )
