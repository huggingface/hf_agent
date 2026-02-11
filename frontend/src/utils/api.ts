/**
 * Centralized API utilities.
 *
 * Reads the HF OAuth token from localStorage and injects it as
 * an Authorization: Bearer header on every request.
 * WebSocket URLs include the token as a query parameter.
 */

import { getStoredToken, triggerLogin } from '@/hooks/useAuth';

/** Wrapper around fetch that includes auth and common headers. */
export async function apiFetch(
  path: string,
  options: RequestInit = {}
): Promise<Response> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string>),
  };

  // Inject Bearer token if available
  const token = getStoredToken();
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const response = await fetch(path, {
    ...options,
    headers,
    credentials: 'include', // Still send cookies for backward compat
  });

  // Handle 401 — trigger login if auth is required
  if (response.status === 401) {
    try {
      const authStatus = await fetch('/auth/status');
      const data = await authStatus.json();
      if (data.auth_enabled) {
        await triggerLogin();
        throw new Error('Authentication required — redirecting to login.');
      }
    } catch (e) {
      if (e instanceof Error && e.message.includes('redirecting')) throw e;
      // auth/status failed — ignore
    }
  }

  return response;
}

/** Build the WebSocket URL for a session, including auth token. */
export function getWebSocketUrl(sessionId: string): string {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const base = `${protocol}//${window.location.host}/api/ws/${sessionId}`;

  // Pass token as query param (WebSocket can't set custom headers from browser)
  const token = getStoredToken();
  if (token) {
    return `${base}?token=${encodeURIComponent(token)}`;
  }
  return base;
}
