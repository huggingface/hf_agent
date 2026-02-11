/**
 * Centralized API utilities with automatic auth header injection.
 *
 * In production (OAuth enabled):
 *   - REST calls include the HttpOnly cookie automatically (same-origin)
 *   - WebSocket passes token via query parameter
 *
 * In development (no OAuth):
 *   - Auth is bypassed on the backend, no token needed
 */

/** Get the base URL for API calls (handles dev proxy vs production) */
function getApiBase(): string {
  // In development, Vite proxies /api and /auth to the backend
  // In production, same origin
  return '';
}

/** Wrapper around fetch that includes credentials (cookies) and common headers. */
export async function apiFetch(
  path: string,
  options: RequestInit = {}
): Promise<Response> {
  const url = `${getApiBase()}${path}`;

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string>),
  };

  const response = await fetch(url, {
    ...options,
    headers,
    credentials: 'include', // Send cookies (hf_access_token) with every request
  });

  // Handle 401 - redirect to login if auth is required
  if (response.status === 401) {
    const authStatus = await fetch(`${getApiBase()}/auth/status`, {
      credentials: 'include',
    });
    const data = await authStatus.json();
    if (data.auth_enabled) {
      window.location.href = '/auth/login';
      throw new Error('Authentication required — redirecting to login.');
    }
  }

  return response;
}

/** Build the WebSocket URL for a session, including auth token if available. */
export function getWebSocketUrl(sessionId: string): string {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  // Always use same origin — Vite proxy (ws: true) handles dev,
  // same origin works directly in production. No cross-origin issues.
  return `${protocol}//${window.location.host}/api/ws/${sessionId}`;
}
