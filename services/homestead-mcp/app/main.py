from __future__ import annotations

import os
import re
from typing import Any
from urllib.parse import quote

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field


app = FastAPI(title="Homestead MCP Facade", version="0.1.0")
PROJECT_ID_RE = re.compile(r"[a-z0-9][a-z0-9-]*")
COMMAND_ID_RE = re.compile(r"cmd-[a-f0-9]{8}")
SESSION_ID_RE = re.compile(r"session-[a-f0-9]{8}")
OUTPUT_ID_RE = re.compile(r"[a-z0-9][a-z0-9-]*--\d{4}-\d{2}-\d{2}-[a-z0-9][a-z0-9-]*")

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
        "name": "homestead.agent_boot",
        "description": "Return the standard Homestead agent boot orientation and current operating context.",
        "input_schema": {},
    },
    {
        "name": "homestead.projects",
        "description": "List config-backed Homestead project summaries.",
        "input_schema": {},
    },
    {
        "name": "homestead.project_context",
        "description": "Return one Homestead project context by project id.",
        "input_schema": {"project_id": "string"},
    },
    {
        "name": "homestead.commands_create",
        "description": "Create a manual Adam-commanded work command.",
        "input_schema": {"title": "string", "description": "string optional", "project_id": "string optional"},
    },
    {
        "name": "homestead.commands_list",
        "description": "List manual Homestead commands.",
        "input_schema": {},
    },
    {
        "name": "homestead.commands_read",
        "description": "Read one manual Homestead command.",
        "input_schema": {"command_id": "string"},
    },
    {
        "name": "homestead.commands_update",
        "description": "Update one manual Homestead command.",
        "input_schema": {"command_id": "string", "status": "string optional", "session_id": "string optional"},
    },
    {
        "name": "homestead.session_start",
        "description": "Start a manual agent work session.",
        "input_schema": {"agent": "string", "command_id": "string optional", "project_id": "string optional"},
    },
    {
        "name": "homestead.session_end",
        "description": "End a manual agent work session.",
        "input_schema": {"session_id": "string", "outcome": "string optional"},
    },
    {
        "name": "homestead.sessions",
        "description": "List manual Homestead agent sessions.",
        "input_schema": {},
    },
    {
        "name": "homestead.session_read",
        "description": "Read one manual Homestead agent session.",
        "input_schema": {"session_id": "string"},
    },
    {
        "name": "homestead.outputs_write",
        "description": "Write a durable Homestead output capsule bundle.",
        "input_schema": {
            "title": "string",
            "summary": "string",
            "project_id": "string optional",
            "slug": "string optional",
            "command_id": "string optional",
            "session_id": "string optional",
            "created_by": "string optional",
            "handoff": "string optional",
            "capsule": "string optional",
            "next_ai_prompt": "string optional",
            "okf": "object optional",
            "pam": "object optional",
        },
    },
    {
        "name": "homestead.outputs_list",
        "description": "List durable Homestead output capsule summaries.",
        "input_schema": {},
    },
    {
        "name": "homestead.outputs_read",
        "description": "Read one durable Homestead output capsule bundle.",
        "input_schema": {"output_id": "string"},
    },
    {
        "name": "homestead.ops_policy",
        "description": "Return the manual ops policy gate configuration.",
        "input_schema": {},
    },
    {
        "name": "homestead.check_ops_policy",
        "description": "Check whether a requesting surface may run a manual action or system probe.",
        "input_schema": {
            "operation_type": "action or probe string",
            "operation": "string",
            "requesting_agent": "string optional",
            "surface": "string optional",
        },
    },
    {
        "name": "homestead.list_manual_ops",
        "description": "List manual-only Homestead actions and system probes.",
        "input_schema": {},
    },
    {
        "name": "homestead.run_manual_action",
        "description": "Run one explicit receipt-backed manual Homestead action.",
        "input_schema": {"action": "string", "requesting_agent": "string optional", "note": "string optional"},
    },
    {
        "name": "homestead.run_system_probe",
        "description": "Run one explicit receipt-backed Homestead system probe.",
        "input_schema": {
            "probe": "string optional",
            "requesting_agent": "string optional",
            "note": "string optional",
            "max_tokens": "integer optional",
        },
    },
    {
        "name": "homestead.list_recent_ops",
        "description": "List recent manual ops and system probe receipts.",
        "input_schema": {"limit": "integer optional"},
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


def require_command_id(arguments: dict[str, Any]) -> str:
    command_id = arguments.get("command_id")
    if not isinstance(command_id, str) or not command_id:
        raise HTTPException(status_code=400, detail="command_id is required")
    normalized = command_id.strip().lower()
    if not COMMAND_ID_RE.fullmatch(normalized):
        raise HTTPException(status_code=400, detail="command_id contains unsupported characters")
    return normalized


def require_session_id(arguments: dict[str, Any]) -> str:
    session_id = arguments.get("session_id")
    if not isinstance(session_id, str) or not session_id:
        raise HTTPException(status_code=400, detail="session_id is required")
    normalized = session_id.strip().lower()
    if not SESSION_ID_RE.fullmatch(normalized):
        raise HTTPException(status_code=400, detail="session_id contains unsupported characters")
    return normalized


def require_output_id(arguments: dict[str, Any]) -> str:
    output_id = arguments.get("output_id")
    if not isinstance(output_id, str) or not output_id:
        raise HTTPException(status_code=400, detail="output_id is required")
    normalized = output_id.strip().lower()
    if not OUTPUT_ID_RE.fullmatch(normalized):
        raise HTTPException(status_code=400, detail="output_id contains unsupported characters")
    return normalized


async def api_request(method: str, path: str, json_body: dict[str, Any] | None = None) -> Any:
    headers = {"x-homestead-surface": "mcp"}
    policy_token = os.getenv("HOMESTEAD_MCP_POLICY_TOKEN", "").strip()
    if policy_token:
        headers["x-homestead-policy-token"] = policy_token
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.request(
            method,
            f"{api_url()}{path}",
            json=json_body,
            headers=headers,
        )
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
    if tool == "homestead.agent_boot":
        return await api_request("GET", "/agent/boot")
    if tool == "homestead.projects":
        return await api_request("GET", "/os/projects")
    if tool == "homestead.project_context":
        project_id = arguments.get("project_id")
        if not isinstance(project_id, str) or not project_id:
            raise HTTPException(status_code=400, detail="project_id is required")
        normalized_project_id = project_id.strip().lower()
        if not PROJECT_ID_RE.fullmatch(normalized_project_id):
            raise HTTPException(status_code=400, detail="project_id must be a slug")
        return await api_request("GET", f"/os/projects/{quote(normalized_project_id, safe='')}")
    if tool == "homestead.commands_create":
        return await api_request("POST", "/commands", arguments)
    if tool == "homestead.commands_list":
        return await api_request("GET", "/commands")
    if tool == "homestead.commands_read":
        command_id = require_command_id(arguments)
        return await api_request("GET", f"/commands/{quote(command_id, safe='')}")
    if tool == "homestead.commands_update":
        command_id = require_command_id(arguments)
        payload = {key: value for key, value in arguments.items() if key != "command_id"}
        return await api_request("PATCH", f"/commands/{quote(command_id, safe='')}", payload)
    if tool == "homestead.session_start":
        return await api_request("POST", "/agent/sessions/start", arguments)
    if tool == "homestead.session_end":
        return await api_request("POST", "/agent/sessions/end", arguments)
    if tool == "homestead.sessions":
        return await api_request("GET", "/agent/sessions")
    if tool == "homestead.session_read":
        session_id = require_session_id(arguments)
        return await api_request("GET", f"/agent/sessions/{quote(session_id, safe='')}")
    if tool == "homestead.outputs_write":
        return await api_request("POST", "/outputs", arguments)
    if tool == "homestead.outputs_list":
        return await api_request("GET", "/outputs")
    if tool == "homestead.outputs_read":
        output_id = require_output_id(arguments)
        return await api_request("GET", f"/outputs/{quote(output_id, safe='')}")
    if tool == "homestead.ops_policy":
        return await api_request("GET", "/ops/policy")
    if tool == "homestead.check_ops_policy":
        return await api_request("POST", "/ops/policy/check", arguments)
    if tool == "homestead.list_manual_ops":
        return await api_request("GET", "/ops/actions")
    if tool == "homestead.run_manual_action":
        return await api_request("POST", "/ops/actions/run", arguments)
    if tool == "homestead.run_system_probe":
        return await api_request("POST", "/ops/probes/run", arguments)
    if tool == "homestead.list_recent_ops":
        limit = int(arguments.get("limit", 20))
        return await api_request("GET", f"/ops/recent?limit={limit}")
    if tool == "homestead.sync_keep_health":
        payload = {"action": "sync_keep_health", **arguments}
        return await api_request("POST", "/ops/actions/run", payload)

    raise HTTPException(status_code=404, detail=f"unknown tool: {tool}")
