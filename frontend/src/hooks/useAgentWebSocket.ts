import { useCallback, useEffect, useRef } from 'react';
import { useAgentStore } from '@/store/agentStore';
import { useSessionStore } from '@/store/sessionStore';
import type { AgentEvent } from '@/types/events';
import type { Message } from '@/types/agent';

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
    setProcessing,
    setConnected,
    setPendingApprovals,
    setError,
  } = useAgentStore();

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
          break;

        case 'assistant_message': {
          const content = (event.data?.content as string) || '';
          const message: Message = {
            id: `msg_${Date.now()}`,
            role: 'assistant',
            content,
            timestamp: new Date().toISOString(),
          };
          addMessage(sessionId, message);
          break;
        }

        case 'tool_call': {
          const toolName = (event.data?.tool as string) || 'unknown';
          const args = event.data?.arguments || {};
          const message: Message = {
            id: `tool_${Date.now()}`,
            role: 'tool',
            content: `Calling ${toolName}...`,
            timestamp: new Date().toISOString(),
            toolName,
          };
          addMessage(sessionId, message);
          // Store tool call args for display
          console.log('Tool call:', toolName, args);
          break;
        }

        case 'tool_output': {
          const toolName = (event.data?.tool as string) || 'unknown';
          const output = (event.data?.output as string) || '';
          const success = event.data?.success as boolean;
          const message: Message = {
            id: `tool_out_${Date.now()}`,
            role: 'tool',
            content: output,
            timestamp: new Date().toISOString(),
            toolName,
          };
          addMessage(sessionId, message);
          console.log('Tool output:', toolName, success);
          break;
        }

        case 'approval_required': {
          const tools = event.data?.tools as Array<{
            tool: string;
            arguments: Record<string, unknown>;
            tool_call_id: string;
          }>;
          const count = (event.data?.count as number) || 0;
          setPendingApprovals({ tools, count });
          setProcessing(false);
          break;
        }

        case 'turn_complete':
          setProcessing(false);
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
