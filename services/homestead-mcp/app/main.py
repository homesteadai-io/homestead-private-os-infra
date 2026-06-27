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

    raise HTTPException(status_code=404, detail=f"unknown tool: {tool}")

