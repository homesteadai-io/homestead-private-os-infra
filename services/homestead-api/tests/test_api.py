from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

import app.main as main
from app.main import app


client = TestClient(app)
POLICY_TOKEN = "pytest-policy-token"


def trusted_codex_headers(monkeypatch) -> dict[str, str]:
    monkeypatch.setenv("OPS_POLICY_SURFACE_TOKEN", POLICY_TOKEN)
    return {"x-homestead-surface": "codex", "x-homestead-policy-token": POLICY_TOKEN}


@pytest.fixture(autouse=True)
def clear_langfuse_env(monkeypatch):
    for name in [
        "LANGFUSE_ENABLED",
        "LANGFUSE_HOST",
        "LANGFUSE_PUBLIC_KEY",
        "LANGFUSE_SECRET_KEY",
        "LANGFUSE_ENVIRONMENT",
        "LANGFUSE_RELEASE",
        "MODEL_ROUTE_RECEIPTS_ENABLED",
        "MODEL_ROUTE_RECEIPTS_INCLUDE_CONTENT",
        "MODEL_GATEWAY",
        "LITELLM_BASE_URL",
        "LITELLM_API_KEY",
        "LITELLM_DEFAULT_MODEL",
        "LITELLM_SEND_TEMPERATURE",
        "KEEP_HEALTH_DIR",
        "CADDY_HTTP_BIND",
        "CADDY_HTTPS_BIND",
        "CADDY_HTTP_PORT",
        "CADDY_HTTPS_PORT",
        "HOMESTEAD_SELF_URL",
        "OPS_POLICY_SURFACE_TOKEN",
        "HOMESTEAD_STATE_DIR",
    ]:
        monkeypatch.delenv(name, raising=False)


def init_repo(path: Path) -> None:
    subprocess.run(["git", "init"], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=path, check=True)
    (path / "index.md").write_text("# Homestead\n\nPrivate OS markdown shelf.\n", encoding="utf-8")
    subprocess.run(["git", "add", "index.md"], cwd=path, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=path, check=True, capture_output=True)


def test_health(monkeypatch, tmp_path):
    monkeypatch.setenv("HOMESTEAD_REPO_PATH", str(tmp_path))
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["ok"] is True


def test_repo_status_and_search(monkeypatch, tmp_path):
    init_repo(tmp_path)
    monkeypatch.setenv("HOMESTEAD_REPO_PATH", str(tmp_path))

    status = client.get("/repo/status")
    assert status.status_code == 200
    assert status.json()["latest_commit"]
    assert status.json()["dirty"] is False

    search = client.post("/search", json={"query": "Private OS"})
    assert search.status_code == 200
    assert search.json()["count"] == 1
    assert search.json()["results"][0]["path"] == "/index.md"


def test_context_pack_and_read_concept(monkeypatch, tmp_path):
    init_repo(tmp_path)
    monkeypatch.setenv("HOMESTEAD_REPO_PATH", str(tmp_path))

    pack = client.post("/context-pack", json={"task": "Homestead"})
    assert pack.status_code == 200
    assert pack.json()["files"][0]["path"] == "/index.md"

    concept = client.post("/read-concept", json={"path": "/index.md"})
    assert concept.status_code == 200
    assert "Private OS" in concept.json()["content"]


def test_receipt_create_is_append_only(monkeypatch, tmp_path):
    monkeypatch.setenv("RECEIPTS_DIR", str(tmp_path / "receipts"))
    payload = {
        "run_id": "test-run",
        "requesting_agent": "pytest",
        "task": "prove receipts",
        "files_read": ["/index.md"],
        "model_used": "not_applicable_v0",
        "actions_taken": ["created receipt"],
        "files_changed": [],
        "review_required": False,
        "verdict": "ok",
    }

    created = client.post("/receipt/create", json=payload)
    assert created.status_code == 200
    body = created.json()
    assert Path(body["markdown_path"]).exists()
    assert Path(body["json_path"]).exists()
    assert json.loads(Path(body["json_path"]).read_text(encoding="utf-8"))["run_id"] == "test-run"

    duplicate = client.post("/receipt/create", json=payload)
    assert duplicate.status_code == 409


def write_test_receipt(root: Path, date: str, receipt_id: str, payload: dict, markdown: str | None = None) -> None:
    date_dir = root / date
    date_dir.mkdir(parents=True, exist_ok=True)
    data = {"run_id": receipt_id, "timestamp": f"{date}T12:00:00Z", **payload}
    (date_dir / f"{receipt_id}.json").write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    (date_dir / f"{receipt_id}.md").write_text(markdown or f"# Receipt {receipt_id}\n", encoding="utf-8")


def test_receipts_recent_lists_metadata_only(monkeypatch, tmp_path):
    receipts = tmp_path / "receipts"
    monkeypatch.setenv("RECEIPTS_DIR", str(receipts))
    write_test_receipt(
        receipts,
        "2026-06-28",
        "model-route-new",
        {
            "requesting_agent": "pytest",
            "task": "model_route",
            "model_used": "openai/gpt-4.1-mini",
            "files_read": [],
            "actions_taken": ["called route"],
            "files_changed": [],
            "review_required": False,
            "verdict": "ok",
            "metadata": {
                "route": "/model/route",
                "gateway": "direct",
                "requested_model": "openai/gpt-4.1-mini",
                "model_used": "openai/gpt-4.1-mini-2025-04-14",
                "latency_ms": 123,
                "ok": True,
                "usage": {"total_tokens": 9},
                "langfuse_trace_id": "trace-123",
            },
        },
        markdown="# Receipt\n\nprompt-only-secret should stay out of lists\n",
    )
    write_test_receipt(
        receipts,
        "2026-06-27",
        "old-format",
        {
            "requesting_agent": "legacy",
            "task": "legacy_task",
            "model_used": "not_applicable_v0",
            "files_read": [],
            "actions_taken": [],
            "files_changed": [],
            "review_required": False,
            "verdict": "ok",
        },
    )

    response = client.get("/receipts/recent?limit=10")

    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 2
    first = body["receipts"][0]
    assert first["receipt_id"] == "model-route-new"
    assert first["route"] == "/model/route"
    assert first["gateway"] == "direct"
    assert first["requested_model"] == "openai/gpt-4.1-mini"
    assert first["latency_ms"] == 123
    assert first["usage"]["total_tokens"] == 9
    assert first["langfuse_trace_id"] == "trace-123"
    assert "prompt-only-secret" not in json.dumps(body)
    legacy = body["receipts"][1]
    assert legacy["receipt_id"] == "old-format"
    assert legacy["route"] is None
    assert legacy["model_used"] == "not_applicable_v0"


def test_receipts_by_date_and_read_one(monkeypatch, tmp_path):
    receipts = tmp_path / "receipts"
    monkeypatch.setenv("RECEIPTS_DIR", str(receipts))
    write_test_receipt(
        receipts,
        "2026-06-28",
        "model-route-read",
        {
            "requesting_agent": "pytest-read",
            "task": "model_route",
            "model_used": "openai/gpt-4.1-mini",
            "files_read": [],
            "actions_taken": ["called route"],
            "files_changed": [],
            "review_required": False,
            "verdict": "ok",
            "metadata": {"route": "/model/route", "ok": True},
        },
        markdown="# Read Me\n\nExplicit receipt content.\n",
    )

    by_date = client.get("/receipts/by-date/2026-06-28")
    read_one = client.get("/receipts/2026-06-28/model-route-read")

    assert by_date.status_code == 200
    assert by_date.json()["count"] == 1
    assert by_date.json()["receipts"][0]["receipt_id"] == "model-route-read"
    assert "Explicit receipt content" not in json.dumps(by_date.json())
    assert read_one.status_code == 200
    assert read_one.json()["receipt_id"] == "model-route-read"
    assert read_one.json()["json"]["requesting_agent"] == "pytest-read"
    assert "Explicit receipt content" in read_one.json()["markdown"]


def test_receipt_missing_and_malformed_date_are_safe(monkeypatch, tmp_path):
    monkeypatch.setenv("RECEIPTS_DIR", str(tmp_path / "receipts"))

    missing = client.get("/receipts/2026-06-28/missing")
    bad_date = client.get("/receipts/by-date/not-a-date")
    bad_id = client.get("/receipts/2026-06-28/bad%20id")

    assert missing.status_code == 404
    assert missing.json()["detail"] == "receipt not found"
    assert bad_date.status_code == 400
    assert bad_date.json()["detail"] == "date must be YYYY-MM-DD"
    assert bad_id.status_code == 400
    assert "unsupported characters" in bad_id.json()["detail"]


def test_receipt_stats(monkeypatch, tmp_path):
    receipts = tmp_path / "receipts"
    monkeypatch.setenv("RECEIPTS_DIR", str(receipts))
    write_test_receipt(
        receipts,
        "2026-06-28",
        "ok-run",
        {
            "requesting_agent": "pytest",
            "task": "model_route",
            "model_used": "model",
            "files_read": [],
            "actions_taken": [],
            "files_changed": [],
            "review_required": False,
            "verdict": "ok",
        },
    )
    write_test_receipt(
        receipts,
        "2026-06-28",
        "needs-review",
        {
            "requesting_agent": "pytest",
            "task": "model_route",
            "model_used": "model",
            "files_read": [],
            "actions_taken": [],
            "files_changed": [],
            "review_required": True,
            "verdict": "error",
        },
    )

    response = client.get("/receipts/stats")

    assert response.status_code == 200
    assert response.json()["total"] == 2
    assert response.json()["by_task"]["model_route"] == 2
    assert response.json()["by_verdict"]["ok"] == 1
    assert response.json()["by_verdict"]["error"] == 1
    assert response.json()["review_required"] == 1
    assert response.json()["attention_required"] == 1


def test_receipts_review_lists_attention_metadata_only(monkeypatch, tmp_path):
    receipts = tmp_path / "receipts"
    monkeypatch.setenv("RECEIPTS_DIR", str(receipts))
    write_test_receipt(
        receipts,
        "2026-06-28",
        "ok-run",
        {
            "requesting_agent": "pytest",
            "task": "model_route",
            "model_used": "model",
            "files_read": [],
            "actions_taken": [],
            "files_changed": [],
            "review_required": False,
            "verdict": "ok",
            "metadata": {"ok": True, "route": "/model/route"},
        },
        markdown="# OK\n\nprivate prompt should not appear in queue\n",
    )
    write_test_receipt(
        receipts,
        "2026-06-28",
        "error-run",
        {
            "requesting_agent": "pytest",
            "task": "model_route",
            "model_used": "model",
            "files_read": [],
            "actions_taken": ["failed safely"],
            "files_changed": [],
            "review_required": False,
            "verdict": "error",
            "metadata": {
                "ok": False,
                "route": "/model/route",
                "gateway": "direct",
                "error_summary": "provider failed",
            },
        },
        markdown="# Error\n\nfull failure context should not appear in queue\n",
    )
    write_test_receipt(
        receipts,
        "2026-06-27",
        "manual-review",
        {
            "requesting_agent": "pytest",
            "task": "manual",
            "model_used": "not_applicable_v0",
            "files_read": [],
            "actions_taken": [],
            "files_changed": [],
            "review_required": True,
            "verdict": "recorded",
        },
    )

    response = client.get("/receipts/review?limit=10")

    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 2
    assert body["total_attention_items"] == 2
    assert body["queue_empty"] is False
    assert [item["receipt_id"] for item in body["receipts"]] == ["error-run", "manual-review"]
    assert body["receipts"][0]["attention"] == "review"
    assert "verdict:error" in body["receipts"][0]["review_reasons"]
    assert "metadata_ok:false" in body["receipts"][0]["review_reasons"]
    assert "error_summary_present" in body["receipts"][0]["review_reasons"]
    assert "review_required" in body["receipts"][1]["review_reasons"]
    combined = json.dumps(body)
    assert "private prompt" not in combined
    assert "full failure context" not in combined


def test_receipts_review_rejects_bad_limit(monkeypatch, tmp_path):
    monkeypatch.setenv("RECEIPTS_DIR", str(tmp_path / "receipts"))

    response = client.get("/receipts/review?limit=0")

    assert response.status_code == 400
    assert response.json()["detail"] == "limit must be between 1 and 100"


def test_node_status_reports_cloud_health_without_secrets(monkeypatch, tmp_path):
    init_repo(tmp_path)
    receipts = tmp_path / "receipts"
    monkeypatch.setenv("HOMESTEAD_REPO_PATH", str(tmp_path))
    monkeypatch.setenv("RECEIPTS_DIR", str(receipts))
    monkeypatch.setenv("HOMESTEAD_ENV", "pytest")
    monkeypatch.setenv("MODEL_GATEWAY", "direct")
    monkeypatch.setenv("OPENROUTER_API_KEY", "super-secret-openrouter")
    monkeypatch.setenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    monkeypatch.setenv("OPENROUTER_DEFAULT_MODEL", "openai/gpt-4.1-mini")
    monkeypatch.setenv("OPENROUTER_HTTP_REFERER", "https://homesteadai.io")
    monkeypatch.setenv("OPENROUTER_APP_TITLE", "Homestead Private OS")
    monkeypatch.setenv("LITELLM_API_KEY", "super-secret-litellm")
    monkeypatch.setenv("LITELLM_BASE_URL", "http://litellm:4000")
    monkeypatch.setenv("LITELLM_DEFAULT_MODEL", "haiku")
    monkeypatch.setenv("LANGFUSE_ENABLED", "true")
    monkeypatch.setenv("LANGFUSE_HOST", "http://langfuse-web:3000")
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-secret")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-secret")
    write_test_receipt(
        receipts,
        "2026-06-28",
        "model-route-status",
        {
            "requesting_agent": "pytest",
            "task": "model_route",
            "model_used": "openai/gpt-4.1-mini",
            "files_read": [],
            "actions_taken": [],
            "files_changed": [],
            "review_required": False,
            "verdict": "ok",
            "metadata": {"route": "/model/route", "gateway": "direct", "ok": True},
        },
    )

    response = client.get("/node/status")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["environment"] == "pytest"
    assert body["model_gateway"]["active"] == "direct"
    assert body["model_gateway"]["openrouter"]["configured"] is True
    assert body["model_gateway"]["litellm"]["configured"] is True
    assert body["langfuse"]["enabled"] is True
    assert body["receipts"]["total"] == 1
    assert body["receipts"]["latest"]["gateway"] == "direct"
    assert body["capabilities"]["local_mode"]["enabled"] is False
    assert "super-secret" not in response.text
    assert "pk-secret" not in response.text
    assert "sk-secret" not in response.text


def test_os_context_is_cloud_first_with_local_disabled(monkeypatch, tmp_path):
    init_repo(tmp_path)
    monkeypatch.setenv("HOMESTEAD_REPO_PATH", str(tmp_path))
    monkeypatch.setenv("RECEIPTS_DIR", str(tmp_path / "receipts"))

    response = client.get("/os/context")

    assert response.status_code == 200
    body = response.json()
    assert body["cloud_first"] is True
    assert body["local_mode"]["enabled"] is False
    assert body["local_mode"]["activation"] == "manual_switch_only"
    assert "homestead.node_status" in body["mcp_tools"]
    assert "homestead.os_capabilities" in body["mcp_tools"]
    assert "homestead.receipts_review" in body["mcp_tools"]
    assert body["keep"]["health_receipts_enabled"] is True
    assert body["keep"]["policy"]["source_control"] == "may_remain_dirty_until_separate_keep_sync_policy"
    assert "homestead.agent_boot" in body["mcp_tools"]
    assert "homestead.projects" in body["mcp_tools"]
    assert "homestead.project_context" in body["mcp_tools"]


def test_agent_boot_and_projects_are_agent_safe_without_secrets(monkeypatch, tmp_path):
    init_repo(tmp_path)
    monkeypatch.setenv("HOMESTEAD_REPO_PATH", str(tmp_path))
    monkeypatch.setenv("RECEIPTS_DIR", str(tmp_path / "receipts"))
    monkeypatch.setenv("OPENROUTER_API_KEY", "super-secret-openrouter")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-secret")
    monkeypatch.setenv("OPS_POLICY_SURFACE_TOKEN", POLICY_TOKEN)

    boot = client.get("/agent/boot")
    projects = client.get("/os/projects")
    project = client.get("/os/projects/homestead-private-os")
    missing = client.get("/os/projects/not-real")

    assert boot.status_code == 200
    body = boot.json()
    assert body["release"] == "v0-agent-boot-projects"
    assert body["orientation"]["who_is_adam"] == "Adam is the authority. Agents and Codex are operators."
    assert body["authority"]["agents_decide_next_work"] is False
    assert body["loop_protocol"]["needs_decision"] == "escalate_to_adam"
    assert body["project_registry"]["default_project_id"] == "homestead-private-os"
    assert body["active_project"]["project_id"] == "homestead-private-os"
    assert body["capabilities"]["entries"]["agent_boot"]["enabled"] is True
    assert body["capabilities"]["entries"]["project_registry"]["project_count"] >= 6
    assert body["manual_ops"]["catalog"]["mode"] == "manual_only"
    assert body["disabled"]["runner"]["enabled"] is False
    assert body["disabled"]["local_mode"]["enabled"] is False
    assert body["disabled"]["dashboard"]["enabled"] is False
    assert body["content_policy"]["prompt_capture_default"] is False
    assert body["content_policy"]["completion_capture_default"] is False
    assert "/docs/HANDOFF-AGENT-BOOT-PROJECTS.md" in body["read_first"]

    assert projects.status_code == 200
    assert projects.json()["mode"] == "config_backed"
    project_ids = {item["project_id"] for item in projects.json()["projects"]}
    assert {"homestead-private-os", "the-keep", "lyhna-witness", "loop-forge"}.issubset(project_ids)
    assert project.status_code == 200
    assert project.json()["authority"]["adam"] == "authority"
    assert project.json()["authority"]["autonomous_claiming"] is False
    assert missing.status_code == 404
    assert missing.json()["detail"] == "unknown project"
    combined = boot.text + projects.text + project.text + missing.text
    assert "super-secret" not in combined
    assert "sk-secret" not in combined
    assert POLICY_TOKEN not in combined


def test_project_context_rejects_non_slug_ids_without_echoing_input(monkeypatch, tmp_path):
    init_repo(tmp_path)
    monkeypatch.setenv("HOMESTEAD_REPO_PATH", str(tmp_path))

    response = client.get("/os/projects/not%20a%20secret")

    assert response.status_code == 404
    assert response.json()["detail"] == "unknown project"
    assert "secret" not in response.text


def test_command_sessions_lifecycle_is_policy_gated_and_manual(monkeypatch, tmp_path):
    init_repo(tmp_path)
    receipts = tmp_path / "receipts"
    state = tmp_path / "state"
    monkeypatch.setenv("HOMESTEAD_REPO_PATH", str(tmp_path))
    monkeypatch.setenv("RECEIPTS_DIR", str(receipts))
    monkeypatch.setenv("HOMESTEAD_STATE_DIR", str(state))
    monkeypatch.setenv("OPENROUTER_API_KEY", "super-secret-openrouter")
    headers = trusted_codex_headers(monkeypatch)

    denied = client.post(
        "/commands",
        headers={"x-homestead-surface": "codex"},
        json={"title": "Denied command", "created_by": "spoofed-codex"},
    )
    assert denied.status_code == 403
    assert denied.json()["detail"]["operation_type"] == "command"
    assert denied.json()["detail"]["operation"] == "create"
    assert not (state / "command-sessions" / "commands.jsonl").exists()
    assert len(list(receipts.rglob("ops-policy-command-create-*.json"))) == 1

    created = client.post(
        "/commands",
        headers=headers,
        json={
            "title": "Prepare release handoff",
            "description": "Operator metadata only",
            "project_id": "homestead-private-os",
            "created_by": "codex",
        },
    )
    assert created.status_code == 200
    command = created.json()["command"]
    command_id = command["command_id"]
    assert command_id.startswith("cmd-")
    assert command["status"] == "new"
    assert command["autonomous_claim"] is False
    assert created.json()["events"][0]["policy"]["surface"] == "codex"
    assert created.json()["events"][0]["policy"]["decision"] == "allow_with_receipt"

    invalid_status = client.patch(
        f"/commands/{command_id}",
        headers=headers,
        json={"status": "running_the_show", "updated_by": "codex"},
    )
    assert invalid_status.status_code == 400
    assert invalid_status.json()["detail"] == "invalid command status"

    started = client.post(
        "/agent/sessions/start",
        headers=headers,
        json={"agent": "codex", "command_id": command_id, "project_id": "homestead-private-os", "note": "manual start"},
    )
    assert started.status_code == 200
    session = started.json()["session"]
    session_id = session["session_id"]
    assert session_id.startswith("session-")
    assert session["status"] == "active"
    assert session["command_id"] == command_id
    assert session["autonomous_claim"] is False

    unchanged = client.get(f"/commands/{command_id}")
    assert unchanged.status_code == 200
    assert unchanged.json()["command"]["status"] == "new"
    assert unchanged.json()["command"]["session_id"] is None

    updated = client.patch(
        f"/commands/{command_id}",
        headers=headers,
        json={"status": "working", "session_id": session_id, "updated_by": "codex", "note": "manual link"},
    )
    assert updated.status_code == 200
    assert updated.json()["command"]["status"] == "working"
    assert updated.json()["command"]["session_id"] == session_id

    ended = client.post(
        "/agent/sessions/end",
        headers=headers,
        json={"session_id": session_id, "ended_by": "codex", "outcome": "handoff_ready", "note": "manual end"},
    )
    assert ended.status_code == 200
    assert ended.json()["session"]["status"] == "ended"
    assert ended.json()["events"][-1]["policy"]["operation_type"] == "session"

    duplicate_end = client.post(
        "/agent/sessions/end",
        headers=headers,
        json={"session_id": session_id, "ended_by": "codex"},
    )
    assert duplicate_end.status_code == 409

    commands = client.get("/commands")
    sessions = client.get("/agent/sessions")
    boot = client.get("/agent/boot")
    caps = client.get("/os/capabilities")
    assert commands.status_code == 200
    assert commands.json()["count"] == 1
    assert commands.json()["autonomous_claiming"] is False
    assert sessions.status_code == 200
    assert sessions.json()["count"] == 1
    assert sessions.json()["autonomous_claiming"] is False
    assert boot.json()["command_sessions"]["commands_total"] == 1
    assert boot.json()["command_sessions"]["sessions_active"] == 0
    command_caps = caps.json()["entries"]["command_sessions"]
    assert command_caps["enabled"] is True
    assert command_caps["status"] == "manual_only"
    assert command_caps["autonomous_claiming"] is False
    assert command_caps["runner_enabled"] is False
    assert command_caps["scheduler_enabled"] is False

    combined = (
        denied.text
        + created.text
        + started.text
        + updated.text
        + ended.text
        + commands.text
        + sessions.text
        + boot.text
        + caps.text
    )
    assert "super-secret-openrouter" not in combined
    assert POLICY_TOKEN not in combined


def test_output_capsule_write_list_read_and_policy(monkeypatch, tmp_path):
    init_repo(tmp_path)
    receipts = tmp_path / "receipts"
    monkeypatch.setenv("HOMESTEAD_REPO_PATH", str(tmp_path))
    monkeypatch.setenv("RECEIPTS_DIR", str(receipts))
    monkeypatch.setenv("OPENROUTER_API_KEY", "super-secret-openrouter")
    headers = trusted_codex_headers(monkeypatch)

    assert Path("docs/OUTPUT-CAPSULE-WRITE-POLICY.md").exists()
    assert Path("docs/HANDOFF-OUTPUT-CAPSULES.md").exists()

    denied = client.post(
        "/outputs",
        headers={"x-homestead-surface": "codex"},
        json={"title": "Denied output", "summary": "Should not write", "created_by": "spoofed-codex"},
    )
    assert denied.status_code == 403
    assert denied.json()["detail"]["operation_type"] == "output"
    assert denied.json()["detail"]["operation"] == "write"
    assert not (tmp_path / "System Outputs").exists()
    assert len(list(receipts.rglob("ops-policy-output-write-*.json"))) == 1

    command = client.post(
        "/commands",
        headers=headers,
        json={"title": "Output capsule command", "created_by": "codex", "project_id": "homestead-private-os"},
    ).json()["command"]
    session = client.post(
        "/agent/sessions/start",
        headers=headers,
        json={"agent": "codex", "command_id": command["command_id"], "project_id": "homestead-private-os"},
    ).json()["session"]

    created = client.post(
        "/outputs",
        headers=headers,
        json={
            "title": "Agent Boot Projects",
            "summary": "Durable handoff for the agent boot project registry release.",
            "project_id": "homestead-private-os",
            "slug": "agent-boot-projects",
            "command_id": command["command_id"],
            "session_id": session["session_id"],
            "created_by": "codex",
            "handoff": "Read the boot and project registry contract first.",
            "capsule": "The output capsule preserves continuation context only.",
            "next_ai_prompt": "Continue from this capsule without inventing autonomy.",
            "okf": {"status": "placeholder"},
            "pam": {"status": "placeholder"},
        },
    )

    assert created.status_code == 200
    body = created.json()
    output_id = body["output_id"]
    assert output_id.startswith("homestead-private-os--")
    summary = body["summary"]
    assert summary["project_id"] == "homestead-private-os"
    assert summary["command_id"] == command["command_id"]
    assert summary["session_id"] == session["session_id"]
    assert summary["relative_path"].startswith("/System Outputs/homestead-private-os/")
    assert "/System Receipts" not in summary["relative_path"]
    assert "bundle_path" not in summary
    assert body["capsule"]["policy"]["surface"] == "codex"
    assert body["capsule"]["content_policy"]["prompt_capture_default"] is False
    assert body["capsule"]["content_policy"]["completion_capture_default"] is False

    bundle_dir = tmp_path / summary["relative_path"].lstrip("/")
    expected = {"index.md", "HANDOFF.md", "handoff.json", "CAPSULE.md", "capsule.json", "next-ai-prompt.md", "okf", "pam"}
    assert expected.issubset({path.name for path in bundle_dir.iterdir()})
    assert (bundle_dir / "okf" / "README.md").exists()
    assert (bundle_dir / "pam" / "README.md").exists()
    index_text = (bundle_dir / "index.md").read_text(encoding="utf-8")
    assert "[HANDOFF.md](HANDOFF.md)" in index_text
    assert "[CAPSULE.md](CAPSULE.md)" in index_text
    assert "[next-ai-prompt.md](next-ai-prompt.md)" in index_text
    assert "[handoff.json](handoff.json)" in index_text
    assert "[capsule.json](capsule.json)" in index_text
    assert "[okf/](okf/)" in index_text
    assert "[pam/](pam/)" in index_text
    assert "/System Outputs/homestead-private-os/" in index_text

    listed = client.get("/outputs")
    read = client.get(f"/outputs/{output_id}")
    boot = client.get("/agent/boot")
    caps = client.get("/os/capabilities")

    assert listed.status_code == 200
    assert listed.json()["count"] == 1
    assert listed.json()["outputs"][0]["output_id"] == output_id
    assert read.status_code == 200
    assert read.json()["output_id"] == output_id
    assert expected.issubset(set(read.json()["files"]))
    assert "bundle_path" not in read.json()
    assert "index.md" in read.json()["markdown"]
    assert "Continue from this capsule" in read.json()["markdown"]["next-ai-prompt.md"]
    assert boot.json()["output_capsules"]["count"] == 1
    output_caps = caps.json()["entries"]["output_capsules"]
    assert output_caps["enabled"] is True
    assert output_caps["status"] == "manual_only"
    assert output_caps["root"] == "/System Outputs"
    assert output_caps["policy_gate"] == "required"
    assert output_caps["runner_enabled"] is False
    assert output_caps["scheduler_enabled"] is False

    duplicate = client.post(
        "/outputs",
        headers=headers,
        json={
            "title": "Agent Boot Projects",
            "summary": "Duplicate should not overwrite.",
            "project_id": "homestead-private-os",
            "slug": "agent-boot-projects",
            "created_by": "codex",
        },
    )
    assert duplicate.status_code == 409

    secret_like = "OPENROUTER" + "_API" + "_KEY" + "=" + "sk-secret-should-not-write"
    leak_response = client.post(
        "/outputs",
        headers=headers,
        json={
            "title": "Secret Leak",
            "summary": secret_like,
            "project_id": "homestead-private-os",
            "slug": "secret-leak",
            "created_by": "codex",
        },
    )
    assert leak_response.status_code == 400
    assert list((tmp_path / "System Outputs" / "homestead-private-os").glob("*secret-leak")) == []

    missing_command = client.post(
        "/outputs",
        headers=headers,
        json={
            "title": "Missing Link",
            "summary": "Should reject nonexistent command links.",
            "project_id": "homestead-private-os",
            "slug": "missing-link",
            "command_id": "cmd-deadbeef",
            "created_by": "codex",
        },
    )
    assert missing_command.status_code == 404
    assert missing_command.json()["detail"] == "command not found"

    combined = (
        created.text
        + listed.text
        + read.text
        + boot.text
        + caps.text
        + duplicate.text
        + leak_response.text
        + missing_command.text
    )
    assert "super-secret-openrouter" not in combined
    assert secret_like not in combined
    assert POLICY_TOKEN not in combined
    assert str(tmp_path) not in combined


def test_output_capsule_partial_failure_does_not_claim_final_path(monkeypatch, tmp_path):
    init_repo(tmp_path)
    monkeypatch.setenv("HOMESTEAD_REPO_PATH", str(tmp_path))
    monkeypatch.setenv("RECEIPTS_DIR", str(tmp_path / "receipts"))
    headers = trusted_codex_headers(monkeypatch)
    original_renderer = main.output_capsule_markdown

    def fail_capsule_render(metadata, body):
        raise RuntimeError("simulated capsule render failure")

    monkeypatch.setattr(main, "output_capsule_markdown", fail_capsule_render)
    non_raising_client = TestClient(app, raise_server_exceptions=False)
    failed = non_raising_client.post(
        "/outputs",
        headers=headers,
        json={
            "title": "Retryable Capsule",
            "summary": "A failed bundle write must not claim the final path.",
            "project_id": "homestead-private-os",
            "slug": "retryable-capsule",
            "created_by": "codex",
        },
    )
    assert failed.status_code == 500
    published = [
        path
        for path in (tmp_path / "System Outputs" / "homestead-private-os").glob("*retryable-capsule")
        if not path.name.startswith(".")
    ]
    assert published == []

    monkeypatch.setattr(main, "output_capsule_markdown", original_renderer)
    created = client.post(
        "/outputs",
        headers=headers,
        json={
            "title": "Retryable Capsule",
            "summary": "A retry can publish the final bundle.",
            "project_id": "homestead-private-os",
            "slug": "retryable-capsule",
            "created_by": "codex",
        },
    )
    assert created.status_code == 200
    assert created.json()["summary"]["relative_path"].endswith("-retryable-capsule")


def test_os_capabilities_registry_is_agent_safe_without_secrets(monkeypatch, tmp_path):
    init_repo(tmp_path)
    monkeypatch.setenv("HOMESTEAD_REPO_PATH", str(tmp_path))
    monkeypatch.setenv("RECEIPTS_DIR", str(tmp_path / "receipts"))
    monkeypatch.setenv("OPENROUTER_API_KEY", "super-secret-openrouter")
    monkeypatch.setenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    monkeypatch.setenv("OPENROUTER_DEFAULT_MODEL", "openai/gpt-4.1-mini")
    monkeypatch.setenv("OPENROUTER_HTTP_REFERER", "https://homesteadai.io")
    monkeypatch.setenv("OPENROUTER_APP_TITLE", "Homestead Private OS")
    monkeypatch.setenv("LITELLM_API_KEY", "super-secret-litellm")
    monkeypatch.setenv("LITELLM_BASE_URL", "http://litellm:4000")
    monkeypatch.setenv("LITELLM_DEFAULT_MODEL", "haiku")
    monkeypatch.setenv("LANGFUSE_ENABLED", "true")
    monkeypatch.setenv("LANGFUSE_HOST", "http://langfuse-web:3000")
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-secret")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-secret")
    monkeypatch.setenv("MODEL_ROUTE_RECEIPTS_ENABLED", "true")

    response = client.get("/os/capabilities")

    assert response.status_code == 200
    body = response.json()
    entries = body["entries"]
    assert body["cloud_first"] is True
    assert body["production_default_gateway"] == "direct"
    assert entries["model_route"]["enabled"] is True
    assert entries["agent_boot"]["surface"] == ["/agent/boot", "homestead.agent_boot"]
    assert entries["project_registry"]["status"] == "config_backed"
    assert entries["direct_openrouter_gateway"]["status"] == "production_default"
    assert entries["litellm_gateway"]["status"] == "available_private_optional"
    assert entries["ops_policy_gate"]["enabled"] is True
    assert entries["ops_policy_gate"]["default_decision"] == "deny"
    assert entries["ops_policy_gate"]["scheduler_enabled"] is False
    assert entries["ops_policy_gate"]["autonomous_execution"] is False
    assert entries["review_queue"]["surface"] == ["/receipts/review", "homestead.receipts_review"]
    assert entries["keep_health_sync"]["policy"]["content_policy"]["secret_values"] == "never_write"
    assert entries["local_mode"]["enabled"] is False
    assert entries["runner"]["enabled"] is False
    assert entries["alerts"]["enabled"] is False
    assert entries["dashboard"]["enabled"] is False
    assert "super-secret" not in response.text
    assert "pk-secret" not in response.text
    assert "sk-secret" not in response.text


def test_manual_ops_catalog_and_capability_registry(monkeypatch, tmp_path):
    init_repo(tmp_path)
    monkeypatch.setenv("HOMESTEAD_REPO_PATH", str(tmp_path))
    monkeypatch.setenv("RECEIPTS_DIR", str(tmp_path / "receipts"))

    catalog = client.get("/ops/actions")
    caps = client.get("/os/capabilities")

    assert catalog.status_code == 200
    assert catalog.json()["mode"] == "manual_only"
    assert catalog.json()["policy_gate_enabled"] is True
    assert catalog.json()["policy"]["default_decision"] == "deny"
    assert catalog.json()["scheduler_enabled"] is False
    assert catalog.json()["runner_enabled"] is False
    assert "sync_keep_health" in catalog.json()["actions"]
    assert "model_route" in catalog.json()["probes"]
    assert caps.status_code == 200
    manual_ops = caps.json()["entries"]["manual_ops"]
    assert manual_ops["status"] == "manual_only"
    assert manual_ops["policy_gate"] == "required"
    assert manual_ops["scheduler_enabled"] is False
    assert manual_ops["autonomous_execution"] is False


def test_ops_policy_surface_and_policy_check(monkeypatch, tmp_path):
    init_repo(tmp_path)
    monkeypatch.setenv("HOMESTEAD_REPO_PATH", str(tmp_path))
    monkeypatch.setenv("RECEIPTS_DIR", str(tmp_path / "receipts"))
    monkeypatch.setenv("OPENROUTER_API_KEY", "super-secret-openrouter")
    headers = trusted_codex_headers(monkeypatch)

    policy = client.get("/ops/policy")
    allowed = client.post(
        "/ops/policy/check",
        headers=headers,
        json={
            "operation_type": "probe",
            "operation": "node_status",
            "requesting_agent": "codex-policy-test",
        },
    )
    denied = client.post(
        "/ops/policy/check",
        json={
            "operation_type": "action",
            "operation": "turn_on_runner",
            "requesting_agent": "unknown",
        },
    )
    needs_confirmation = client.post(
        "/ops/policy/check",
        headers=headers,
        json={
            "operation_type": "action",
            "operation": "change_runtime_config",
            "requesting_agent": "codex-policy-test",
        },
    )
    spoofed = client.post(
        "/ops/policy/check",
        headers={"x-homestead-surface": "codex"},
        json={
            "operation_type": "action",
            "operation": "refresh_node_status",
            "requesting_agent": "unknown",
        },
    )

    assert policy.status_code == 200
    assert policy.json()["default_decision"] == "deny"
    assert policy.json()["mode"] == "manual_only"
    assert policy.json()["trusted_surface_token_required"] is True
    assert policy.json()["trusted_surface_token_configured"] is True
    assert allowed.status_code == 200
    assert allowed.json()["decision"] == "allow_with_receipt"
    assert allowed.json()["ok"] is True
    assert allowed.json()["surface"] == "codex"
    assert allowed.json()["receipt_required"] is True
    assert denied.status_code == 200
    assert denied.json()["decision"] == "deny"
    assert denied.json()["ok"] is False
    assert needs_confirmation.status_code == 200
    assert needs_confirmation.json()["decision"] == "needs_confirmation"
    assert needs_confirmation.json()["requires_confirmation"] is True
    assert spoofed.status_code == 200
    assert spoofed.json()["decision"] == "deny"
    assert spoofed.json()["surface"] == "unknown"
    combined = policy.text + allowed.text + denied.text + needs_confirmation.text + spoofed.text
    assert "super-secret-openrouter" not in combined
    assert POLICY_TOKEN not in combined


def test_manual_action_refresh_node_status_writes_receipt(monkeypatch, tmp_path):
    init_repo(tmp_path)
    receipts = tmp_path / "receipts"
    monkeypatch.setenv("HOMESTEAD_REPO_PATH", str(tmp_path))
    monkeypatch.setenv("RECEIPTS_DIR", str(receipts))
    monkeypatch.setenv("OPENROUTER_API_KEY", "super-secret-openrouter")
    headers = trusted_codex_headers(monkeypatch)

    response = client.post(
        "/ops/actions/run",
        headers=headers,
        json={
            "action": "refresh_node_status",
            "requesting_agent": "codex-manual-ops",
            "note": "manual action note",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["action"] == "refresh_node_status"
    assert body["mode"] == "manual_only"
    assert body["receipt_id"].startswith("manual-ops-action-refresh-node-status-")
    json_path = Path(body["json_path"])
    receipt = json.loads(json_path.read_text(encoding="utf-8"))
    assert receipt["task"] == "manual_ops_action"
    assert receipt["requesting_agent"] == "codex-manual-ops"
    assert receipt["review_required"] is False
    assert receipt["metadata"]["action"] == "refresh_node_status"
    assert receipt["metadata"]["manual_only"] is True
    assert receipt["metadata"]["note"] == "manual action note"
    assert receipt["metadata"]["policy"]["surface"] == "codex"
    assert receipt["metadata"]["policy"]["decision"] == "allow_with_receipt"
    assert "super-secret-openrouter" not in response.text
    assert "super-secret-openrouter" not in json.dumps(receipt)


def test_spoofed_surface_cannot_run_allowed_manual_action(monkeypatch, tmp_path):
    init_repo(tmp_path)
    receipts = tmp_path / "receipts"
    monkeypatch.setenv("HOMESTEAD_REPO_PATH", str(tmp_path))
    monkeypatch.setenv("RECEIPTS_DIR", str(receipts))
    monkeypatch.setenv("OPS_POLICY_SURFACE_TOKEN", POLICY_TOKEN)

    response = client.post(
        "/ops/actions/run",
        headers={"x-homestead-surface": "codex"},
        json={"action": "refresh_node_status", "requesting_agent": "spoofed-codex"},
    )

    assert response.status_code == 403
    detail = response.json()["detail"]
    assert detail["decision"] == "deny"
    assert detail["surface"] == "unknown"
    assert detail["operation"] == "refresh_node_status"
    assert list(receipts.rglob("manual-ops-action-refresh-node-status-*.json")) == []
    receipt_paths = list(receipts.rglob("ops-policy-action-refresh-node-status-*.json"))
    assert len(receipt_paths) == 1
    receipt = json.loads(receipt_paths[0].read_text(encoding="utf-8"))
    assert receipt["task"] == "ops_policy_decision"
    assert receipt["review_required"] is True
    assert receipt["metadata"]["surface"] == "unknown"
    assert receipt["metadata"]["allowed"] is False
    assert POLICY_TOKEN not in response.text


def test_manual_action_sync_keep_health_records_files_changed(monkeypatch, tmp_path):
    init_repo(tmp_path)
    receipts = tmp_path / "receipts"
    monkeypatch.setenv("HOMESTEAD_REPO_PATH", str(tmp_path))
    monkeypatch.setenv("RECEIPTS_DIR", str(receipts))
    monkeypatch.setenv("KEEP_HEALTH_DIR", "System Receipts/Homestead Health")
    headers = trusted_codex_headers(monkeypatch)

    response = client.post(
        "/ops/actions/run",
        headers=headers,
        json={"action": "sync_keep_health", "requesting_agent": "codex-manual-sync"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["result"]["health_dir"] == "/System Receipts/Homestead Health"
    assert "/System Receipts/Homestead Health/index.md" in body["result"]["files_changed"]
    receipt = json.loads(Path(body["json_path"]).read_text(encoding="utf-8"))
    assert receipt["metadata"]["action"] == "sync_keep_health"
    assert receipt["files_changed"]


def test_manual_action_unknown_is_safe(monkeypatch, tmp_path):
    receipts = tmp_path / "receipts"
    monkeypatch.setenv("RECEIPTS_DIR", str(receipts))

    response = client.post(
        "/ops/actions/run",
        json={"action": "turn_on_runner", "requesting_agent": "codex-denied-op"},
    )

    assert response.status_code == 403
    detail = response.json()["detail"]
    assert detail["decision"] == "deny"
    assert detail["operation"] == "turn_on_runner"
    assert detail["receipt_id"].startswith("ops-policy-action-turn-on-runner-")
    paths = list(receipts.rglob("ops-policy-action-turn-on-runner-*.json"))
    assert len(paths) == 1
    receipt = json.loads(paths[0].read_text(encoding="utf-8"))
    assert receipt["task"] == "ops_policy_decision"
    assert receipt["requesting_agent"] == "codex-denied-op"
    assert receipt["review_required"] is True
    assert receipt["metadata"]["policy_decision"] == "deny"
    assert receipt["metadata"]["allowed"] is False


def test_system_probe_exposure_and_recent_ops(monkeypatch, tmp_path):
    init_repo(tmp_path)
    receipts = tmp_path / "receipts"
    monkeypatch.setenv("HOMESTEAD_REPO_PATH", str(tmp_path))
    monkeypatch.setenv("RECEIPTS_DIR", str(receipts))
    headers = trusted_codex_headers(monkeypatch)

    probe = client.post(
        "/ops/probes/run",
        headers=headers,
        json={"probe": "exposure_config", "requesting_agent": "codex-probe"},
    )
    recent = client.get("/ops/recent?limit=5")

    assert probe.status_code == 200
    body = probe.json()
    assert body["ok"] is True
    assert body["probe"] == "exposure_config"
    assert body["receipt_id"].startswith("system-probe-exposure-config-")
    assert recent.status_code == 200
    assert recent.json()["count"] == 1
    first = recent.json()["receipts"][0]
    assert first["probe"] == "exposure_config"
    assert first["ok"] is True
    assert first["receipt_id"] == body["receipt_id"]


def test_system_probe_model_route_uses_self_url_without_returning_content(monkeypatch, tmp_path):
    class FakeAsyncClient:
        def __init__(self, timeout):
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, headers=None, json=None):
            assert url == "http://homestead-api:8000/model/route"
            assert headers["x-homestead-surface"] == "codex-model-probe"
            assert json["max_tokens"] == 40
            return httpx.Response(
                200,
                json={
                    "gateway": "direct",
                    "model": "openai/gpt-4.1-mini",
                    "content": "private assistant content should not be returned",
                    "finish_reason": "stop",
                    "receipt_id": "model-route-probe",
                },
            )

    receipts = tmp_path / "receipts"
    monkeypatch.setenv("RECEIPTS_DIR", str(receipts))
    monkeypatch.setenv("HOMESTEAD_SELF_URL", "http://homestead-api:8000")
    monkeypatch.setattr(main.httpx, "AsyncClient", FakeAsyncClient)
    headers = trusted_codex_headers(monkeypatch)

    response = client.post(
        "/ops/probes/run",
        headers=headers,
        json={"probe": "model_route", "requesting_agent": "codex-model-probe", "max_tokens": 40},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["results"][0]["probe"] == "model_route"
    assert body["results"][0]["gateway"] == "direct"
    assert body["results"][0]["model_route_receipt_id"] == "model-route-probe"
    assert "private assistant content" not in response.text
    receipt = json.loads(Path(body["json_path"]).read_text(encoding="utf-8"))
    assert "private assistant content" not in json.dumps(receipt)


def test_system_probe_failure_enters_review_queue(monkeypatch, tmp_path):
    class FakeAsyncClient:
        def __init__(self, timeout):
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, headers=None, json=None):
            return httpx.Response(503, json={"detail": "down"})

    receipts = tmp_path / "receipts"
    monkeypatch.setenv("RECEIPTS_DIR", str(receipts))
    monkeypatch.setenv("HOMESTEAD_SELF_URL", "http://homestead-api:8000")
    monkeypatch.setattr(main.httpx, "AsyncClient", FakeAsyncClient)
    headers = trusted_codex_headers(monkeypatch)

    probe = client.post(
        "/ops/probes/run",
        headers=headers,
        json={"probe": "model_route", "requesting_agent": "codex-fail-probe"},
    )
    review = client.get("/receipts/review?limit=5")

    assert probe.status_code == 200
    assert probe.json()["ok"] is False
    assert review.status_code == 200
    assert review.json()["count"] == 1
    assert review.json()["receipts"][0]["probe"] == "model_route"
    assert "review_required" in review.json()["receipts"][0]["review_reasons"]


def test_keep_health_sync_writes_metadata_only_to_keep(monkeypatch, tmp_path):
    init_repo(tmp_path)
    receipts = tmp_path / "receipts"
    monkeypatch.setenv("HOMESTEAD_REPO_PATH", str(tmp_path))
    monkeypatch.setenv("RECEIPTS_DIR", str(receipts))
    monkeypatch.setenv("KEEP_HEALTH_DIR", "System Receipts/Homestead Health")
    monkeypatch.setenv("MODEL_GATEWAY", "direct")
    monkeypatch.setenv("OPENROUTER_API_KEY", "super-secret-openrouter")
    headers = trusted_codex_headers(monkeypatch)
    write_test_receipt(
        receipts,
        "2026-06-28",
        "model-route-keep-health",
        {
            "requesting_agent": "pytest",
            "task": "model_route",
            "model_used": "openai/gpt-4.1-mini",
            "files_read": [],
            "actions_taken": [],
            "files_changed": [],
            "review_required": False,
            "verdict": "ok",
            "metadata": {
                "route": "/model/route",
                "gateway": "direct",
                "ok": True,
                "requested_model": "openai/gpt-4.1-mini",
            },
        },
        markdown="# Receipt\n\nsecret prompt should stay server-side\n",
    )

    response = client.post(
        "/keep/health/sync",
        headers=headers,
        json={"requesting_agent": "pytest-operator", "note": "acceptance sync"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["health_dir"] == "/System Receipts/Homestead Health"
    expected = [
        "/System Receipts/Homestead Health/index.md",
        "/System Receipts/Homestead Health/homestead-latest.md",
        "/System Receipts/Homestead Health/homestead-health-log.md",
        "/System Receipts/Homestead Health/gateway/gateway-health.md",
    ]
    for path in expected:
        assert path in body["files_changed"]
        assert (tmp_path / path.lstrip("/")).exists()

    combined = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (tmp_path / "System Receipts" / "Homestead Health").rglob("*.md")
    )
    assert "model-route-keep-health" in combined
    assert "acceptance sync" in combined
    assert "secret prompt" not in combined
    assert "super-secret-openrouter" not in combined


def test_keep_health_sync_direct_path_is_gated(monkeypatch, tmp_path):
    init_repo(tmp_path)
    receipts = tmp_path / "receipts"
    monkeypatch.setenv("HOMESTEAD_REPO_PATH", str(tmp_path))
    monkeypatch.setenv("RECEIPTS_DIR", str(receipts))
    monkeypatch.setenv("KEEP_HEALTH_DIR", "System Receipts/Homestead Health")
    monkeypatch.setenv("OPS_POLICY_SURFACE_TOKEN", POLICY_TOKEN)

    response = client.post(
        "/keep/health/sync",
        headers={"x-homestead-surface": "codex"},
        json={"requesting_agent": "spoofed-codex", "note": "should not write"},
    )

    assert response.status_code == 403
    detail = response.json()["detail"]
    assert detail["decision"] == "deny"
    assert detail["surface"] == "unknown"
    assert detail["operation"] == "sync_keep_health"
    assert detail["receipt_id"].startswith("ops-policy-action-sync-keep-health-")
    assert not (tmp_path / "System Receipts" / "Homestead Health").exists()
    receipt_paths = list(receipts.rglob("ops-policy-action-sync-keep-health-*.json"))
    assert len(receipt_paths) == 1
    receipt = json.loads(receipt_paths[0].read_text(encoding="utf-8"))
    assert receipt["task"] == "ops_policy_decision"
    assert receipt["review_required"] is True
    assert receipt["metadata"]["surface"] == "unknown"
    assert receipt["metadata"]["policy_decision"] == "deny"
    assert "should not write" not in json.dumps(receipt)
    assert POLICY_TOKEN not in response.text


def test_model_route_requires_openrouter_config(monkeypatch):
    for name in [
        "OPENROUTER_API_KEY",
        "OPENROUTER_BASE_URL",
        "OPENROUTER_DEFAULT_MODEL",
        "OPENROUTER_HTTP_REFERER",
        "OPENROUTER_APP_TITLE",
    ]:
        monkeypatch.delenv(name, raising=False)

    response = client.post("/model/route", json={"prompt": "hello"})

    assert response.status_code == 503
    assert "OPENROUTER_API_KEY" in response.json()["detail"]["missing"]


def test_model_route_calls_openrouter_with_expected_headers(monkeypatch):
    captured = {}

    class FakeAsyncClient:
        def __init__(self, timeout):
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, headers, json):
            captured["url"] = url
            captured["headers"] = headers
            captured["json"] = json
            return httpx.Response(
                200,
                json={
                    "model": "openai/gpt-4.1-mini",
                    "choices": [
                        {
                            "message": {"role": "assistant", "content": "Hello from Homestead."},
                            "finish_reason": "stop",
                        }
                    ],
                    "usage": {"prompt_tokens": 4, "completion_tokens": 4, "total_tokens": 8},
                },
            )

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1/")
    monkeypatch.setenv("OPENROUTER_DEFAULT_MODEL", "openai/gpt-4.1-mini")
    monkeypatch.setenv("OPENROUTER_HTTP_REFERER", "https://homesteadai.io")
    monkeypatch.setenv("OPENROUTER_APP_TITLE", "Homestead Private OS")
    monkeypatch.setattr(main.httpx, "AsyncClient", FakeAsyncClient)

    response = client.post(
        "/model/route",
        json={"prompt": "Say hello.", "max_tokens": 80, "temperature": 0.1},
    )

    assert response.status_code == 200
    assert response.json()["gateway"] == "direct"
    assert response.json()["content"] == "Hello from Homestead."
    assert captured["url"] == "https://openrouter.ai/api/v1/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer test-key"
    assert captured["headers"]["HTTP-Referer"] == "https://homesteadai.io"
    assert captured["headers"]["X-OpenRouter-Title"] == "Homestead Private OS"
    assert captured["json"]["model"] == "openai/gpt-4.1-mini"
    assert captured["json"]["messages"] == [{"role": "user", "content": "Say hello."}]
    assert captured["json"]["max_tokens"] == 80
    assert captured["json"]["temperature"] == 0.1


def test_model_route_rejects_unknown_gateway(monkeypatch):
    monkeypatch.setenv("MODEL_GATEWAY", "space-laser")

    response = client.post("/model/route", json={"prompt": "hello"})

    assert response.status_code == 503
    assert response.json()["detail"]["error"] == "Model gateway is not configured"
    assert response.json()["detail"]["gateway"] == "space-laser"


def test_model_route_litellm_uses_config_and_omits_temperature_by_default(monkeypatch):
    captured = {}

    class FakeAsyncClient:
        def __init__(self, timeout):
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, headers, json):
            captured["url"] = url
            captured["headers"] = headers
            captured["json"] = json
            return httpx.Response(
                200,
                json={
                    "model": "haiku",
                    "choices": [{"message": {"content": "ok from litellm"}, "finish_reason": "stop"}],
                    "usage": {"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5},
                },
            )

    monkeypatch.setenv("MODEL_GATEWAY", "litellm")
    monkeypatch.setenv("LITELLM_BASE_URL", "http://127.0.0.1:4000")
    monkeypatch.setenv("LITELLM_API_KEY", "litellm-secret")
    monkeypatch.setenv("LITELLM_DEFAULT_MODEL", "haiku")
    monkeypatch.setattr(main.httpx, "AsyncClient", FakeAsyncClient)

    response = client.post("/model/route", json={"prompt": "hello", "temperature": 0.1})

    assert response.status_code == 200
    assert response.json()["gateway"] == "litellm"
    assert response.json()["content"] == "ok from litellm"
    assert captured["url"] == "http://127.0.0.1:4000/v1/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer litellm-secret"
    assert "HTTP-Referer" not in captured["headers"]
    assert "X-OpenRouter-Title" not in captured["headers"]
    assert captured["json"]["model"] == "haiku"
    assert captured["json"]["max_tokens"] == 256
    assert "temperature" not in captured["json"]


def test_model_route_litellm_can_send_temperature_when_enabled(monkeypatch):
    captured = {}

    class FakeAsyncClient:
        def __init__(self, timeout):
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, headers, json):
            captured["json"] = json
            return httpx.Response(
                200,
                json={
                    "model": "aux",
                    "choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}],
                },
            )

    monkeypatch.setenv("MODEL_GATEWAY", "litellm")
    monkeypatch.setenv("LITELLM_BASE_URL", "http://127.0.0.1:4000")
    monkeypatch.setenv("LITELLM_API_KEY", "litellm-secret")
    monkeypatch.setenv("LITELLM_DEFAULT_MODEL", "aux")
    monkeypatch.setenv("LITELLM_SEND_TEMPERATURE", "true")
    monkeypatch.setattr(main.httpx, "AsyncClient", FakeAsyncClient)

    response = client.post("/model/route", json={"prompt": "hello", "temperature": 0.7})

    assert response.status_code == 200
    assert captured["json"]["temperature"] == 0.7


def test_model_route_litellm_failure_does_not_fallback_to_openrouter(monkeypatch):
    calls = []

    class FakeAsyncClient:
        def __init__(self, timeout):
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, headers, json):
            calls.append(url)
            return httpx.Response(500, json={"error": {"message": "litellm upstream failed"}})

    monkeypatch.setenv("MODEL_GATEWAY", "litellm")
    monkeypatch.setenv("LITELLM_BASE_URL", "http://127.0.0.1:4000")
    monkeypatch.setenv("LITELLM_API_KEY", "litellm-secret")
    monkeypatch.setenv("LITELLM_DEFAULT_MODEL", "haiku")
    monkeypatch.setenv("OPENROUTER_API_KEY", "openrouter-secret")
    monkeypatch.setenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    monkeypatch.setenv("OPENROUTER_DEFAULT_MODEL", "openai/gpt-4.1-mini")
    monkeypatch.setenv("OPENROUTER_HTTP_REFERER", "https://homesteadai.io")
    monkeypatch.setenv("OPENROUTER_APP_TITLE", "Homestead Private OS")
    monkeypatch.setattr(main.httpx, "AsyncClient", FakeAsyncClient)

    response = client.post("/model/route", json={"prompt": "do not leak prompt"})

    assert response.status_code == 502
    assert calls == ["http://127.0.0.1:4000/v1/chat/completions"]
    assert response.json()["detail"]["error"] == "litellm upstream failed"
    assert "openrouter-secret" not in response.text
    assert "litellm-secret" not in response.text
    assert "do not leak prompt" not in response.text


def test_model_route_tracing_enabled_posts_langfuse_without_prompt(monkeypatch):
    calls = []

    class FakeAsyncClient:
        def __init__(self, timeout):
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, headers=None, json=None, auth=None):
            calls.append({"url": url, "headers": headers, "json": json, "auth": auth})
            if url.endswith("/chat/completions"):
                return httpx.Response(
                    200,
                    json={
                        "model": "openai/gpt-4.1-mini",
                        "choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}],
                        "usage": {"prompt_tokens": 2, "completion_tokens": 1, "total_tokens": 3},
                    },
                )
            return httpx.Response(
                207,
                json={"successes": [{"id": "trace"}], "errors": []},
                request=httpx.Request("POST", url),
            )

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    monkeypatch.setenv("OPENROUTER_DEFAULT_MODEL", "openai/gpt-4.1-mini")
    monkeypatch.setenv("OPENROUTER_HTTP_REFERER", "https://homesteadai.io")
    monkeypatch.setenv("OPENROUTER_APP_TITLE", "Homestead Private OS")
    monkeypatch.setenv("LANGFUSE_ENABLED", "true")
    monkeypatch.setenv("LANGFUSE_HOST", "http://100.112.20.36:3000")
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-test")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-test")
    monkeypatch.setenv("LANGFUSE_ENVIRONMENT", "homestead-private-os")
    monkeypatch.setenv("LANGFUSE_RELEASE", "v0-openrouter-route")
    monkeypatch.setattr(main.httpx, "AsyncClient", FakeAsyncClient)

    response = client.post(
        "/model/route",
        json={"prompt": "private prompt should not be traced", "max_tokens": 80},
        headers={"x-homestead-surface": "pytest"},
    )

    assert response.status_code == 200
    assert response.json()["content"] == "ok"
    assert len(calls) == 2
    trace_call = calls[1]
    assert trace_call["url"] == "http://100.112.20.36:3000/api/public/ingestion"
    assert trace_call["auth"] == ("pk-test", "sk-test")
    batch = trace_call["json"]["batch"]
    assert [item["type"] for item in batch] == ["trace-create", "generation-create"]
    metadata = batch[0]["body"]["metadata"]
    assert metadata["route"] == "/model/route"
    assert metadata["requested_model"] == "openai/gpt-4.1-mini"
    assert metadata["model_used"] == "openai/gpt-4.1-mini"
    assert metadata["ok"] is True
    assert metadata["requesting_surface"] == "pytest"
    assert "private prompt" not in json.dumps(trace_call["json"])
    assert "content" not in batch[1]["body"]


def test_model_route_tracing_failure_is_fail_open(monkeypatch):
    calls = []

    class FakeAsyncClient:
        def __init__(self, timeout):
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, headers=None, json=None, auth=None):
            calls.append(url)
            if url.endswith("/chat/completions"):
                return httpx.Response(
                    200,
                    json={
                        "model": "openai/gpt-4.1-mini",
                        "choices": [{"message": {"content": "still works"}, "finish_reason": "stop"}],
                    },
                )
            raise httpx.ConnectError("langfuse unavailable")

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    monkeypatch.setenv("OPENROUTER_DEFAULT_MODEL", "openai/gpt-4.1-mini")
    monkeypatch.setenv("OPENROUTER_HTTP_REFERER", "https://homesteadai.io")
    monkeypatch.setenv("OPENROUTER_APP_TITLE", "Homestead Private OS")
    monkeypatch.setenv("LANGFUSE_ENABLED", "true")
    monkeypatch.setenv("LANGFUSE_HOST", "http://100.112.20.36:3000")
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-test")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-test")
    monkeypatch.setattr(main.httpx, "AsyncClient", FakeAsyncClient)

    response = client.post("/model/route", json={"prompt": "hello"})

    assert response.status_code == 200
    assert response.json()["content"] == "still works"
    assert calls == [
        "https://openrouter.ai/api/v1/chat/completions",
        "http://100.112.20.36:3000/api/public/ingestion",
    ]


def test_model_route_receipts_disabled_does_not_write(monkeypatch, tmp_path):
    class FakeAsyncClient:
        def __init__(self, timeout):
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, headers=None, json=None, auth=None):
            return httpx.Response(
                200,
                json={
                    "model": "openai/gpt-4.1-mini",
                    "choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}],
                },
            )

    receipts = tmp_path / "receipts"
    monkeypatch.setenv("RECEIPTS_DIR", str(receipts))
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    monkeypatch.setenv("OPENROUTER_DEFAULT_MODEL", "openai/gpt-4.1-mini")
    monkeypatch.setenv("OPENROUTER_HTTP_REFERER", "https://homesteadai.io")
    monkeypatch.setenv("OPENROUTER_APP_TITLE", "Homestead Private OS")
    monkeypatch.setenv("MODEL_ROUTE_RECEIPTS_ENABLED", "false")
    monkeypatch.setattr(main.httpx, "AsyncClient", FakeAsyncClient)

    response = client.post("/model/route", json={"prompt": "secret prompt"})

    assert response.status_code == 200
    assert "receipt_id" not in response.json()
    assert not receipts.exists()


def test_model_route_receipts_enabled_writes_metadata_without_prompt(monkeypatch, tmp_path):
    class FakeAsyncClient:
        def __init__(self, timeout):
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, headers=None, json=None, auth=None):
            if url.endswith("/chat/completions"):
                return httpx.Response(
                    200,
                    json={
                        "model": "openai/gpt-4.1-mini",
                        "choices": [{"message": {"content": "receipt ok"}, "finish_reason": "stop"}],
                        "usage": {"prompt_tokens": 5, "completion_tokens": 2, "total_tokens": 7},
                    },
                )
            return httpx.Response(
                207,
                json={"successes": [{"id": "trace"}], "errors": []},
                request=httpx.Request("POST", url),
            )

    receipts = tmp_path / "receipts"
    monkeypatch.setenv("RECEIPTS_DIR", str(receipts))
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    monkeypatch.setenv("OPENROUTER_DEFAULT_MODEL", "openai/gpt-4.1-mini")
    monkeypatch.setenv("OPENROUTER_HTTP_REFERER", "https://homesteadai.io")
    monkeypatch.setenv("OPENROUTER_APP_TITLE", "Homestead Private OS")
    monkeypatch.setenv("LANGFUSE_ENABLED", "true")
    monkeypatch.setenv("LANGFUSE_HOST", "http://100.112.20.36:3000")
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-test")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-test")
    monkeypatch.setenv("MODEL_ROUTE_RECEIPTS_ENABLED", "true")
    monkeypatch.setattr(main.httpx, "AsyncClient", FakeAsyncClient)

    response = client.post(
        "/model/route",
        json={"prompt": "do not put this prompt in the receipt", "max_tokens": 80},
        headers={"x-homestead-surface": "pytest-receipts"},
    )

    body = response.json()
    assert response.status_code == 200
    assert body["receipt_id"].startswith("model-route-")
    receipt_path = Path(body["receipt_path"])
    json_path = receipt_path.with_suffix(".json")
    assert receipt_path.exists()
    assert json_path.exists()

    receipt_text = receipt_path.read_text(encoding="utf-8")
    receipt_json = json.loads(json_path.read_text(encoding="utf-8"))
    metadata = receipt_json["metadata"]
    assert receipt_json["task"] == "model_route"
    assert receipt_json["requesting_agent"] == "pytest-receipts"
    assert receipt_json["files_read"] == []
    assert receipt_json["files_changed"] == []
    assert receipt_json["review_required"] is False
    assert receipt_json["verdict"] == "ok"
    assert metadata["route"] == "/model/route"
    assert metadata["requested_model"] == "openai/gpt-4.1-mini"
    assert metadata["model_used"] == "openai/gpt-4.1-mini"
    assert isinstance(metadata["latency_ms"], int)
    assert metadata["ok"] is True
    assert metadata["usage"]["total_tokens"] == 7
    assert metadata["langfuse_trace_id"]
    assert "do not put this prompt" not in receipt_text
    assert "receipt ok" not in receipt_text
    assert "do not put this prompt" not in json.dumps(receipt_json)
    assert "receipt ok" not in json.dumps(receipt_json)


def test_model_route_receipt_writer_failure_is_fail_open(monkeypatch):
    class FakeAsyncClient:
        def __init__(self, timeout):
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, headers=None, json=None, auth=None):
            return httpx.Response(
                200,
                json={
                    "model": "openai/gpt-4.1-mini",
                    "choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}],
                },
            )

    def fail_write(payload):
        raise OSError("disk path leaked? no")

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    monkeypatch.setenv("OPENROUTER_DEFAULT_MODEL", "openai/gpt-4.1-mini")
    monkeypatch.setenv("OPENROUTER_HTTP_REFERER", "https://homesteadai.io")
    monkeypatch.setenv("OPENROUTER_APP_TITLE", "Homestead Private OS")
    monkeypatch.setenv("MODEL_ROUTE_RECEIPTS_ENABLED", "true")
    monkeypatch.setattr(main.httpx, "AsyncClient", FakeAsyncClient)
    monkeypatch.setattr(main, "write_model_route_receipt", fail_write)

    response = client.post("/model/route", json={"prompt": "hello"})

    assert response.status_code == 200
    assert response.json()["content"] == "ok"
    assert response.json()["receipt_error"] == "receipt write failed"
    assert "disk path" not in response.text


def test_model_route_openrouter_failure_writes_safe_receipt(monkeypatch, tmp_path):
    class FakeAsyncClient:
        def __init__(self, timeout):
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, headers=None, json=None, auth=None):
            return httpx.Response(500, json={"error": {"message": "provider failed"}})

    receipts = tmp_path / "receipts"
    monkeypatch.setenv("RECEIPTS_DIR", str(receipts))
    monkeypatch.setenv("OPENROUTER_API_KEY", "super-secret-openrouter")
    monkeypatch.setenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    monkeypatch.setenv("OPENROUTER_DEFAULT_MODEL", "openai/gpt-4.1-mini")
    monkeypatch.setenv("OPENROUTER_HTTP_REFERER", "https://homesteadai.io")
    monkeypatch.setenv("OPENROUTER_APP_TITLE", "Homestead Private OS")
    monkeypatch.setenv("MODEL_ROUTE_RECEIPTS_ENABLED", "true")
    monkeypatch.setattr(main.httpx, "AsyncClient", FakeAsyncClient)

    response = client.post("/model/route", json={"prompt": "do not leak failure prompt"})

    assert response.status_code == 502
    paths = list(receipts.rglob("model-route-*.json"))
    assert len(paths) == 1
    receipt_json = json.loads(paths[0].read_text(encoding="utf-8"))
    receipt_text = paths[0].with_suffix(".md").read_text(encoding="utf-8")
    assert receipt_json["verdict"] == "error"
    assert receipt_json["review_required"] is True
    assert receipt_json["metadata"]["ok"] is False
    assert receipt_json["metadata"]["error_summary"] == "provider failed"
    combined = json.dumps(receipt_json) + receipt_text + response.text
    assert "super-secret-openrouter" not in combined
    assert "do not leak failure prompt" not in combined


def test_model_route_errors_do_not_leak_secrets_or_prompt(monkeypatch):
    class FakeAsyncClient:
        def __init__(self, timeout):
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, headers=None, json=None, auth=None):
            if url.endswith("/chat/completions"):
                return httpx.Response(500, json={"error": {"message": "provider failed"}})
            raise AssertionError("Langfuse should not change the error response")

    monkeypatch.setenv("OPENROUTER_API_KEY", "super-secret-openrouter")
    monkeypatch.setenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    monkeypatch.setenv("OPENROUTER_DEFAULT_MODEL", "openai/gpt-4.1-mini")
    monkeypatch.setenv("OPENROUTER_HTTP_REFERER", "https://homesteadai.io")
    monkeypatch.setenv("OPENROUTER_APP_TITLE", "Homestead Private OS")
    monkeypatch.setenv("LANGFUSE_ENABLED", "true")
    monkeypatch.setenv("LANGFUSE_HOST", "http://100.112.20.36:3000")
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-secret")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-secret")
    monkeypatch.setattr(main.httpx, "AsyncClient", FakeAsyncClient)

    response = client.post("/model/route", json={"prompt": "do not leak this prompt"})

    assert response.status_code == 502
    body = response.text
    assert "super-secret-openrouter" not in body
    assert "pk-secret" not in body
    assert "sk-secret" not in body
    assert "do not leak this prompt" not in body
    assert "provider failed" in body


def test_model_route_does_not_double_prefix_bearer(monkeypatch):
    captured = {}

    class FakeAsyncClient:
        def __init__(self, timeout):
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, headers, json):
            captured["headers"] = headers
            return httpx.Response(
                200,
                json={
                    "model": "openai/gpt-4.1-mini",
                    "choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}],
                },
            )

    monkeypatch.setenv("OPENROUTER_API_KEY", "Bearer test-key")
    monkeypatch.setenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    monkeypatch.setenv("OPENROUTER_DEFAULT_MODEL", "openai/gpt-4.1-mini")
    monkeypatch.setenv("OPENROUTER_HTTP_REFERER", "https://homesteadai.io")
    monkeypatch.setenv("OPENROUTER_APP_TITLE", "Homestead Private OS")
    monkeypatch.setattr(main.httpx, "AsyncClient", FakeAsyncClient)

    response = client.post("/model/route", json={"prompt": "hello"})

    assert response.status_code == 200
    assert captured["headers"]["Authorization"] == "Bearer test-key"


def test_model_route_normalizes_header_like_api_key(monkeypatch):
    captured = {}

    class FakeAsyncClient:
        def __init__(self, timeout):
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, headers, json):
            captured["headers"] = headers
            return httpx.Response(
                200,
                json={
                    "model": "openai/gpt-4.1-mini",
                    "choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}],
                },
            )

    monkeypatch.setenv("OPENROUTER_API_KEY", "Authorization: Bearer test-key")
    monkeypatch.setenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    monkeypatch.setenv("OPENROUTER_DEFAULT_MODEL", "openai/gpt-4.1-mini")
    monkeypatch.setenv("OPENROUTER_HTTP_REFERER", "https://homesteadai.io")
    monkeypatch.setenv("OPENROUTER_APP_TITLE", "Homestead Private OS")
    monkeypatch.setattr(main.httpx, "AsyncClient", FakeAsyncClient)

    response = client.post("/model/route", json={"prompt": "hello"})

    assert response.status_code == 200
    assert captured["headers"]["Authorization"] == "Bearer test-key"
