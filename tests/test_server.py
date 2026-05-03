"""Smoke tests for codagent.server.

Exhaustive Phase 2 coverage lives in ``test_server_runs.py``. This file
keeps the lightweight smoke checks (healthz, basic POST /v1/runs shape,
JSON validation).
"""

from __future__ import annotations

import pytest

pytest.importorskip("starlette")

from codagent.server import create_app


async def _yield_two(_body):
    for tok in ["hello", "world"]:
        yield tok


def test_post_runs_returns_run_id_and_queued_status():
    from starlette.testclient import TestClient

    client = TestClient(create_app(llm_call=_yield_two))
    resp = client.post("/v1/runs", json={"prompt": "x"})
    assert resp.status_code == 201
    body = resp.json()
    assert "run_id" in body
    assert body["status"] in ("queued", "running")


def test_post_runs_rejects_non_json():
    from starlette.testclient import TestClient

    client = TestClient(create_app(llm_call=_yield_two))
    resp = client.post(
        "/v1/runs",
        content="not json",
        headers={"content-type": "text/plain"},
    )
    assert resp.status_code == 400


def test_post_runs_rejects_non_object_json():
    from starlette.testclient import TestClient

    client = TestClient(create_app(llm_call=_yield_two))
    resp = client.post("/v1/runs", json=[1, 2, 3])
    assert resp.status_code == 400


def test_get_run_returns_404_for_unknown():
    from starlette.testclient import TestClient

    client = TestClient(create_app(llm_call=_yield_two))
    resp = client.get("/v1/runs/does-not-exist")
    assert resp.status_code == 404


def test_healthz():
    from starlette.testclient import TestClient

    client = TestClient(create_app(llm_call=_yield_two))
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
