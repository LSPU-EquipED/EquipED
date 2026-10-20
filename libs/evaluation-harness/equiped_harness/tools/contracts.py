"""Neutral errors shared by explicit bounded tool transports."""

from enum import StrEnum


class Code(StrEnum):
    CAPACITY = "verification_capacity_exceeded"
    INVALID = "invalid_public_scope"
    DISABLED = "verification_disabled"
    RUNTIME = "browser_runtime_unavailable"
    KEY = "provider_configuration_unavailable"
    SECURITY = "unsafe_destination"
    DEADLINE = "tool_deadline_exceeded"
    HTTP = "provider_http_error"
    MALFORMED = "malformed_public_response"
    LIMIT = "response_limit_exceeded"
    ROBOTS = "robots_access_unavailable"
    ACCESS = "public_page_access_unavailable"
    BUDGET = "tool_reservation_exhausted"
    REPLAY = "tool_already_started"
    EXECUTION = "tool_execution_error"


class VerificationError(Exception):
    """Safe to expose code/hash only. Never carries URLs, queries or response bytes."""

    def __init__(self, code: Code, reference_hash: str = ""):
        self.code = code
        self.reference_hash = reference_hash
        self.http_status = 422 if code in {Code.CAPACITY, Code.INVALID} else 503
        super().__init__(f"{code.value}:{reference_hash}")
