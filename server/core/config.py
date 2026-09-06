"""Environment-backed settings for the server core layer."""

from __future__ import annotations

import os
from dataclasses import dataclass
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
    email_provider: str = "console"
    resend_api_key: str | None = None
    email_from: str = "EquipED <no-reply@example.invalid>"
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_starttls: bool = True
    smtp_timeout_seconds: int = 10
    app_public_url: str = "http://localhost:5173"
    session_cookie_secure: bool = False

    chroma_persist_directory: str = _resolve_chroma_path("chroma_data")
    chroma_host: str | None = None
    chroma_port: int | None = None
    chroma_ssl: bool = False

    llm_provider: str = "local"
    llm_model_name: str = "equiped-gemma3-4b-qat-q4"
    llm_api_base: str | None = None
    llm_api_key: str | None = None
    # Dev-only hostname allowlist for the LLM endpoint locality guard. When a
    # hostname matches, the private-network check is bypassed — for self-hosted
    # models reached through a tunnel (e.g. Cloudflare) during local testing.
    # MUST remain empty in production (data residency).
    llm_allowed_endpoints: tuple[str, ...] = ()
    llm_temperature: float = 0.2
    llm_temperature_itso: float = 0.0
    # Default raised from 2048 to 4096 to give larger SLM evaluation outputs
    # more headroom and reduce the chance of JSON truncation in agent responses.
    # Fits comfortably within typical 8K-context local models (e.g. Gemma-2-2B)
    # alongside the bounded prompt payload.
    llm_max_new_tokens: int = 4096
    llm_request_timeout_seconds: int = 120
    llm_readiness_timeout_seconds: float = 15.0
    evaluation_heartbeat_stale_seconds: int = 300
    llm_response_mode: str = "json_object"
    llm_inflight_limit: int = 4
    llm_rpm_limit: int = 0
    llm_tpm_limit: int = 0
    llm_local_quota_enabled: bool = False
    # Per-agent model overrides.
    llm_model_sme: str | None = None
    llm_model_coord: str | None = None
    llm_model_gad: str | None = None
    llm_model_itso: str | None = None

    embedding_model_name: str = "paraphrase-multilingual-MiniLM-L12-v2"

    # Path to the Tesseract OCR binary and language(s) to use for scanned
    # (image-based) PDF pages. When tesseract_cmd is None, pytesseract falls
    # back to searching PATH, which fails on machines without Tesseract
    # installed/registered on PATH (e.g. a fresh Windows dev box).
    tesseract_cmd: str | None = None
    tesseract_lang: str = "eng+fil"
    # Optional override for Tesseract's language-pack directory. Lets a
    # per-developer machine add language packs (e.g. fil.traineddata) it
    # doesn't have permission to drop into the system Tesseract install
    # (Program Files requires admin rights on Windows) without touching
    # the shared installation.
    tessdata_prefix: str | None = None

    ocr_max_pages: int = 125
    ocr_dpi: int = 200
    ocr_max_pixels: int = 8000000
    ocr_timeout_seconds: int = 20
    ocr_concurrency: int = 1
    ocr_semaphore_timeout_seconds: int = 30

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
    # Keep the assembled request bounded for provider-neutral local operation.
    agent_total_prompt_budget_chars: int = 32000
    sme_total_prompt_budget_chars: int = 15000

    # When enabled, ITSO prompt receives bounded policy clause evidence
    # from the local policy collection. MUST only be enabled when the LLM
    # backend is institutionally approved and local/self-hosted. Default
    # False blocks delivery of policy text to any (including external) LLM.
    itso_policy_delivery_enabled: bool = False

    # Only call toxicity classification on generated evaluation content
    # when an explicitly configured local/self-hosted endpoint is approved.
    # Default False ensures generated content is never sent to arbitrary
    # or external endpoints without explicit operator consent.
    toxicity_assessment_enabled: bool = False

    # Dedicated toxicity classifier endpoint. Must point to a local/self-hosted
    # service — validated at client-creation time by a locality guard.
    # Toxicity never reuses the global LLM_API_BASE or LLM_MODEL_NAME.
    toxicity_api_base: str | None = None
    toxicity_model_name: str | None = None
    toxicity_api_key: str | None = None
    toxicity_request_timeout_seconds: int = 30

    curriculum_alignment_max_concurrent_checks: int = 4
    curriculum_alignment_max_checks_per_user: int = 1
    curriculum_alignment_recheck_cooldown_seconds: int = 30

    @property
    def database_configured(self) -> bool:
        return bool(self.database_url)

    @property
    def chroma_configured(self) -> bool:
        if self.chroma_host:
            return self.chroma_port is not None
        return bool(self.chroma_persist_directory)

    def get_agent_temperature(self, agent_name: str) -> float:
        """Return the temperature for a specific agent, falling back to global default.

        Currently only ``itso`` has a dedicated temperature setting.
        All other agents use the global ``llm_temperature``.
        """
        if agent_name == "itso":
            return self.llm_temperature_itso
        return self.llm_temperature

    def get_agent_model(self, agent_name: str) -> str:
        """Return the model for a specific agent, falling back to global default."""
        mapping = {
            "sme": self.llm_model_sme,
            "coordinator": self.llm_model_coord,
            "gad": self.llm_model_gad,
            "itso": self.llm_model_itso,
        }
        return mapping.get(agent_name) or self.llm_model_name

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

    smtp_port = _env("SMTP_PORT", "587")
    try:
        parsed_smtp_port = int(smtp_port or "587")
    except ValueError as exc:
        raise ConfigurationError("SMTP_PORT must be a valid integer") from exc
    if parsed_smtp_port < 1 or parsed_smtp_port > 65535:
        raise ConfigurationError("SMTP_PORT must be between 1 and 65535")

    smtp_timeout_seconds = _env("SMTP_TIMEOUT_SECONDS", "10")
    try:
        parsed_smtp_timeout_seconds = int(smtp_timeout_seconds or "10")
    except ValueError as exc:
        raise ConfigurationError(
            "SMTP_TIMEOUT_SECONDS must be a valid integer"
        ) from exc
    if parsed_smtp_timeout_seconds < 1:
        raise ConfigurationError("SMTP_TIMEOUT_SECONDS must be at least 1")

    llm_temperature = _env("LLM_TEMPERATURE", "0.2")
    try:
        parsed_llm_temperature = float(llm_temperature or "0.2")
    except ValueError as exc:
        raise ConfigurationError("LLM_TEMPERATURE must be a valid number") from exc

    llm_temperature_itso = _env("LLM_TEMPERATURE_ITSO", "0.0")
    try:
        parsed_llm_temperature_itso = float(llm_temperature_itso or "0.0")
    except ValueError as exc:
        raise ConfigurationError("LLM_TEMPERATURE_ITSO must be a valid number") from exc
    if parsed_llm_temperature_itso < 0 or parsed_llm_temperature_itso >= 1.0:
        raise ConfigurationError(
            "LLM_TEMPERATURE_ITSO must be between 0.0 (inclusive) and 1.0 (exclusive)"
        )

    llm_max_new_tokens = _env("LLM_MAX_NEW_TOKENS", "4096")
    try:
        parsed_llm_max_new_tokens = int(llm_max_new_tokens or "4096")
    except ValueError as exc:
        raise ConfigurationError("LLM_MAX_NEW_TOKENS must be a valid integer") from exc
    if parsed_llm_max_new_tokens < 1:
        raise ConfigurationError("LLM_MAX_NEW_TOKENS must be at least 1")
    if parsed_llm_max_new_tokens > 32768:
        raise ConfigurationError("LLM_MAX_NEW_TOKENS cannot exceed 32768")

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
        raise ConfigurationError("LLM_REQUEST_TIMEOUT_SECONDS must be at least 1")
    if parsed_llm_request_timeout_seconds > 3600:
        raise ConfigurationError("LLM_REQUEST_TIMEOUT_SECONDS cannot exceed 3600")

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

    agent_total_prompt_budget_chars = _env("AGENT_TOTAL_PROMPT_BUDGET_CHARS", "32000")
    try:
        parsed_agent_total_prompt_budget_chars = int(
            agent_total_prompt_budget_chars or "32000"
        )
    except ValueError as exc:
        raise ConfigurationError(
            "AGENT_TOTAL_PROMPT_BUDGET_CHARS must be a valid integer"
        ) from exc
    if parsed_agent_total_prompt_budget_chars < 1000:
        raise ConfigurationError(
            "AGENT_TOTAL_PROMPT_BUDGET_CHARS must be at least 1000"
        )
    sme_total_prompt_budget_chars = _env("SME_TOTAL_PROMPT_BUDGET_CHARS", "15000")
    try:
        parsed_sme_total_prompt_budget_chars = int(
            sme_total_prompt_budget_chars or "15000"
        )
    except ValueError as exc:
        raise ConfigurationError(
            "SME_TOTAL_PROMPT_BUDGET_CHARS must be a valid integer"
        ) from exc
    if parsed_sme_total_prompt_budget_chars < 15000:
        raise ConfigurationError("SME_TOTAL_PROMPT_BUDGET_CHARS must be at least 15000")

    itso_policy_delivery_enabled = _bool_env("ITSO_POLICY_DELIVERY_ENABLED", False)
    toxicity_assessment_enabled = _bool_env("TOXICITY_ASSESSMENT_ENABLED", False)
    toxicity_api_base = _env("TOXICITY_API_BASE")
    toxicity_model_name = _env("TOXICITY_MODEL_NAME")
    toxicity_api_key = _env("TOXICITY_API_KEY")
    toxicity_request_timeout_seconds_raw = _env(
        "TOXICITY_REQUEST_TIMEOUT_SECONDS", "30"
    )
    try:
        parsed_toxicity_request_timeout_seconds = int(
            toxicity_request_timeout_seconds_raw or "30"
        )
    except ValueError as exc:
        raise ConfigurationError(
            "TOXICITY_REQUEST_TIMEOUT_SECONDS must be a valid integer"
        ) from exc
    if parsed_toxicity_request_timeout_seconds < 1:
        raise ConfigurationError("TOXICITY_REQUEST_TIMEOUT_SECONDS must be at least 1")

    curriculum_alignment_max_concurrent_checks_raw = _env(
        "CURRICULUM_ALIGNMENT_MAX_CONCURRENT_CHECKS", "4"
    )
    try:
        parsed_curriculum_alignment_max_concurrent_checks = int(
            curriculum_alignment_max_concurrent_checks_raw or "4"
        )
    except ValueError as exc:
        raise ConfigurationError(
            "CURRICULUM_ALIGNMENT_MAX_CONCURRENT_CHECKS must be a valid integer"
        ) from exc
    if parsed_curriculum_alignment_max_concurrent_checks < 1:
        raise ConfigurationError(
            "CURRICULUM_ALIGNMENT_MAX_CONCURRENT_CHECKS must be at least 1"
        )

    curriculum_alignment_max_checks_per_user_raw = _env(
        "CURRICULUM_ALIGNMENT_MAX_CHECKS_PER_USER", "1"
    )
    try:
        parsed_curriculum_alignment_max_checks_per_user = int(
            curriculum_alignment_max_checks_per_user_raw or "1"
        )
    except ValueError as exc:
        raise ConfigurationError(
            "CURRICULUM_ALIGNMENT_MAX_CHECKS_PER_USER must be a valid integer"
        ) from exc
    if parsed_curriculum_alignment_max_checks_per_user < 1:
        raise ConfigurationError(
            "CURRICULUM_ALIGNMENT_MAX_CHECKS_PER_USER must be at least 1"
        )

    curriculum_alignment_recheck_cooldown_seconds_raw = _env(
        "CURRICULUM_ALIGNMENT_RECHECK_COOLDOWN_SECONDS", "30"
    )
    try:
        parsed_curriculum_alignment_recheck_cooldown_seconds = int(
            curriculum_alignment_recheck_cooldown_seconds_raw or "30"
        )
    except ValueError as exc:
        raise ConfigurationError(
            "CURRICULUM_ALIGNMENT_RECHECK_COOLDOWN_SECONDS must be a valid integer"
        ) from exc
    if parsed_curriculum_alignment_recheck_cooldown_seconds < 0:
        raise ConfigurationError(
            "CURRICULUM_ALIGNMENT_RECHECK_COOLDOWN_SECONDS must be zero or positive"
        )

    if (
        parsed_curriculum_alignment_max_checks_per_user
        > parsed_curriculum_alignment_max_concurrent_checks
    ):
        raise ConfigurationError(
            "CURRICULUM_ALIGNMENT_MAX_CHECKS_PER_USER must be less than or equal to "
            "CURRICULUM_ALIGNMENT_MAX_CONCURRENT_CHECKS"
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

    ocr_max_pages_raw = _env("OCR_MAX_PAGES", "125")
    try:
        parsed_ocr_max_pages = int(ocr_max_pages_raw or "125")
    except ValueError as exc:
        raise ConfigurationError("OCR_MAX_PAGES must be a valid integer") from exc
    if parsed_ocr_max_pages < 1 or parsed_ocr_max_pages > 500:
        raise ConfigurationError("OCR_MAX_PAGES must be between 1 and 500")

    ocr_dpi_raw = _env("OCR_DPI", "200")
    try:
        parsed_ocr_dpi = int(ocr_dpi_raw or "200")
    except ValueError as exc:
        raise ConfigurationError("OCR_DPI must be a valid integer") from exc

    ocr_max_pixels_raw = _env("OCR_MAX_PIXELS", "8000000")
    try:
        parsed_ocr_max_pixels = int(ocr_max_pixels_raw or "8000000")
    except ValueError as exc:
        raise ConfigurationError("OCR_MAX_PIXELS must be a valid integer") from exc

    ocr_timeout_seconds_raw = _env("OCR_TIMEOUT_SECONDS", "20")
    try:
        parsed_ocr_timeout_seconds = int(ocr_timeout_seconds_raw or "20")
    except ValueError as exc:
        raise ConfigurationError("OCR_TIMEOUT_SECONDS must be a valid integer") from exc

    ocr_concurrency_raw = _env("OCR_CONCURRENCY", "1")
    try:
        parsed_ocr_concurrency = int(ocr_concurrency_raw or "1")
    except ValueError as exc:
        raise ConfigurationError("OCR_CONCURRENCY must be a valid integer") from exc

    ocr_semaphore_timeout_seconds_raw = _env("OCR_SEMAPHORE_TIMEOUT_SECONDS", "30")
    try:
        parsed_ocr_semaphore_timeout_seconds = int(
            ocr_semaphore_timeout_seconds_raw or "30"
        )
    except ValueError as exc:
        raise ConfigurationError(
            "OCR_SEMAPHORE_TIMEOUT_SECONDS must be a valid integer"
        ) from exc

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
        email_provider=(
            (_env("EMAIL_PROVIDER", "console") or "console").strip().lower()
        ),
        resend_api_key=_env("RESEND_API_KEY"),
        email_from=_env("EMAIL_FROM", "EquipED <no-reply@example.invalid>")
        or "EquipED <no-reply@example.invalid>",
        smtp_host=_env("SMTP_HOST"),
        smtp_port=parsed_smtp_port,
        smtp_username=_env("SMTP_USERNAME"),
        smtp_password=_env("SMTP_PASSWORD"),
        smtp_starttls=_bool_env("SMTP_STARTTLS", True),
        smtp_timeout_seconds=parsed_smtp_timeout_seconds,
        app_public_url=_env("APP_PUBLIC_URL", "http://localhost:5173")
        or "http://localhost:5173",
        session_cookie_secure=_bool_env("SESSION_COOKIE_SECURE", False),
        chroma_persist_directory=_resolve_chroma_path(
            _env("CHROMA_PERSIST_DIRECTORY", "chroma_data") or "chroma_data",
        ),
        chroma_host=_env("CHROMA_HOST"),
        chroma_port=parsed_chroma_port,
        chroma_ssl=_bool_env("CHROMA_SSL", False),
        llm_provider=_env("LLM_PROVIDER", "local") or "local",
        llm_model_name=_env("LLM_MODEL_NAME", "equiped-gemma3-4b-qat-q4")
        or "equiped-gemma3-4b-qat-q4",
        llm_api_base=_env("LLM_API_BASE"),
        llm_api_key=_env("LLM_API_KEY"),
        llm_allowed_endpoints=_csv_env("LLM_ALLOWED_ENDPOINTS"),
        llm_temperature=parsed_llm_temperature,
        llm_temperature_itso=parsed_llm_temperature_itso,
        llm_max_new_tokens=parsed_llm_max_new_tokens,
        llm_request_timeout_seconds=parsed_llm_request_timeout_seconds,
        llm_readiness_timeout_seconds=float(
            _env("LLM_READINESS_TIMEOUT_SECONDS", "15.0") or "15.0"
        ),
        evaluation_heartbeat_stale_seconds=int(
            _env("EVALUATION_HEARTBEAT_STALE_SECONDS", "300") or "300"
        ),
        llm_response_mode=_env("LLM_RESPONSE_MODE", "json_object") or "json_object",
        llm_inflight_limit=int(_env("LLM_INFLIGHT_LIMIT", "4") or "4"),
        llm_rpm_limit=int(_env("LLM_RPM_LIMIT", "0") or "0"),
        llm_tpm_limit=int(_env("LLM_TPM_LIMIT", "0") or "0"),
        llm_local_quota_enabled=_bool_env("LLM_LOCAL_QUOTA_ENABLED", False),
        llm_model_sme=_env("LLM_MODEL_SME"),
        llm_model_coord=_env("LLM_MODEL_COORD"),
        llm_model_gad=_env("LLM_MODEL_GAD"),
        llm_model_itso=_env("LLM_MODEL_ITSO"),
        agent_max_chunks=parsed_agent_max_chunks,
        agent_max_excerpt_chars=parsed_agent_max_excerpt_chars,
        agent_prompt_budget_chars=parsed_agent_prompt_budget_chars,
        agent_small_doc_threshold=parsed_agent_small_doc_threshold,
        agent_total_prompt_budget_chars=parsed_agent_total_prompt_budget_chars,
        sme_total_prompt_budget_chars=parsed_sme_total_prompt_budget_chars,
        itso_policy_delivery_enabled=itso_policy_delivery_enabled,
        toxicity_assessment_enabled=toxicity_assessment_enabled,
        toxicity_api_base=toxicity_api_base,
        toxicity_model_name=toxicity_model_name,
        toxicity_api_key=toxicity_api_key,
        toxicity_request_timeout_seconds=parsed_toxicity_request_timeout_seconds,
        curriculum_alignment_max_concurrent_checks=(
            parsed_curriculum_alignment_max_concurrent_checks
        ),
        curriculum_alignment_max_checks_per_user=(
            parsed_curriculum_alignment_max_checks_per_user
        ),
        curriculum_alignment_recheck_cooldown_seconds=(
            parsed_curriculum_alignment_recheck_cooldown_seconds
        ),
        embedding_model_name=_env(
            "EMBEDDING_MODEL_NAME",
            "paraphrase-multilingual-MiniLM-L12-v2",
        )
        or "paraphrase-multilingual-MiniLM-L12-v2",
        tesseract_cmd=_env("TESSERACT_CMD"),
        tesseract_lang=_env("TESSERACT_LANG", "eng+fil") or "eng+fil",
        tessdata_prefix=_env("TESSDATA_PREFIX"),
        ocr_max_pages=parsed_ocr_max_pages,
        ocr_dpi=parsed_ocr_dpi,
        ocr_max_pixels=parsed_ocr_max_pixels,
        ocr_timeout_seconds=parsed_ocr_timeout_seconds,
        ocr_concurrency=parsed_ocr_concurrency,
        ocr_semaphore_timeout_seconds=parsed_ocr_semaphore_timeout_seconds,
    )

    if settings.llm_response_mode not in {"json_object", "json_schema"}:
        raise ConfigurationError("LLM_RESPONSE_MODE must be json_object or json_schema")
    if settings.llm_inflight_limit < 1:
        raise ConfigurationError("LLM_INFLIGHT_LIMIT must be at least 1")
    if settings.llm_rpm_limit < 0 or settings.llm_tpm_limit < 0:
        raise ConfigurationError(
            "LLM_RPM_LIMIT and LLM_TPM_LIMIT must be zero or positive"
        )

    if settings.llm_allowed_endpoints and settings.environment != "development":
        raise ConfigurationError(
            "LLM_ALLOWED_ENDPOINTS must remain empty outside development "
            "(data residency)"
        )

    if settings.cors_allow_credentials and "*" in settings.cors_origins:
        raise ConfigurationError(
            "CORS_ORIGINS cannot include '*' when credentials are enabled"
        )

    if settings.email_provider not in {"console", "resend", "smtp"}:
        raise ConfigurationError("EMAIL_PROVIDER must be one of: console, resend, smtp")
    if settings.email_provider == "smtp" and not all(
        (settings.smtp_host, settings.smtp_username, settings.smtp_password)
    ):
        raise ConfigurationError(
            "SMTP_HOST, SMTP_USERNAME, and SMTP_PASSWORD must be set when "
            "EMAIL_PROVIDER=smtp"
        )

    if settings.environment != "development":
        if settings.email_provider == "console":
            raise ConfigurationError(
                "EMAIL_PROVIDER=console is not allowed in production"
            )
        if not settings.session_cookie_secure:
            raise ConfigurationError(
                "SESSION_COOKIE_SECURE must be true outside development"
            )
        if not settings.app_public_url.lower().startswith("https://"):
            raise ConfigurationError(
                "APP_PUBLIC_URL must use HTTPS outside development"
            )
        if settings.email_provider == "smtp" and not settings.smtp_starttls:
            raise ConfigurationError(
                "SMTP_STARTTLS must be true outside development when "
                "EMAIL_PROVIDER=smtp"
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
