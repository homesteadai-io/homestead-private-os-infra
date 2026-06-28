from __future__ import annotations

import json
import os
import re
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field


app = FastAPI(title="Homestead Private OS API", version="0.1.0")


def repo_path() -> Path:
    return Path(os.getenv("HOMESTEAD_REPO_PATH", ".")).resolve()


def receipts_dir() -> Path:
    return Path(os.getenv("RECEIPTS_DIR", "receipts")).resolve()


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def run_git(args: list[str], cwd: Path) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=str(cwd),
            text=True,
            capture_output=True,
            timeout=20,
            check=False,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=500, detail="git is not installed") from exc
    except subprocess.TimeoutExpired as exc:
        raise HTTPException(status_code=504, detail=f"git {' '.join(args)} timed out") from exc

    return {
        "ok": completed.returncode == 0,
        "returncode": completed.returncode,
        "stdout": completed.stdout.strip(),
        "stderr": completed.stderr.strip(),
    }


def require_repo() -> Path:
    root = repo_path()
    if not root.exists():
        raise HTTPException(status_code=404, detail=f"repo path does not exist: {root}")

    probe = run_git(["rev-parse", "--is-inside-work-tree"], root)
    if not probe["ok"] or probe["stdout"] != "true":
        raise HTTPException(status_code=400, detail=f"path is not a git work tree: {root}")

    return root


def safe_relative_path(path: str) -> Path:
    root = repo_path()
    candidate = (root / path).resolve()
    if root not in [candidate, *candidate.parents]:
        raise HTTPException(status_code=400, detail="path escapes configured repo")
    return candidate


def markdown_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in root.rglob("*.md"):
        if ".git" in path.parts:
            continue
        if any(part in {"_raw", "node_modules", ".venv", "venv"} for part in path.parts):
            continue
        if path.is_file():
            files.append(path)
    return sorted(files)


def snippet_for(text: str, query: str, max_chars: int = 320) -> str:
    if not query:
        return text[:max_chars].replace("\n", " ").strip()

    match = re.search(re.escape(query), text, flags=re.IGNORECASE)
    if not match:
        return text[:max_chars].replace("\n", " ").strip()

    start = max(match.start() - max_chars // 2, 0)
    end = min(match.end() + max_chars // 2, len(text))
    return text[start:end].replace("\n", " ").strip()


def query_terms(query: str) -> list[str]:
    terms = re.findall(r"[A-Za-z0-9][A-Za-z0-9_-]{2,}", query.lower())
    return list(dict.fromkeys(terms))


def relevance_score(path: Path, text: str, terms: list[str]) -> int:
    haystack = text.lower()
    filename = path.name.lower()
    score = 0
    for term in terms:
        if term in filename:
            score += 8
        if term in haystack:
            score += min(haystack.count(term), 10)
    return score


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    max_results: int = Field(default=10, ge=1, le=50)


class ContextPackRequest(BaseModel):
    task: str = Field(..., min_length=1)
    max_files: int = Field(default=8, ge=1, le=25)


class ReadConceptRequest(BaseModel):
    path: str = Field(..., min_length=1)


class ReceiptRequest(BaseModel):
    run_id: str | None = None
    timestamp: str | None = None
    requesting_agent: str = "unknown"
    task: str
    files_read: list[str] = Field(default_factory=list)
    model_used: str = "not_applicable_v0"
    actions_taken: list[str] = Field(default_factory=list)
    files_changed: list[str] = Field(default_factory=list)
    review_required: bool = False
    verdict: str = "recorded"
    metadata: dict[str, Any] = Field(default_factory=dict)


class ModelRouteRequest(BaseModel):
    prompt: str = Field(..., min_length=1)
    system: str | None = None
    model: str | None = None
    max_tokens: int = Field(default=256, ge=1, le=4096)
    temperature: float | None = Field(default=None, ge=0, le=2)


def clean_run_id(value: str | None) -> str:
    raw = value or f"run-{uuid4().hex[:12]}"
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", raw).strip("-._")
    return cleaned or f"run-{uuid4().hex[:12]}"


def validate_receipt_date(value: str) -> str:
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="date must be YYYY-MM-DD") from exc
    return parsed.isoformat()


def safe_receipt_id(value: str) -> str:
    receipt_id = clean_run_id(value)
    if receipt_id != value or not receipt_id:
        raise HTTPException(status_code=400, detail="receipt_id contains unsupported characters")
    return receipt_id


def receipt_json_path(date: str, receipt_id: str) -> Path:
    safe_date = validate_receipt_date(date)
    safe_id = safe_receipt_id(receipt_id)
    return receipts_dir() / safe_date / f"{safe_id}.json"


def read_receipt_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="receipt not found") from exc
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail="receipt JSON is invalid") from exc
    if not isinstance(data, dict):
        raise HTTPException(status_code=500, detail="receipt JSON must be an object")
    return data


def receipt_summary(json_path: Path) -> dict[str, Any]:
    data = read_receipt_json(json_path)
    metadata = data.get("metadata") if isinstance(data.get("metadata"), dict) else {}
    receipt_id = str(data.get("run_id") or json_path.stem)
    markdown_path = json_path.with_suffix(".md")
    usage = metadata.get("usage")
    return {
        "receipt_id": receipt_id,
        "timestamp": data.get("timestamp"),
        "task": data.get("task"),
        "requesting_agent": data.get("requesting_agent"),
        "verdict": data.get("verdict"),
        "review_required": data.get("review_required"),
        "route": metadata.get("route"),
        "gateway": metadata.get("gateway"),
        "requested_model": metadata.get("requested_model"),
        "model_used": metadata.get("model_used") or data.get("model_used"),
        "latency_ms": metadata.get("latency_ms"),
        "usage": usage,
        "langfuse_trace_id": metadata.get("langfuse_trace_id"),
        "markdown_path": str(markdown_path),
        "json_path": str(json_path),
    }


def receipt_json_files_for_date(date: str) -> list[Path]:
    safe_date = validate_receipt_date(date)
    date_dir = receipts_dir() / safe_date
    if not date_dir.exists():
        return []
    if not date_dir.is_dir():
        raise HTTPException(status_code=500, detail="receipt date path is not a directory")
    return sorted(date_dir.glob("*.json"))


def all_receipt_json_files() -> list[Path]:
    root = receipts_dir()
    if not root.exists():
        return []
    paths: list[Path] = []
    for date_dir in sorted(root.iterdir(), reverse=True):
        if date_dir.is_dir() and re.fullmatch(r"\d{4}-\d{2}-\d{2}", date_dir.name):
            paths.extend(sorted(date_dir.glob("*.json"), reverse=True))
    return paths


def sorted_receipt_summaries(paths: list[Path]) -> list[dict[str, Any]]:
    summaries = [receipt_summary(path) for path in paths]
    return sorted(
        summaries,
        key=lambda item: (str(item.get("timestamp") or ""), str(item.get("receipt_id") or "")),
        reverse=True,
    )


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "ok": True,
        "service": "homestead-api",
        "version": "0.1.0",
        "repo_path": str(repo_path()),
    }


@app.get("/receipts/recent")
def receipts_recent(limit: int = 20) -> dict[str, Any]:
    if limit < 1 or limit > 100:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 100")
    summaries = sorted_receipt_summaries(all_receipt_json_files())[:limit]
    return {"limit": limit, "count": len(summaries), "receipts": summaries}


@app.get("/receipts/by-date/{date}")
def receipts_by_date(date: str) -> dict[str, Any]:
    safe_date = validate_receipt_date(date)
    summaries = sorted_receipt_summaries(receipt_json_files_for_date(safe_date))
    return {"date": safe_date, "count": len(summaries), "receipts": summaries}


@app.get("/receipts/stats")
def receipts_stats() -> dict[str, Any]:
    summaries = sorted_receipt_summaries(all_receipt_json_files())
    by_task: dict[str, int] = {}
    by_verdict: dict[str, int] = {}
    review_required = 0
    for summary in summaries:
        task = str(summary.get("task") or "unknown")
        verdict = str(summary.get("verdict") or "unknown")
        by_task[task] = by_task.get(task, 0) + 1
        by_verdict[verdict] = by_verdict.get(verdict, 0) + 1
        if summary.get("review_required") is True:
            review_required += 1
    return {
        "total": len(summaries),
        "by_task": by_task,
        "by_verdict": by_verdict,
        "review_required": review_required,
        "latest_timestamp": summaries[0].get("timestamp") if summaries else None,
    }


@app.get("/receipts/{date}/{receipt_id}")
def receipt_read(date: str, receipt_id: str) -> dict[str, Any]:
    safe_date = validate_receipt_date(date)
    safe_id = safe_receipt_id(receipt_id)
    json_path = receipt_json_path(safe_date, safe_id)
    data = read_receipt_json(json_path)
    markdown_path = json_path.with_suffix(".md")
    markdown = None
    if markdown_path.exists():
        markdown = markdown_path.read_text(encoding="utf-8", errors="replace")
    return {
        "receipt_id": safe_id,
        "date": safe_date,
        "summary": receipt_summary(json_path),
        "json": data,
        "markdown": markdown,
        "markdown_path": str(markdown_path),
        "json_path": str(json_path),
    }


@app.get("/repo/status")
def repo_status() -> dict[str, Any]:
    root = require_repo()
    branch = run_git(["branch", "--show-current"], root)
    commit = run_git(["log", "-1", "--pretty=format:%H %s"], root)
    dirty = run_git(["status", "--porcelain"], root)

    return {
        "repo_path": str(root),
        "branch": branch["stdout"] or "DETACHED",
        "latest_commit": commit["stdout"],
        "dirty": bool(dirty["stdout"]),
        "dirty_files": dirty["stdout"].splitlines() if dirty["stdout"] else [],
    }


@app.post("/repo/sync")
def repo_sync() -> dict[str, Any]:
    root = require_repo()
    result = run_git(["fetch", "--all", "--prune"], root)
    return {
        "operation": "git fetch --all --prune",
        "repo_path": str(root),
        "ok": result["ok"],
        "stdout": result["stdout"],
        "stderr": result["stderr"],
    }


@app.post("/search")
def search(request: SearchRequest) -> dict[str, Any]:
    root = repo_path()
    if not root.exists():
        raise HTTPException(status_code=404, detail=f"repo path does not exist: {root}")

    results: list[tuple[int, dict[str, Any]]] = []
    terms = query_terms(request.query)
    query_lower = request.query.lower()
    for path in markdown_files(root):
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            text = path.read_text(encoding="utf-8", errors="replace")

        score = relevance_score(path, text, terms)
        if score == 0 and query_lower not in text.lower() and query_lower not in path.name.lower():
            continue

        relative = "/" + path.relative_to(root).as_posix()
        results.append(
            (
                score,
                {
                "path": relative,
                "snippet": snippet_for(text, request.query),
                },
            )
        )

    ranked = [item for _, item in sorted(results, key=lambda result: (-result[0], result[1]["path"]))]
    limited = ranked[: request.max_results]
    return {"query": request.query, "count": len(limited), "results": limited}


@app.post("/context-pack")
def context_pack(request: ContextPackRequest) -> dict[str, Any]:
    found = search(SearchRequest(query=request.task, max_results=request.max_files))
    return {
        "task": request.task,
        "generated_at": utc_now(),
        "files": found["results"],
    }


def openrouter_config() -> dict[str, str]:
    api_key = normalize_api_key(os.getenv("OPENROUTER_API_KEY", ""))
    values = {
        "api_key": api_key,
        "base_url": os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1").strip(),
        "default_model": os.getenv("OPENROUTER_DEFAULT_MODEL", "").strip(),
        "http_referer": os.getenv("OPENROUTER_HTTP_REFERER", "").strip(),
        "app_title": os.getenv("OPENROUTER_APP_TITLE", "Homestead Private OS").strip(),
    }
    missing = [
        name
        for name, value in {
            "OPENROUTER_API_KEY": values["api_key"],
            "OPENROUTER_BASE_URL": values["base_url"],
            "OPENROUTER_DEFAULT_MODEL": values["default_model"],
            "OPENROUTER_HTTP_REFERER": values["http_referer"],
            "OPENROUTER_APP_TITLE": values["app_title"],
        }.items()
        if not value
    ]
    if missing:
        raise HTTPException(status_code=503, detail={"error": "OpenRouter is not configured", "missing": missing})
    return values


def model_gateway() -> str:
    gateway = os.getenv("MODEL_GATEWAY", "direct").strip().lower() or "direct"
    if gateway not in {"direct", "litellm"}:
        raise HTTPException(status_code=503, detail={"error": "Model gateway is not configured", "gateway": gateway})
    return gateway


def litellm_config() -> dict[str, str]:
    api_key = normalize_api_key(os.getenv("LITELLM_API_KEY", ""))
    values = {
        "api_key": api_key,
        "base_url": os.getenv("LITELLM_BASE_URL", "http://127.0.0.1:4000").strip(),
        "default_model": os.getenv("LITELLM_DEFAULT_MODEL", "").strip(),
    }
    missing = [
        name
        for name, value in {
            "LITELLM_API_KEY": values["api_key"],
            "LITELLM_BASE_URL": values["base_url"],
            "LITELLM_DEFAULT_MODEL": values["default_model"],
        }.items()
        if not value
    ]
    if missing:
        raise HTTPException(status_code=503, detail={"error": "LiteLLM is not configured", "missing": missing})
    return values


def resolved_temperature(request: ModelRouteRequest) -> float:
    return 0.2 if request.temperature is None else request.temperature


def litellm_should_send_temperature(request: ModelRouteRequest) -> bool:
    if not env_flag("LITELLM_SEND_TEMPERATURE"):
        return False
    return request.temperature is not None


def normalize_api_key(value: str) -> str:
    key = value.strip().strip("\"'")
    if "=" in key and key.split("=", 1)[0].strip() == "OPENROUTER_API_KEY":
        key = key.split("=", 1)[1].strip().strip("\"'")
    if ":" in key and key.split(":", 1)[0].strip().lower() == "authorization":
        key = key.split(":", 1)[1].strip().strip("\"'")
    return key


def bearer_header(api_key: str) -> str:
    if api_key.lower().startswith("bearer "):
        return api_key
    return f"Bearer {api_key}"


def env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def langfuse_config() -> dict[str, str] | None:
    if not env_flag("LANGFUSE_ENABLED"):
        return None

    values = {
        "host": os.getenv("LANGFUSE_HOST", "").strip().rstrip("/"),
        "public_key": os.getenv("LANGFUSE_PUBLIC_KEY", "").strip(),
        "secret_key": os.getenv("LANGFUSE_SECRET_KEY", "").strip(),
        "environment": os.getenv("LANGFUSE_ENVIRONMENT", "homestead-private-os").strip(),
        "release": os.getenv("LANGFUSE_RELEASE", "v0-openrouter-route").strip(),
    }
    if not values["host"] or not values["public_key"] or not values["secret_key"]:
        return None
    return values


def langfuse_usage(usage: Any) -> dict[str, Any] | None:
    if not isinstance(usage, dict):
        return None

    allowed = {
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
        "prompt_tokens_details",
        "completion_tokens_details",
    }
    clean = {key: value for key, value in usage.items() if key in allowed}
    return clean or None


async def send_langfuse_model_route_trace(
    *,
    gateway: str,
    requested_model: str,
    model_used: str | None,
    latency_ms: int,
    ok: bool,
    usage: Any = None,
    error: str | None = None,
    requesting_surface: str | None = None,
    max_tokens: int | None = None,
    temperature: float | None = None,
) -> str | None:
    config = langfuse_config()
    if not config:
        return None

    trace_id = uuid4().hex
    generation_id = uuid4().hex
    now = utc_now()
    metadata = {
        "route": "/model/route",
        "gateway": gateway,
        "requested_model": requested_model,
        "model_used": model_used,
        "latency_ms": latency_ms,
        "ok": ok,
        "environment": config["environment"],
    }
    if error:
        metadata["error"] = error
    if requesting_surface:
        metadata["requesting_surface"] = requesting_surface[:120]

    generation_body: dict[str, Any] = {
        "id": generation_id,
        "traceId": trace_id,
        "name": f"homestead.model_route.{gateway}",
        "startTime": now,
        "endTime": now,
        "model": model_used or requested_model,
        "metadata": metadata,
    }
    model_parameters: dict[str, Any] = {}
    if max_tokens is not None:
        model_parameters["max_tokens"] = max_tokens
    if temperature is not None:
        model_parameters["temperature"] = temperature
    if model_parameters:
        generation_body["modelParameters"] = model_parameters
    clean_usage = langfuse_usage(usage)
    if clean_usage:
        generation_body["usage"] = clean_usage

    payload = {
        "batch": [
            {
                "id": uuid4().hex,
                "type": "trace-create",
                "timestamp": now,
                "body": {
                    "id": trace_id,
                    "name": "homestead.model_route",
                    "release": config["release"],
                    "metadata": metadata,
                    "tags": ["homestead", "model-route", config["environment"]],
                },
            },
            {
                "id": uuid4().hex,
                "type": "generation-create",
                "timestamp": now,
                "body": generation_body,
            },
        ]
    }

    try:
        async with httpx.AsyncClient(timeout=3) as client:
            response = await client.post(
                f"{config['host']}/api/public/ingestion",
                auth=(config["public_key"], config["secret_key"]),
                json=payload,
            )
            response.raise_for_status()
    except Exception:
        return None

    return trace_id


def model_route_receipts_enabled() -> bool:
    return env_flag("MODEL_ROUTE_RECEIPTS_ENABLED")


def model_route_receipts_include_content() -> bool:
    return env_flag("MODEL_ROUTE_RECEIPTS_INCLUDE_CONTENT")


def model_route_run_id() -> str:
    return f"model-route-{uuid4().hex[:12]}"


def receipt_usage(usage: Any) -> Any:
    if not isinstance(usage, dict):
        return usage
    return json.loads(json.dumps(usage))


def model_route_receipt_payload(
    *,
    gateway: str,
    requesting_agent: str,
    requested_model: str,
    model_used: str | None,
    latency_ms: int,
    ok: bool,
    usage: Any = None,
    langfuse_trace_id: str | None = None,
    error_summary: str | None = None,
    prompt: str | None = None,
    content: str | None = None,
    system: str | None = None,
) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "route": "/model/route",
        "gateway": gateway,
        "requested_model": requested_model,
        "model_used": model_used,
        "latency_ms": latency_ms,
        "ok": ok,
    }
    if error_summary:
        metadata["error_summary"] = error_summary
    if usage is not None:
        metadata["usage"] = receipt_usage(usage)
    if langfuse_trace_id:
        metadata["langfuse_trace_id"] = langfuse_trace_id

    if model_route_receipts_include_content():
        metadata["content_capture"] = {
            "prompt": prompt,
            "system": system,
            "response": content,
        }

    route_description = "direct OpenRouter routing" if gateway == "direct" else "optional LiteLLM gateway routing"
    actions_taken = [
        f"called /model/route using {route_description}",
        "recorded model route metadata; prompt/content omitted by default",
    ]
    if langfuse_trace_id:
        actions_taken.append("linked Langfuse trace metadata")

    return {
        "run_id": model_route_run_id(),
        "timestamp": utc_now(),
        "requesting_agent": requesting_agent or "unknown",
        "task": "model_route",
        "files_read": [],
        "model_used": model_used or requested_model,
        "actions_taken": actions_taken,
        "files_changed": [],
        "review_required": not ok,
        "verdict": "ok" if ok else "error",
        "metadata": metadata,
    }


def write_model_route_receipt(payload: dict[str, Any]) -> dict[str, Any]:
    return write_receipt_payload(payload)


def safe_receipt_result(result: dict[str, Any]) -> dict[str, str]:
    return {
        "receipt_id": result["run_id"],
        "receipt_path": result["markdown_path"],
    }


async def record_model_route_receipt(payload: dict[str, Any]) -> dict[str, str] | None:
    if not model_route_receipts_enabled():
        return None
    try:
        return safe_receipt_result(write_model_route_receipt(payload))
    except Exception:
        return {"receipt_error": "receipt write failed"}


def requesting_surface(request: Request) -> str | None:
    return request.headers.get("x-homestead-surface") or request.headers.get("user-agent")


@app.post("/model/route")
async def model_route(request: ModelRouteRequest, http_request: Request) -> dict[str, Any]:
    gateway = model_gateway()
    if gateway == "direct":
        config = openrouter_config()
        model = request.model or config["default_model"]
        headers = {
            "Authorization": bearer_header(config["api_key"]),
            "Content-Type": "application/json",
            "HTTP-Referer": config["http_referer"],
            "X-OpenRouter-Title": config["app_title"],
        }
        url = f"{config['base_url'].rstrip('/')}/chat/completions"
        upstream_name = "OpenRouter"
    else:
        config = litellm_config()
        model = request.model or config["default_model"]
        headers = {
            "Authorization": bearer_header(config["api_key"]),
            "Content-Type": "application/json",
        }
        url = f"{config['base_url'].rstrip('/')}/v1/chat/completions"
        upstream_name = "LiteLLM"

    messages: list[dict[str, str]] = []
    if request.system:
        messages.append({"role": "system", "content": request.system})
    messages.append({"role": "user", "content": request.prompt})

    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": request.max_tokens,
    }
    if gateway == "direct":
        payload["temperature"] = resolved_temperature(request)
    elif litellm_should_send_temperature(request):
        payload["temperature"] = request.temperature
    trace_temperature = payload.get("temperature")

    started = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(url, headers=headers, json=payload)
    except httpx.TimeoutException as exc:
        latency_ms = int((time.perf_counter() - started) * 1000)
        surface = requesting_surface(http_request)
        error_message = f"{upstream_name} request timed out"
        trace_id = await send_langfuse_model_route_trace(
            gateway=gateway,
            requested_model=model,
            model_used=None,
            latency_ms=latency_ms,
            ok=False,
            error=error_message,
            requesting_surface=surface,
            max_tokens=request.max_tokens,
            temperature=trace_temperature,
        )
        await record_model_route_receipt(
            model_route_receipt_payload(
                gateway=gateway,
                requesting_agent=surface or "unknown",
                requested_model=model,
                model_used=None,
                latency_ms=latency_ms,
                ok=False,
                error_summary=error_message,
                langfuse_trace_id=trace_id,
                prompt=request.prompt,
                system=request.system,
            )
        )
        raise HTTPException(status_code=504, detail=error_message) from exc
    except httpx.RequestError as exc:
        latency_ms = int((time.perf_counter() - started) * 1000)
        surface = requesting_surface(http_request)
        error_message = f"{upstream_name} request failed"
        trace_id = await send_langfuse_model_route_trace(
            gateway=gateway,
            requested_model=model,
            model_used=None,
            latency_ms=latency_ms,
            ok=False,
            error=error_message,
            requesting_surface=surface,
            max_tokens=request.max_tokens,
            temperature=trace_temperature,
        )
        await record_model_route_receipt(
            model_route_receipt_payload(
                gateway=gateway,
                requesting_agent=surface or "unknown",
                requested_model=model,
                model_used=None,
                latency_ms=latency_ms,
                ok=False,
                error_summary=error_message,
                langfuse_trace_id=trace_id,
                prompt=request.prompt,
                system=request.system,
            )
        )
        raise HTTPException(status_code=502, detail=error_message) from exc

    if response.status_code >= 400:
        message = f"{upstream_name} returned an error"
        try:
            body = response.json()
            if isinstance(body, dict):
                error = body.get("error")
                if isinstance(error, dict) and isinstance(error.get("message"), str):
                    message = error["message"]
        except ValueError:
            pass
        latency_ms = int((time.perf_counter() - started) * 1000)
        surface = requesting_surface(http_request)
        trace_id = await send_langfuse_model_route_trace(
            gateway=gateway,
            requested_model=model,
            model_used=None,
            latency_ms=latency_ms,
            ok=False,
            error=message,
            requesting_surface=surface,
            max_tokens=request.max_tokens,
            temperature=trace_temperature,
        )
        await record_model_route_receipt(
            model_route_receipt_payload(
                gateway=gateway,
                requesting_agent=surface or "unknown",
                requested_model=model,
                model_used=None,
                latency_ms=latency_ms,
                ok=False,
                error_summary=message,
                langfuse_trace_id=trace_id,
                prompt=request.prompt,
                system=request.system,
            )
        )
        raise HTTPException(status_code=502, detail={"error": message, "upstream_status": response.status_code})

    try:
        data = response.json()
    except ValueError as exc:
        raise HTTPException(status_code=502, detail=f"{upstream_name} returned invalid JSON") from exc

    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        raise HTTPException(status_code=502, detail=f"{upstream_name} returned no choices")
    first = choices[0]
    if not isinstance(first, dict):
        raise HTTPException(status_code=502, detail=f"{upstream_name} returned an invalid choice")
    message = first.get("message")
    content = message.get("content") if isinstance(message, dict) else None
    if not isinstance(content, str):
        raise HTTPException(status_code=502, detail=f"{upstream_name} returned no assistant content")

    model_used = data.get("model") or model
    latency_ms = int((time.perf_counter() - started) * 1000)
    surface = requesting_surface(http_request)
    trace_id = await send_langfuse_model_route_trace(
        gateway=gateway,
        requested_model=model,
        model_used=model_used,
        latency_ms=latency_ms,
        ok=True,
        usage=data.get("usage"),
        requesting_surface=surface,
        max_tokens=request.max_tokens,
        temperature=trace_temperature,
    )

    result = {
        "gateway": gateway,
        "model": model_used,
        "content": content,
        "finish_reason": first.get("finish_reason"),
        "usage": data.get("usage"),
    }
    receipt_result = await record_model_route_receipt(
        model_route_receipt_payload(
            gateway=gateway,
            requesting_agent=surface or "unknown",
            requested_model=model,
            model_used=model_used,
            latency_ms=latency_ms,
            ok=True,
            usage=data.get("usage"),
            langfuse_trace_id=trace_id,
            prompt=request.prompt,
            content=content,
            system=request.system,
        )
    )
    if receipt_result:
        result.update(receipt_result)
    return result


@app.post("/read-concept")
def read_concept(request: ReadConceptRequest) -> dict[str, Any]:
    path = safe_relative_path(request.path.lstrip("/"))
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail=f"file not found: {request.path}")
    if path.suffix.lower() != ".md":
        raise HTTPException(status_code=400, detail="only markdown files are readable in v0")

    text = path.read_text(encoding="utf-8", errors="replace")
    return {
        "path": "/" + path.relative_to(repo_path()).as_posix(),
        "content": text,
    }


@app.post("/receipt/create")
def create_receipt(request: ReceiptRequest) -> dict[str, Any]:
    return write_receipt_payload(request.model_dump())


def write_receipt_payload(payload: dict[str, Any]) -> dict[str, Any]:
    run_id = clean_run_id(payload.get("run_id"))
    timestamp = payload.get("timestamp") or utc_now()
    try:
        date_part = datetime.fromisoformat(timestamp.replace("Z", "+00:00")).date().isoformat()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="timestamp must be ISO 8601") from exc

    base = receipts_dir() / date_part
    base.mkdir(parents=True, exist_ok=True)
    md_path = base / f"{run_id}.md"
    json_path = base / f"{run_id}.json"

    if md_path.exists() or json_path.exists():
        raise HTTPException(status_code=409, detail=f"receipt already exists: {run_id}")

    payload["run_id"] = run_id
    payload["timestamp"] = timestamp

    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(receipt_markdown(payload), encoding="utf-8")

    return {
        "run_id": run_id,
        "timestamp": timestamp,
        "markdown_path": str(md_path),
        "json_path": str(json_path),
    }


def receipt_markdown(payload: dict[str, Any]) -> str:
    def lines(items: list[str]) -> str:
        return "\n".join(f"- {item}" for item in items) if items else "- none"

    metadata = payload.get("metadata") or {}
    metadata_section = ""
    if metadata:
        metadata_section = f"""
## Metadata

```json
{json.dumps(metadata, indent=2, sort_keys=True)}
```
"""

    return f"""# Homestead Receipt: {payload["run_id"]}

| Field | Value |
|---|---|
| run_id | {payload["run_id"]} |
| timestamp | {payload["timestamp"]} |
| requesting_agent | {payload["requesting_agent"]} |
| task | {payload["task"]} |
| model_used | {payload["model_used"]} |
| review_required | {payload["review_required"]} |
| verdict | {payload["verdict"]} |

## Files Read

{lines(payload["files_read"])}

## Actions Taken

{lines(payload["actions_taken"])}

## Files Changed

{lines(payload["files_changed"])}
{metadata_section}"""
