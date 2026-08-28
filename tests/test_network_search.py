from dataclasses import replace

from fastapi.testclient import TestClient

from app.config import load_settings
from app.main import create_app


def test_network_fallback_adds_source_and_warning() -> None:
    settings = replace(
        load_settings(),
        network_search_enabled=True,
        network_search_provider="mock",
    )
    client = TestClient(create_app(settings))
    match = client.post(
        "/api/v1/intent/match",
        json={"employee_input": "开展一种尚未收录的特殊作业"},
    ).json()
    group = match["engineering_groups"][0]
    client.post(
        "/api/v1/intent/confirm",
        json={
            "request_id": match["request_id"],
            "selections": [
                {"group_id": group["group_id"], "use_network_fallback": True}
            ],
        },
    )

    response = client.post(
        "/api/v1/knowledge/retrieve",
        json={"request_id": match["request_id"], "allow_network_fallback": True},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["contains_external_content"] is True
    assert body["items"][0]["source_type"] == "network"
    assert body["items"][0]["source_url"]
    assert "来源于网络" in body["items"][0]["warning"]


def test_disabled_network_search_never_returns_network_item() -> None:
    client = TestClient(create_app())
    match = client.post(
        "/api/v1/intent/match",
        json={"employee_input": "开展一种尚未收录的特殊作业"},
    ).json()
    group = match["engineering_groups"][0]
    client.post(
        "/api/v1/intent/confirm",
        json={
            "request_id": match["request_id"],
            "selections": [
                {"group_id": group["group_id"], "use_network_fallback": True}
            ],
        },
    )

    response = client.post(
        "/api/v1/knowledge/retrieve",
        json={"request_id": match["request_id"]},
    )

    body = response.json()
    assert body["status"] == "fallback_required"
    assert body["items"] == []
    assert body["missing_items"][0]["reason"] == "network_search_disabled"


def test_capabilities_do_not_expose_secrets() -> None:
    client = TestClient(create_app())
    body = client.get("/api/v1/system/capabilities").json()

    assert "api_key" not in body
    assert body["top_k"] == 3

