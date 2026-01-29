/**
 * Agent-related types
 */

export interface Session {
  id: string;
  title: string;
  createdAt: string;
  messageCount: number;
}

export interface MessageSegment {
  type: 'text' | 'tools';
  content?: string;
  tools?: TraceLog[];
}

export interface Message {
  id: string;
  role: 'user' | 'assistant' | 'tool';
  content: string;
  timestamp: string;
  segments?: MessageSegment[];
  approval?: {
    status: 'pending' | 'approved' | 'rejected';
    batch: ApprovalBatch;
    decisions?: ToolApproval[];
  };
  toolOutput?: string;
}

export interface ToolCall {
  id: string;
  tool: string;
  arguments: Record<string, unknown>;
  status: 'pending' | 'running' | 'completed' | 'failed';
  output?: string;
}

export interface ToolApproval {
  tool_call_id: string;
  approved: boolean;
  feedback?: string | null;
  modified_arguments?: Record<string, unknown>;  // For edited scripts
}

export interface ApprovalBatch {
  tools: Array<{
    tool: string;
    arguments: Record<string, unknown>;
    tool_call_id: string;
  }>;
  count: number;
}

export interface TraceLog {
  id: string;
  type: 'call' | 'output';
  text: string;
  tool: string;
  timestamp: string;
  completed?: boolean;
  args?: Record<string, unknown>; // Store args for auto-exec jobs
  output?: string; // Store tool output for display
  success?: boolean; // Whether the tool call succeeded
}

export interface User {
  authenticated: boolean;
  user_id?: string;
  username?: string;
  name?: string;
  picture?: string;
  has_anthropic_key?: boolean;
}

export interface AuthState {
  token: string | null;
  user: User | null;
  isLoading: boolean;
}
