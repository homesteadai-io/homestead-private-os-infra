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
        "MODEL_ROUTE_RECEIPTS_ENABLED",
        "MODEL_ROUTE_RECEIPTS_INCLUDE_CONTENT",
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
