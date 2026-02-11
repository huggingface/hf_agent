/**
 * Authentication hook — non-blocking, lazy.
 *
 * On mount: checks if the user is already authenticated (cookie/dev mode).
 * Does NOT redirect to login automatically — the welcome screen handles that.
 *
 * Exports `triggerLogin()` for components that need to start the OAuth flow
 * (e.g. the "Start Session" button on the welcome screen).
 */

import { useEffect, useCallback } from 'react';
import { useAgentStore } from '@/store/agentStore';

/** Redirect to the OAuth login page. */
export function triggerLogin() {
  window.location.href = '/auth/login';
}

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

        // Not authenticated — check if auth is even enabled
        const statusRes = await fetch('/auth/status', { credentials: 'include' });
        const statusData = await statusRes.json();
        if (!statusData.auth_enabled) {
          // Dev mode — set dev user so the app is usable
          setUser({ authenticated: true, username: 'dev' });
          return;
        }

        // Auth is enabled but user is not logged in.
        // Don't redirect — let the welcome screen show first.
        // The user will be prompted to log in when they click "Start Session".
        setUser(null);
      } catch {
        // Backend not ready — set dev user so the app is usable
        setUser({ authenticated: true, username: 'dev' });
      }
    }

    checkAuth();
  }, [setUser]);

  return { triggerLogin };
}
