import { create } from 'zustand';
import type { Message, ApprovalBatch, User, TraceLog } from '@/types/agent';

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
  parameters?: any;
}

interface AgentStore {
  // State per session (keyed by session ID)
  messagesBySession: Record<string, Message[]>;
  isProcessing: boolean;
  isConnected: boolean;
  pendingApprovals: ApprovalBatch | null;
  user: User | null;
  error: string | null;
  traceLogs: TraceLog[];
  panelContent: { title: string; content: string; language?: string; parameters?: any } | null;
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
  setPendingApprovals: (approvals: ApprovalBatch | null) => void;
  setUser: (user: User | null) => void;
  setError: (error: string | null) => void;
  getMessages: (sessionId: string) => Message[];
  addTraceLog: (log: TraceLog) => void;
  updateTraceLog: (toolName: string, updates: Partial<TraceLog>) => void;
  clearTraceLogs: () => void;
  setPanelContent: (content: { title: string; content: string; language?: string; parameters?: any } | null) => void;
  setPanelTab: (tab: PanelTab) => void;
  setActivePanelTab: (tabId: string) => void;
  clearPanelTabs: () => void;
  removePanelTab: (tabId: string) => void;
  setPlan: (plan: PlanItem[]) => void;
  setCurrentTurnMessageId: (id: string | null) => void;
  updateCurrentTurnTrace: (sessionId: string) => void;
  showToolOutput: (log: TraceLog) => void;
}

export const useAgentStore = create<AgentStore>((set, get) => ({
  messagesBySession: {},
  isProcessing: false,
  isConnected: false,
  pendingApprovals: null,
  user: null,
  error: null,
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

  setPendingApprovals: (approvals: ApprovalBatch | null) => {
    set({ pendingApprovals: approvals });
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

  updateTraceLog: (toolName: string, updates: Partial<TraceLog>) => {
    set((state) => {
      // Find the last trace log with this tool name and update it
      const traceLogs = [...state.traceLogs];
      for (let i = traceLogs.length - 1; i >= 0; i--) {
        if (traceLogs[i].tool === toolName && traceLogs[i].type === 'call') {
          traceLogs[i] = { ...traceLogs[i], ...updates };
          break;
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
    if (state.currentTurnMessageId) {
      const currentMessages = state.messagesBySession[sessionId] || [];
      const updatedMessages = currentMessages.map((msg) =>
        msg.id === state.currentTurnMessageId
          ? { ...msg, trace: state.traceLogs.length > 0 ? [...state.traceLogs] : undefined }
          : msg
      );
      set({
        messagesBySession: {
          ...state.messagesBySession,
          [sessionId]: updatedMessages,
        },
      });
    }
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
}));
