from __future__ import annotations

import pytest
from server.modules.training_data import serving
from server.modules.training_data.models import AgentAdapterPublication
from server.modules.training_data.serving import (
    LoadedAdapter,
    ServerAdapterState,
    build_adapter_plans,
    get_server_adapter_state,
    gguf_filename,
    parse_gguf_filename,
)
from server.tests.training_data.conftest import make_adapter


def _state(*loaded, unrecognized=(), reachable=True):
    return ServerAdapterState(
        reachable=reachable,
        loaded=tuple(loaded),
        server_ids=tuple(item.server_id for item in loaded),
        unrecognized=tuple(unrecognized),
    )


def test_filename_roundtrip_and_windows_paths():
    assert gguf_filename("sme", 3) == "sme-v3.gguf"
    assert parse_gguf_filename("sme-v3.gguf") == ("sme", 3)
    assert parse_gguf_filename("F:\\Dev\\Models\\gemma\\sme-v3.gguf") == ("sme", 3)
    assert parse_gguf_filename("/models/GAD-V12.GGUF") == ("gad", 12)


@pytest.mark.parametrize(
    "path", ["sme.gguf", "sme-v3-final.gguf", "sme-v3.bin", "-v3.gguf", "sme-vx.gguf"]
)
def test_unparseable_names(path):
    assert parse_gguf_filename(path) is None


def test_state_marks_ambiguous_and_unknown_files_unrecognized(monkeypatch):
    serving.clear_server_adapter_cache()
    monkeypatch.setattr(
        serving,
        "fetch_lora_adapters",
        lambda: [
            {"id": 0, "path": "sme-v1.gguf", "scale": 0.0},
            {"id": 1, "path": "gad-v1.gguf", "scale": 0.0},
            {"id": 2, "path": "gad-v1.gguf", "scale": 0.0},  # duplicate
            {"id": 3, "path": "mystery.gguf", "scale": 0.0},
        ],
    )
    state = get_server_adapter_state(ttl_seconds=0)
    assert state.reachable
    assert state.server_ids == (0, 1, 2, 3)
    assert state.find("sme", 1) == LoadedAdapter(0, "sme", 1)
    assert state.find("gad", 1) is None
    assert sorted(state.unrecognized) == ["gad-v1.gguf", "gad-v1.gguf", "mystery.gguf"]


def test_state_unreachable_never_raises(monkeypatch):
    from server.core.exceptions import InfrastructureUnavailableError

    serving.clear_server_adapter_cache()

    def boom():
        raise InfrastructureUnavailableError("down")

    monkeypatch.setattr(serving, "fetch_lora_adapters", boom)
    state = get_server_adapter_state(ttl_seconds=0)
    assert state.reachable is False and state.loaded == ()


def test_state_is_cached_within_ttl(monkeypatch):
    serving.clear_server_adapter_cache()
    calls = []

    def fake():
        calls.append(1)
        return []

    monkeypatch.setattr(serving, "fetch_lora_adapters", fake)
    get_server_adapter_state(ttl_seconds=60)
    get_server_adapter_state(ttl_seconds=60)
    assert len(calls) == 1


def test_published_adapter_loaded_gets_scale_one_others_zero(db_session, admin_user):
    a1 = make_adapter(db_session, "sme", 1)
    a2 = make_adapter(db_session, "sme", 2)
    db_session.add(
        AgentAdapterPublication(
            agent_id="sme", adapter_id=a2.adapter_id, published_by=admin_user.user_id
        )
    )
    db_session.commit()
    state = _state(
        LoadedAdapter(0, "sme", 1),
        LoadedAdapter(1, "sme", 2),
        LoadedAdapter(2, "gad", 1),
    )
    plans = build_adapter_plans(db_session, ["sme", "gad"], None, state)
    assert plans["sme"].requested == "sme-v2"
    assert plans["sme"].applied == "sme-v2"
    assert plans["sme"].lora == (
        {"id": 0, "scale": 0.0},
        {"id": 1, "scale": 1.0},
        {"id": 2, "scale": 0.0},
    )
    # gad has nothing published: base, every loaded id explicitly off
    assert plans["gad"].requested == "base" and plans["gad"].applied is None
    assert plans["gad"].lora == (
        {"id": 0, "scale": 0.0},
        {"id": 1, "scale": 0.0},
        {"id": 2, "scale": 0.0},
    )
    assert a1.adapter_id != a2.adapter_id


def test_explicit_base_beats_published(db_session, admin_user):
    a1 = make_adapter(db_session, "sme", 1)
    db_session.add(
        AgentAdapterPublication(
            agent_id="sme", adapter_id=a1.adapter_id, published_by=admin_user.user_id
        )
    )
    db_session.commit()
    state = _state(LoadedAdapter(0, "sme", 1))
    plans = build_adapter_plans(
        db_session, ["sme"], {"sme": {"adapter_id": None}}, state
    )
    assert plans["sme"].requested == "base"
    assert plans["sme"].lora == ({"id": 0, "scale": 0.0},)


def test_explicit_version_overrides_published(db_session, admin_user):
    a1 = make_adapter(db_session, "sme", 1)
    a2 = make_adapter(db_session, "sme", 2)
    db_session.add(
        AgentAdapterPublication(
            agent_id="sme", adapter_id=a2.adapter_id, published_by=admin_user.user_id
        )
    )
    db_session.commit()
    state = _state(LoadedAdapter(0, "sme", 1), LoadedAdapter(1, "sme", 2))
    plans = build_adapter_plans(
        db_session, ["sme"], {"sme": {"adapter_id": str(a1.adapter_id)}}, state
    )
    assert plans["sme"].requested == "sme-v1"
    assert plans["sme"].lora == ({"id": 0, "scale": 1.0}, {"id": 1, "scale": 0.0})


def test_requested_adapter_not_loaded_falls_back_to_base(db_session, admin_user):
    a3 = make_adapter(db_session, "sme", 3)
    db_session.add(
        AgentAdapterPublication(
            agent_id="sme", adapter_id=a3.adapter_id, published_by=admin_user.user_id
        )
    )
    db_session.commit()
    # Another adapter is loaded, but not v3.
    state = _state(LoadedAdapter(0, "sme", 1))
    plan = build_adapter_plans(db_session, ["sme"], None, state)["sme"]
    assert plan.requested == "sme-v3" and plan.applied is None
    assert plan.reason == "not_loaded"
    assert plan.lora == ({"id": 0, "scale": 0.0},)
    assert plan.record() == {
        "requested": "sme-v3",
        "applied": None,
        "reason": "not_loaded",
    }


def test_no_adapters_loaded_sends_no_lora_field(db_session, admin_user):
    a1 = make_adapter(db_session, "sme", 1)
    db_session.add(
        AgentAdapterPublication(
            agent_id="sme", adapter_id=a1.adapter_id, published_by=admin_user.user_id
        )
    )
    db_session.commit()
    plan = build_adapter_plans(db_session, ["sme"], None, _state())["sme"]
    assert plan.lora is None and plan.reason == "not_loaded"


def test_unreachable_server_falls_back_with_reason(db_session, admin_user):
    a1 = make_adapter(db_session, "sme", 1)
    db_session.add(
        AgentAdapterPublication(
            agent_id="sme", adapter_id=a1.adapter_id, published_by=admin_user.user_id
        )
    )
    db_session.commit()
    plan = build_adapter_plans(db_session, ["sme"], None, _state(reachable=False))[
        "sme"
    ]
    assert plan.applied is None and plan.reason == "server_unreachable"
    assert plan.lora is None
