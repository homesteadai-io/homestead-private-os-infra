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
    assert "homestead.receipts_review" in names
    assert "homestead.node_status" in names
    assert "homestead.os_status" in names
    assert "homestead.os_context" in names
    assert "homestead.os_capabilities" in names
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
