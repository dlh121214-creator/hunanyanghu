from fastapi.testclient import TestClient

from app.main import create_app
from app.providers.model import MockTextModelClient
from app.services.composer import ComposeService


def _prepare_multiple(client: TestClient) -> str:
    match = client.post(
        "/api/v1/intent/match",
        json={"employee_input": "进行坑槽挖补，并重新铺筑沥青面层"},
    ).json()
    selections = [
        {
            "group_id": group["group_id"],
            "type_id": group["candidates"][0]["type_id"],
        }
        for group in match["engineering_groups"]
    ]
    assert client.post(
        "/api/v1/intent/confirm",
        json={"request_id": match["request_id"], "selections": selections},
    ).status_code == 200
    assert client.post(
        "/api/v1/knowledge/retrieve", json={"request_id": match["request_id"]}
    ).status_code == 200
    return match["request_id"]


def test_multiple_items_are_composed() -> None:
    client = TestClient(create_app())
    request_id = _prepare_multiple(client)

    response = client.post(
        "/api/v1/output/compose", json={"request_id": request_id}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["output_mode"] == "composed"
    assert "坑槽修补" in body["content"]
    assert "沥青混凝土摊铺" in body["content"]


def test_invalid_composed_content_degrades_to_separate_items() -> None:
    app = create_app()
    app.state.compose_service = ComposeService(
        MockTextModelClient(lambda _: "内容不完整"), degrade_on_failure=True
    )
    client = TestClient(app)
    request_id = _prepare_multiple(client)

    response = client.post(
        "/api/v1/output/compose", json={"request_id": request_id}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "degraded"
    assert body["output_mode"] == "separate"
    assert len(body["items"]) == 2
    assert body["validation_errors"]


def test_single_item_cannot_call_compose() -> None:
    client = TestClient(create_app())
    match = client.post(
        "/api/v1/intent/match", json={"employee_input": "进行坑槽挖补"}
    ).json()
    group = match["engineering_groups"][0]
    client.post(
        "/api/v1/intent/confirm",
        json={
            "request_id": match["request_id"],
            "selections": [
                {
                    "group_id": group["group_id"],
                    "type_id": group["candidates"][0]["type_id"],
                }
            ],
        },
    )
    client.post(
        "/api/v1/knowledge/retrieve", json={"request_id": match["request_id"]}
    )

    response = client.post(
        "/api/v1/output/compose", json={"request_id": match["request_id"]}
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "COMPOSE_NOT_REQUIRED"

