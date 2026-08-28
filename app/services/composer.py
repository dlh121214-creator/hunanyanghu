from __future__ import annotations

import json
import re

from app.errors import AppError
from app.providers.model import MockTextModelClient, TextModelClient
from app.schemas import ComposeResponse, KnowledgeItem


LOCAL_COMPOSE_PROMPT = """你是养护工程交底内容整理助手。只能整理用户提供的材料。
要求：
1. 按施工顺序组织；
2. 合并完全重复的内容；
3. 调整章节结构；
4. 改善文字衔接；
5. 保留每项工程的独有要求；
6. 每项工程必须写明输入材料中的来源名称。
不允许：
- 自行补充技术参数；
- 修改原始数值；
- 删除看似重复但适用范围不同的要求；
- 自行解决知识资料之间的冲突；
- 引用本次输入材料之外的内容。
直接输出整理后的正文。"""


EXTERNAL_COMPOSE_PROMPT = """你是养护工程网络参考资料整理助手。只能整理用户提供的材料。
要求：
1. 输出开头必须明确说明部分或全部内容来源于网络，仅供参考并需要核验；
2. 只能整理本次输入的本地知识和网络API返回内容；
3. 不得使用模型自身知识补充；
4. 每项内容必须保留来源名称，网络来源还要保留链接；
5. 本地来源与网络来源必须明确区分；
6. 不得把网络资料描述为企业正式交底要求；
7. 不得修改技术参数、数值、适用条件和标准编号；
8. 不同来源存在冲突时分别展示，不得自行判断；
9. 无明确来源的内容不得进入结果；
10. 不得通过改写掩盖内容来源。
直接输出整理后的正文。"""

NETWORK_WARNING = (
    "当前知识库无匹配工程类型，部分或全部数据来源于网络，请注意分辨并结合"
    "企业制度、项目实际情况及现行标准进行核验。"
)


def _mock_compose(user_prompt: str) -> str:
    payload = json.loads(user_prompt)
    sections: list[str] = []
    if payload.get("contains_external_content"):
        sections.append(NETWORK_WARNING)
    for index, item in enumerate(payload["items"], start=1):
        source = f"来源：{item['source_name']}"
        if item.get("source_url"):
            source += f"（{item['source_url']}）"
        sections.append(
            f"{index}. {item['type_name']}\n{item['content']}\n{source}"
        )
    return "\n\n".join(sections)


def build_mock_compose_client() -> MockTextModelClient:
    return MockTextModelClient(_mock_compose)


def _protected_tokens(items: list[KnowledgeItem]) -> set[str]:
    tokens: set[str] = set()
    pattern = re.compile(
        r"(?:[A-Za-z]{1,8}[/-]?\d+(?:\.\d+)?(?:[-—][A-Za-z0-9.]+)?)|"
        r"(?:\d+(?:\.\d+)?\s*(?:mm|cm|m|km|kg|t|MPa|%|℃|小时|分钟|天))",
        re.IGNORECASE,
    )
    for item in items:
        tokens.update(pattern.findall(item.content))
    return tokens


def validate_composed_content(
    content: str, items: list[KnowledgeItem]
) -> list[str]:
    errors: list[str] = []
    if not content.strip():
        return ["模型输出为空"]
    for item in items:
        if item.type_name not in content:
            errors.append(f"遗漏工程类型：{item.type_name}")
        if item.source_name not in content:
            errors.append(f"遗漏来源：{item.source_name}")
        if item.source_type == "network" and item.source_url:
            if item.source_url not in content:
                errors.append(f"遗漏网络来源链接：{item.source_url}")
    for token in sorted(_protected_tokens(items)):
        if token not in content:
            errors.append(f"遗漏受保护内容：{token}")
    if any(item.source_type == "network" for item in items):
        if "来源于网络" not in content or "核验" not in content:
            errors.append("网络内容缺少风险提示")
    return errors


class ComposeService:
    def __init__(
        self,
        client: TextModelClient,
        *,
        degrade_on_failure: bool,
    ) -> None:
        self.client = client
        self.degrade_on_failure = degrade_on_failure

    async def compose(
        self, *, request_id: str, items: list[KnowledgeItem]
    ) -> ComposeResponse:
        if len(items) < 2:
            raise AppError(
                code="COMPOSE_NOT_REQUIRED",
                message="只有多个工程时才允许调用整合模型",
                status_code=422,
            )
        contains_external = any(item.source_type == "network" for item in items)
        prompt = EXTERNAL_COMPOSE_PROMPT if contains_external else LOCAL_COMPOSE_PROMPT
        user_prompt = json.dumps(
            {
                "contains_external_content": contains_external,
                "items": [item.model_dump() for item in items],
            },
            ensure_ascii=False,
        )
        try:
            content = await self.client.generate_text(
                system_prompt=prompt,
                user_prompt=user_prompt,
                temperature=0.1,
            )
            errors = validate_composed_content(content, items)
        except AppError as exc:
            if not self.degrade_on_failure:
                raise
            return ComposeResponse(
                request_id=request_id,
                status="degraded",
                output_mode="separate",
                items=items,
                contains_external_content=contains_external,
                warnings=["整合模型调用失败，已降级为分工程展示。"],
                validation_errors=[exc.message],
            )
        if errors:
            if not self.degrade_on_failure:
                raise AppError(
                    code="COMPOSE_VALIDATION_FAILED",
                    message="整合结果未通过安全校验",
                    status_code=502,
                    details={"validation_errors": errors},
                )
            return ComposeResponse(
                request_id=request_id,
                status="degraded",
                output_mode="separate",
                items=items,
                contains_external_content=contains_external,
                warnings=["整合结果未通过安全校验，已降级为分工程展示。"],
                validation_errors=errors,
            )
        warnings = [NETWORK_WARNING] if contains_external else []
        return ComposeResponse(
            request_id=request_id,
            status="success",
            output_mode="composed",
            content=content,
            contains_external_content=contains_external,
            warnings=warnings,
        )
