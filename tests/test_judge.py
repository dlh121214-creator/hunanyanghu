import json

import httpx
import pytest

from app.providers.model import MockJsonModelClient, OpenAICompatibleModelClient
from app.services.judge import JudgeService, build_mock_judge_client


@pytest.mark.asyncio
async def test_mock_judge_splits_multiple_engineering_descriptions() -> None:
    service = JudgeService(build_mock_judge_client())

    result = await service.analyze("坑槽挖补，并重新铺筑沥青面层")

    assert len(result.engineering_groups) == 2
    assert result.engineering_groups[0].group_id == "group_1"


@pytest.mark.asyncio
async def test_judge_retries_invalid_schema_once() -> None:
    calls = 0

    def responder(_: str) -> dict[str, object]:
        nonlocal calls
        calls += 1
        if calls == 1:
            return {"engineering_groups": []}
        return {
            "engineering_groups": [
                {
                    "group_id": "group_1",
                    "engineering_description": "坑槽修补",
                }
            ]
        }

    service = JudgeService(MockJsonModelClient(responder))
    result = await service.analyze("坑槽修补")

    assert calls == 2
    assert len(result.engineering_groups) == 1


@pytest.mark.asyncio
async def test_openai_compatible_client_parses_json_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert payload["model"] == "qwen3-8b"
        assert payload["enable_thinking"] is False
        assert payload["response_format"]["type"] == "json_object"
        assert "engineering_groups" in payload["messages"][0]["content"]
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "engineering_groups": [
                                        {
                                            "group_id": "group_1",
                                            "engineering_description": "坑槽修补",
                                        }
                                    ]
                                },
                                ensure_ascii=False,
                            )
                        }
                    }
                ]
            },
        )

    client = OpenAICompatibleModelClient(
        base_url="https://model.example/v1",
        api_key="secret",
        model_name="qwen3-8b",
        timeout_seconds=30,
        transport=httpx.MockTransport(handler),
    )
    service = JudgeService(client)

    result = await service.analyze("坑槽修补")

    assert result.engineering_groups[0].engineering_description == "坑槽修补"
