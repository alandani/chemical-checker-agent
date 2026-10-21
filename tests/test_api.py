import json
import time

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    from api.main import app

    with TestClient(app) as c:
        yield c


def _wait_done(client, run_id: str, timeout: float = 30) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        state = client.get(f"/api/runs/{run_id}").json()
        if state["status"] in ("done", "needs_input"):
            return state
        time.sleep(0.1)
    raise AssertionError("run did not finish")


def test_health(client):
    body = client.get("/api/health").json()
    assert body["ok"] and "regions" in body


def test_resolve_local_name(client):
    body = client.post("/api/resolve", json={"raw_input": "Topiramate"}).json()
    assert body["compound"]["cas"] == "97240-79-4"
    assert body["compound"]["label"] == "Topiramate"


def test_molecule_svg(client):
    r = client.get("/api/svg/molecule", params={"smiles": "CCO", "theme": "dark"})
    assert r.status_code == 200 and r.text.startswith("<svg")
    assert client.get("/api/svg/molecule", params={"smiles": "not smiles"}).status_code == 422


def test_run_lifecycle_with_events_and_recost(client):
    compound = client.post("/api/resolve", json={"raw_input": "Topiramate"}).json()["compound"]
    query = {"raw_input": "Topiramate", "quantity": 10, "budget": 500, "compare_synthesis": True}
    run_id = client.post("/api/runs", json={"query": query, "compound": compound}).json()["run_id"]

    with client.stream("GET", f"/api/runs/{run_id}/events") as r:
        text = "".join(r.iter_text())
    assert "event: stage" in text and "event: done" in text
    done = json.loads(text.split("event: done\ndata: ")[1].split("\n\n")[0])
    assert done["cost"]["cheapest"] == "make"
    assert done["route"]["steps"][0]["yield"] == 0.55  # alias used in the API
    assert done["materials"][0]["priced"] is True

    state = _wait_done(client, run_id)
    before = state["cost"]["make_total_aud"]
    after = client.post(f"/api/runs/{run_id}/recost", json={"consumables_margin": 0.5}).json()
    assert after["cost"]["make_total_aud"] > before

    assert any(r["run_id"] == run_id for r in client.get("/api/runs").json())
    assert client.get(f"/api/runs/{run_id}/export/offers.csv").text.startswith("Vendor,")
    assert "<html" in client.get(f"/api/runs/{run_id}/export/report.html").text


def test_admin_overview(client):
    body = client.get("/api/admin/overview").json()
    assert len(body["vendors"]) == 11 and body["stats"]["reactions"] >= 3
