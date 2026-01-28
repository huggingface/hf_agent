import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import type { User } from '@/types/agent';

const API_BASE = import.meta.env.DEV ? 'http://127.0.0.1:7860' : '';

interface AuthStore {
  // State
  token: string | null;
  user: User | null;
  isLoading: boolean;
  error: string | null;

  // Sync state
  lastSynced: string | null;
  pendingSyncCount: number;

  // Actions
  setToken: (token: string | null) => void;
  setUser: (user: User | null) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  setSyncStatus: (lastSynced: string, pendingCount: number) => void;

  // Auth actions
  handleAuthCallback: () => Promise<boolean>;
  fetchCurrentUser: () => Promise<void>;
  logout: () => Promise<void>;
  setAnthropicKey: (key: string) => Promise<boolean>;
  removeAnthropicKey: () => Promise<void>;

  // Helpers
  getAuthHeaders: () => Record<string, string>;
  isAuthenticated: () => boolean;
}

export const useAuthStore = create<AuthStore>()(
  persist(
    (set, get) => ({
      token: null,
      user: null,
      isLoading: true,
      error: null,
      lastSynced: null,
      pendingSyncCount: 0,

      setToken: (token) => set({ token }),
      setUser: (user) => set({ user }),
      setLoading: (isLoading) => set({ isLoading }),
      setError: (error) => set({ error }),
      setSyncStatus: (lastSynced, pendingCount) => set({
        lastSynced,
        pendingSyncCount: pendingCount
      }),

      handleAuthCallback: async () => {
        // Check for auth callback in URL fragment
        const hash = window.location.hash;
        if (hash.startsWith('#auth_callback=')) {
          const token = decodeURIComponent(hash.substring('#auth_callback='.length));

          // Clear the hash from URL
          window.history.replaceState(null, '', window.location.pathname);

          // Store token
          set({ token, isLoading: true });

          // Fetch user info
          await get().fetchCurrentUser();

          return true;
        }
        return false;
      },

      fetchCurrentUser: async () => {
        const { token } = get();
        if (!token) {
          set({ user: null, isLoading: false });
          return;
        }

        try {
          const response = await fetch(`${API_BASE}/auth/me`, {
            headers: get().getAuthHeaders(),
          });

          if (response.ok) {
            const data = await response.json();
            if (data.authenticated) {
              set({
                user: {
                  authenticated: true,
                  user_id: data.user_id,
                  username: data.username,
                  name: data.name,
                  picture: data.picture,
                  has_anthropic_key: data.has_anthropic_key,
                },
                isLoading: false,
                error: null,
              });
            } else {
              // Token invalid, clear it
              set({ token: null, user: null, isLoading: false });
            }
          } else {
            // Auth failed, clear token
            set({ token: null, user: null, isLoading: false });
          }
        } catch (error) {
          console.error('Failed to fetch user:', error);
          set({ isLoading: false, error: 'Failed to fetch user info' });
        }
      },

      logout: async () => {
        const { token } = get();

        try {
          if (token) {
            await fetch(`${API_BASE}/auth/logout`, {
              method: 'POST',
              headers: get().getAuthHeaders(),
            });
          }
        } catch (error) {
          console.error('Logout request failed:', error);
        }

        // Clear state regardless of API result
        set({ token: null, user: null, error: null });
      },

      setAnthropicKey: async (key: string) => {
        const { token } = get();
        if (!token) return false;

        try {
          const response = await fetch(`${API_BASE}/auth/anthropic-key`, {
            method: 'POST',
            headers: {
              ...get().getAuthHeaders(),
              'Content-Type': 'application/json',
            },
            body: JSON.stringify({ key }),
          });

          if (response.ok) {
            // Update user to reflect they now have a key
            const { user } = get();
            if (user) {
              set({ user: { ...user, has_anthropic_key: true } });
            }
            return true;
          } else {
            const data = await response.json();
            set({ error: data.detail || 'Failed to set API key' });
            return false;
          }
        } catch (error) {
          console.error('Failed to set Anthropic key:', error);
          set({ error: 'Failed to set API key' });
          return false;
        }
      },

      removeAnthropicKey: async () => {
        const { token } = get();
        if (!token) return;

        try {
          await fetch(`${API_BASE}/auth/anthropic-key`, {
            method: 'DELETE',
            headers: get().getAuthHeaders(),
          });

          // Update user to reflect they no longer have a key
          const { user } = get();
          if (user) {
            set({ user: { ...user, has_anthropic_key: false } });
          }
        } catch (error) {
          console.error('Failed to remove Anthropic key:', error);
        }
      },

      getAuthHeaders: (): Record<string, string> => {
        const { token } = get();
        if (token) {
          return { Authorization: `Bearer ${token}` };
        }
        return {};
      },

      isAuthenticated: () => {
        const { token, user } = get();
        return !!(token && user?.authenticated);
      },
    }),
    {
      name: 'hf-agent-auth',
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({
        token: state.token,
        // Don't persist user - fetch fresh on load
      }),
    }
  )
);

// Initialize: check for auth callback on load
if (typeof window !== 'undefined') {
  // Handle auth callback from OAuth
  useAuthStore.getState().handleAuthCallback().then((wasCallback) => {
    if (!wasCallback) {
      // No callback, just fetch current user if we have a token
      const token = useAuthStore.getState().token;
      if (token) {
        useAuthStore.getState().fetchCurrentUser();
      } else {
        useAuthStore.getState().setLoading(false);
      }
    }
  });
}
