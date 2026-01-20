import { create } from 'zustand';
import type { Message, ApprovalBatch, User, TraceLog } from '@/types/agent';

export interface PlanItem {
  id: string;
  content: string;
  status: 'pending' | 'in_progress' | 'completed';
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
  plan: PlanItem[];

  // Actions
  addMessage: (sessionId: string, message: Message) => void;
  clearMessages: (sessionId: string) => void;
  setProcessing: (isProcessing: boolean) => void;
  setConnected: (isConnected: boolean) => void;
  setPendingApprovals: (approvals: ApprovalBatch | null) => void;
  setUser: (user: User | null) => void;
  setError: (error: string | null) => void;
  getMessages: (sessionId: string) => Message[];
  addTraceLog: (log: TraceLog) => void;
  clearTraceLogs: () => void;
  setPanelContent: (content: { title: string; content: string; language?: string; parameters?: any } | null) => void;
  setPlan: (plan: PlanItem[]) => void;
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
  plan: [],

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

  clearTraceLogs: () => {
    set({ traceLogs: [] });
  },

  setPanelContent: (content) => {
    set({ panelContent: content });
  },

  setPlan: (plan: PlanItem[]) => {
    set({ plan });
  },
}));
