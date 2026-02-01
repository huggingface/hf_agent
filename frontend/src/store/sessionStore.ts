import { create } from 'zustand';
import type { Session, Message, MessageSegment, TraceLog } from '@/types/agent';
import { useAuthStore } from './authStore';

const API_BASE = import.meta.env.DEV ? 'http://127.0.0.1:7860' : '';

/**
 * Transform raw LiteLLM messages into UI Message format with segments.
 * Groups ALL consecutive assistant/tool messages between user messages into ONE blob.
 * This ensures one user message → one assistant response blob in the UI.
 */
function transformRawMessages(rawMessages: any[], sessionId: string): Message[] {
  const messages: Message[] = [];

  console.log('[transformRawMessages] Input:', rawMessages.length, 'messages');

  // Build a map of tool_call_id -> tool result for quick lookup
  const toolResults = new Map<string, { content: string; success: boolean }>();
  for (const msg of rawMessages) {
    if (msg.role === 'tool' && msg.tool_call_id) {
      const content = typeof msg.content === 'string' ? msg.content : JSON.stringify(msg.content);
      // Check for error indicators in the content
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
      // Create as an approved job message
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
      // Regular assistant message
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
    // Skip tool result messages - they're looked up via toolResults map
    if (msg.role === 'tool') continue;

    if (msg.role === 'user') {
      // Flush any pending assistant blob before adding user message
      flushAssistantBlob();

      const content = extractTextContent(msg.content);
      messages.push({
        id: `msg-${sessionId}-${msgIndex++}`,
        role: 'user',
        content,
        timestamp: new Date().toISOString(),
      });
    } else if (msg.role === 'assistant') {
      // Initialize blob if needed
      if (!currentAssistantBlob) {
        currentAssistantBlob = {
          segments: [],
          content: '',
          hasJobTool: false,
        };
      }

      const textContent = extractTextContent(msg.content);
      const toolCalls = msg.tool_calls || [];

      // Append text content
      if (textContent) {
        if (currentAssistantBlob.content) {
          currentAssistantBlob.content += '\n\n' + textContent;
        } else {
          currentAssistantBlob.content = textContent;
        }
        currentAssistantBlob.segments.push({ type: 'text', content: textContent });
      }

      // Process tool calls
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

        // Check for hf_jobs approval tool
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

  // Flush final assistant blob
  flushAssistantBlob();

  console.log('[transformRawMessages] Output:', messages.length, 'messages');

  return messages;
}

/**
 * Extract text content from LiteLLM message content (string or content blocks array).
 */
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

interface SessionStore {
  sessions: Session[];
  activeSessionId: string | null;
  isLoading: boolean;
  isLoaded: boolean;  // True once loadSessions has completed
  error: string | null;

  // Actions
  loadSessions: () => Promise<void>;
  createSession: () => Promise<string | null>;
  selectSession: (id: string) => Promise<void>;
  deleteSession: (id: string) => Promise<void>;
  switchModel: (modelName: string) => Promise<boolean>;
  clearError: () => void;
}

export const useSessionStore = create<SessionStore>()((set, get) => ({
  sessions: [],
  activeSessionId: null,
  isLoading: false,
  isLoaded: false,
  error: null,

  loadSessions: async () => {
    const { isAuthenticated, getAuthHeaders } = useAuthStore.getState();
    if (!isAuthenticated()) {
      set({ sessions: [], isLoading: false, isLoaded: true });
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

      set({ sessions, isLoading: false, isLoaded: true });
    } catch (error) {
      console.error('Failed to load sessions:', error);
      set({ sessions: [], isLoading: false, isLoaded: true, error: 'Failed to load sessions' });
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

      // Transform raw LiteLLM messages into UI format with segments, approvals, etc.
      const messages = transformRawMessages(data.messages || [], id);

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

  switchModel: async (modelName: string) => {
    const { activeSessionId } = get();
    if (!activeSessionId) return false;

    const { getAuthHeaders } = useAuthStore.getState();

    try {
      const response = await fetch(`${API_BASE}/api/session/${activeSessionId}`, {
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

      return true;
    } catch (error) {
      console.error('Failed to switch model:', error);
      set({ error: 'Failed to switch model' });
      return false;
    }
  },

  clearError: () => set({ error: null }),
}));
