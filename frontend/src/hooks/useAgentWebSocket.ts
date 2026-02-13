import { useCallback, useEffect, useRef } from 'react';
import { useAgentStore, type PlanItem } from '@/store/agentStore';
import { useSessionStore } from '@/store/sessionStore';
import { useLayoutStore } from '@/store/layoutStore';
import { getWebSocketUrl } from '@/utils/api';
import { logger } from '@/utils/logger';
import type { AgentEvent } from '@/types/events';
import type { Message, TraceLog } from '@/types/agent';

const WS_RECONNECT_DELAY = 1000;
const WS_MAX_RECONNECT_DELAY = 30000;
const WS_MAX_RETRIES = 5;

interface UseAgentWebSocketOptions {
  sessionId: string | null;
  onReady?: () => void;
  onError?: (error: string) => void;
  onSessionDead?: (sessionId: string) => void;
}

export function useAgentWebSocket({
  sessionId,
  onReady,
  onError,
  onSessionDead,
}: UseAgentWebSocketOptions) {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<number | null>(null);
  const reconnectDelayRef = useRef(WS_RECONNECT_DELAY);
  const retriesRef = useRef(0);

  const {
    addMessage,
    updateMessage,
    appendToMessage,
    setProcessing,
    setConnected,
    setError,
    addTraceLog,
    updateTraceLog,
    clearTraceLogs,
    setPanelContent,
    setPanelTab,
    setActivePanelTab,
    clearPanelTabs,
    setPlan,
    setCurrentTurnMessageId,
    updateCurrentTurnTrace,
    removeLastTurn,
  } = useAgentStore();

  const { setRightPanelOpen, setLeftSidebarOpen } = useLayoutStore();

  const { setSessionActive } = useSessionStore();

  const handleEvent = useCallback(
    (event: AgentEvent) => {
      if (!sessionId) return;

      switch (event.event_type) {
        case 'ready':
          setConnected(true);
          setProcessing(false);
          setSessionActive(sessionId, true);
          onReady?.();
          break;

        case 'processing':
          setProcessing(true);
          clearTraceLogs();
          // Don't clear panel tabs here - they should persist during approval flow
          // Tabs will be cleared when a new tool_call sets up new content
          setCurrentTurnMessageId(null); // Start a new turn
          break;

        // ── Streaming: individual token chunks ──────────────────
        case 'assistant_chunk': {
          const delta = (event.data?.content as string) || '';
          if (!delta) break;

          const currentTurnMsgId = useAgentStore.getState().currentTurnMessageId;

          if (currentTurnMsgId) {
            // Append delta to the existing streaming message
            appendToMessage(sessionId, currentTurnMsgId, delta);
          } else {
            // First chunk — create the message (with pending traces if any)
            const currentTrace = useAgentStore.getState().traceLogs;
            const messageId = `msg_${Date.now()}`;
            const segments: Array<{ type: 'text' | 'tools'; content?: string; tools?: typeof currentTrace }> = [];

            if (currentTrace.length > 0) {
              segments.push({ type: 'tools', tools: [...currentTrace] });
              clearTraceLogs();
            }
            segments.push({ type: 'text', content: delta });

            const message: Message = {
              id: messageId,
              role: 'assistant',
              content: delta,
              timestamp: new Date().toISOString(),
              segments,
            };
            addMessage(sessionId, message);
            setCurrentTurnMessageId(messageId);
          }
          break;
        }

        // ── Streaming ended (text is already rendered via chunks) ─
        case 'assistant_stream_end':
          // Nothing to do — chunks already built the message.
          // This event is just a signal that the stream is complete.
          break;

        // ── Legacy non-streaming full message (kept for backwards compat)
        case 'assistant_message': {
          const content = (event.data?.content as string) || '';
          const currentTrace = useAgentStore.getState().traceLogs;
          const currentTurnMsgId = useAgentStore.getState().currentTurnMessageId;

          if (currentTurnMsgId) {
            // Update existing message - add segments chronologically
            const messages = useAgentStore.getState().getMessages(sessionId);
            const existingMsg = messages.find(m => m.id === currentTurnMsgId);

            if (existingMsg) {
              const segments = existingMsg.segments ? [...existingMsg.segments] : [];

              // If there are pending traces, add them as a tools segment first
              if (currentTrace.length > 0) {
                segments.push({ type: 'tools', tools: [...currentTrace] });
                clearTraceLogs();
              }

              // Add the new text segment
              if (content) {
                segments.push({ type: 'text', content });
              }

              updateMessage(sessionId, currentTurnMsgId, {
                content: existingMsg.content + '\n\n' + content,
                segments,
              });
            }
          } else {
            // Create new message
            const messageId = `msg_${Date.now()}`;
            const segments: Array<{ type: 'text' | 'tools'; content?: string; tools?: typeof currentTrace }> = [];

            // Add any pending traces first
            if (currentTrace.length > 0) {
              segments.push({ type: 'tools', tools: [...currentTrace] });
              clearTraceLogs();
            }

            // Add the text
            if (content) {
              segments.push({ type: 'text', content });
            }

            const message: Message = {
              id: messageId,
              role: 'assistant',
              content,
              timestamp: new Date().toISOString(),
              segments,
            };
            addMessage(sessionId, message);
            setCurrentTurnMessageId(messageId);
          }
          break;
        }

        case 'tool_call': {
          const toolName = (event.data?.tool as string) || 'unknown';
          const toolCallId = (event.data?.tool_call_id as string) || '';
          const args = (event.data?.arguments as Record<string, string | undefined>) || {};

          // Don't display plan_tool in trace logs (it shows up elsewhere in the UI)
          if (toolName !== 'plan_tool') {
            const log: TraceLog = {
              id: `tool_${Date.now()}_${toolCallId}`,
              toolCallId,
              type: 'call',
              text: `Agent is executing ${toolName}...`,
              tool: toolName,
              timestamp: new Date().toISOString(),
              completed: false,
              args,
            };
            addTraceLog(log);

            // If no assistant message exists for this turn, create one now
            // so the ToolCallGroup renders immediately in the chat flow.
            const currentTurnMsgId = useAgentStore.getState().currentTurnMessageId;
            if (!currentTurnMsgId) {
              const messageId = `msg_${Date.now()}`;
              const currentTrace = useAgentStore.getState().traceLogs;
              addMessage(sessionId, {
                id: messageId,
                role: 'assistant',
                content: '',
                timestamp: new Date().toISOString(),
                segments: [{ type: 'tools', tools: [...currentTrace] }],
              });
              setCurrentTurnMessageId(messageId);
              clearTraceLogs();
            } else {
              updateCurrentTurnTrace(sessionId);
            }
          }

          // Auto-expand Right Panel for specific tools
          if (toolName === 'hf_jobs' && (args.operation === 'run' || args.operation === 'scheduled run') && args.script) {
            // Clear any existing tabs from previous jobs before setting new script
            clearPanelTabs();
            // Use tab system for jobs - add script tab immediately
            setPanelTab({
              id: 'script',
              title: 'Script',
              content: args.script,
              language: 'python',
              parameters: args
            });
            setActivePanelTab('script');
            setRightPanelOpen(true);
            setLeftSidebarOpen(false);
          } else if (toolName === 'hf_repo_files' && args.operation === 'upload' && args.content) {
            setPanelContent({
              title: `File Upload: ${args.path || 'unnamed'}`,
              content: args.content,
              parameters: args,
              language: args.path?.endsWith('.py') ? 'python' : undefined
            });
            setRightPanelOpen(true);
            setLeftSidebarOpen(false);
          }

          logger.log('Tool call:', toolName, args);
          break;
        }

        case 'tool_output': {
          const toolName = (event.data?.tool as string) || 'unknown';
          const toolCallId = (event.data?.tool_call_id as string) || '';
          const output = (event.data?.output as string) || '';
          const success = event.data?.success as boolean;

          // Mark the corresponding trace log as completed and store the output.
          // If it had a pending approval, mark it as approved (tool_output means it ran).
          const prevLog = useAgentStore.getState().traceLogs.find(
            (l) => l.toolCallId === toolCallId
          );
          const wasApproval = prevLog?.approvalStatus === 'pending';
          updateTraceLog(toolCallId, toolName, {
            completed: true,
            output,
            success,
            ...(wasApproval ? { approvalStatus: 'approved' as const } : {}),
          });
          updateCurrentTurnTrace(sessionId);

          // For hf_jobs: parse job output and enrich the TraceLog with job info
          if (toolName === 'hf_jobs' && output) {
            const updates: Partial<TraceLog> = { approvalStatus: 'approved' as const };

            // Parse job URL
            const urlMatch = output.match(/\*\*View at:\*\*\s*(https:\/\/[^\s\n]+)/);
            if (urlMatch) updates.jobUrl = urlMatch[1];

            // Parse job status
            const statusMatch = output.match(/\*\*Final Status:\*\*\s*([^\n]+)/);
            if (statusMatch) updates.jobStatus = statusMatch[1].trim();

            // Parse logs
            if (output.includes('**Logs:**')) {
              const parts = output.split('**Logs:**');
              if (parts.length > 1) {
                const codeBlockMatch = parts[1].trim().match(/```([\s\S]*?)```/);
                if (codeBlockMatch) updates.jobLogs = codeBlockMatch[1].trim();
              }
            }

            updateTraceLog(toolCallId, toolName, updates);
            updateCurrentTurnTrace(sessionId);
          }

          // Don't create message bubbles for tool outputs - they only show in trace logs
          logger.log('Tool output:', toolName, success);
          break;
        }

        case 'tool_log': {
          const toolName = (event.data?.tool as string) || 'unknown';
          const log = (event.data?.log as string) || '';

          if (toolName === 'hf_jobs') {
            const currentTabs = useAgentStore.getState().panelTabs;
            const logsTab = currentTabs.find(t => t.id === 'logs');

            // Append to existing logs tab or create new one
            const newContent = logsTab
              ? logsTab.content + '\n' + log
              : '--- Job execution started ---\n' + log;

            setPanelTab({
              id: 'logs',
              title: 'Logs',
              content: newContent,
              language: 'text'
            });

            // Auto-switch to logs tab when logs start streaming
            setActivePanelTab('logs');

            if (!useLayoutStore.getState().isRightPanelOpen) {
              setRightPanelOpen(true);
            }
          }
          break;
        }

        case 'plan_update': {
          const plan = (event.data?.plan as PlanItem[]) || [];
          setPlan(plan);
          if (!useLayoutStore.getState().isRightPanelOpen) {
            setRightPanelOpen(true);
          }
          break;
        }

        case 'approval_required': {
          const tools = event.data?.tools as Array<{
            tool: string;
            arguments: Record<string, unknown>;
            tool_call_id: string;
          }>;

          // Create or update trace logs for approval tools.
          // The backend only sends tool_call events for non-approval tools,
          // so we must create TraceLogs here for approval-requiring tools.
          if (tools) {
            for (const t of tools) {
              // Check if a TraceLog already exists (shouldn't, but be safe)
              const existing = useAgentStore.getState().traceLogs.find(
                (log) => log.toolCallId === t.tool_call_id
              );
              if (!existing) {
                addTraceLog({
                  id: `tool_${Date.now()}_${t.tool_call_id}`,
                  toolCallId: t.tool_call_id,
                  type: 'call',
                  text: `Approval required for ${t.tool}`,
                  tool: t.tool,
                  timestamp: new Date().toISOString(),
                  completed: false,
                  args: t.arguments as Record<string, unknown>,
                  approvalStatus: 'pending',
                });
              } else {
                updateTraceLog(t.tool_call_id, t.tool, {
                  approvalStatus: 'pending',
                  args: t.arguments as Record<string, unknown>,
                });
              }
            }

            // Ensure there's a message to render the approval UI in
            const currentTurnMsgId = useAgentStore.getState().currentTurnMessageId;
            if (!currentTurnMsgId) {
              const messageId = `msg_${Date.now()}`;
              const currentTrace = useAgentStore.getState().traceLogs;
              addMessage(sessionId, {
                id: messageId,
                role: 'assistant',
                content: '',
                timestamp: new Date().toISOString(),
                segments: [{ type: 'tools', tools: [...currentTrace] }],
              });
              setCurrentTurnMessageId(messageId);
              clearTraceLogs();
            } else {
              updateCurrentTurnTrace(sessionId);
            }
          }

          // Show the first tool's content in the panel
          if (tools && tools.length > 0) {
            const firstTool = tools[0];
            const args = firstTool.arguments as Record<string, string | undefined>;

            clearPanelTabs();

            if (firstTool.tool === 'hf_jobs' && args.script) {
              setPanelTab({
                id: 'script',
                title: 'Script',
                content: args.script,
                language: 'python',
                parameters: args
              });
              setActivePanelTab('script');
            } else if (firstTool.tool === 'hf_repo_files' && args.content) {
              const filename = args.path || 'file';
              const isPython = filename.endsWith('.py');
              setPanelTab({
                id: 'content',
                title: filename.split('/').pop() || 'Content',
                content: args.content,
                language: isPython ? 'python' : 'text',
                parameters: args
              });
              setActivePanelTab('content');
            } else {
              setPanelTab({
                id: 'args',
                title: firstTool.tool,
                content: JSON.stringify(args, null, 2),
                language: 'json',
                parameters: args
              });
              setActivePanelTab('args');
            }

            setRightPanelOpen(true);
            setLeftSidebarOpen(false);
          }

          setProcessing(false);
          break;
        }

        case 'turn_complete':
          setProcessing(false);
          setCurrentTurnMessageId(null); // Clear the current turn
          break;

        case 'compacted': {
          const oldTokens = event.data?.old_tokens as number;
          const newTokens = event.data?.new_tokens as number;
          logger.log(`Context compacted: ${oldTokens} -> ${newTokens} tokens`);
          break;
        }

        case 'error': {
          const errorMsg = (event.data?.error as string) || 'Unknown error';
          setError(errorMsg);
          setProcessing(false);
          onError?.(errorMsg);
          break;
        }

        case 'shutdown':
          setConnected(false);
          setProcessing(false);
          break;

        case 'interrupted':
          setProcessing(false);
          break;

        case 'undo_complete':
          if (sessionId) {
            removeLastTurn(sessionId);
          }
          setProcessing(false);
          break;

        default:
          logger.log('Unknown event:', event);
      }
    },
    // Zustand setters are stable, so we don't need them in deps
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [sessionId, onReady, onError, onSessionDead]
  );

  const connect = useCallback(() => {
    if (!sessionId) return;
    
    // Don't connect if already connected or connecting
    if (wsRef.current?.readyState === WebSocket.OPEN || 
        wsRef.current?.readyState === WebSocket.CONNECTING) {
      return;
    }

    // Build WebSocket URL (centralized in utils/api.ts)
    const wsUrl = getWebSocketUrl(sessionId);

    logger.log('Connecting to WebSocket:', wsUrl);
    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      logger.log('WebSocket connected');
      setConnected(true);
      reconnectDelayRef.current = WS_RECONNECT_DELAY;
      retriesRef.current = 0; // Reset retry counter on successful connect
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data) as AgentEvent;
        handleEvent(data);
      } catch (e) {
        logger.error('Failed to parse WebSocket message:', e);
      }
    };

    ws.onerror = (error) => {
      logger.error('WebSocket error:', error);
    };

    ws.onclose = (event) => {
      logger.log('WebSocket closed', event.code, event.reason);
      setConnected(false);

      // Don't reconnect if:
      // - Normal closure (1000)
      // - Session not found (4004) — session was deleted or backend restarted
      // - Auth failed (4001) or access denied (4003) — won't succeed on retry
      // - No session ID
      const noRetryCodes = [1000, 4001, 4003, 4004];
      if (!noRetryCodes.includes(event.code) && sessionId) {
        retriesRef.current += 1;
        if (retriesRef.current > WS_MAX_RETRIES) {
          logger.warn(`WebSocket: max retries (${WS_MAX_RETRIES}) reached, giving up.`);
          onSessionDead?.(sessionId);
          return;
        }
        // Attempt to reconnect with exponential backoff
        if (reconnectTimeoutRef.current) {
          clearTimeout(reconnectTimeoutRef.current);
        }
        reconnectTimeoutRef.current = window.setTimeout(() => {
          reconnectDelayRef.current = Math.min(
            reconnectDelayRef.current * 2,
            WS_MAX_RECONNECT_DELAY
          );
          connect();
        }, reconnectDelayRef.current);
      } else if (event.code === 4004 && sessionId) {
        // Session not found — remove it from the store (lazy cleanup)
        logger.warn(`Session ${sessionId} no longer exists on backend, removing.`);
        onSessionDead?.(sessionId);
      } else if (noRetryCodes.includes(event.code) && event.code !== 1000) {
        logger.warn(`WebSocket permanently closed: ${event.code} ${event.reason}`);
      }
    };

    wsRef.current = ws;
  }, [sessionId, handleEvent]);

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    setConnected(false);
  }, []);

  const sendPing = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'ping' }));
    }
  }, []);

  // Connect when sessionId changes (with a small delay to ensure session is ready)
  useEffect(() => {
    if (!sessionId) {
      disconnect();
      return;
    }

    // Reset retry state for new session
    retriesRef.current = 0;
    reconnectDelayRef.current = WS_RECONNECT_DELAY;

    // Small delay to ensure session is fully created on backend
    const timeoutId = setTimeout(() => {
      connect();
    }, 100);

    return () => {
      clearTimeout(timeoutId);
      disconnect();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId]);

  // Heartbeat
  useEffect(() => {
    const interval = setInterval(sendPing, 30000);
    return () => clearInterval(interval);
  }, [sendPing]);

  return {
    isConnected: wsRef.current?.readyState === WebSocket.OPEN,
    connect,
    disconnect,
  };
}
