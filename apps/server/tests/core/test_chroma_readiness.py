from __future__ import annotations

import pytest
from server.core.config import Settings


@pytest.fixture
def settings() -> Settings:
    return Settings(chroma_persist_directory="test-chroma")


def test_ready_checks_cached_chroma_client_heartbeat(client, monkeypatch):
    class CachedClient:
        fail = False

        def heartbeat(self):
            if self.fail:
                raise RuntimeError("private sentinel credential detail")
            return 1

    chroma_client = CachedClient()
    import server.main as main

    monkeypatch.setattr(main, "get_chroma_client", lambda: chroma_client)

    healthy = client.get("/ready").json()
    assert healthy["checks"]["chroma"]["ready"] is True

    chroma_client.fail = True
    failed_response = client.get("/ready")
    failed = failed_response.json()
    assert failed["status"] == "not_ready"
    assert failed["checks"]["chroma"] == {
        "configured": True,
        "ready": False,
        "detail": "Chroma heartbeat failed",
    }
    assert "private sentinel credential detail" not in failed_response.text
