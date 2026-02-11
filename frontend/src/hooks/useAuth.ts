/**
 * Authentication hook — non-blocking.
 *
 * The app renders immediately. This hook fires a background check to /auth/me
 * and updates the agent store with user info when it resolves.
 * If an API call later returns 401, apiFetch handles the redirect to /auth/login.
 *
 * This avoids blocking the entire UI on an auth check that depends on backend
 * availability (which can be slow during session/MCP initialization).
 */

import { useEffect } from 'react';
import { useAgentStore } from '@/store/agentStore';

export function useAuth() {
  const setUser = useAgentStore((s) => s.setUser);

  useEffect(() => {
    async function checkAuth() {
      try {
        const response = await fetch('/auth/me', { credentials: 'include' });
        if (response.ok) {
          const data = await response.json();
          if (data.authenticated) {
            setUser({
              authenticated: true,
              username: data.username,
              name: data.name,
              picture: data.picture,
            });
            return;
          }
        }

        // Not authenticated — check if auth is required
        const statusRes = await fetch('/auth/status', { credentials: 'include' });
        const statusData = await statusRes.json();
        if (statusData.auth_enabled) {
          window.location.href = '/auth/login';
          return;
        }

        // Dev mode — set dev user
        setUser({ authenticated: true, username: 'dev' });
      } catch {
        // Backend not ready — set dev user so the app is usable
        setUser({ authenticated: true, username: 'dev' });
      }
    }

    checkAuth();
  }, [setUser]);
}
