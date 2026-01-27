import { useCallback, useEffect, useRef } from 'react';
import { useAgentStore } from '@/store/agentStore';
import { useSessionStore } from '@/store/sessionStore';
import { useLayoutStore } from '@/store/layoutStore';
import type { AgentEvent } from '@/types/events';
import type { Message, TraceLog } from '@/types/agent';

const WS_RECONNECT_DELAY = 1000;
const WS_MAX_RECONNECT_DELAY = 30000;

interface UseAgentWebSocketOptions {
  sessionId: string | null;
  onReady?: () => void;
  onError?: (error: string) => void;
}

export function useAgentWebSocket({
  sessionId,
  onReady,
  onError,
}: UseAgentWebSocketOptions) {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<number | null>(null);
  const reconnectDelayRef = useRef(WS_RECONNECT_DELAY);

  const {
    addMessage,
    updateMessage,
    setProcessing,
    setConnected,
    setPendingApprovals,
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
          const args = (event.data?.arguments as Record<string, any>) || {};

          // Don't display plan_tool in trace logs (it shows up elsewhere in the UI)
          if (toolName !== 'plan_tool') {
            const log: TraceLog = {
              id: `tool_${Date.now()}`,
              type: 'call',
              text: `Agent is executing ${toolName}...`,
              tool: toolName,
              timestamp: new Date().toISOString(),
              completed: false,
              // Store args for auto-exec message creation later
              args: toolName === 'hf_jobs' ? args : undefined,
            };
            addTraceLog(log);
            // Update the current turn message's trace in real-time
            updateCurrentTurnTrace(sessionId);
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

          console.log('Tool call:', toolName, args);
          break;
        }

        case 'tool_output': {
          const toolName = (event.data?.tool as string) || 'unknown';
          const output = (event.data?.output as string) || '';
          const success = event.data?.success as boolean;

          // Mark the corresponding trace log as completed and store the output
          updateTraceLog(toolName, { completed: true, output, success });
          // Update the current turn message's trace in real-time
          updateCurrentTurnTrace(sessionId);

          // Special handling for hf_jobs - update or create job message with output
          if (toolName === 'hf_jobs') {
            const messages = useAgentStore.getState().getMessages(sessionId);
            const traceLogs = useAgentStore.getState().traceLogs;

            // Find existing approval message for this job
            let jobMsg = [...messages].reverse().find(m => m.approval);

            if (!jobMsg) {
              // No approval message exists - this was an auto-executed job
              // Create a job execution message so user can see results
              const jobTrace = [...traceLogs].reverse().find(t => t.tool === 'hf_jobs');
              const args = jobTrace?.args || {};

              const autoExecMessage: Message = {
                id: `msg_auto_${Date.now()}`,
                role: 'assistant',
                content: '',
                timestamp: new Date().toISOString(),
                approval: {
                  status: 'approved', // Auto-approved (no user action needed)
                  batch: {
                    tools: [{
                      tool: toolName,
                      arguments: args,
                      tool_call_id: `auto_${Date.now()}`
                    }],
                    count: 1
                  }
                },
                toolOutput: output
              };
              addMessage(sessionId, autoExecMessage);
              console.log('Created auto-exec message with tool output:', toolName);
            } else {
              // Update existing approval message
              const currentOutput = jobMsg.toolOutput || '';
              const newOutput = currentOutput ? currentOutput + '\n\n' + output : output;

              useAgentStore.getState().updateMessage(sessionId, jobMsg.id, {
                toolOutput: newOutput
              });
              console.log('Updated job message with tool output:', toolName);
            }
          }

          // Don't create message bubbles for tool outputs - they only show in trace logs
          console.log('Tool output:', toolName, success);
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
          const plan = (event.data?.plan as any[]) || [];
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
          const count = (event.data?.count as number) || 0;

          // Create a persistent message for the approval request
          const message: Message = {
            id: `msg_approval_${Date.now()}`,
            role: 'assistant',
            content: '', // Content is handled by the approval UI
            timestamp: new Date().toISOString(),
            approval: {
                status: 'pending',
                batch: { tools, count }
            }
          };
          addMessage(sessionId, message);

          // Show the first tool's content in the panel so users see what they're approving
          if (tools && tools.length > 0) {
            const firstTool = tools[0];
            const args = firstTool.arguments as Record<string, any>;

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
              // For other tools, show args as JSON
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

          // Clear currentTurnMessageId so subsequent assistant_message events create a new message below the approval
          setCurrentTurnMessageId(null);

          // We don't set pendingApprovals in the global store anymore as the message handles the UI
          setPendingApprovals(null);
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
          console.log(`Context compacted: ${oldTokens} -> ${newTokens} tokens`);
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
          // Could remove last messages from store
          break;

        default:
          console.log('Unknown event:', event);
      }
    },
    // Zustand setters are stable, so we don't need them in deps
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [sessionId, onReady, onError]
  );

  const connect = useCallback(() => {
    if (!sessionId) return;
    
    // Don't connect if already connected or connecting
    if (wsRef.current?.readyState === WebSocket.OPEN || 
        wsRef.current?.readyState === WebSocket.CONNECTING) {
      return;
    }

    // Connect directly to backend (Vite doesn't proxy WebSockets)
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    // In development, connect directly to backend port 7860
    // In production, use the same host
    const isDev = import.meta.env.DEV;
    const host = isDev ? '127.0.0.1:7860' : window.location.host;
    const wsUrl = `${protocol}//${host}/api/ws/${sessionId}`;

    console.log('Connecting to WebSocket:', wsUrl);
    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      console.log('WebSocket connected');
      setConnected(true);
      reconnectDelayRef.current = WS_RECONNECT_DELAY;
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data) as AgentEvent;
        handleEvent(data);
      } catch (e) {
        console.error('Failed to parse WebSocket message:', e);
      }
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
    };

    ws.onclose = (event) => {
      console.log('WebSocket closed', event.code, event.reason);
      setConnected(false);

      // Only reconnect if it wasn't a normal closure and session still exists
      if (event.code !== 1000 && sessionId) {
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
