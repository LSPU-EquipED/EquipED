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

The backend currently returns FastAPI-style error payloads for feature endpoints.
Client features normalize these responses into a local `ApiError` shape instead of
introducing a second transport contract.

**Current backend error shape:**

```json
{
  "detail": "Human-readable summary"
}
```

**Client-normalized handling:**

- Authentication failures and upload validation failures are read from `detail`
- The web client treats the normalized error message as the source for inline form and screen-level feedback
- Session transport remains the HTTP-only cookie; no JWT or local token fallback is introduced

All application errors should eventually normalize to a consistent envelope.
Exact backend payload shape is still planned for a later broader API pass.

```json
{
  "error": {
    "code": "STRING_CODE",
    "message": "Human-readable summary",
    "details": { "optional": "context" }
  }
}
```

## Authentication

Authentication is session-based for Phase 1 and uses an HTTP-only session cookie.

### `POST /api/v1/auth/login`

Authenticates a local user with email and password.

**Request shape:**

```json
{
  "email": "admin@example.com",
  "password": "example-password"
}
```

**Response shape:**

```json
{
  "authenticated": true,
  "user": {
    "id": "uuid",
    "displayName": "Platform Admin",
    "email": "admin@example.com",
    "role": "admin"
  }
}
```

### `POST /api/v1/auth/logout`

Revokes the active server-side session for the current cookie, if present.

### `GET /api/v1/auth/me`

Returns the current authenticated user when a valid session cookie is present.

**Anonymous response shape:**

```json
{
  "authenticated": false,
  "user": null
}
```

## Documents

Documents endpoints are authenticated in the current client/server integration flow.
Browser clients must send the session cookie on every request.

### `GET /api/v1/documents`

Returns a paginated document inventory for the authenticated user context.

**Query parameters:**

- `source_type` (optional)
- `program` (optional)
- `page` (default `1`)
- `page_size` (default `20`)

**Response shape:**

```json
{
  "items": [
    {
      "document_id": "uuid",
      "title": "Sample SLM",
      "course_title": "Systems Integration and Architecture",
      "lesson_title": null,
      "source_type": "slm",
      "program": "bsit",
      "page_count": 24,
      "processing_status": "PROCESSED",
      "has_ocr_pages": false,
      "uploaded_at": "2026-05-08T12:00:00Z"
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 20
}
```

### `POST /api/v1/documents/upload`

Uploads a PDF document and runs the existing document ingestion flow.

**Request shape:** `multipart/form-data`

- `file` (required PDF file)
- `source_type` (required)
- `title` (required)
- `course_title` (optional)
- `lesson_title` (optional)
- `program` (required when `source_type=slm`)

**Response shape:**

```json
{
  "document_id": "uuid",
  "title": "Sample SLM",
  "course_title": "Systems Integration and Architecture",
  "lesson_title": null,
  "source_type": "slm",
  "processing_status": "PROCESSED"
}
```

## Notes

- Public self-service registration is intentionally out of scope.
- Upload completion does not imply evaluation completion.
- Feature endpoints for evaluations, reports, admin, and feedback will expand later.
