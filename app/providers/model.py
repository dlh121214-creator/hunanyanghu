from __future__ import annotations

import json
import re
from collections.abc import Callable
from typing import Any, Protocol

import httpx

from app.errors import AppError


class JsonModelClient(Protocol):
    async def generate_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        schema_name: str,
        schema: dict[str, Any],
        temperature: float = 0.0,
    ) -> dict[str, Any]: ...


class TextModelClient(Protocol):
    async def generate_text(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.1,
    ) -> str: ...


def _extract_json(content: str) -> dict[str, Any]:
    cleaned = content.strip()
    fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", cleaned, re.DOTALL)
    if fenced:
        cleaned = fenced.group(1).strip()
    try:
        value = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise AppError(
            code="MODEL_RESPONSE_INVALID",
            message="模型未返回合法JSON",
            status_code=502,
            details={"reason": str(exc)},
        ) from exc
    if not isinstance(value, dict):
        raise AppError(
            code="MODEL_RESPONSE_INVALID",
            message="模型JSON顶层必须是对象",
            status_code=502,
        )
    return value


class OpenAICompatibleModelClient:
    def __init__(
        self,
        *,
        base_url: str | None,
        api_key: str | None,
        model_name: str,
        timeout_seconds: int,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        if not base_url:
            raise AppError(
                code="MODEL_CONFIG_ERROR",
                message="模型API地址未配置",
                status_code=503,
            )
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model_name = model_name
        self.timeout_seconds = timeout_seconds
        self.transport = transport

    def _endpoint(self) -> str:
        if self.base_url.endswith("/chat/completions"):
            return self.base_url
        return f"{self.base_url}/chat/completions"

    async def _post(self, payload: dict[str, Any]) -> str:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        try:
            async with httpx.AsyncClient(
                timeout=self.timeout_seconds, transport=self.transport
            ) as client:
                response = await client.post(
                    self._endpoint(), headers=headers, json=payload
                )
                response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise AppError(
                code="MODEL_TIMEOUT",
                message="模型API调用超时",
                status_code=504,
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise AppError(
                code="MODEL_UPSTREAM_ERROR",
                message="模型API返回异常状态",
                status_code=502,
                details={"upstream_status": exc.response.status_code},
            ) from exc
        except httpx.HTTPError as exc:
            raise AppError(
                code="MODEL_UNAVAILABLE",
                message="无法连接模型API",
                status_code=503,
                details={"reason": type(exc).__name__},
            ) from exc

        try:
            body = response.json()
            content = body["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise AppError(
                code="MODEL_RESPONSE_INVALID",
                message="模型API响应结构不符合OpenAI兼容格式",
                status_code=502,
            ) from exc
        if not isinstance(content, str) or not content.strip():
            raise AppError(
                code="MODEL_RESPONSE_INVALID",
                message="模型API返回内容为空",
                status_code=502,
            )
        return content

    async def generate_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        schema_name: str,
        schema: dict[str, Any],
        temperature: float = 0.0,
    ) -> dict[str, Any]:
        schema_instruction = (
            "\n必须只返回一个JSON对象，并满足以下JSON Schema：\n"
            + json.dumps(schema, ensure_ascii=False, separators=(",", ":"))
        )
        payload = {
            "model": self.model_name,
            "messages": [
                {
                    "role": "system",
                    "content": system_prompt + schema_instruction,
                },
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
            "enable_thinking": False,
            # qwen3-8b对json_object下的对象数组响应更稳定；返回后仍由
            # 业务Schema严格校验。保留schema_name参数以兼容统一客户端协议。
            "response_format": {"type": "json_object"},
        }
        del schema_name
        return _extract_json(await self._post(payload))

    async def generate_text(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.1,
    ) -> str:
        return await self._post(
            {
                "model": self.model_name,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": temperature,
                "enable_thinking": False,
            }
        )


class MockJsonModelClient:
    def __init__(self, responder: Callable[[str], dict[str, Any]]) -> None:
        self.responder = responder

    async def generate_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        schema_name: str,
        schema: dict[str, Any],
        temperature: float = 0.0,
    ) -> dict[str, Any]:
        del system_prompt, schema_name, schema, temperature
        return self.responder(user_prompt)


class MockTextModelClient:
    def __init__(self, responder: Callable[[str], str]) -> None:
        self.responder = responder

    async def generate_text(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.1,
    ) -> str:
        del system_prompt, temperature
        return self.responder(user_prompt)
