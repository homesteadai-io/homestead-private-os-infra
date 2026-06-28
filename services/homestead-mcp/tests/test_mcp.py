from __future__ import annotations

from fastapi.testclient import TestClient

import app.main as main
from app.main import app


client = TestClient(app)


def test_tools_surface_lists_required_homestead_tools():
    response = client.get("/tools")
    assert response.status_code == 200
    names = {tool["name"] for tool in response.json()["tools"]}
    assert "homestead.search_keep" in names
    assert "homestead.read_concept" in names
    assert "homestead.build_context_pack" in names
    assert "homestead.repo_status" in names
    assert "homestead.create_receipt" in names
    assert "homestead.list_recent_receipts" in names
    assert "homestead.read_receipt" in names
    assert "homestead.receipt_stats" in names
    assert "homestead.node_status" in names
    assert "homestead.os_status" in names
    assert "homestead.os_context" in names
    assert "homestead.sync_keep_health" in names


def test_receipt_tools_dispatch_to_api(monkeypatch):
    calls = []

    async def fake_api_request(method, path, json_body=None):
        calls.append((method, path, json_body))
        return {"ok": True, "path": path}

    monkeypatch.setattr(main, "api_request", fake_api_request)

    recent = client.post("/call", json={"tool": "homestead.list_recent_receipts", "arguments": {"limit": 5}})
    read = client.post(
        "/call",
        json={
            "tool": "homestead.read_receipt",
            "arguments": {"date": "2026-06-28", "receipt_id": "model-route-test"},
        },
    )
    stats = client.post("/call", json={"tool": "homestead.receipt_stats", "arguments": {}})

    assert recent.status_code == 200
    assert read.status_code == 200
    assert stats.status_code == 200
    assert calls == [
        ("GET", "/receipts/recent?limit=5", None),
        ("GET", "/receipts/2026-06-28/model-route-test", None),
        ("GET", "/receipts/stats", None),
    ]


def test_status_and_keep_health_tools_dispatch_to_api(monkeypatch):
    calls = []

    async def fake_api_request(method, path, json_body=None):
        calls.append((method, path, json_body))
        return {"ok": True, "path": path}

    monkeypatch.setattr(main, "api_request", fake_api_request)

    node = client.post("/call", json={"tool": "homestead.node_status", "arguments": {}})
    os_status = client.post("/call", json={"tool": "homestead.os_status", "arguments": {}})
    os_context = client.post("/call", json={"tool": "homestead.os_context", "arguments": {}})
    sync = client.post(
        "/call",
        json={
            "tool": "homestead.sync_keep_health",
            "arguments": {"requesting_agent": "pytest", "note": "sync"},
        },
    )

    assert node.status_code == 200
    assert os_status.status_code == 200
    assert os_context.status_code == 200
    assert sync.status_code == 200
    assert calls == [
        ("GET", "/node/status", None),
        ("GET", "/os/status", None),
        ("GET", "/os/context", None),
        ("POST", "/keep/health/sync", {"requesting_agent": "pytest", "note": "sync"}),
    ]
