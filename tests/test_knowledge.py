from fastapi.testclient import TestClient

from app.main import create_app


def _confirm(client: TestClient, employee_input: str, selected_indexes: list[int]) -> str:
    match = client.post(
        "/api/v1/intent/match", json={"employee_input": employee_input}
    ).json()
    selections = []
    for group, index in zip(match["engineering_groups"], selected_indexes, strict=True):
        selections.append(
            {
                "group_id": group["group_id"],
                "type_id": group["candidates"][index]["type_id"],
            }
        )
    response = client.post(
        "/api/v1/intent/confirm",
        json={"request_id": match["request_id"], "selections": selections},
    )
    assert response.status_code == 200
    return match["request_id"]


def test_single_engineering_retrieval_is_direct() -> None:
    client = TestClient(create_app())
    request_id = _confirm(client, "进行坑槽挖补", [0])

    response = client.post(
        "/api/v1/knowledge/retrieve", json={"request_id": request_id}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["output_mode"] == "direct"
    assert body["items"][0]["source_type"] == "local"


def test_multiple_engineering_retrieval_requires_compose() -> None:
    client = TestClient(create_app())
    request_id = _confirm(client, "进行坑槽挖补，并重新铺筑沥青面层", [0, 0])

    response = client.post(
        "/api/v1/knowledge/retrieve", json={"request_id": request_id}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["output_mode"] == "compose"
    assert len(body["items"]) == 2


def test_missing_mock_knowledge_marks_network_fallback() -> None:
    client = TestClient(create_app())
    request_id = _confirm(client, "需要重新划线恢复道路标线", [0])

    response = client.post(
        "/api/v1/knowledge/retrieve", json={"request_id": request_id}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "fallback_required"
    assert body["missing_items"][0]["reason"] == "network_search_disabled"
