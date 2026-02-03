import { create } from 'zustand';
import type { Message, MessageSegment, TraceLog } from '@/types/agent';
import { useAuthStore } from './authStore';
import { useAgentStore } from './agentStore';

const API_BASE = import.meta.env.DEV ? 'http://127.0.0.1:7860' : '';

// Session metadata for list display
export interface SessionMeta {
  id: string;
  title: string;
  createdAt: string;
  updatedAt?: string;
  messageCount: number;
  lastPreview?: string;
  modelName?: string;
}

// Phase state machine - explicit states for session lifecycle
export type SessionPhase =
  | { status: 'idle' }
  | { status: 'loading'; sessionId: string }
  | { status: 'ready'; sessionId: string }
  | { status: 'active'; sessionId: string }
  | { status: 'error'; sessionId: string; error: string };

interface SessionStore {
  // Session list (independent of active session)
  sessions: SessionMeta[];
  sessionsLoading: boolean;
  sessionsLoaded: boolean;
  sessionsError: string | null;

  // Active session state machine
  phase: SessionPhase;

  // Model name for active session
  activeModelName: string | null;

  // Actions - List management
  loadSessions: () => Promise<void>;

  // Actions - Session lifecycle
  selectSession: (id: string) => Promise<void>;
  createSession: () => Promise<string | null>;
  deleteSession: (id: string) => Promise<void>;
  switchModel: (modelName: string) => Promise<boolean>;

  // Actions - Phase transitions (called by SSE hook)
  markActive: () => void;
  markError: (error: string) => void;
  reset: () => void;

  // Helpers
  getActiveSessionId: () => string | null;
  getPhaseSessionId: () => string | null;
  isSessionSelected: (id: string) => boolean;
}

/**
 * Transform raw LiteLLM messages into UI Message format with segments.
 * Groups ALL consecutive assistant/tool messages between user messages into ONE blob.
 */
function transformRawMessages(rawMessages: any[], sessionId: string): Message[] {
  const messages: Message[] = [];

  console.log('[transformRawMessages] Input:', rawMessages.length, 'messages');

  // Build a map of tool_call_id -> tool result for quick lookup
  const toolResults = new Map<string, { content: string; success: boolean }>();
  for (const msg of rawMessages) {
    if (msg.role === 'tool' && msg.tool_call_id) {
      const content = typeof msg.content === 'string' ? msg.content : JSON.stringify(msg.content);
      const isError = content.toLowerCase().includes('error') ||
        content.toLowerCase().includes('traceback') ||
        content.toLowerCase().includes('exception');
      toolResults.set(msg.tool_call_id, { content, success: !isError });
    }
  }

  let msgIndex = 0;
  let currentAssistantBlob: {
    segments: MessageSegment[];
    content: string;
    hasJobTool: boolean;
    jobToolOutput?: string;
    jobToolCalls?: any[];
  } | null = null;

  const flushAssistantBlob = () => {
    if (!currentAssistantBlob) return;

    if (currentAssistantBlob.hasJobTool && currentAssistantBlob.jobToolCalls) {
      messages.push({
        id: `msg-${sessionId}-${msgIndex++}`,
        role: 'assistant',
        content: currentAssistantBlob.content,
        timestamp: new Date().toISOString(),
        segments: currentAssistantBlob.segments,
        approval: {
          status: 'approved',
          batch: {
            tools: currentAssistantBlob.jobToolCalls,
            count: currentAssistantBlob.jobToolCalls.length,
          },
        },
        toolOutput: currentAssistantBlob.jobToolOutput,
      });
    } else {
      messages.push({
        id: `msg-${sessionId}-${msgIndex++}`,
        role: 'assistant',
        content: currentAssistantBlob.content,
        timestamp: new Date().toISOString(),
        segments: currentAssistantBlob.segments.length > 0 ? currentAssistantBlob.segments : undefined,
      });
    }
    currentAssistantBlob = null;
  };

  for (const msg of rawMessages) {
    if (msg.role === 'tool') continue;

    if (msg.role === 'user') {
      flushAssistantBlob();

      const content = extractTextContent(msg.content);
      messages.push({
        id: `msg-${sessionId}-${msgIndex++}`,
        role: 'user',
        content,
        timestamp: new Date().toISOString(),
      });
    } else if (msg.role === 'assistant') {
      if (!currentAssistantBlob) {
        currentAssistantBlob = {
          segments: [],
          content: '',
          hasJobTool: false,
        };
      }

      const textContent = extractTextContent(msg.content);
      const toolCalls = msg.tool_calls || [];

      if (textContent) {
        if (currentAssistantBlob.content) {
          currentAssistantBlob.content += '\n\n' + textContent;
        } else {
          currentAssistantBlob.content = textContent;
        }
        currentAssistantBlob.segments.push({ type: 'text', content: textContent });
      }

      if (toolCalls.length > 0) {
        const tools: TraceLog[] = toolCalls.map((tc: any, idx: number) => {
          const toolCallId = tc.id || `tool_${msgIndex}_${idx}`;
          const toolName = tc.function?.name || tc.name || 'unknown';
          const args = tc.function?.arguments || tc.arguments || {};
          const parsedArgs = typeof args === 'string' ? JSON.parse(args) : args;
          const result = toolResults.get(toolCallId);

          return {
            id: toolCallId,
            type: 'call' as const,
            text: `Executed ${toolName}`,
            tool: toolName,
            timestamp: new Date().toISOString(),
            completed: true,
            args: parsedArgs,
            output: result?.content,
            success: result?.success ?? true,
          };
        });

        currentAssistantBlob.segments.push({ type: 'tools', tools });

        const jobTool = tools.find(t => t.tool === 'hf_jobs' && t.args?.script);
        if (jobTool) {
          currentAssistantBlob.hasJobTool = true;
          currentAssistantBlob.jobToolOutput = jobTool.output;
          currentAssistantBlob.jobToolCalls = toolCalls.map((tc: any) => ({
            tool: tc.function?.name || tc.name || 'unknown',
            arguments: typeof tc.function?.arguments === 'string'
              ? JSON.parse(tc.function.arguments)
              : (tc.function?.arguments || tc.arguments || {}),
            tool_call_id: tc.id,
          }));
        }
      }
    }
  }

  flushAssistantBlob();

  console.log('[transformRawMessages] Output:', messages.length, 'messages');

  return messages;
}

function extractTextContent(content: any): string {
  if (typeof content === 'string') {
    return content;
  }
  if (Array.isArray(content)) {
    return content
      .filter((block: any) => block.type === 'text')
      .map((block: any) => block.text || '')
      .join('\n');
  }
  return '';
}

export const useSessionStore = create<SessionStore>()((set, get) => ({
  // Initial state
  sessions: [],
  sessionsLoading: false,
  sessionsLoaded: false,
  sessionsError: null,
  phase: { status: 'idle' },
  activeModelName: null,

  // ============================================================
  // SESSION LIST MANAGEMENT
  // ============================================================

  loadSessions: async () => {
    const { isAuthenticated, getAuthHeaders } = useAuthStore.getState();

    if (!isAuthenticated()) {
      set({ sessions: [], sessionsLoaded: true, sessionsLoading: false });
      return;
    }

    set({ sessionsLoading: true, sessionsError: null });

    try {
      const response = await fetch(`${API_BASE}/api/sessions`, {
        headers: getAuthHeaders(),
      });

      if (!response.ok) {
        throw new Error(`Failed to load sessions: ${response.status}`);
      }

      const data = await response.json();

      const sessions: SessionMeta[] = data.map((s: any) => ({
        id: s.session_id,
        title: s.title || `Chat ${s.session_id.slice(0, 8)}`,
        createdAt: s.created_at,
        updatedAt: s.updated_at,
        messageCount: s.message_count || 0,
        lastPreview: s.last_message_preview,
      }));

      // Sort by most recent
      sessions.sort((a, b) =>
        new Date(b.updatedAt || b.createdAt).getTime() -
        new Date(a.updatedAt || a.createdAt).getTime()
      );

      set({ sessions, sessionsLoading: false, sessionsLoaded: true });
    } catch (error) {
      console.error('Failed to load sessions:', error);
      set({
        sessionsLoading: false,
        sessionsLoaded: true,
        sessionsError: error instanceof Error ? error.message : 'Failed to load sessions'
      });
    }
  },

  // ============================================================
  // SESSION ACTIVATION (STATE MACHINE)
  // ============================================================

  selectSession: async (id: string) => {
    const { phase } = get();

    // Already active on this session? Do nothing
    if (phase.status === 'active' && phase.sessionId === id) {
      return;
    }

    // Already loading this session? Do nothing
    if (phase.status === 'loading' && phase.sessionId === id) {
      return;
    }

    // Transition: * -> loading
    set({ phase: { status: 'loading', sessionId: id } });

    // Clear previous session state
    const agentStore = useAgentStore.getState();
    agentStore.clearMessages();
    agentStore.clearTraceLogs();
    agentStore.setPlan([]);
    agentStore.clearPanelTabs();
    agentStore.setCurrentTurnMessageId(null);

    try {
      const { getAuthHeaders } = useAuthStore.getState();

      // Single request that guarantees session is ready
      const response = await fetch(`${API_BASE}/api/session/${id}/activate`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...getAuthHeaders(),
        },
      });

      if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
        throw new Error(error.detail || `HTTP ${response.status}`);
      }

      const data = await response.json();

      // Load messages into agent store
      const messages = transformRawMessages(data.messages || [], id);
      agentStore.setMessages(messages);

      // Transition: loading -> ready (SSE hook will see this and connect)
      set({
        phase: { status: 'ready', sessionId: id },
        activeModelName: data.model_name || null,
      });

    } catch (error) {
      console.error('Failed to activate session:', error);
      set({
        phase: {
          status: 'error',
          sessionId: id,
          error: error instanceof Error ? error.message : 'Failed to load session'
        }
      });
    }
  },

  createSession: async () => {
    // Transition: * -> loading
    set({ phase: { status: 'loading', sessionId: '_new_' } });

    // Clear previous session state
    const agentStore = useAgentStore.getState();
    agentStore.clearMessages();
    agentStore.clearTraceLogs();
    agentStore.setPlan([]);
    agentStore.clearPanelTabs();
    agentStore.setCurrentTurnMessageId(null);

    try {
      const { getAuthHeaders } = useAuthStore.getState();

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
      const modelName = data.model_name;

      // Add to session list
      const newSession: SessionMeta = {
        id: sessionId,
        title: `Chat ${sessionId.slice(0, 8)}`,
        createdAt: new Date().toISOString(),
        messageCount: 0,
        modelName: modelName,
      };

      // Update list and transition: loading -> ready
      set((state) => ({
        sessions: [newSession, ...state.sessions],
        phase: { status: 'ready', sessionId },
        activeModelName: modelName || null,
      }));

      return sessionId;
    } catch (error) {
      console.error('Failed to create session:', error);
      set({
        phase: {
          status: 'error',
          sessionId: '_new_',
          error: error instanceof Error ? error.message : 'Failed to create session'
        }
      });
      return null;
    }
  },

  deleteSession: async (id: string) => {
    const { getAuthHeaders } = useAuthStore.getState();
    const { phase } = get();

    try {
      const response = await fetch(`${API_BASE}/api/session/${id}`, {
        method: 'DELETE',
        headers: getAuthHeaders(),
      });

      if (!response.ok) {
        throw new Error('Failed to delete session');
      }

      // Remove from list
      set((state) => ({
        sessions: state.sessions.filter((s) => s.id !== id),
      }));

      // If we deleted the selected/active session, reset phase
      const isCurrentSession =
        (phase.status === 'active' || phase.status === 'ready' || phase.status === 'loading') &&
        phase.sessionId === id;

      if (isCurrentSession) {
        useAgentStore.getState().clearMessages();
        set({ phase: { status: 'idle' }, activeModelName: null });
      }
    } catch (error) {
      console.error('Failed to delete session:', error);
    }
  },

  switchModel: async (modelName: string) => {
    const { phase } = get();
    const sessionId = phase.status === 'active' || phase.status === 'ready'
      ? phase.sessionId
      : null;

    if (!sessionId) return false;

    const { getAuthHeaders } = useAuthStore.getState();

    try {
      const response = await fetch(`${API_BASE}/api/session/${sessionId}`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          ...getAuthHeaders(),
        },
        body: JSON.stringify({ model_name: modelName }),
      });

      if (!response.ok) {
        throw new Error('Failed to switch model');
      }

      set({ activeModelName: modelName });
      return true;
    } catch (error) {
      console.error('Failed to switch model:', error);
      return false;
    }
  },

  // ============================================================
  // PHASE TRANSITIONS (called by SSE hook)
  // ============================================================

  markActive: () => {
    const { phase } = get();
    if (phase.status === 'ready') {
      set({ phase: { status: 'active', sessionId: phase.sessionId } });
    }
  },

  markError: (error: string) => {
    const { phase } = get();
    if (phase.status === 'ready' || phase.status === 'loading') {
      set({ phase: { status: 'error', sessionId: phase.sessionId, error } });
    }
  },

  reset: () => {
    set({ phase: { status: 'idle' }, activeModelName: null });
    useAgentStore.getState().clearMessages();
  },

  // ============================================================
  // HELPERS
  // ============================================================

  // Returns session ID only when fully active (SSE connected)
  getActiveSessionId: () => {
    const { phase } = get();
    if (phase.status === 'active') {
      return phase.sessionId;
    }
    return null;
  },

  // Returns session ID for ready or active phases (for SSE connection)
  getPhaseSessionId: () => {
    const { phase } = get();
    if (phase.status === 'ready' || phase.status === 'active') {
      return phase.sessionId;
    }
    return null;
  },

  // For sidebar highlighting - show selected even while loading
  isSessionSelected: (id: string) => {
    const { phase } = get();
    if (phase.status === 'idle') return false;
    return phase.sessionId === id;
  },
}));
