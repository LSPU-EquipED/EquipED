"""Environment-backed settings for the server core layer."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from .exceptions import ConfigurationError


def _env(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name)
    return default if value is None or value == "" else value


def _bool_env(name: str, default: bool = False) -> bool:
    value = _env(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _csv_env(name: str) -> tuple[str, ...]:
    value = _env(name)
    if not value:
        return ()
    return tuple(part.strip() for part in value.split(",") if part.strip())


# Repo root is three levels up from this file (server/core/config.py).
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _resolve_chroma_path(value: str) -> str:
    """Resolve chroma_persist_directory against repo root if relative.

    Absolute paths are preserved as-is.
    Relative paths (including the default "chroma_data") resolve against
    the repository root so they never accidentally land under server/.
    """
    p = Path(value)
    if p.is_absolute():
        return str(p)
    return str(_REPO_ROOT / p)


@dataclass(frozen=True, slots=True)
class Settings:
    app_name: str = "EquipEd"
    app_version: str = "0.1.0"
    environment: str = "development"
    api_prefix: str = "/api/v1"
    cors_origins: tuple[str, ...] = ()
    cors_allow_credentials: bool = True

    database_url: str | None = None
    database_echo: bool = False

    session_cookie_name: str = "equiped_session"
    session_ttl_hours: int = 24
    bootstrap_admin_email: str | None = None
    bootstrap_admin_name: str | None = None
    bootstrap_admin_password: str | None = None

    chroma_persist_directory: str = _resolve_chroma_path("chroma_data")
    chroma_host: str | None = None
    chroma_port: int | None = None
    chroma_ssl: bool = False

    llm_provider: str = "local"
    llm_model_name: str = "google/gemma-2-2b-it"
    llm_api_base: str | None = None
    llm_api_key: str | None = None
    llm_temperature: float = 0.2
    # Default raised from 2048 to 4096 to give larger SLM evaluation outputs
    # more headroom and reduce the chance of JSON truncation in agent responses.
    # Fits comfortably within typical 8K-context local models (e.g. Gemma-2-2B)
    # alongside the bounded prompt payload.
    llm_max_new_tokens: int = 4096
    llm_agent_delay_seconds: int = 0
    llm_request_timeout_seconds: int = 120
    agent_debug_rubric_context: bool = False

    # Per-agent delay overrides (JSON dict, e.g. {"itso": 20, "gad": 5}).
    # Falls back to llm_agent_delay_seconds for any agent not listed.
    llm_agent_delay_per_agent: dict[str, int] = field(default_factory=dict)

    embedding_model_name: str = "paraphrase-multilingual-MiniLM-L12-v2"

    # Per-agent prompt packing caps (Phase 1, deterministic)
    agent_max_chunks: int = 12
    agent_max_excerpt_chars: int = 800
    agent_prompt_budget_chars: int = 5000
    agent_small_doc_threshold: int = 6

    # Total assembled-prompt budget (cap on the serialized JSON sent to the
    # LLM). Independent of agent_prompt_budget_chars, which only caps the
    # document_chunks payload. This safety net prevents the final prompt —
    # including rubric_context, reference_context, and instructions — from
    # exceeding remote provider request limits.
    #
    # Note: Groq's free tier enforces a 6,000 tokens-per-minute (TPM) cap
    # for ``llama-3.1-8b-instant``. With ``llm_max_new_tokens=4096``
    # reserved for output, the input must stay under ~1,900 tokens
    # (~7,600 chars) to avoid HTTP 413 (TPM-exceeded) failures. The 8,000
    # default (~2,000 tokens) gives a safe margin; operators on paid tiers
    # or local models can raise it via AGENT_TOTAL_PROMPT_BUDGET_CHARS.
    agent_total_prompt_budget_chars: int = 8000

    @property
    def database_configured(self) -> bool:
        return bool(self.database_url)

    @property
    def chroma_configured(self) -> bool:
        if self.chroma_host:
            return self.chroma_port is not None
        return bool(self.chroma_persist_directory)

    @property
    def llm_configured(self) -> bool:
        return bool(self.llm_model_name)

    @property
    def embedding_configured(self) -> bool:
        return bool(self.embedding_model_name)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Load process settings once and reuse them as a singleton."""
    from dotenv import load_dotenv

    load_dotenv()

    chroma_port = _env("CHROMA_PORT")
    if chroma_port:
        try:
            parsed_chroma_port = int(chroma_port)
        except ValueError as exc:
            raise ConfigurationError("CHROMA_PORT must be a valid integer") from exc
    else:
        parsed_chroma_port = None

    session_ttl_hours = _env("SESSION_TTL_HOURS", "24")
    try:
        parsed_session_ttl_hours = int(session_ttl_hours or "24")
    except ValueError as exc:
        raise ConfigurationError("SESSION_TTL_HOURS must be a valid integer") from exc

    llm_temperature = _env("LLM_TEMPERATURE", "0.2")
    try:
        parsed_llm_temperature = float(llm_temperature or "0.2")
    except ValueError as exc:
        raise ConfigurationError("LLM_TEMPERATURE must be a valid number") from exc

    llm_max_new_tokens = _env("LLM_MAX_NEW_TOKENS", "4096")
    try:
        parsed_llm_max_new_tokens = int(llm_max_new_tokens or "4096")
    except ValueError as exc:
        raise ConfigurationError("LLM_MAX_NEW_TOKENS must be a valid integer") from exc
    if parsed_llm_max_new_tokens < 1:
        raise ConfigurationError("LLM_MAX_NEW_TOKENS must be at least 1")

    llm_request_timeout_seconds_raw = _env("LLM_REQUEST_TIMEOUT_SECONDS", "120")
    try:
        parsed_llm_request_timeout_seconds = int(
            llm_request_timeout_seconds_raw or "120"
        )
    except ValueError as exc:
        raise ConfigurationError(
            "LLM_REQUEST_TIMEOUT_SECONDS must be a valid integer"
        ) from exc
    if parsed_llm_request_timeout_seconds < 1:
        raise ConfigurationError(
            "LLM_REQUEST_TIMEOUT_SECONDS must be at least 1"
        )

    llm_agent_delay_seconds = _env("LLM_AGENT_DELAY_SECONDS", "0")
    try:
        parsed_llm_agent_delay_seconds = int(llm_agent_delay_seconds or "0")
    except ValueError as exc:
        raise ConfigurationError(
            "LLM_AGENT_DELAY_SECONDS must be a valid integer"
        ) from exc

    llm_agent_delay_per_agent_raw = _env("LLM_AGENT_DELAY_PER_AGENT", "{}")
    try:
        parsed_llm_agent_delay_per_agent = json.loads(
            llm_agent_delay_per_agent_raw or "{}"
        )
        if not isinstance(parsed_llm_agent_delay_per_agent, dict):
            raise ConfigurationError(
                "LLM_AGENT_DELAY_PER_AGENT must be a JSON object"
            )
        # Validate all values are integers
        for key, val in parsed_llm_agent_delay_per_agent.items():
            if not isinstance(val, int):
                raise ConfigurationError(
                    f"LLM_AGENT_DELAY_PER_AGENT[{key}] must be an integer"
                )
    except (json.JSONDecodeError, ConfigurationError):
        raise
    except Exception as exc:
        raise ConfigurationError(
            "LLM_AGENT_DELAY_PER_AGENT must be valid JSON"
        ) from exc

    agent_max_chunks = _env("AGENT_MAX_CHUNKS", "12")
    try:
        parsed_agent_max_chunks = int(agent_max_chunks or "12")
    except ValueError as exc:
        raise ConfigurationError("AGENT_MAX_CHUNKS must be a valid integer") from exc
    if parsed_agent_max_chunks < 1:
        raise ConfigurationError("AGENT_MAX_CHUNKS must be at least 1")

    agent_max_excerpt_chars = _env("AGENT_MAX_EXCERPT_CHARS", "800")
    try:
        parsed_agent_max_excerpt_chars = int(agent_max_excerpt_chars or "800")
    except ValueError as exc:
        raise ConfigurationError(
            "AGENT_MAX_EXCERPT_CHARS must be a valid integer"
        ) from exc
    if parsed_agent_max_excerpt_chars < 50:
        raise ConfigurationError("AGENT_MAX_EXCERPT_CHARS must be at least 50")

    agent_prompt_budget_chars = _env("AGENT_PROMPT_BUDGET_CHARS", "5000")
    try:
        parsed_agent_prompt_budget_chars = int(agent_prompt_budget_chars or "5000")
    except ValueError as exc:
        raise ConfigurationError(
            "AGENT_PROMPT_BUDGET_CHARS must be a valid integer"
        ) from exc
    if parsed_agent_prompt_budget_chars < 200:
        raise ConfigurationError("AGENT_PROMPT_BUDGET_CHARS must be at least 200")

    agent_small_doc_threshold = _env("AGENT_SMALL_DOC_THRESHOLD", "6")
    try:
        parsed_agent_small_doc_threshold = int(agent_small_doc_threshold or "6")
    except ValueError as exc:
        raise ConfigurationError(
            "AGENT_SMALL_DOC_THRESHOLD must be a valid integer"
        ) from exc
    if parsed_agent_small_doc_threshold < 1:
        raise ConfigurationError("AGENT_SMALL_DOC_THRESHOLD must be at least 1")

    agent_total_prompt_budget_chars = _env(
        "AGENT_TOTAL_PROMPT_BUDGET_CHARS", "8000"
    )
    try:
        parsed_agent_total_prompt_budget_chars = int(
            agent_total_prompt_budget_chars or "8000"
        )
    except ValueError as exc:
        raise ConfigurationError(
            "AGENT_TOTAL_PROMPT_BUDGET_CHARS must be a valid integer"
        ) from exc
    if parsed_agent_total_prompt_budget_chars < 1000:
        raise ConfigurationError(
            "AGENT_TOTAL_PROMPT_BUDGET_CHARS must be at least 1000"
        )

    # Cross-field validation: the chunk budget must leave room for the rest
    # of the prompt payload. Otherwise the total-budget safety net is a
    # no-op (document_chunks alone would already exceed it, so the trim
    # loop in _enforce_total_prompt_budget would fire on every run).
    if parsed_agent_prompt_budget_chars >= parsed_agent_total_prompt_budget_chars:
        raise ConfigurationError(
            "AGENT_PROMPT_BUDGET_CHARS must be less than "
            "AGENT_TOTAL_PROMPT_BUDGET_CHARS"
        )

    settings = Settings(
        app_name=_env("APP_NAME", "EquipEd") or "EquipEd",
        app_version=_env("APP_VERSION", "0.1.0") or "0.1.0",
        environment=_env("APP_ENV", "development") or "development",
        api_prefix=_env("API_PREFIX", "/api/v1") or "/api/v1",
        cors_origins=_csv_env("CORS_ORIGINS"),
        cors_allow_credentials=_bool_env("CORS_ALLOW_CREDENTIALS", True),
        database_url=_env("DATABASE_URL"),
        database_echo=_bool_env("DATABASE_ECHO", False),
        session_cookie_name=_env("SESSION_COOKIE_NAME", "equiped_session")
        or "equiped_session",
        session_ttl_hours=parsed_session_ttl_hours,
        bootstrap_admin_email=_env("BOOTSTRAP_ADMIN_EMAIL"),
        bootstrap_admin_name=_env("BOOTSTRAP_ADMIN_NAME"),
        bootstrap_admin_password=_env("BOOTSTRAP_ADMIN_PASSWORD"),
        chroma_persist_directory=_resolve_chroma_path(
            _env("CHROMA_PERSIST_DIRECTORY", "chroma_data") or "chroma_data",
        ),
        chroma_host=_env("CHROMA_HOST"),
        chroma_port=parsed_chroma_port,
        chroma_ssl=_bool_env("CHROMA_SSL", False),
        llm_provider=_env("LLM_PROVIDER", "local") or "local",
        llm_model_name=_env("LLM_MODEL_NAME", "google/gemma-2-2b-it")
        or "google/gemma-2-2b-it",
        llm_api_base=_env("LLM_API_BASE"),
        llm_api_key=_env("LLM_API_KEY"),
        llm_temperature=parsed_llm_temperature,
        llm_max_new_tokens=parsed_llm_max_new_tokens,
        llm_agent_delay_seconds=parsed_llm_agent_delay_seconds,
        llm_request_timeout_seconds=parsed_llm_request_timeout_seconds,
        llm_agent_delay_per_agent=parsed_llm_agent_delay_per_agent,
        agent_debug_rubric_context=_bool_env("AGENT_DEBUG_RUBRIC_CONTEXT", False),
        agent_max_chunks=parsed_agent_max_chunks,
        agent_max_excerpt_chars=parsed_agent_max_excerpt_chars,
        agent_prompt_budget_chars=parsed_agent_prompt_budget_chars,
        agent_small_doc_threshold=parsed_agent_small_doc_threshold,
        agent_total_prompt_budget_chars=parsed_agent_total_prompt_budget_chars,
        embedding_model_name=_env(
            "EMBEDDING_MODEL_NAME",
            "paraphrase-multilingual-MiniLM-L12-v2",
        )
        or "paraphrase-multilingual-MiniLM-L12-v2",
    )

    if settings.cors_allow_credentials and "*" in settings.cors_origins:
        raise ConfigurationError(
            "CORS_ORIGINS cannot include '*' when credentials are enabled"
        )

    bootstrap_values = (
        settings.bootstrap_admin_email,
        settings.bootstrap_admin_name,
        settings.bootstrap_admin_password,
    )
    if any(bootstrap_values) and not all(bootstrap_values):
        raise ConfigurationError(
            "BOOTSTRAP_ADMIN_EMAIL, BOOTSTRAP_ADMIN_NAME, and "
            "BOOTSTRAP_ADMIN_PASSWORD must be set together"
        )

    return settings


__all__ = ["Settings", "get_settings"]
