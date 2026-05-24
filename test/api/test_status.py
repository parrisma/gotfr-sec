"""Smoke tests for the bootstrap HTTP API."""


def test_root(client):
    response = client.get("/")

    assert response.status_code == 200
    assert response.json() == {
        "service": "gofr-sec",
        "status": "ok",
        "docs": "/docs",
    }


def test_ping(client):
    response = client.get("/ping")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_status(client):
    response = client.get("/v1/status")

    assert response.status_code == 200
    assert response.json() == {
        "service": "gofr-sec",
        "phase": "bootstrap",
        "proposal": "docs/gofr_sec_proposal.md",
    }