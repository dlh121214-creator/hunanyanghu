from fastapi.testclient import TestClient

from app.main import create_app


def _create_match(client: TestClient) -> dict:
    response = client.post(
        "/api/v1/intent/match", json={"employee_input": "进行坑槽挖补"}
    )
    assert response.status_code == 200
    return response.json()


def test_confirm_candidate_from_returned_list() -> None:
    client = TestClient(create_app())
    match = _create_match(client)
    group = match["engineering_groups"][0]
    candidate = group["candidates"][0]

    response = client.post(
        "/api/v1/intent/confirm",
        json={
            "request_id": match["request_id"],
            "selections": [
                {"group_id": group["group_id"], "type_id": candidate["type_id"]}
            ],
        },
    )

    assert response.status_code == 200
    assert response.json()["next_action"] == "retrieve"


def test_confirm_rejects_type_outside_candidates() -> None:
    client = TestClient(create_app())
    match = _create_match(client)
    group_id = match["engineering_groups"][0]["group_id"]

    response = client.post(
        "/api/v1/intent/confirm",
        json={
            "request_id": match["request_id"],
            "selections": [{"group_id": group_id, "type_id": "NOT_RETURNED"}],
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "TYPE_NOT_IN_CANDIDATES"


def test_network_fallback_can_be_selected() -> None:
    client = TestClient(create_app())
    match = _create_match(client)
    group_id = match["engineering_groups"][0]["group_id"]

    response = client.post(
        "/api/v1/intent/confirm",
        json={
            "request_id": match["request_id"],
            "selections": [
                {"group_id": group_id, "use_network_fallback": True}
            ],
        },
    )

    assert response.status_code == 200
    assert response.json()["next_action"] == "network_fallback"


def test_type_and_network_fallback_are_mutually_exclusive() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/api/v1/intent/confirm",
        json={
            "request_id": "request",
            "selections": [
                {
                    "group_id": "group_1",
                    "type_id": "ROAD_POTHOLE_REPAIR",
                    "use_network_fallback": True,
                }
            ],
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_issue_report_uses_match_context() -> None:
    app = create_app()
    client = TestClient(app)
    match = _create_match(client)

    response = client.post(
        "/api/v1/issues/report",
        json={
            "request_id": match["request_id"],
            "missing_type_name": "特殊处治",
            "employee_description": "现有候选均不匹配",
        },
    )

    assert response.status_code == 200
    report_id = response.json()["report_id"]
    stored = app.state.workflow_store._issues[report_id]
    assert stored["original_input"] == "进行坑槽挖补"


def test_test_page_is_available() -> None:
    client = TestClient(create_app())
    response = client.get("/")

    assert response.status_code == 200
    assert "养护工程交底参考" in response.text
