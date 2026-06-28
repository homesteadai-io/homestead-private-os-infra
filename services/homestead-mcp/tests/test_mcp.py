from __future__ import annotations

import httpx
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
    assert "homestead.receipts_review" in names
    assert "homestead.node_status" in names
    assert "homestead.os_status" in names
    assert "homestead.os_context" in names
    assert "homestead.os_capabilities" in names
    assert "homestead.agent_boot" in names
    assert "homestead.projects" in names
    assert "homestead.project_context" in names
    assert "homestead.ops_policy" in names
    assert "homestead.check_ops_policy" in names
    assert "homestead.list_manual_ops" in names
    assert "homestead.run_manual_action" in names
    assert "homestead.run_system_probe" in names
    assert "homestead.list_recent_ops" in names
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
    review = client.post("/call", json={"tool": "homestead.receipts_review", "arguments": {"limit": 3}})

    assert recent.status_code == 200
    assert read.status_code == 200
    assert stats.status_code == 200
    assert review.status_code == 200
    assert calls == [
        ("GET", "/receipts/recent?limit=5", None),
        ("GET", "/receipts/2026-06-28/model-route-test", None),
        ("GET", "/receipts/stats", None),
        ("GET", "/receipts/review?limit=3", None),
    ]


def test_api_request_sends_mcp_surface_and_policy_token(monkeypatch):
    calls = []

    class FakeAsyncClient:
        def __init__(self, timeout):
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def request(self, method, url, json=None, headers=None):
            calls.append({"method": method, "url": url, "json": json, "headers": headers})
            return httpx.Response(200, json={"ok": True}, request=httpx.Request(method, url))

    monkeypatch.setenv("HOMESTEAD_API_URL", "http://homestead-api:8000")
    monkeypatch.setenv("HOMESTEAD_MCP_POLICY_TOKEN", "pytest-mcp-token")
    monkeypatch.setattr(main.httpx, "AsyncClient", FakeAsyncClient)

    response = client.get("/health")

    assert response.status_code == 200
    assert calls[0]["headers"] == {
        "x-homestead-surface": "mcp",
        "x-homestead-policy-token": "pytest-mcp-token",
    }
    assert "pytest-mcp-token" not in response.text


def test_status_and_keep_health_tools_dispatch_to_api(monkeypatch):
    calls = []

    async def fake_api_request(method, path, json_body=None):
        calls.append((method, path, json_body))
        return {"ok": True, "path": path}

    monkeypatch.setattr(main, "api_request", fake_api_request)

    node = client.post("/call", json={"tool": "homestead.node_status", "arguments": {}})
    os_status = client.post("/call", json={"tool": "homestead.os_status", "arguments": {}})
    os_context = client.post("/call", json={"tool": "homestead.os_context", "arguments": {}})
    os_capabilities = client.post("/call", json={"tool": "homestead.os_capabilities", "arguments": {}})
    agent_boot = client.post("/call", json={"tool": "homestead.agent_boot", "arguments": {}})
    projects = client.post("/call", json={"tool": "homestead.projects", "arguments": {}})
    project_context = client.post(
        "/call",
        json={"tool": "homestead.project_context", "arguments": {"project_id": "homestead-private-os"}},
    )
    ops_policy = client.post("/call", json={"tool": "homestead.ops_policy", "arguments": {}})
    check_ops_policy = client.post(
        "/call",
        json={
            "tool": "homestead.check_ops_policy",
            "arguments": {
                "operation_type": "probe",
                "operation": "node_status",
                "requesting_agent": "pytest-mcp",
            },
        },
    )
    list_manual_ops = client.post("/call", json={"tool": "homestead.list_manual_ops", "arguments": {}})
    run_action = client.post(
        "/call",
        json={
            "tool": "homestead.run_manual_action",
            "arguments": {"action": "refresh_node_status", "requesting_agent": "pytest"},
        },
    )
    run_probe = client.post(
        "/call",
        json={
            "tool": "homestead.run_system_probe",
            "arguments": {"probe": "node_status", "requesting_agent": "pytest"},
        },
    )
    recent_ops = client.post("/call", json={"tool": "homestead.list_recent_ops", "arguments": {"limit": 4}})
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
    assert os_capabilities.status_code == 200
    assert agent_boot.status_code == 200
    assert projects.status_code == 200
    assert project_context.status_code == 200
    assert ops_policy.status_code == 200
    assert check_ops_policy.status_code == 200
    assert list_manual_ops.status_code == 200
    assert run_action.status_code == 200
    assert run_probe.status_code == 200
    assert recent_ops.status_code == 200
    assert sync.status_code == 200
    assert calls == [
        ("GET", "/node/status", None),
        ("GET", "/os/status", None),
        ("GET", "/os/context", None),
        ("GET", "/os/capabilities", None),
        ("GET", "/agent/boot", None),
        ("GET", "/os/projects", None),
        ("GET", "/os/projects/homestead-private-os", None),
        ("GET", "/ops/policy", None),
        (
            "POST",
            "/ops/policy/check",
            {"operation_type": "probe", "operation": "node_status", "requesting_agent": "pytest-mcp"},
        ),
        ("GET", "/ops/actions", None),
        ("POST", "/ops/actions/run", {"action": "refresh_node_status", "requesting_agent": "pytest"}),
        ("POST", "/ops/probes/run", {"probe": "node_status", "requesting_agent": "pytest"}),
        ("GET", "/ops/recent?limit=4", None),
        ("POST", "/ops/actions/run", {"action": "sync_keep_health", "requesting_agent": "pytest", "note": "sync"}),
    ]


def test_project_context_requires_project_id():
    response = client.post("/call", json={"tool": "homestead.project_context", "arguments": {}})

    assert response.status_code == 400
    assert response.json()["detail"] == "project_id is required"


def test_project_context_rejects_non_slug_project_id():
    response = client.post("/call", json={"tool": "homestead.project_context", "arguments": {"project_id": "bad/id?x=1"}})

    assert response.status_code == 400
    assert response.json()["detail"] == "project_id must be a slug"
