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


@pytest.fixture(autouse=True)
def clear_langfuse_env(monkeypatch):
    for name in [
        "LANGFUSE_ENABLED",
        "LANGFUSE_HOST",
        "LANGFUSE_PUBLIC_KEY",
        "LANGFUSE_SECRET_KEY",
        "LANGFUSE_ENVIRONMENT",
        "LANGFUSE_RELEASE",
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
    assert response.json()["content"] == "Hello from Homestead."
    assert captured["url"] == "https://openrouter.ai/api/v1/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer test-key"
    assert captured["headers"]["HTTP-Referer"] == "https://homesteadai.io"
    assert captured["headers"]["X-OpenRouter-Title"] == "Homestead Private OS"
    assert captured["json"]["model"] == "openai/gpt-4.1-mini"
    assert captured["json"]["messages"] == [{"role": "user", "content": "Say hello."}]
    assert captured["json"]["max_tokens"] == 80


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
            return httpx.Response(207, json={"successes": [{"id": "trace"}], "errors": []})

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
