from __future__ import annotations

import re

from pydantic import ValidationError

from app.errors import AppError
from app.providers.model import JsonModelClient, MockJsonModelClient
from app.schemas import EngineeringGroupExtraction


JUDGE_SYSTEM_PROMPT = """你是养护工程描述分组助手。
只判断员工输入中包含一个还是多个独立养护工程，并将每个工程整理为简短描述。
不要匹配标准标签，不要计算匹配度，不要生成施工或养护内容。
不得创造员工没有提到的工程。只返回符合JSON Schema的结果。"""


# 千问结构化输出接口对JSON Schema子集的兼容性更稳定。这里仅向模型发送
# 扁平结构；长度、数量等完整业务约束仍由EngineeringGroupExtraction校验。
JUDGE_OUTPUT_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {
        "engineering_groups": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "group_id": {"type": "string"},
                    "engineering_description": {"type": "string"},
                },
                "required": ["group_id", "engineering_description"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["engineering_groups"],
    "additionalProperties": False,
}


def _mock_judge(user_input: str) -> dict[str, object]:
    text = user_input.strip()
    parts = [
        part.strip(" ，,。；;")
        for part in re.split(r"(?:并且|同时|以及|并|；|;)", text)
        if part.strip(" ，,。；;")
    ]
    if not parts:
        parts = [text]
    return {
        "engineering_groups": [
            {
                "group_id": f"group_{index}",
                "engineering_description": part,
            }
            for index, part in enumerate(parts, start=1)
        ]
    }


def build_mock_judge_client() -> MockJsonModelClient:
    return MockJsonModelClient(_mock_judge)


class JudgeService:
    def __init__(self, client: JsonModelClient) -> None:
        self.client = client

    async def analyze(self, employee_input: str) -> EngineeringGroupExtraction:
        if not employee_input.strip():
            raise AppError(
                code="EMPTY_EMPLOYEE_INPUT",
                message="工程描述不能为空",
                status_code=422,
            )

        last_error: AppError | None = None
        for attempt in range(2):
            repair = (
                "\n上一次输出未通过结构校验，请严格按照JSON Schema重新输出。"
                if attempt
                else ""
            )
            try:
                raw = await self.client.generate_json(
                    system_prompt=JUDGE_SYSTEM_PROMPT + repair,
                    user_prompt=employee_input,
                    schema_name="engineering_group_extraction",
                    schema=JUDGE_OUTPUT_SCHEMA,
                    temperature=0.0,
                )
                return EngineeringGroupExtraction.model_validate(raw)
            except ValidationError as exc:
                last_error = AppError(
                    code="MODEL_SCHEMA_VALIDATION_FAILED",
                    message="判断模型输出未通过结构校验",
                    status_code=502,
                    details={"errors": exc.errors()},
                )
            except AppError as exc:
                last_error = exc
                if exc.code not in {
                    "MODEL_RESPONSE_INVALID",
                    "MODEL_SCHEMA_VALIDATION_FAILED",
                }:
                    break
        assert last_error is not None
        raise last_error
