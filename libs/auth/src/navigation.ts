/**
 * Resolves destination URLs across application boundaries.
 *
 * In a unified origin (Caddy on :3000 or production edge reverse proxy),
 * cross-app transitions use standard relative paths (`/admin`, `/login`, `/dashboard`).
 *
 * In multi-port local development without a reverse proxy (Faculty on 5173, Admin on 5174),
 * it redirects to the appropriate development port so each app runs in its native Vite context.
 */
export function getCrossAppUrl(path: string): string {
  if (typeof window === 'undefined') {
    return path;
  }

  const { protocol, hostname, port } = window.location;

  // Running on Faculty Vite (:5173) and navigating to an Admin-owned surface
  if (
    port === '5173' &&
    (path === '/admin' ||
      path.startsWith('/admin/') ||
      path.startsWith('/matrix') ||
      path.startsWith('/evaluation-map'))
  ) {
    return `${protocol}//${hostname}:5174${path}`;
  }

  // Running on Admin Vite (:5174) and navigating to Faculty-owned surface or public auth
  if (
    port === '5174' &&
    (path === '/login' ||
      path === '/register' ||
      path === '/dashboard' ||
      path.startsWith('/documents') ||
      path.startsWith('/evaluations') ||
      path.startsWith('/specialists') ||
      path.startsWith('/syllabus-alignment') ||
      path.startsWith('/curriculum-alignment') ||
      path.startsWith('/storage') ||
      path.startsWith('/alignment'))
  ) {
    return `${protocol}//${hostname}:5173${path}`;
  }

  return path;
}

export function navigateCrossApp(path: string): void {
  if (typeof window !== 'undefined') {
    window.location.assign(getCrossAppUrl(path));
  }
}
