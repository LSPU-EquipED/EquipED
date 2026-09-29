"""Resolve which LoRA adapter each agent should use on the model server.

The server exposes loaded adapters by numeric id (load order). Files are named
``<agent>-v<version>.gguf`` so a loaded adapter can be matched back to a
``TrainedAdapter`` row without any hand-entered ids.
"""

from __future__ import annotations

import re
import threading
import time
import uuid
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import PureWindowsPath

from server.core.exceptions import InfrastructureUnavailableError
from server.core.llm import fetch_lora_adapters
from server.modules.training_data.models import (
    AgentAdapterPublication,
    TrainedAdapter,
)
from sqlalchemy.orm import Session

_NAME_RE = re.compile(r"^(?P<agent>[a-z]+)-v(?P<version>\d+)\.gguf$")


def gguf_filename(agent_id: str, version: int) -> str:
    return f"{agent_id}-v{version}.gguf"


def parse_gguf_filename(path: str) -> tuple[str, int] | None:
    # PureWindowsPath understands both "\" and "/" separators.
    name = PureWindowsPath(path).name.lower()
    match = _NAME_RE.match(name)
    if match is None:
        return None
    return match.group("agent"), int(match.group("version"))


@dataclass(frozen=True)
class LoadedAdapter:
    server_id: int
    agent_id: str
    version: int


@dataclass(frozen=True)
class ServerAdapterState:
    reachable: bool
    loaded: tuple[LoadedAdapter, ...]
    server_ids: tuple[int, ...]
    unrecognized: tuple[str, ...]

    def find(self, agent_id: str, version: int) -> LoadedAdapter | None:
        for item in self.loaded:
            if item.agent_id == agent_id and item.version == version:
                return item
        return None


_UNREACHABLE = ServerAdapterState(False, (), (), ())
_cache_lock = threading.Lock()
_cache: tuple[float, ServerAdapterState] | None = None


def clear_server_adapter_cache() -> None:
    global _cache
    with _cache_lock:
        _cache = None


def _read_state() -> ServerAdapterState:
    try:
        entries = fetch_lora_adapters()
    except InfrastructureUnavailableError:
        return _UNREACHABLE
    parsed: list[tuple[int, str, tuple[str, int] | None]] = []
    for entry in entries:
        path = str(entry.get("path", ""))
        parsed.append((int(entry["id"]), path, parse_gguf_filename(path)))
    counts: dict[tuple[str, int], int] = {}
    for _, _, key in parsed:
        if key is not None:
            counts[key] = counts.get(key, 0) + 1
    loaded: list[LoadedAdapter] = []
    unrecognized: list[str] = []
    for server_id, path, key in parsed:
        if key is None or counts[key] > 1:
            unrecognized.append(PureWindowsPath(path).name or path)
        else:
            loaded.append(LoadedAdapter(server_id, key[0], key[1]))
    return ServerAdapterState(
        True,
        tuple(loaded),
        tuple(server_id for server_id, _, _ in parsed),
        tuple(unrecognized),
    )


def get_server_adapter_state(*, ttl_seconds: float = 30.0) -> ServerAdapterState:
    """Loaded-adapter state, cached briefly. Never raises."""
    global _cache
    now = time.monotonic()
    with _cache_lock:
        if _cache is not None and now - _cache[0] < ttl_seconds:
            return _cache[1]
    state = _read_state()
    with _cache_lock:
        _cache = (now, state)
    return state


@dataclass(frozen=True)
class AdapterPlan:
    agent_id: str
    requested: str
    applied: str | None
    reason: str | None
    lora: tuple[dict, ...] | None

    def record(self) -> dict:
        return {
            "requested": self.requested,
            "applied": self.applied,
            "reason": self.reason,
        }


def _label(adapter: TrainedAdapter | None, agent_id: str) -> str:
    return "base" if adapter is None else f"{agent_id}-v{adapter.version}"


def _resolve_target(
    session: Session,
    agent_id: str,
    adapter_request: Mapping[str, Mapping] | None,
) -> TrainedAdapter | None:
    if adapter_request is not None and agent_id in adapter_request:
        raw = adapter_request[agent_id].get("adapter_id")
        if raw is None:
            return None
        return session.get(TrainedAdapter, uuid.UUID(str(raw)))
    published = session.get(AgentAdapterPublication, agent_id)
    if published is None:
        return None
    return session.get(TrainedAdapter, published.adapter_id)


def _plan_for(
    agent_id: str, target: TrainedAdapter | None, state: ServerAdapterState
) -> AdapterPlan:
    requested = _label(target, agent_id)
    if not state.reachable:
        return AdapterPlan(
            agent_id,
            requested,
            None,
            "server_unreachable" if target is not None else None,
            None,
        )
    loaded = state.find(agent_id, target.version) if target is not None else None
    if not state.server_ids:
        return AdapterPlan(
            agent_id, requested, None, "not_loaded" if target else None, None
        )
    chosen_id = loaded.server_id if loaded is not None else None
    lora = tuple(
        {"id": sid, "scale": 1.0 if sid == chosen_id else 0.0}
        for sid in state.server_ids
    )
    reason = "not_loaded" if target is not None and loaded is None else None
    return AdapterPlan(
        agent_id, requested, requested if loaded is not None else None, reason, lora
    )


def build_adapter_plans(
    session: Session,
    agent_ids: Iterable[str],
    adapter_request: Mapping[str, Mapping] | None,
    state: ServerAdapterState | None = None,
) -> dict[str, AdapterPlan]:
    """One plan per agent: explicit request first, else published, else base."""
    state = state if state is not None else get_server_adapter_state()
    plans: dict[str, AdapterPlan] = {}
    for agent_id in agent_ids:
        target = _resolve_target(session, agent_id, adapter_request)
        plans[agent_id] = _plan_for(agent_id, target, state)
    return plans


__all__ = [
    "AdapterPlan",
    "LoadedAdapter",
    "ServerAdapterState",
    "build_adapter_plans",
    "clear_server_adapter_cache",
    "get_server_adapter_state",
    "gguf_filename",
    "parse_gguf_filename",
]
