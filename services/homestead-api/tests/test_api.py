from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


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

