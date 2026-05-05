# API Contract (Scaffold)

This document defines the minimal API contract expected by the client shell during Phase 1.
It is intentionally small and will expand as feature development begins.

## Base URL

`/api/v1`

## Health & Readiness

### `GET /api/v1/`

Returns a lightweight service identity payload.

### `GET /health`

Returns `200 OK` with `{ "status": "ok" }` when the service process is running.

### `GET /ready`

Returns readiness for external dependencies. If any dependency is not ready, returns `503`.

**Response shape (scaffold):**

```json
{
  "status": "ready | not_ready",
  "dependencies": {
    "database": { "configured": true, "ready": true, "detail": "..." },
    "chroma": { "configured": true, "ready": true, "detail": "..." },
    "llm": { "configured": false, "ready": false, "detail": "..." },
    "embedding": { "configured": true, "ready": true, "detail": "..." }
  }
}
```

## Error Envelope (Planned)

All application errors should eventually normalize to a consistent envelope.
Exact payload shape will be defined when the first feature endpoints are implemented.

```json
{
  "error": {
    "code": "STRING_CODE",
    "message": "Human-readable summary",
    "details": { "optional": "context" }
  }
}
```

## Notes

- Authentication is session-based for Phase 1, but auth endpoints are not yet wired.
- Feature endpoints (documents, evaluations, admin, feedback) will be added later.
