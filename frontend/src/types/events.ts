/**
 * Event types from the agent backend
 */

export type EventType =
  | 'ready'
  | 'processing'
  | 'assistant_message'
  | 'tool_call'
  | 'tool_output'
  | 'tool_log'
  | 'approval_required'
  | 'turn_complete'
  | 'compacted'
  | 'error'
  | 'shutdown'
  | 'interrupted'
  | 'undo_complete'
  | 'plan_update'
  // New events for multi-user/persistence
  | 'session_sync'
  | 'tab_conflict'
  | 'tab_joined'
  | 'tab_left'
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

// New event data types for multi-user/persistence
export interface SessionSyncEventData {
  last_synced: string;
  pending_count: number;
}

export interface TabConflictEventData {
  conflicting_tab: string;
}

export interface TabJoinedEventData {
  tab_id: string;
  total_tabs: number;
}

export interface TabLeftEventData {
  tab_id: string;
  total_tabs: number;
}

export interface ServerShutdownEventData {
  message: string;
}
