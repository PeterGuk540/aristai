import asyncio
import threading

import pytest
from fastapi.testclient import TestClient

from api.api.mcp_executor import invoke_tool_handler
from api.main import app
import mcp_server.server as mcp_server
from api.services.action_store import ActionStore


def test_invoke_tool_handler_without_db():
    def handler(foo: str):
        return {"foo": foo}

    result = invoke_tool_handler(handler, {"foo": "bar"})
    assert result == {"foo": "bar"}


def test_invoke_tool_handler_requires_db_raises():
    def handler(db, foo: str):
        return {"foo": foo}

    with pytest.raises(RuntimeError):
        invoke_tool_handler(handler, {"foo": "bar"})


class FakeRedis:
    def __init__(self):
        self._store = {}

    def set(self, key, value, ex=None):
        self._store[key] = value

    def get(self, key):
        return self._store.get(key)

    def delete(self, key):
        self._store.pop(key, None)

    def ttl(self, key):
        return 60


def test_navigation_tool_execute_ok(monkeypatch):
    from api.api import routes as routes_pkg
    monkeypatch.setattr(
        routes_pkg.mcp,
        "action_store",
        ActionStore(redis_client=FakeRedis(), ttl_seconds=60),
    )
    client = TestClient(app)
    response = client.post(
        "/api/mcp/execute",
        json={"tool": "navigate_to_page", "arguments": {"page": "courses"}},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["tool"] == "navigate_to_page"


def test_concurrent_read_tools_use_thread_sessions(monkeypatch):
    class FakeSession:
        def __init__(self):
            self.thread_id = threading.get_ident()

        def close(self):
            return None

    monkeypatch.setattr(mcp_server, "SessionLocal", lambda: FakeSession())

    def handler(db):
        assert db.thread_id == threading.get_ident()
        return db.thread_id

    async def run_concurrent():
        tasks = [
            asyncio.to_thread(mcp_server._invoke_tool_handler_in_thread, handler, {})
            for _ in range(5)
        ]
        return await asyncio.gather(*tasks)

    results = asyncio.run(run_concurrent())
    assert len(results) == 5


def test_write_tool_returns_plan(monkeypatch):
    from api.api import routes as routes_pkg
    monkeypatch.setattr(
        routes_pkg.mcp,
        "action_store",
        ActionStore(redis_client=FakeRedis(), ttl_seconds=60),
    )
    client = TestClient(app)
    response = client.post(
        "/api/mcp/execute",
        json={"tool": "create_course", "arguments": {"title": "History"}},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["requires_confirmation"] is True
    assert "action_id" in payload
