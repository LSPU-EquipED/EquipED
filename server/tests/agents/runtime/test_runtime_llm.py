from server.modules.agents.runtime import llm


class Client:
    model = "primary"

    def generate(self, prompt, *, temperature, max_new_tokens):
        raise RuntimeError("HTTP 503")


class Fallback:
    model = "fallback"

    def __init__(self):
        self.calls = []

    def generate(self, prompt, *, temperature, max_new_tokens):
        self.calls.append((prompt, temperature, max_new_tokens))
        return "ok"


def test_adapter_fallback_forwards_tokens_and_tracks_state(monkeypatch):
    fallback = Fallback()
    monkeypatch.setattr(llm, "get_llm_client", lambda: fallback)
    settings = type("S", (), {"llm_temperature": 0.2, "llm_max_new_tokens": 99})()
    monkeypatch.setattr(llm, "get_settings", lambda: settings)
    adapter = llm.FallbackAwareClient(Client(), "itso")
    assert adapter.generate("p", temperature=.7, max_new_tokens=123) == "ok"
    assert fallback.calls == [("p", .7, 123)]
    assert adapter.requested_model == "primary"
    assert adapter.actual_model == "fallback"
    assert adapter.fallback_occurred is True


def test_adapter_fallback_state_accumulates(monkeypatch):
    calls = iter([("one", "fallback"), ("two", "primary")])
    monkeypatch.setattr(llm, "call_llm", lambda *a, **k: next(calls))
    adapter = llm.FallbackAwareClient(Client(), "itso")
    adapter.generate("p", temperature=0, max_new_tokens=1)
    adapter.generate("p", temperature=0, max_new_tokens=1)
    assert adapter.actual_model == "primary"
    assert adapter.fallback_occurred is True


def test_adapter_explicit_requested_model_without_primary_model(monkeypatch):
    class ModelLessClient:
        def generate(self, prompt, *, temperature, max_new_tokens):
            return "unused"

    monkeypatch.setattr(llm, "call_llm", lambda *a, **k: ("ok", "fallback"))
    adapter = llm.FallbackAwareClient(
        ModelLessClient(), "itso", requested_model="requested"
    )
    assert adapter.requested_model == "requested"
    assert adapter.actual_model == "requested"
    assert adapter.model == "requested"
    adapter.generate("p", temperature=0, max_new_tokens=1)
    assert adapter.actual_model == "fallback"
    assert adapter.model == "fallback"
    assert adapter.fallback_occurred is True
