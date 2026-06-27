from __future__ import annotations

from fastapi.testclient import TestClient

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

