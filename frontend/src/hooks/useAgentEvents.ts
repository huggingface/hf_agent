import { useCallback, useEffect, useRef } from 'react';
import { useAgentStore } from '@/store/agentStore';
import { useLayoutStore } from '@/store/layoutStore';
import { useAuthStore } from '@/store/authStore';
import type { AgentEvent } from '@/types/events';
import type { Message, TraceLog } from '@/types/agent';

const API_BASE = import.meta.env.DEV ? 'http://127.0.0.1:7860' : '';

interface UseAgentEventsOptions {
  sessionId: string | null;
  onReady?: () => void;
  onError?: (error: string) => void;
}

/**
 * SSE-based hook for receiving agent events.
 * EventSource auto-reconnects on connection loss.
 */
export function useAgentEvents({
  sessionId,
  onReady,
  onError,
}: UseAgentEventsOptions) {
  const eventSourceRef = useRef<EventSource | null>(null);
  const isConnectingRef = useRef(false);

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
      if (!sessionId) return;

      switch (event.event_type) {
        case 'connected':
          // Initial SSE connection established
          setConnected(true);
          break;

        case 'ready':
          setConnected(true);
          setProcessing(false);
          onReady?.();
          break;

        case 'processing':
          setProcessing(true);
          clearTraceLogs();
          setCurrentTurnMessageId(null);
          break;

        case 'assistant_message': {
          const content = (event.data?.content as string) || '';
          if (!content) break; // No text content, nothing to add

          const currentTurnMsgId = useAgentStore.getState().currentTurnMessageId;

          if (currentTurnMsgId) {
            // Add text segment to existing message
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
            // Create new message with text segment
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

            // Add tool to traceLogs for reference
            addTraceLog(log);

            // Immediately add/update tools segment in current message
            const currentTurnMsgId = useAgentStore.getState().currentTurnMessageId;
            const currentTrace = useAgentStore.getState().traceLogs;

            if (currentTurnMsgId) {
              // Add to existing message's tools segment
              const messages = useAgentStore.getState().messages;
              const existingMsg = messages.find(m => m.id === currentTurnMsgId);

              if (existingMsg) {
                const segments = existingMsg.segments ? [...existingMsg.segments] : [];
                const lastSegment = segments[segments.length - 1];

                if (lastSegment && lastSegment.type === 'tools') {
                  // Append to existing tools segment
                  lastSegment.tools = [...currentTrace];
                } else {
                  // Create new tools segment
                  segments.push({ type: 'tools', tools: [...currentTrace] });
                }

                updateMessage(currentTurnMsgId, { segments });
              }
            } else {
              // No message yet - create one with tools segment
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
            // Clear previous job state when starting a new job
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

          console.log('Tool call:', toolName, args);
          break;
        }

        case 'tool_output': {
          const toolName = (event.data?.tool as string) || 'unknown';
          const output = (event.data?.output as string) || '';
          const success = event.data?.success as boolean;

          // Update the trace log
          updateTraceLog(toolName, { completed: true, output, success });

          // Update the tools segment in current message to reflect completion
          const currentTurnMsgId = useAgentStore.getState().currentTurnMessageId;
          const currentTrace = useAgentStore.getState().traceLogs;

          if (currentTurnMsgId) {
            const messages = useAgentStore.getState().messages;
            const existingMsg = messages.find(m => m.id === currentTurnMsgId);

            if (existingMsg && existingMsg.segments) {
              // Find and update the tools segment with updated trace logs
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
            const currentTurnMsgId = useAgentStore.getState().currentTurnMessageId;

            if (currentTurnMsgId) {
              // Update current turn message with job output
              const messages = useAgentStore.getState().messages;
              const currentMsg = messages.find(m => m.id === currentTurnMsgId);
              const currentOutput = currentMsg?.toolOutput || '';
              const newOutput = currentOutput ? currentOutput + '\n\n' + output : output;

              updateMessage(currentTurnMsgId, { toolOutput: newOutput });
              console.log('Updated current turn message with job output:', toolName);
            } else {
              // Fallback: look for recent message with approval or create new one
              const messages = useAgentStore.getState().messages;
              const jobMsg = [...messages].reverse().find(m => m.approval);

              if (jobMsg) {
                const currentOutput = jobMsg.toolOutput || '';
                const newOutput = currentOutput ? currentOutput + '\n\n' + output : output;
                updateMessage(jobMsg.id, { toolOutput: newOutput });
                console.log('Updated approval message with job output:', toolName);
              } else {
                // Last resort: create new message (shouldn't happen with new flow)
                const traceLogs = useAgentStore.getState().traceLogs;
                const jobTrace = [...traceLogs].reverse().find(t => t.tool === 'hf_jobs');
                const args = jobTrace?.args || {};

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
                        arguments: args,
                        tool_call_id: `auto_${Date.now()}`
                      }],
                      count: 1
                    }
                  },
                  toolOutput: output
                };
                addMessage(autoExecMessage);
                setCurrentTurnMessageId(messageId);
                console.log('Created auto-exec message with tool output:', toolName);
              }
            }
          }

          console.log('Tool output:', toolName, success);
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

          // Set the active job - this will show the JobStatusHeader
          setActiveJob({
            jobId,
            url,
            status: isGpu ? 'queued' : 'pending',
            hardware,
            isGpu,
            submittedAt: new Date().toISOString(),
            statusMessage: isGpu ? 'Waiting for GPU resources...' : 'Starting job...',
          });

          // Create logs tab with initial empty content
          setPanelTab({
            id: 'logs',
            title: 'Logs',
            content: '',
            language: 'text'
          });

          // Switch to logs tab and open panel
          setActivePanelTab('logs');
          if (!useLayoutStore.getState().isRightPanelOpen) {
            setRightPanelOpen(true);
          }
          break;
        }

        case 'job_status': {
          const status = (event.data?.status as string) || '';
          const message = (event.data?.message as string) || '';

          // Map backend status to frontend status type
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

          // Clear active job when job completes - wait 3 seconds so user can see final status
          if (['completed', 'failed', 'canceled', 'error'].includes(mappedStatus)) {
            setTimeout(() => {
              // Only clear if this is still the same job and still in terminal state
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
            // Add approval to existing turn message
            updateMessage(currentTurnMsgId, { approval: approvalData });
          } else {
            // No message yet - create one with approval (shouldn't happen with new flow)
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

          // Don't reset currentTurnMessageId - keep accumulating into same blob
          setPendingApprovals(null);
          setProcessing(false);
          break;
        }

        case 'turn_complete':
          setProcessing(false);
          // Don't reset currentTurnMessageId here - keep accumulating into same message
          // until user sends a new message (reset happens in 'processing' event)
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
          break;

        case 'server_shutdown': {
          const message = event.data?.message as string;
          console.warn('Server shutdown:', message);
          setError(message || 'Server is shutting down');
          setConnected(false);
          break;
        }

        default:
          console.log('Unknown event:', event);
      }
    },
    [sessionId, onReady, onError]
  );

  const connect = useCallback(() => {
    if (!sessionId) return;

    // Prevent duplicate connections
    if (isConnectingRef.current || eventSourceRef.current?.readyState === EventSource.OPEN) {
      return;
    }

    isConnectingRef.current = true;

    // Close existing connection if any
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }

    // Build SSE URL
    const token = useAuthStore.getState().token;
    const tokenParam = token ? `?token=${encodeURIComponent(token)}` : '';
    const sseUrl = `${API_BASE}/api/events/${sessionId}${tokenParam}`;

    console.log('Connecting to SSE:', sseUrl.replace(/token=[^&]+/, 'token=***'));

    const eventSource = new EventSource(sseUrl);

    eventSource.onopen = () => {
      console.log('SSE connected');
      isConnectingRef.current = false;
      setConnected(true);
    };

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data) as AgentEvent;
        handleEvent(data);
      } catch (e) {
        console.error('Failed to parse SSE message:', e);
      }
    };

    eventSource.onerror = (error) => {
      console.error('SSE error:', error);
      isConnectingRef.current = false;
      setConnected(false);
      // EventSource auto-reconnects, but we should track state
    };

    eventSourceRef.current = eventSource;
  }, [sessionId, handleEvent, setConnected]);

  const disconnect = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
      setConnected(false);
    }
  }, [setConnected]);

  // Connect when sessionId changes
  // eslint-disable-next-line react-hooks/exhaustive-deps
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
  }, [sessionId]); // Only reconnect when sessionId changes

  return {
    isConnected: eventSourceRef.current?.readyState === EventSource.OPEN,
    connect,
    disconnect,
  };
}
