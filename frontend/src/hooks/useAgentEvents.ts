import { useCallback, useEffect, useRef } from 'react';
import { useAgentStore } from '@/store/agentStore';
import { useLayoutStore } from '@/store/layoutStore';
import { useAuthStore } from '@/store/authStore';
import { useSessionStore } from '@/store/sessionStore';
import type { AgentEvent } from '@/types/events';
import type { Message, TraceLog } from '@/types/agent';

const API_BASE = import.meta.env.DEV ? 'http://127.0.0.1:7860' : '';

/**
 * SSE-based hook for receiving agent events.
 * Only connects when session phase is 'ready' - guaranteeing the backend session exists.
 */
export function useAgentEvents() {
  const eventSourceRef = useRef<EventSource | null>(null);
  const currentSessionIdRef = useRef<string | null>(null);

  // Get phase from session store
  const phase = useSessionStore((s) => s.phase);
  const markActive = useSessionStore((s) => s.markActive);
  const markError = useSessionStore((s) => s.markError);

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
    setActiveJob,
    updateJobStatus,
  } = useAgentStore();

  const { setRightPanelOpen, setLeftSidebarOpen } = useLayoutStore();

  const handleEvent = useCallback(
    (event: AgentEvent) => {
      switch (event.event_type) {
        case 'connected':
          setConnected(true);
          break;

        case 'ready':
          setConnected(true);
          setProcessing(false);
          break;

        case 'processing':
          setProcessing(true);
          clearTraceLogs();
          setCurrentTurnMessageId(null);
          break;

        case 'assistant_message': {
          const content = (event.data?.content as string) || '';
          if (!content) break;

          const currentTurnMsgId = useAgentStore.getState().currentTurnMessageId;

          if (currentTurnMsgId) {
            const messages = useAgentStore.getState().messages;
            const existingMsg = messages.find(m => m.id === currentTurnMsgId);

            if (existingMsg) {
              const existingSegments = existingMsg.segments || [];
              const newContent = existingMsg.content + content;
              updateMessage(currentTurnMsgId, {
                content: newContent,
                segments: [...existingSegments, { type: 'text', content }],
              });
            }
          } else {
            const messageId = `msg_${Date.now()}`;
            const message: Message = {
              id: messageId,
              role: 'assistant',
              content,
              timestamp: new Date().toISOString(),
              segments: [{ type: 'text', content }],
            };
            addMessage(message);
            setCurrentTurnMessageId(messageId);
          }
          break;
        }

        case 'tool_call': {
          const toolName = (event.data?.tool as string) || 'unknown';
          const args = (event.data?.arguments as Record<string, any>) || {};

          if (toolName !== 'plan_tool') {
            const log: TraceLog = {
              id: `tool_${Date.now()}`,
              type: 'call',
              text: `Agent is executing ${toolName}...`,
              tool: toolName,
              timestamp: new Date().toISOString(),
              completed: false,
              args: toolName === 'hf_jobs' ? args : undefined,
            };

            addTraceLog(log);

            const currentTurnMsgId = useAgentStore.getState().currentTurnMessageId;
            const currentTrace = useAgentStore.getState().traceLogs;

            if (currentTurnMsgId) {
              const messages = useAgentStore.getState().messages;
              const existingMsg = messages.find(m => m.id === currentTurnMsgId);

              if (existingMsg) {
                const segments = existingMsg.segments ? [...existingMsg.segments] : [];
                const lastSegment = segments[segments.length - 1];

                if (lastSegment && lastSegment.type === 'tools') {
                  lastSegment.tools = [...currentTrace];
                } else {
                  segments.push({ type: 'tools', tools: [...currentTrace] });
                }

                updateMessage(currentTurnMsgId, { segments });
              }
            } else {
              const messageId = `msg_${Date.now()}`;
              const message: Message = {
                id: messageId,
                role: 'assistant',
                content: '',
                timestamp: new Date().toISOString(),
                segments: [{ type: 'tools', tools: [...currentTrace] }],
              };
              addMessage(message);
              setCurrentTurnMessageId(messageId);
            }
          }

          if (toolName === 'hf_jobs' && (args.operation === 'run' || args.operation === 'scheduled run') && args.script) {
            setActiveJob(null);
            clearPanelTabs();
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

          console.log('[SSE] Tool call:', toolName, args);
          break;
        }

        case 'tool_output': {
          const toolName = (event.data?.tool as string) || 'unknown';
          const output = (event.data?.output as string) || '';
          const success = event.data?.success as boolean;

          updateTraceLog(toolName, { completed: true, output, success });

          const currentTurnMsgId = useAgentStore.getState().currentTurnMessageId;
          const currentTrace = useAgentStore.getState().traceLogs;

          if (currentTurnMsgId) {
            const messages = useAgentStore.getState().messages;
            const existingMsg = messages.find(m => m.id === currentTurnMsgId);

            if (existingMsg && existingMsg.segments) {
              const segments = existingMsg.segments.map(seg => {
                if (seg.type === 'tools') {
                  return { ...seg, tools: [...currentTrace] };
                }
                return seg;
              });
              updateMessage(currentTurnMsgId, { segments });
            }
          }

          if (toolName === 'hf_jobs') {
            const turnMsgId = useAgentStore.getState().currentTurnMessageId;

            if (turnMsgId) {
              const messages = useAgentStore.getState().messages;
              const currentMsg = messages.find(m => m.id === turnMsgId);
              const currentOutput = currentMsg?.toolOutput || '';
              const newOutput = currentOutput ? currentOutput + '\n\n' + output : output;

              updateMessage(turnMsgId, { toolOutput: newOutput });
            } else {
              const messages = useAgentStore.getState().messages;
              const jobMsg = [...messages].reverse().find(m => m.approval);

              if (jobMsg) {
                const currentOutput = jobMsg.toolOutput || '';
                const newOutput = currentOutput ? currentOutput + '\n\n' + output : output;
                updateMessage(jobMsg.id, { toolOutput: newOutput });
              } else {
                const traceLogs = useAgentStore.getState().traceLogs;
                const jobTrace = [...traceLogs].reverse().find(t => t.tool === 'hf_jobs');
                const traceArgs = jobTrace?.args || {};

                const messageId = `msg_${Date.now()}`;
                const autoExecMessage: Message = {
                  id: messageId,
                  role: 'assistant',
                  content: '',
                  timestamp: new Date().toISOString(),
                  approval: {
                    status: 'approved',
                    batch: {
                      tools: [{
                        tool: toolName,
                        arguments: traceArgs,
                        tool_call_id: `auto_${Date.now()}`
                      }],
                      count: 1
                    }
                  },
                  toolOutput: output
                };
                addMessage(autoExecMessage);
                setCurrentTurnMessageId(messageId);
              }
            }
          }

          console.log('[SSE] Tool output:', toolName, success);
          break;
        }

        case 'tool_log': {
          const toolName = (event.data?.tool as string) || 'unknown';
          const log = (event.data?.log as string) || '';

          if (toolName === 'hf_jobs') {
            const currentTabs = useAgentStore.getState().panelTabs;
            const logsTab = currentTabs.find(t => t.id === 'logs');

            const newContent = logsTab
              ? logsTab.content + '\n' + log
              : log;

            setPanelTab({
              id: 'logs',
              title: 'Logs',
              content: newContent,
              language: 'text'
            });

            setActivePanelTab('logs');

            if (!useLayoutStore.getState().isRightPanelOpen) {
              setRightPanelOpen(true);
            }
          }
          break;
        }

        case 'job_started': {
          const jobId = (event.data?.job_id as string) || '';
          const url = (event.data?.url as string) || '';
          const hardware = (event.data?.hardware as string) || 'cpu-basic';
          const isGpu = (event.data?.is_gpu as boolean) || false;

          setActiveJob({
            jobId,
            url,
            status: isGpu ? 'queued' : 'pending',
            hardware,
            isGpu,
            submittedAt: new Date().toISOString(),
            statusMessage: isGpu ? 'Waiting for GPU resources...' : 'Starting job...',
          });

          setPanelTab({
            id: 'logs',
            title: 'Logs',
            content: '',
            language: 'text'
          });

          setActivePanelTab('logs');
          if (!useLayoutStore.getState().isRightPanelOpen) {
            setRightPanelOpen(true);
          }
          break;
        }

        case 'job_status': {
          const status = (event.data?.status as string) || '';
          const message = (event.data?.message as string) || '';

          const statusMap: Record<string, 'queued' | 'pending' | 'running' | 'completed' | 'failed' | 'canceled' | 'error'> = {
            'queued': 'queued',
            'pending': 'pending',
            'running': 'running',
            'completed': 'completed',
            'failed': 'failed',
            'canceled': 'canceled',
            'error': 'error',
          };

          const mappedStatus = statusMap[status.toLowerCase()] || 'pending';
          updateJobStatus(mappedStatus, message);

          if (['completed', 'failed', 'canceled', 'error'].includes(mappedStatus)) {
            setTimeout(() => {
              const currentJob = useAgentStore.getState().activeJob;
              if (currentJob && ['completed', 'failed', 'canceled', 'error'].includes(currentJob.status)) {
                setActiveJob(null);
              }
            }, 3000);
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

          const currentTurnMsgId = useAgentStore.getState().currentTurnMessageId;
          const approvalData = {
            status: 'pending' as const,
            batch: { tools, count }
          };

          if (currentTurnMsgId) {
            updateMessage(currentTurnMsgId, { approval: approvalData });
          } else {
            const messageId = `msg_${Date.now()}`;
            const message: Message = {
              id: messageId,
              role: 'assistant',
              content: '',
              timestamp: new Date().toISOString(),
              approval: approvalData,
            };
            addMessage(message);
            setCurrentTurnMessageId(messageId);
          }

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
                parameters: { ...args, tool_call_id: firstTool.tool_call_id }
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
                parameters: { ...args, tool_call_id: firstTool.tool_call_id }
              });
              setActivePanelTab('content');
            } else {
              setPanelTab({
                id: 'args',
                title: firstTool.tool,
                content: JSON.stringify(args, null, 2),
                language: 'json',
                parameters: { ...args, tool_call_id: firstTool.tool_call_id }
              });
              setActivePanelTab('args');
            }

            setRightPanelOpen(true);
            setLeftSidebarOpen(false);
          }

          setPendingApprovals(null);
          setProcessing(false);
          break;
        }

        case 'turn_complete':
          setProcessing(false);
          break;

        case 'compacted': {
          const oldTokens = event.data?.old_tokens as number;
          const newTokens = event.data?.new_tokens as number;
          console.log(`[SSE] Context compacted: ${oldTokens} -> ${newTokens} tokens`);
          break;
        }

        case 'error': {
          const errorMsg = (event.data?.error as string) || 'Unknown error';
          setError(errorMsg);
          setProcessing(false);
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
          break;

        case 'server_shutdown': {
          const message = event.data?.message as string;
          console.warn('[SSE] Server shutdown:', message);
          setError(message || 'Server is shutting down');
          setConnected(false);
          break;
        }

        default:
          console.log('[SSE] Unknown event:', event);
      }
    },
    []
  );

  // Main effect: connect SSE when phase is 'ready', keep alive when 'active'
  useEffect(() => {
    const isReadyOrActive = phase.status === 'ready' || phase.status === 'active';
    const sessionId = phase.status === 'ready' ? phase.sessionId :
                      phase.status === 'active' ? phase.sessionId : null;

    // If not ready/active, close any existing connection
    if (!isReadyOrActive) {
      if (eventSourceRef.current) {
        console.log('[SSE] Closing connection (phase:', phase.status, ')');
        eventSourceRef.current.close();
        eventSourceRef.current = null;
        currentSessionIdRef.current = null;
        setConnected(false);
      }
      return;
    }

    // Already connected to this session - do nothing
    if (currentSessionIdRef.current === sessionId && eventSourceRef.current) {
      return;
    }

    // Only initiate new connection when phase is 'ready' (not 'active')
    if (phase.status !== 'ready') {
      return;
    }

    // Close existing connection if connecting to different session
    if (eventSourceRef.current) {
      console.log('[SSE] Closing previous connection');
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }

    const token = useAuthStore.getState().token;
    const tokenParam = token ? `?token=${encodeURIComponent(token)}` : '';
    const sseUrl = `${API_BASE}/api/events/${sessionId}${tokenParam}`;

    console.log('[SSE] Connecting to session:', sessionId);

    const eventSource = new EventSource(sseUrl);

    eventSource.onopen = () => {
      console.log('[SSE] Connected successfully');
      currentSessionIdRef.current = sessionId;
      setConnected(true);
      markActive(); // Transition: ready -> active
    };

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data) as AgentEvent;
        handleEvent(data);
      } catch (e) {
        console.error('[SSE] Failed to parse message:', e);
      }
    };

    eventSource.onerror = (error) => {
      console.error('[SSE] Connection error:', error);
      setConnected(false);

      // If connection failed and we never opened, mark as error
      if (eventSource.readyState === EventSource.CLOSED) {
        markError('Failed to connect to session');
        currentSessionIdRef.current = null;
      }
    };

    eventSourceRef.current = eventSource;

    // Only cleanup on unmount, not on phase changes
    // Phase changes are handled at the top of the effect
  }, [phase, handleEvent, setConnected, markActive, markError]);

  // Separate cleanup effect for unmount only
  useEffect(() => {
    return () => {
      if (eventSourceRef.current) {
        console.log('[SSE] Unmount: closing connection');
        eventSourceRef.current.close();
        eventSourceRef.current = null;
        currentSessionIdRef.current = null;
      }
    };
  }, []);

  return {
    isConnected: useAgentStore((s) => s.isConnected),
  };
}
