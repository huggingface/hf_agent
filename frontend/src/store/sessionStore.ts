import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { SessionMeta } from '@/types/agent';

interface SessionStore {
  sessions: SessionMeta[];
  activeSessionId: string | null;

  // Actions
  createSession: (id: string) => void;
  deleteSession: (id: string) => void;
  switchSession: (id: string) => void;
  updateSessionTitle: (id: string, title: string) => void;
  setSessionActive: (id: string, isActive: boolean) => void;
}

export const useSessionStore = create<SessionStore>()(
  persist(
    (set, get) => ({
      sessions: [],
      activeSessionId: null,

      createSession: (id: string) => {
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

      deleteSession: (id: string) => {
        set((state) => {
          const newSessions = state.sessions.filter((s) => s.id !== id);
          const newActiveId =
            state.activeSessionId === id
              ? newSessions[newSessions.length - 1]?.id || null
              : state.activeSessionId;
          return {
            sessions: newSessions,
            activeSessionId: newActiveId,
          };
        });
      },

      switchSession: (id: string) => {
        set({ activeSessionId: id });
      },

      updateSessionTitle: (id: string, title: string) => {
        set((state) => ({
          sessions: state.sessions.map((s) =>
            s.id === id ? { ...s, title } : s
          ),
        }));
      },

      setSessionActive: (id: string, isActive: boolean) => {
        set((state) => ({
          sessions: state.sessions.map((s) =>
            s.id === id ? { ...s, isActive } : s
          ),
        }));
      },
    }),
    {
      name: 'hf-agent-sessions',
      partialize: (state) => ({
        sessions: state.sessions,
        activeSessionId: state.activeSessionId,
      }),
    }
  )
);
