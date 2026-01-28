import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import type { SessionMeta, PersistedSessionMeta } from '@/types/agent';
import { useAuthStore } from './authStore';

const API_BASE = import.meta.env.DEV ? 'http://127.0.0.1:7860' : '';

interface SessionStore {
  // In-memory sessions (current browser session)
  sessions: SessionMeta[];
  activeSessionId: string | null;

  // Persisted sessions from HF Dataset
  persistedSessions: PersistedSessionMeta[];
  isLoadingPersisted: boolean;

  // Actions for in-memory sessions
  createSession: () => Promise<string | null>;
  deleteSession: (id: string) => Promise<void>;
  switchSession: (id: string) => void;
  updateSessionTitle: (id: string, title: string) => void;
  setSessionActive: (id: string, isActive: boolean) => void;

  // Legacy action for backward compatibility
  createSessionLegacy: (id: string) => void;

  // Actions for persisted sessions
  loadPersistedSessions: () => Promise<void>;
  resumeSession: (sessionId: string) => Promise<string | null>;

  // Clear all
  clearSessions: () => void;
}

export const useSessionStore = create<SessionStore>()(
  persist(
    (set, get) => ({
      sessions: [],
      activeSessionId: null,
      persistedSessions: [],
      isLoadingPersisted: false,

      createSession: async () => {
        try {
          const authHeaders = useAuthStore.getState().getAuthHeaders();

          const response = await fetch(`${API_BASE}/api/session`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              ...authHeaders,
            },
          });

          if (!response.ok) {
            throw new Error('Failed to create session');
          }

          const data = await response.json();
          const sessionId = data.session_id;

          const newSession: SessionMeta = {
            id: sessionId,
            title: `Chat ${get().sessions.length + 1}`,
            createdAt: new Date().toISOString(),
            isActive: true,
          };

          set((state) => ({
            sessions: [...state.sessions, newSession],
            activeSessionId: sessionId,
          }));

          return sessionId;
        } catch (error) {
          console.error('Failed to create session:', error);
          return null;
        }
      },

      // Legacy version for backward compatibility with existing code
      createSessionLegacy: (id: string) => {
        const newSession: SessionMeta = {
          id,
          title: `Chat ${get().sessions.length + 1}`,
          createdAt: new Date().toISOString(),
          isActive: true,
        };
        set((state) => ({
          sessions: [...state.sessions, newSession],
          activeSessionId: id,
        }));
      },

      deleteSession: async (id) => {
        try {
          const authHeaders = useAuthStore.getState().getAuthHeaders();

          await fetch(`${API_BASE}/api/session/${id}`, {
            method: 'DELETE',
            headers: authHeaders,
          });

          set((state) => {
            const newSessions = state.sessions.filter((s) => s.id !== id);
            const newActiveId =
              state.activeSessionId === id
                ? newSessions.length > 0
                  ? newSessions[newSessions.length - 1].id
                  : null
                : state.activeSessionId;
            return {
              sessions: newSessions,
              activeSessionId: newActiveId,
            };
          });
        } catch (error) {
          console.error('Failed to delete session:', error);
        }
      },

      switchSession: (id) => {
        set({ activeSessionId: id });
      },

      updateSessionTitle: (id, title) => {
        set((state) => ({
          sessions: state.sessions.map((s) =>
            s.id === id ? { ...s, title } : s
          ),
        }));
      },

      setSessionActive: (id, isActive) => {
        set((state) => ({
          sessions: state.sessions.map((s) =>
            s.id === id ? { ...s, isActive } : s
          ),
        }));
      },

      loadPersistedSessions: async () => {
        const { isAuthenticated } = useAuthStore.getState();
        if (!isAuthenticated()) {
          set({ persistedSessions: [], isLoadingPersisted: false });
          return;
        }

        set({ isLoadingPersisted: true });

        try {
          const authHeaders = useAuthStore.getState().getAuthHeaders();

          const response = await fetch(`${API_BASE}/api/sessions/persisted`, {
            headers: authHeaders,
          });

          if (response.ok) {
            const data = await response.json();
            set({ persistedSessions: data, isLoadingPersisted: false });
          } else {
            set({ persistedSessions: [], isLoadingPersisted: false });
          }
        } catch (error) {
          console.error('Failed to load persisted sessions:', error);
          set({ persistedSessions: [], isLoadingPersisted: false });
        }
      },

      resumeSession: async (sessionId: string) => {
        try {
          const authHeaders = useAuthStore.getState().getAuthHeaders();

          const response = await fetch(`${API_BASE}/api/session/${sessionId}/resume`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              ...authHeaders,
            },
          });

          if (!response.ok) {
            throw new Error('Failed to resume session');
          }

          const data = await response.json();
          const newSessionId = data.session_id;

          // Find persisted session to get title
          const persisted = get().persistedSessions.find(
            (s) => s.session_id === sessionId
          );

          const newSession: SessionMeta = {
            id: newSessionId,
            title: persisted?.title || 'Resumed Session',
            createdAt: persisted?.created_at || new Date().toISOString(),
            isActive: true,
          };

          set((state) => ({
            sessions: [...state.sessions, newSession],
            activeSessionId: newSessionId,
          }));

          return newSessionId;
        } catch (error) {
          console.error('Failed to resume session:', error);
          return null;
        }
      },

      clearSessions: () => {
        set({
          sessions: [],
          activeSessionId: null,
          persistedSessions: [],
        });
      },
    }),
    {
      name: 'hf-agent-sessions',
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({
        sessions: state.sessions,
        activeSessionId: state.activeSessionId,
        // Don't persist persistedSessions - always fetch fresh
      }),
    }
  )
);
