/**
 * Convert backend LLM messages (litellm format) to Vercel AI SDK UIMessage format.
 */
import type { UIMessage } from 'ai';

const USAGE_THRESHOLD_TOOL_NAME = 'usage_threshold';
const YOLO_BUDGET_TOOL_NAME = 'yolo_budget';

interface LLMToolCall {
  id: string;
  function: { name: string; arguments: string };
}

interface LLMMessage {
  role: 'user' | 'assistant' | 'tool' | 'system';
  content: string | null;
  tool_calls?: LLMToolCall[] | null;
  tool_call_id?: string | null;
  name?: string | null;
}

export interface PendingApprovalItem {
  tool: string;
  tool_call_id: string;
  arguments: Record<string, unknown>;
}

// Generate stable IDs based on message position to prevent duplicate renders
// when the same message is re-converted multiple times (e.g., during polling)
let uiMessageCounter = 0;
function nextId(): string {
  return `msg-${++uiMessageCounter}`;
}

/**
 * @param pendingApprovalIds - Set of tool_call_ids that are waiting for approval.
 *   When provided, matching tool calls without results will get state
 *   'approval-requested' instead of 'input-available'.
 * @param existingUIMessages - Current UI messages to preserve IDs when content matches.
 *   This prevents React from re-rendering messages with new IDs during polling.
 */
export function llmMessagesToUIMessages(
  messages: LLMMessage[],
  pendingApprovalIds?: Set<string>,
  existingUIMessages?: UIMessage[],
  pendingApprovalItems?: PendingApprovalItem[],
): UIMessage[] {
  // Build a map of tool_call_id -> tool result for pairing
  const toolResults = new Map<string, { output: string; isError: boolean }>();
  const restoredPendingIds = new Set<string>();
  for (const msg of messages) {
    if (msg.role === 'tool' && msg.tool_call_id) {
      toolResults.set(msg.tool_call_id, {
        output: msg.content || '',
        isError: false,
      });
    }
  }

  const uiMessages: UIMessage[] = [];

  // Helper to get existing message ID at a given position if roles match
  const getExistingId = (
    index: number,
    role: 'user' | 'assistant',
    expectedText?: string,
  ): string | null => {
    if (!existingUIMessages || index >= existingUIMessages.length) return null;
    const existing = existingUIMessages[index];
    if (existing.role !== role) return null;
    if (expectedText === undefined) return existing.id;

    const existingText = joinText(existing.parts);
    if (role === 'user') return existingText === expectedText ? existing.id : null;
    return existingText.startsWith(expectedText) ? existing.id : null;
  };
  const getExistingPendingToolMessageId = (toolCallId: string): string | null => {
    for (const existing of existingUIMessages || []) {
      if (existing.role !== 'assistant') continue;
      const hasTool = existing.parts.some(
        (part) =>
          part.type === 'dynamic-tool' &&
          part.toolCallId === toolCallId,
      );
      if (hasTool) return existing.id;
    }
    return null;
  };

  for (const msg of messages) {
    if (msg.role === 'system') continue;
    if (msg.role === 'tool') continue; // handled via tool_calls pairing

    if (msg.role === 'user') {
      // Skip internal system-style nudges (doom-loop correction, compact
      // hints, restore notices, etc.) — they're meant for the LLM, not
      // the user. They always start with "[SYSTEM:".
      if (typeof msg.content === 'string' && msg.content.trimStart().startsWith('[SYSTEM:')) {
        continue;
      }
      // Try to reuse existing ID if the message at this position matches
      const content = msg.content || '';
      const existingId = getExistingId(uiMessages.length, 'user', content);
      uiMessages.push({
        id: existingId || nextId(),
        role: 'user',
        parts: [{ type: 'text', text: content }],
      });
      continue;
    }

    if (msg.role === 'assistant') {
      const parts: UIMessage['parts'] = [];

      if (msg.content) {
        parts.push({ type: 'text', text: msg.content });
      }

      if (msg.tool_calls) {
        for (const tc of msg.tool_calls) {
          let input: Record<string, unknown> = {};
          try {
            input = JSON.parse(tc.function.arguments);
          } catch { /* malformed */ }

          const result = toolResults.get(tc.id);
          if (result) {
            parts.push({
              type: 'dynamic-tool',
              toolCallId: tc.id,
              toolName: tc.function.name,
              state: 'output-available',
              input,
              output: result.output,
            });
          } else if (pendingApprovalIds?.has(tc.id)) {
            restoredPendingIds.add(tc.id);
            parts.push({
              type: 'dynamic-tool',
              toolCallId: tc.id,
              toolName: tc.function.name,
              state: 'approval-requested',
              input,
              approval: { id: `approval-${tc.id}` },
            });
          } else {
            parts.push({
              type: 'dynamic-tool',
              toolCallId: tc.id,
              toolName: tc.function.name,
              state: 'input-available',
              input,
            });
          }
        }
      }

      // During live streaming the SDK groups all text + tool parts between
      // user messages into one assistant UIMessage (one start/finish pair per
      // turn).  The backend stores multiple assistant messages per turn (one
      // per LLM API call), so merge consecutive assistant messages to match.
      const prev = uiMessages[uiMessages.length - 1];
      if (prev && prev.role === 'assistant') {
        prev.parts.push(...parts);
      } else {
        // Try to reuse existing ID if the message at this position matches
        const expectedText = joinText(parts);
        const existingId = getExistingId(
          uiMessages.length,
          'assistant',
          expectedText,
        );
        const newId = existingId || nextId();
        uiMessages.push({
          id: newId,
          role: 'assistant',
          parts,
        });
      }
    }
  }

  for (const pending of pendingApprovalItems || []) {
    if (
      ![USAGE_THRESHOLD_TOOL_NAME, YOLO_BUDGET_TOOL_NAME].includes(pending.tool) ||
      restoredPendingIds.has(pending.tool_call_id)
    ) {
      continue;
    }
    const id = getExistingPendingToolMessageId(pending.tool_call_id) || nextId();
    uiMessages.push({
      id,
      role: 'assistant',
      parts: [
        {
          type: 'dynamic-tool',
          toolCallId: pending.tool_call_id,
          toolName: pending.tool,
          state: 'approval-requested',
          input: pending.arguments || {},
          approval: { id: `approval-${pending.tool_call_id}` },
        },
      ],
    });
  }

  return uiMessages;
}

function joinText(parts: UIMessage['parts']): string {
  return parts
    .filter((p): p is { type: 'text'; text: string } => p.type === 'text')
    .map((p) => p.text)
    .join('');
}
