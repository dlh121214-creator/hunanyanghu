from fastapi.testclient import TestClient

from app.main import create_app


def test_health_and_request_id() -> None:
    client = TestClient(create_app())
    response = client.get("/health", headers={"X-Request-ID": "test-request"})

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "test-request"
    assert response.json()["status"] == "ok"


def test_openapi_is_available() -> None:
    client = TestClient(create_app())
    response = client.get("/openapi.json")

    assert response.status_code == 200
    assert response.json()["info"]["title"].startswith("湖南养护工程")

