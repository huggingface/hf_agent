/**
 * Agent-related types
 */

export interface SessionMeta {
  id: string;
  title: string;
  createdAt: string;
  isActive: boolean;
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
}

export interface ApprovalBatch {
  tools: Array<{
    tool: string;
    arguments: Record<string, unknown>;
    tool_call_id: string;
  }>;
  count: number;
}

export type ApprovalStatus = 'none' | 'pending' | 'approved' | 'rejected';

export interface TraceLog {
  id: string;
  toolCallId?: string; // Backend tool_call_id for reliable matching
  type: 'call' | 'output';
  text: string;
  tool: string;
  timestamp: string;
  completed?: boolean;
  args?: Record<string, unknown>; // Store args for auto-exec jobs
  output?: string; // Store tool output for display
  success?: boolean; // Whether the tool call succeeded
  /** Approval state for tools that need user confirmation */
  approvalStatus?: ApprovalStatus;
  /** Parsed job info (URL, status, logs) for hf_jobs */
  jobUrl?: string;
  jobStatus?: string;
  jobLogs?: string;
}

export interface User {
  authenticated: boolean;
  username?: string;
  name?: string;
  picture?: string;
}
