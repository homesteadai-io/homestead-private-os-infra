from __future__ import annotations

import json
import os
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx
from fastapi import FastAPI, HTTPException
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


class ModelRouteRequest(BaseModel):
    prompt: str = Field(..., min_length=1)
    system: str | None = None
    model: str | None = None
    max_tokens: int = Field(default=256, ge=1, le=4096)
    temperature: float = Field(default=0.2, ge=0, le=2)


def clean_run_id(value: str | None) -> str:
    raw = value or f"run-{uuid4().hex[:12]}"
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", raw).strip("-._")
    return cleaned or f"run-{uuid4().hex[:12]}"


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "ok": True,
        "service": "homestead-api",
        "version": "0.1.0",
        "repo_path": str(repo_path()),
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


@app.post("/model/route")
async def model_route(request: ModelRouteRequest) -> dict[str, Any]:
    config = openrouter_config()
    model = request.model or config["default_model"]
    messages: list[dict[str, str]] = []
    if request.system:
        messages.append({"role": "system", "content": request.system})
    messages.append({"role": "user", "content": request.prompt})

    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": request.max_tokens,
        "temperature": request.temperature,
    }
    headers = {
        "Authorization": bearer_header(config["api_key"]),
        "Content-Type": "application/json",
        "HTTP-Referer": config["http_referer"],
        "X-OpenRouter-Title": config["app_title"],
    }
    url = f"{config['base_url'].rstrip('/')}/chat/completions"

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(url, headers=headers, json=payload)
    except httpx.TimeoutException as exc:
        raise HTTPException(status_code=504, detail="OpenRouter request timed out") from exc
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail="OpenRouter request failed") from exc

    if response.status_code >= 400:
        message = "OpenRouter returned an error"
        try:
            body = response.json()
            if isinstance(body, dict):
                error = body.get("error")
                if isinstance(error, dict) and isinstance(error.get("message"), str):
                    message = error["message"]
        except ValueError:
            pass
        raise HTTPException(status_code=502, detail={"error": message, "upstream_status": response.status_code})

    try:
        data = response.json()
    except ValueError as exc:
        raise HTTPException(status_code=502, detail="OpenRouter returned invalid JSON") from exc

    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        raise HTTPException(status_code=502, detail="OpenRouter returned no choices")
    first = choices[0]
    if not isinstance(first, dict):
        raise HTTPException(status_code=502, detail="OpenRouter returned an invalid choice")
    message = first.get("message")
    content = message.get("content") if isinstance(message, dict) else None
    if not isinstance(content, str):
        raise HTTPException(status_code=502, detail="OpenRouter returned no assistant content")

    return {
        "model": data.get("model") or model,
        "content": content,
        "finish_reason": first.get("finish_reason"),
        "usage": data.get("usage"),
    }


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
    run_id = clean_run_id(request.run_id)
    timestamp = request.timestamp or utc_now()
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

    payload = request.model_dump()
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
"""
