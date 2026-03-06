/**
 * Convert backend LLM messages (litellm format) to Vercel AI SDK UIMessage format.
 */
import type { UIMessage } from 'ai';

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

let idCounter = 0;
function nextId(): string {
  return `msg-${Date.now()}-${++idCounter}`;
}

/**
 * @param pendingApprovalIds - Set of tool_call_ids that are waiting for approval.
 *   When provided, matching tool calls without results will get state
 *   'approval-requested' instead of 'input-available'.
 */
export function llmMessagesToUIMessages(
  messages: LLMMessage[],
  pendingApprovalIds?: Set<string>,
): UIMessage[] {
  // Build a map of tool_call_id -> tool result for pairing
  const toolResults = new Map<string, { output: string; isError: boolean }>();
  for (const msg of messages) {
    if (msg.role === 'tool' && msg.tool_call_id) {
      toolResults.set(msg.tool_call_id, {
        output: msg.content || '',
        isError: false,
      });
    }
  }

  const uiMessages: UIMessage[] = [];

  for (const msg of messages) {
    if (msg.role === 'system') continue;
    if (msg.role === 'tool') continue; // handled via tool_calls pairing

    if (msg.role === 'user') {
      uiMessages.push({
        id: nextId(),
        role: 'user',
        parts: [{ type: 'text', text: msg.content || '' }],
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
        uiMessages.push({
          id: nextId(),
          role: 'assistant',
          parts,
        });
      }
    }
  }

  return uiMessages;
}
