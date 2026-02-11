import UserMessage from './UserMessage';
import AssistantMessage from './AssistantMessage';
import type { Message } from '@/types/agent';

interface MessageBubbleProps {
  message: Message;
  /** True if this is the user message that starts the last turn. */
  isLastTurn?: boolean;
  /** Callback to undo (remove) the last turn. */
  onUndoTurn?: () => void;
  /** Whether the agent is currently processing. */
  isProcessing?: boolean;
  /** True when this message is actively receiving streaming chunks. */
  isStreaming?: boolean;
}

/**
 * Thin dispatcher — routes each message to the correct
 * specialised component based on its role / content.
 */
export default function MessageBubble({
  message,
  isLastTurn = false,
  onUndoTurn,
  isProcessing = false,
  isStreaming = false,
}: MessageBubbleProps) {
  // Legacy approval-only messages (from old localStorage data) — skip them.
  // Approvals are now rendered inline within ToolCallGroup.
  if (message.approval && !message.content && !message.segments?.length) {
    return null;
  }

  if (message.role === 'user') {
    return (
      <UserMessage
        message={message}
        isLastTurn={isLastTurn}
        onUndoTurn={onUndoTurn}
        isProcessing={isProcessing}
      />
    );
  }

  if (message.role === 'assistant') {
    return <AssistantMessage message={message} isStreaming={isStreaming} />;
  }

  // Fallback (tool messages, etc.)
  return null;
}
