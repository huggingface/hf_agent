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
  // Messages for current session only (not persisted)
  messages: Message[];
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
  currentTurnMessageId: string | null;

  // Actions
  setMessages: (messages: Message[]) => void;
  addMessage: (message: Message) => void;
  updateMessage: (messageId: string, updates: Partial<Message>) => void;
  clearMessages: () => void;
  setProcessing: (isProcessing: boolean) => void;
  setConnected: (isConnected: boolean) => void;
  setPendingApprovals: (approvals: ApprovalBatch | null) => void;
  setUser: (user: User | null) => void;
  setError: (error: string | null) => void;
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
  updateCurrentTurnTrace: () => void;
  showToolOutput: (log: TraceLog) => void;
}

export const useAgentStore = create<AgentStore>()((set, get) => ({
  messages: [],
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

  setMessages: (messages: Message[]) => {
    set({ messages });
  },

  addMessage: (message: Message) => {
    set((state) => ({
      messages: [...state.messages, message],
    }));
  },

  updateMessage: (messageId: string, updates: Partial<Message>) => {
    set((state) => ({
      messages: state.messages.map((msg) =>
        msg.id === messageId ? { ...msg, ...updates } : msg
      ),
    }));
  },

  clearMessages: () => {
    set({ messages: [] });
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

  addTraceLog: (log: TraceLog) => {
    set((state) => ({
      traceLogs: [...state.traceLogs, log],
    }));
  },

  updateTraceLog: (toolName: string, updates: Partial<TraceLog>) => {
    set((state) => {
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
        newTabs = [...state.panelTabs];
        newTabs[existingIndex] = tab;
      } else {
        newTabs = [...state.panelTabs, tab];
      }
      return {
        panelTabs: newTabs,
        activePanelTab: state.activePanelTab || tab.id,
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

  updateCurrentTurnTrace: () => {
    const state = get();
    if (state.currentTurnMessageId) {
      const updatedMessages = state.messages.map((msg) =>
        msg.id === state.currentTurnMessageId
          ? { ...msg, trace: state.traceLogs.length > 0 ? [...state.traceLogs] : undefined }
          : msg
      );
      set({ messages: updatedMessages });
    }
  },

  showToolOutput: (log: TraceLog) => {
    const state = get();

    let language = 'text';
    const content = log.output || '';

    if (content.trim().startsWith('{') || content.trim().startsWith('[') || content.includes('```json')) {
      language = 'json';
    } else if (content.includes('|') && content.includes('---') || content.includes('```')) {
      language = 'markdown';
    }

    const otherTabs = state.panelTabs.filter(t => t.id !== 'tool_output');

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
