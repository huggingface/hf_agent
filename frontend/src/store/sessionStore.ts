import { create } from 'zustand';
import type { Session } from '@/types/agent';
import { useAuthStore } from './authStore';

const API_BASE = import.meta.env.DEV ? 'http://127.0.0.1:7860' : '';

interface SessionStore {
  sessions: Session[];
  activeSessionId: string | null;
  isLoading: boolean;
  error: string | null;

  // Actions
  loadSessions: () => Promise<void>;
  createSession: () => Promise<string | null>;
  selectSession: (id: string) => Promise<void>;
  deleteSession: (id: string) => Promise<void>;
  clearError: () => void;
}

export const useSessionStore = create<SessionStore>()((set, get) => ({
  sessions: [],
  activeSessionId: null,
  isLoading: false,
  error: null,

  loadSessions: async () => {
    const { isAuthenticated, getAuthHeaders } = useAuthStore.getState();
    if (!isAuthenticated()) {
      set({ sessions: [], isLoading: false });
      return;
    }

    set({ isLoading: true, error: null });

    try {
      const response = await fetch(`${API_BASE}/api/sessions`, {
        headers: getAuthHeaders(),
      });

      if (!response.ok) {
        throw new Error('Failed to load sessions');
      }

      const data = await response.json();

      // Transform API response to frontend format
      const sessions: Session[] = data.map((s: any) => ({
        id: s.session_id,
        title: s.title || `Chat ${s.session_id.slice(0, 8)}`,
        createdAt: s.created_at,
        messageCount: s.message_count || 0,
      }));

      set({ sessions, isLoading: false });
    } catch (error) {
      console.error('Failed to load sessions:', error);
      set({ sessions: [], isLoading: false, error: 'Failed to load sessions' });
    }
  },

  createSession: async () => {
    const { getAuthHeaders } = useAuthStore.getState();

    try {
      const response = await fetch(`${API_BASE}/api/session`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...getAuthHeaders(),
        },
      });

      if (!response.ok) {
        throw new Error('Failed to create session');
      }

      const data = await response.json();
      const sessionId = data.session_id;

      // Add new session to the list
      const newSession: Session = {
        id: sessionId,
        title: `Chat ${sessionId.slice(0, 8)}`,
        createdAt: new Date().toISOString(),
        messageCount: 0,
      };

      set((state) => ({
        sessions: [newSession, ...state.sessions],
        activeSessionId: sessionId,
      }));

      return sessionId;
    } catch (error) {
      console.error('Failed to create session:', error);
      set({ error: 'Failed to create session' });
      return null;
    }
  },

  selectSession: async (id: string) => {
    const { activeSessionId } = get();

    // If already selected, do nothing
    if (activeSessionId === id) {
      return;
    }

    const { getAuthHeaders } = useAuthStore.getState();

    set({ isLoading: true, error: null });

    try {
      // Fetch messages for this session
      const response = await fetch(`${API_BASE}/api/session/${id}/messages`, {
        headers: getAuthHeaders(),
      });

      if (!response.ok) {
        throw new Error('Failed to load session');
      }

      const data = await response.json();

      // Load messages into agentStore
      const { useAgentStore } = await import('./agentStore');
      const setMessages = useAgentStore.getState().setMessages;

      // Transform and set messages (REPLACE, not append)
      const messages = (data.messages || []).map((msg: any, index: number) => ({
        id: `msg-${id}-${index}`,
        role: msg.role,
        content: msg.content,
        timestamp: new Date().toISOString(),
      }));

      setMessages(messages);
      set({ activeSessionId: id, isLoading: false });
    } catch (error) {
      console.error('Failed to select session:', error);
      set({ isLoading: false, error: 'Failed to load session' });
    }
  },

  deleteSession: async (id: string) => {
    const { getAuthHeaders } = useAuthStore.getState();
    const wasActiveSession = get().activeSessionId === id;

    try {
      const response = await fetch(`${API_BASE}/api/session/${id}`, {
        method: 'DELETE',
        headers: getAuthHeaders(),
      });

      if (!response.ok) {
        throw new Error('Failed to delete session');
      }

      set((state) => {
        const newSessions = state.sessions.filter((s) => s.id !== id);
        const newActiveId = state.activeSessionId === id
          ? (newSessions.length > 0 ? newSessions[0].id : null)
          : state.activeSessionId;

        return {
          sessions: newSessions,
          activeSessionId: newActiveId,
        };
      });

      // If we deleted the active session, clear messages
      if (wasActiveSession) {
        const { useAgentStore } = await import('./agentStore');
        useAgentStore.getState().clearMessages();
      }
    } catch (error) {
      console.error('Failed to delete session:', error);
      set({ error: 'Failed to delete session' });
    }
  },

  clearError: () => set({ error: null }),
}));
