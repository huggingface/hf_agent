/**
 * Client-side OAuth using @huggingface/hub.
 *
 * Works inside HF Spaces iframes (no third-party cookies needed).
 * Token is stored in localStorage and sent via Authorization header.
 */

import { useEffect } from 'react';
import { oauthLoginUrl, oauthHandleRedirectIfPresent } from '@huggingface/hub';
import { useAgentStore } from '@/store/agentStore';
import { logger } from '@/utils/logger';

const TOKEN_KEY = 'hf_oauth_token';

/** Get the stored HF access token (or null). */
export function getStoredToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

/** Clear the stored token (logout). */
export function clearStoredToken(): void {
  try {
    localStorage.removeItem(TOKEN_KEY);
  } catch {
    // Ignore
  }
}

/** Redirect to HF OAuth login.
 *  Uses window.open as fallback for iframe environments where
 *  top-level navigation is blocked by sandbox restrictions. */
export async function triggerLogin(): Promise<void> {
  const url = await oauthLoginUrl({
    scopes: 'openid profile read-repos write-repos manage-repos inference-api jobs',
  });
  // Try top-level navigation first; if we're in an iframe, open a new tab
  try {
    if (window.top !== window.self) {
      // We're in an iframe — open in parent or new tab
      window.open(url, '_blank');
    } else {
      window.location.href = url;
    }
  } catch {
    // SecurityError from cross-origin iframe — open in new tab
    window.open(url, '_blank');
  }
}

/**
 * Hook: on mount, check for OAuth redirect result or existing token.
 * Sets the user in the agent store when authenticated.
 */
export function useAuth() {
  const setUser = useAgentStore((s) => s.setUser);

  useEffect(() => {
    let cancelled = false;

    async function init() {
      // 1. Check if we're returning from an OAuth redirect
      const oauthResult = await oauthHandleRedirectIfPresent();

      if (oauthResult) {
        // Store the access token
        localStorage.setItem(TOKEN_KEY, oauthResult.accessToken);
        logger.log('OAuth login successful:', oauthResult.userInfo?.name);

        if (!cancelled) {
          setUser({
            authenticated: true,
            username: oauthResult.userInfo?.name || oauthResult.userInfo?.preferred_username || 'user',
            name: oauthResult.userInfo?.name,
            picture: oauthResult.userInfo?.picture,
          });
        }
        return;
      }

      // 2. Check for existing token in localStorage
      const token = getStoredToken();
      if (!token) {
        // Not logged in — welcome screen will handle login trigger
        if (!cancelled) setUser(null);
        return;
      }

      // 3. Validate the stored token
      try {
        const res = await fetch('/auth/me', {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (res.ok) {
          const data = await res.json();
          if (!cancelled && data.authenticated) {
            setUser({
              authenticated: true,
              username: data.username,
              name: data.name,
              picture: data.picture,
            });
            return;
          }
        }
        // Token invalid — clear it
        clearStoredToken();
        if (!cancelled) setUser(null);
      } catch {
        // Backend unreachable in dev — set dev user
        if (!cancelled) setUser({ authenticated: true, username: 'dev' });
      }
    }

    init();
    return () => { cancelled = true; };
  }, [setUser]);
}
