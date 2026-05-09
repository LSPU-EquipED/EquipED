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

function extractErrorDetail(payload: unknown) {
  if (!payload || typeof payload !== 'object') {
    return null;
  }

  const candidate = payload as ApiErrorPayload;
  return candidate.detail ?? candidate.error?.message ?? null;
}

export async function requestJson<TResponse>(path: string, init: RequestInit = {}): Promise<TResponse> {
  const headers = new Headers(init.headers);

  if (!headers.has('Accept')) {
    headers.set('Accept', 'application/json');
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
