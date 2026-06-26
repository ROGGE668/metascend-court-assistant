"""Tests for the FastAPI HTTP sidecar."""

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from src.api_server import AppDependencies, create_app


@pytest.fixture()
def client():
    pipeline = MagicMock()
    pipeline.get_status.return_value = {
        "message": "ready",
        "status": "idle",
        "service_status": {},
        "latency": "",
        "courtroom_running": False,
        "active_case": None,
    }
    pipeline.get_transcript.return_value = "[己方] 我要求对方还款"
    pipeline.get_suggestion.return_value = {"text": "核对借条原件", "laws": ["《民法典》第679条"]}
    pipeline.get_chat_messages.return_value = []
    pipeline.chat_ask.return_value = {
        "sender": "AI",
        "text": "建议核对借条",
        "ref": "《民法典》第679条",
    }
    pipeline.toggle_courtroom.return_value = True

    knowledge_base = MagicMock()
    knowledge_base.search.return_value = [{"content": "借款合同"}]

    deps = AppDependencies(
        pipeline=pipeline,
        knowledge_base=knowledge_base,
    )
    app = create_app(deps)
    with TestClient(app) as c:
        yield c


def test_health_includes_disclaimer(client: TestClient):
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert "参考" in data["disclaimer"]


def test_status(client: TestClient):
    r = client.get("/status")
    assert r.status_code == 200
    assert r.json()["status"] == "idle"


def test_courtroom_start_stop(client: TestClient):
    assert client.post("/courtroom/start").json()["courtroom_running"] is True
    assert client.post("/courtroom/stop").json()["courtroom_running"] is True


def test_transcript(client: TestClient):
    r = client.get("/transcript")
    assert r.json()["transcript"] == "[己方] 我要求对方还款"


def test_suggestion(client: TestClient):
    r = client.get("/suggestion")
    data = r.json()
    assert data["text"] == "核对借条原件"


def test_chat_ask_and_messages(client: TestClient):
    r = client.post("/chat/ask", json={"message": "对方不还钱怎么办"})
    assert r.status_code == 200
    assert r.json()["sender"] == "AI"
    r2 = client.get("/chat/messages")
    assert r2.status_code == 200


def test_knowledge_search(client: TestClient):
    r = client.post("/knowledge/search", json={"query": "借贷"})
    assert r.json()["results"] == [{"content": "借款合同"}]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
