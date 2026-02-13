import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { Message, User, TraceLog } from '@/types/agent';

export interface PlanItem {
  id: string;
  content: string;
  status: 'pending' | 'in_progress' | 'completed';
}

interface PanelTab {
  id: string;
  title: string;
  content: string;
  language?: string;
  parameters?: Record<string, unknown>;
}

export interface LLMHealthError {
  error: string;
  errorType: 'auth' | 'credits' | 'rate_limit' | 'network' | 'unknown';
  model: string;
}

interface AgentStore {
  // State per session (keyed by session ID)
  messagesBySession: Record<string, Message[]>;
  isProcessing: boolean;
  isConnected: boolean;
  user: User | null;
  error: string | null;
  llmHealthError: LLMHealthError | null;
  traceLogs: TraceLog[];
  panelContent: { title: string; content: string; language?: string; parameters?: Record<string, unknown> } | null;
  panelTabs: PanelTab[];
  activePanelTab: string | null;
  plan: PlanItem[];
  currentTurnMessageId: string | null; // Track the current turn's assistant message

  // Actions
  addMessage: (sessionId: string, message: Message) => void;
  updateMessage: (sessionId: string, messageId: string, updates: Partial<Message>) => void;
  clearMessages: (sessionId: string) => void;
  setProcessing: (isProcessing: boolean) => void;
  setConnected: (isConnected: boolean) => void;
  setUser: (user: User | null) => void;
  setError: (error: string | null) => void;
  getMessages: (sessionId: string) => Message[];
  addTraceLog: (log: TraceLog) => void;
  updateTraceLog: (toolCallId: string, toolName: string, updates: Partial<TraceLog>) => void;
  clearTraceLogs: () => void;
  setPanelContent: (content: { title: string; content: string; language?: string; parameters?: Record<string, unknown> } | null) => void;
  setPanelTab: (tab: PanelTab) => void;
  setActivePanelTab: (tabId: string) => void;
  clearPanelTabs: () => void;
  removePanelTab: (tabId: string) => void;
  setPlan: (plan: PlanItem[]) => void;
  setCurrentTurnMessageId: (id: string | null) => void;
  updateCurrentTurnTrace: (sessionId: string) => void;
  showToolOutput: (log: TraceLog) => void;
  /** Append a streaming delta to an existing message. */
  appendToMessage: (sessionId: string, messageId: string, delta: string) => void;
  /** Remove all messages for a session (also clears from localStorage). */
  deleteSessionMessages: (sessionId: string) => void;
  /** Remove the last turn (last user msg + all following assistant/tool msgs). */
  removeLastTurn: (sessionId: string) => void;
  setLlmHealthError: (error: LLMHealthError | null) => void;
}

export const useAgentStore = create<AgentStore>()(
  persist(
  (set, get) => ({
  messagesBySession: {},
  isProcessing: false,
  isConnected: false,
  user: null,
  error: null,
  llmHealthError: null,
  traceLogs: [],
  panelContent: null,
  panelTabs: [],
  activePanelTab: null,
  plan: [],
  currentTurnMessageId: null,

  addMessage: (sessionId: string, message: Message) => {
    set((state) => {
      const currentMessages = state.messagesBySession[sessionId] || [];
      return {
        messagesBySession: {
          ...state.messagesBySession,
          [sessionId]: [...currentMessages, message],
        },
      };
    });
  },

  updateMessage: (sessionId: string, messageId: string, updates: Partial<Message>) => {
    set((state) => {
      const currentMessages = state.messagesBySession[sessionId] || [];
      const updatedMessages = currentMessages.map((msg) =>
        msg.id === messageId ? { ...msg, ...updates } : msg
      );
      return {
        messagesBySession: {
          ...state.messagesBySession,
          [sessionId]: updatedMessages,
        },
      };
    });
  },

  clearMessages: (sessionId: string) => {
    set((state) => ({
      messagesBySession: {
        ...state.messagesBySession,
        [sessionId]: [],
      },
    }));
  },

  setProcessing: (isProcessing: boolean) => {
    set({ isProcessing });
  },

  setConnected: (isConnected: boolean) => {
    set({ isConnected });
  },

  setUser: (user: User | null) => {
    set({ user });
  },

  setError: (error: string | null) => {
    set({ error });
  },

  getMessages: (sessionId: string) => {
    return get().messagesBySession[sessionId] || [];
  },

  addTraceLog: (log: TraceLog) => {
    set((state) => ({
      traceLogs: [...state.traceLogs, log],
    }));
  },

  updateTraceLog: (toolCallId: string, toolName: string, updates: Partial<TraceLog>) => {
    set((state) => {
      const traceLogs = [...state.traceLogs];
      // Prefer matching by tool_call_id (reliable), fall back to tool name (legacy)
      let matched = false;
      if (toolCallId) {
        for (let i = traceLogs.length - 1; i >= 0; i--) {
          if (traceLogs[i].toolCallId === toolCallId) {
            traceLogs[i] = { ...traceLogs[i], ...updates };
            matched = true;
            break;
          }
        }
      }
      if (!matched) {
        // Fallback: match by tool name (last uncompleted call)
        for (let i = traceLogs.length - 1; i >= 0; i--) {
          if (traceLogs[i].tool === toolName && traceLogs[i].type === 'call' && !traceLogs[i].completed) {
            traceLogs[i] = { ...traceLogs[i], ...updates };
            break;
          }
        }
      }
      return { traceLogs };
    });
  },

  clearTraceLogs: () => {
    set({ traceLogs: [] });
  },

  setPanelContent: (content) => {
    set({ panelContent: content });
  },

  setPanelTab: (tab: PanelTab) => {
    set((state) => {
      const existingIndex = state.panelTabs.findIndex(t => t.id === tab.id);
      let newTabs: PanelTab[];
      if (existingIndex >= 0) {
        // Update existing tab
        newTabs = [...state.panelTabs];
        newTabs[existingIndex] = tab;
      } else {
        // Add new tab
        newTabs = [...state.panelTabs, tab];
      }
      return {
        panelTabs: newTabs,
        activePanelTab: state.activePanelTab || tab.id, // Auto-select first tab
      };
    });
  },

  setActivePanelTab: (tabId: string) => {
    set({ activePanelTab: tabId });
  },

  clearPanelTabs: () => {
    set({ panelTabs: [], activePanelTab: null });
  },

  removePanelTab: (tabId: string) => {
    set((state) => {
      const newTabs = state.panelTabs.filter(t => t.id !== tabId);
      // If we removed the active tab, switch to another tab or null
      let newActiveTab = state.activePanelTab;
      if (state.activePanelTab === tabId) {
        newActiveTab = newTabs.length > 0 ? newTabs[newTabs.length - 1].id : null;
      }
      return {
        panelTabs: newTabs,
        activePanelTab: newActiveTab,
      };
    });
  },

  setPlan: (plan: PlanItem[]) => {
    set({ plan });
  },

  setCurrentTurnMessageId: (id: string | null) => {
    set({ currentTurnMessageId: id });
  },

  updateCurrentTurnTrace: (sessionId: string) => {
    const state = get();
    if (!state.currentTurnMessageId) return;

    const currentMessages = state.messagesBySession[sessionId] || [];
    const latestTools = state.traceLogs.length > 0 ? [...state.traceLogs] : undefined;
    if (!latestTools) return;

    const updatedMessages = currentMessages.map((msg) => {
      if (msg.id !== state.currentTurnMessageId) return msg;

      const segments = msg.segments ? [...msg.segments] : [];
      const lastToolsIdx = segments.map((s) => s.type).lastIndexOf('tools');

      if (lastToolsIdx >= 0 && lastToolsIdx === segments.length - 1) {
        // Last segment IS a tools segment — update it in place
        segments[lastToolsIdx] = { type: 'tools', tools: latestTools };
      } else if (lastToolsIdx >= 0) {
        // A tools segment exists but is NOT last (text came after it).
        // Append a NEW tools segment at the end.
        segments.push({ type: 'tools', tools: latestTools });
      } else {
        // No tools segment at all — create one at the end.
        segments.push({ type: 'tools', tools: latestTools });
      }

      return { ...msg, segments };
    });

    set({
      messagesBySession: {
        ...state.messagesBySession,
        [sessionId]: updatedMessages,
      },
    });
  },

  showToolOutput: (log: TraceLog) => {
    // Show tool output in the right panel - only ONE tool output tab at a time
    const state = get();

    // Determine language based on content
    let language = 'text';
    const content = log.output || '';

    // Check if content looks like JSON
    if (content.trim().startsWith('{') || content.trim().startsWith('[') || content.includes('```json')) {
      language = 'json';
    }
    // Check if content has markdown tables or formatting
    else if (content.includes('|') && content.includes('---') || content.includes('```')) {
      language = 'markdown';
    }

    // Remove any existing tool output tab (only keep one)
    const otherTabs = state.panelTabs.filter(t => t.id !== 'tool_output');

    // Create/replace the single tool output tab
    const newTab = {
      id: 'tool_output',
      title: log.tool,
      content: content || 'No output available',
      language,
    };

    set({
      panelTabs: [...otherTabs, newTab],
      activePanelTab: 'tool_output',
    });
  },

  appendToMessage: (sessionId: string, messageId: string, delta: string) => {
    set((state) => {
      const messages = state.messagesBySession[sessionId] || [];
      return {
        messagesBySession: {
          ...state.messagesBySession,
          [sessionId]: messages.map((msg) => {
            if (msg.id !== messageId) return msg;
            const newContent = msg.content + delta;
            const segments = msg.segments ? [...msg.segments] : [];
            const lastSeg = segments[segments.length - 1];

            if (lastSeg && lastSeg.type === 'text') {
              // Append to the existing text segment
              segments[segments.length - 1] = {
                ...lastSeg,
                content: (lastSeg.content || '') + delta,
              };
            } else {
              // Last segment is 'tools' (or empty) — start a NEW text segment
              // so that tools and text remain visually separated.
              segments.push({ type: 'text', content: delta });
            }

            return { ...msg, content: newContent, segments };
          }),
        },
      };
    });
  },

  deleteSessionMessages: (sessionId: string) => {
    set((state) => {
      const { [sessionId]: _, ...rest } = state.messagesBySession;
      return { messagesBySession: rest };
    });
  },

  removeLastTurn: (sessionId: string) => {
    set((state) => {
      const msgs = state.messagesBySession[sessionId];
      if (!msgs || msgs.length === 0) return state;

      // Find the index of the last user message
      let lastUserIdx = -1;
      for (let i = msgs.length - 1; i >= 0; i--) {
        if (msgs[i].role === 'user') {
          lastUserIdx = i;
          break;
        }
      }
      if (lastUserIdx === -1) return state; // no user message to remove

      // Remove everything from that user message onward
      return {
        messagesBySession: {
          ...state.messagesBySession,
          [sessionId]: msgs.slice(0, lastUserIdx),
        },
      };
    });
  },

  setLlmHealthError: (error: LLMHealthError | null) => {
    set({ llmHealthError: error });
  },
}),
    {
      name: 'hf-agent-messages',
      // Only persist messages — all transient UI state stays in-memory
      partialize: (state) => ({
        messagesBySession: state.messagesBySession,
      }),
    }
  )
);
