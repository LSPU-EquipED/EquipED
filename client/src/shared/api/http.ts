const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/$/, '') || '/api/v1';

type ApiErrorPayload = {
  detail?: string;
  error?: {
    message?: string;
  };
};

export class ApiError extends Error {
  readonly status: number;
  readonly payload: unknown;
  readonly detail: string | null;

  constructor(message: string, options: { status: number; payload: unknown; detail?: string | null }) {
    super(message);
    this.name = 'ApiError';
    this.status = options.status;
    this.payload = options.payload;
    this.detail = options.detail ?? null;
  }
}

function buildApiUrl(path: string) {
  if (/^https?:\/\//.test(path)) {
    return path;
  }

  return `${API_BASE_URL}${path.startsWith('/') ? path : `/${path}`}`;
}

async function parseResponseBody(response: Response) {
  const contentType = response.headers.get('content-type') ?? '';

  if (contentType.includes('application/json')) {
    return response.json();
  }

  const text = await response.text();
  return text ? { detail: text } : null;
}

function extractErrorDetail(payload: unknown): string | null {
  if (!payload || typeof payload !== 'object') {
    return null;
  }

  const candidate = payload as ApiErrorPayload & { detail?: unknown };

  // FastAPI validation errors: detail is an array of {loc, msg, type}
  if (Array.isArray(candidate.detail)) {
    return candidate.detail
      .map((err: { loc?: Array<string | number>; msg?: string }) => {
        const field = err.loc ? err.loc[err.loc.length - 1] : 'unknown';
        const message = err.msg ?? 'Unknown error';
        return `${field}: ${message}`;
      })
      .join('; ');
  }

  if (typeof candidate.detail === 'string') {
    return candidate.detail;
  }

  return candidate.error?.message ?? null;
}

export async function requestJson<TResponse>(path: string, init: RequestInit = {}): Promise<TResponse> {
  const headers = new Headers(init.headers);

  if (!headers.has('Accept')) {
    headers.set('Accept', 'application/json');
  }

  if (init.body && !headers.has('Content-Type') && !(init.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json');
  }

  const response = await fetch(buildApiUrl(path), {
    ...init,
    headers,
    credentials: 'include',
  });

  const payload = await parseResponseBody(response);

  if (!response.ok) {
    const detail = extractErrorDetail(payload);
    throw new ApiError(detail ?? `Request failed with status ${response.status}`, {
      status: response.status,
      payload,
      detail,
    });
  }

  return payload as TResponse;
}

export function getErrorMessage(error: unknown, fallback = 'Something went wrong.') {
  if (error instanceof ApiError) {
    return error.detail ?? error.message;
  }

  if (error instanceof Error) {
    return error.message;
  }

  return fallback;
}

export function isApiError(error: unknown): error is ApiError {
  return error instanceof ApiError;
}
