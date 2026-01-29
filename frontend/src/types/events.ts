/**
 * Event types from the agent backend
 */

export type EventType =
  | 'connected'  // SSE connection established
  | 'ready'
  | 'processing'
  | 'stream_chunk'  // Streaming text chunk from LLM
  | 'assistant_message'
  | 'tool_call'
  | 'tool_output'
  | 'tool_log'
  | 'job_started'  // HF job submitted successfully
  | 'job_status'   // HF job status update
  | 'approval_required'
  | 'turn_complete'
  | 'compacted'
  | 'error'
  | 'shutdown'
  | 'interrupted'
  | 'undo_complete'
  | 'plan_update'
  | 'server_shutdown';

export interface AgentEvent {
  event_type: EventType;
  data?: Record<string, unknown>;
}

export interface ReadyEventData {
  message: string;
}

export interface ProcessingEventData {
  message: string;
}

export interface AssistantMessageEventData {
  content: string;
}

export interface StreamChunkEventData {
  content: string;
}

export interface ToolCallEventData {
  tool: string;
  arguments: Record<string, unknown>;
}

export interface ToolOutputEventData {
  tool: string;
  output: string;
  success: boolean;
}

export interface ToolLogEventData {
  tool: string;
  log: string;
}

export interface JobStartedEventData {
  job_id: string;
  url: string;
  hardware: string;
  is_gpu: boolean;
}

export interface JobStatusEventData {
  status: string;
  message: string;
}

export interface PlanUpdateEventData {
  plan: Array<{ id: string; content: string; status: 'pending' | 'in_progress' | 'completed' }>;
}

export interface ApprovalRequiredEventData {
  tools: ApprovalToolItem[];
  count: number;
}

export interface ApprovalToolItem {
  tool: string;
  arguments: Record<string, unknown>;
  tool_call_id: string;
}

export interface TurnCompleteEventData {
  history_size: number;
}

export interface CompactedEventData {
  old_tokens: number;
  new_tokens: number;
}

export interface ErrorEventData {
  error: string;
}

export interface ServerShutdownEventData {
  message: string;
}
