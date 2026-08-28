from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app
from app.services.matcher import KeywordMatcher, load_engineering_types


DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "engineering_types.json"


def test_exact_alias_match_has_high_score() -> None:
    matcher = KeywordMatcher(
        load_engineering_types(DATA_PATH), top_k=3, threshold=70
    )

    result = matcher.match("现在需要进行坑槽挖补")

    assert result[0].type_id == "ROAD_POTHOLE_REPAIR"
    assert result[0].match_score == 95
    assert result[0].above_threshold is True


def test_no_keyword_match_requires_network_fallback() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/api/v1/intent/match",
        json={"employee_input": "开展一种资料中尚未收录的特殊作业"},
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body["engineering_groups"][0]["candidates"]) == 3
    assert body["engineering_groups"][0]["network_fallback_required"] is True


def test_multiple_groups_each_return_candidates() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/api/v1/intent/match",
        json={"employee_input": "进行坑槽挖补，并重新铺筑沥青面层"},
    )

    assert response.status_code == 200
    groups = response.json()["engineering_groups"]
    assert len(groups) == 2
    assert groups[0]["candidates"][0]["type_id"] == "ROAD_POTHOLE_REPAIR"
    assert groups[1]["candidates"][0]["type_id"] == "ASPHALT_PAVING"

