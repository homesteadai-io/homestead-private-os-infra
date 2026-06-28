from __future__ import annotations

import os
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field


app = FastAPI(title="Homestead MCP Facade", version="0.1.0")

TOOLS = [
    {
        "name": "homestead.search_keep",
        "description": "Search markdown files in the configured Keep/repo path.",
        "input_schema": {"query": "string", "max_results": "integer optional"},
    },
    {
        "name": "homestead.read_concept",
        "description": "Read one markdown concept by repo-relative path.",
        "input_schema": {"path": "string"},
    },
    {
        "name": "homestead.build_context_pack",
        "description": "Return relevant markdown paths and snippets for a task.",
        "input_schema": {"task": "string", "max_files": "integer optional"},
    },
    {
        "name": "homestead.repo_status",
        "description": "Return branch, latest commit, and dirty state for the configured repo.",
        "input_schema": {},
    },
    {
        "name": "homestead.create_receipt",
        "description": "Create append-only Markdown and JSON receipts.",
        "input_schema": {
            "task": "string",
            "requesting_agent": "string optional",
            "files_read": "array optional",
            "actions_taken": "array optional",
            "files_changed": "array optional",
            "review_required": "boolean optional",
            "verdict": "string optional",
        },
    },
    {
        "name": "homestead.list_recent_receipts",
        "description": "List recent Homestead receipts as metadata summaries.",
        "input_schema": {"limit": "integer optional"},
    },
    {
        "name": "homestead.read_receipt",
        "description": "Read one Homestead receipt by date and receipt id.",
        "input_schema": {"date": "YYYY-MM-DD string", "receipt_id": "string"},
    },
    {
        "name": "homestead.receipt_stats",
        "description": "Return aggregate counts for Homestead receipts.",
        "input_schema": {},
    },
    {
        "name": "homestead.receipts_review",
        "description": "List receipt summaries that need Adam's attention.",
        "input_schema": {"limit": "integer optional"},
    },
    {
        "name": "homestead.node_status",
        "description": "Return Homestead cloud node health, configuration, and receipt status.",
        "input_schema": {},
    },
    {
        "name": "homestead.os_status",
        "description": "Return Homestead cloud-first OS status.",
        "input_schema": {},
    },
    {
        "name": "homestead.os_context",
        "description": "Return cloud-first Homestead OS context, capabilities, and local-mode readiness.",
        "input_schema": {},
    },
    {
        "name": "homestead.os_capabilities",
        "description": "Return Homestead capability registry with enabled, disabled, and future-only surfaces.",
        "input_schema": {},
    },
    {
        "name": "homestead.sync_keep_health",
        "description": "Write metadata-only Homestead health summaries into The Keep.",
        "input_schema": {"requesting_agent": "string optional", "note": "string optional"},
    },
]


class ToolCall(BaseModel):
    tool: str = Field(..., min_length=1)
    arguments: dict[str, Any] = Field(default_factory=dict)


def api_url() -> str:
    return os.getenv("HOMESTEAD_API_URL", "http://homestead-api:8000").rstrip("/")


async def api_request(method: str, path: str, json_body: dict[str, Any] | None = None) -> Any:
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.request(method, f"{api_url()}{path}", json=json_body)
    if response.status_code >= 400:
        raise HTTPException(status_code=response.status_code, detail=response.text)
    return response.json()


@app.get("/health")
async def health() -> dict[str, Any]:
    upstream = await api_request("GET", "/health")
    return {
        "ok": True,
        "service": "homestead-mcp",
        "upstream": upstream,
    }


@app.get("/tools")
def tools() -> dict[str, Any]:
    return {"tools": TOOLS}


@app.post("/call")
async def call_tool(call: ToolCall) -> dict[str, Any]:
    return {"tool": call.tool, "result": await dispatch(call.tool, call.arguments)}


@app.post("/tools/{tool_name:path}")
async def call_tool_by_path(tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    return {"tool": tool_name, "result": await dispatch(tool_name, arguments)}


async def dispatch(tool: str, arguments: dict[str, Any]) -> Any:
    if tool == "homestead.search_keep":
        return await api_request("POST", "/search", arguments)
    if tool == "homestead.read_concept":
        return await api_request("POST", "/read-concept", arguments)
    if tool == "homestead.build_context_pack":
        return await api_request("POST", "/context-pack", arguments)
    if tool == "homestead.repo_status":
        return await api_request("GET", "/repo/status")
    if tool == "homestead.create_receipt":
        return await api_request("POST", "/receipt/create", arguments)
    if tool == "homestead.list_recent_receipts":
        limit = int(arguments.get("limit", 20))
        return await api_request("GET", f"/receipts/recent?limit={limit}")
    if tool == "homestead.read_receipt":
        date = arguments.get("date")
        receipt_id = arguments.get("receipt_id")
        if not isinstance(date, str) or not isinstance(receipt_id, str):
            raise HTTPException(status_code=400, detail="date and receipt_id are required")
        return await api_request("GET", f"/receipts/{date}/{receipt_id}")
    if tool == "homestead.receipt_stats":
        return await api_request("GET", "/receipts/stats")
    if tool == "homestead.receipts_review":
        limit = int(arguments.get("limit", 20))
        return await api_request("GET", f"/receipts/review?limit={limit}")
    if tool == "homestead.node_status":
        return await api_request("GET", "/node/status")
    if tool == "homestead.os_status":
        return await api_request("GET", "/os/status")
    if tool == "homestead.os_context":
        return await api_request("GET", "/os/context")
    if tool == "homestead.os_capabilities":
        return await api_request("GET", "/os/capabilities")
    if tool == "homestead.sync_keep_health":
        return await api_request("POST", "/keep/health/sync", arguments)

    raise HTTPException(status_code=404, detail=f"unknown tool: {tool}")
