import { useEffect, useRef, useMemo, useCallback } from 'react';
import { Box, Stack, Typography, Avatar } from '@mui/material';
import SmartToyOutlinedIcon from '@mui/icons-material/SmartToyOutlined';
import MessageBubble from './MessageBubble';
import ThinkingIndicator from './ThinkingIndicator';
import MarkdownContent from './MarkdownContent';
import { useAgentStore } from '@/store/agentStore';
import { useSessionStore } from '@/store/sessionStore';
import { apiFetch } from '@/utils/api';
import { logger } from '@/utils/logger';
import type { Message } from '@/types/agent';

interface MessageListProps {
  messages: Message[];
  isProcessing: boolean;
}

const WELCOME_MD = `I'm ready to help you with machine learning tasks using the Hugging Face ecosystem.

**Training & Fine-tuning** — SFT, DPO, GRPO, PPO with TRL · LoRA/PEFT · Submit and monitor jobs on cloud GPUs

**Data** — Find and explore datasets · Process, filter, transform · Push to the Hub

**Models** — Search and discover models · Get details and configs · Deploy for inference

**Research** — Find papers and documentation · Explore code examples · Check APIs and best practices

**Infrastructure** — Run jobs on CPU/GPU instances · Manage repos, branches, PRs · Monitor Spaces and endpoints

What would you like to do?`;

/** Static welcome message rendered when the conversation is empty. */
function WelcomeMessage() {
  return (
    <Stack direction="row" spacing={1.5} alignItems="flex-start">
      <Avatar
        sx={{
          width: 28,
          height: 28,
          bgcolor: 'primary.main',
          flexShrink: 0,
          mt: 0.5,
        }}
      >
        <SmartToyOutlinedIcon sx={{ fontSize: 16, color: '#fff' }} />
      </Avatar>

      <Box sx={{ flex: 1, minWidth: 0 }}>
        <Stack direction="row" alignItems="baseline" spacing={1} sx={{ mb: 0.5 }}>
          <Typography
            variant="caption"
            sx={{
              fontWeight: 700,
              fontSize: '0.72rem',
              color: 'var(--muted-text)',
              textTransform: 'uppercase',
              letterSpacing: '0.04em',
            }}
          >
            Assistant
          </Typography>
        </Stack>
        <Box
          sx={{
            maxWidth: { xs: '95%', md: '85%' },
            bgcolor: 'var(--surface)',
            borderRadius: 1.5,
            borderTopLeftRadius: 4,
            px: { xs: 1.5, md: 2.5 },
            py: 1.5,
            border: '1px solid var(--border)',
          }}
        >
          <MarkdownContent content={WELCOME_MD} />
        </Box>
      </Box>
    </Stack>
  );
}

export default function MessageList({ messages, isProcessing }: MessageListProps) {
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const stickToBottom = useRef(true);
  const { activeSessionId } = useSessionStore();
  const { removeLastTurn, currentTurnMessageId } = useAgentStore();

  // ── Scroll-to-bottom helper ─────────────────────────────────────
  const scrollToBottom = useCallback(() => {
    const el = scrollContainerRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, []);

  // ── Track user scroll intent ────────────────────────────────────
  // When user scrolls up (>80px from bottom), disable auto-scroll.
  // When they scroll back to bottom, re-enable it.
  useEffect(() => {
    const el = scrollContainerRef.current;
    if (!el) return;

    const onScroll = () => {
      const distFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
      stickToBottom.current = distFromBottom < 80;
    };

    el.addEventListener('scroll', onScroll, { passive: true });
    return () => el.removeEventListener('scroll', onScroll);
  }, []);

  // ── Auto-scroll on new messages / state changes ─────────────────
  useEffect(() => {
    if (stickToBottom.current) scrollToBottom();
  }, [messages, isProcessing, scrollToBottom]);

  // ── Auto-scroll on DOM mutations (streaming content growth) ─────
  // This catches token-by-token updates that don't change the messages
  // array reference (appendToMessage mutates in place).
  useEffect(() => {
    const el = scrollContainerRef.current;
    if (!el) return;

    const observer = new MutationObserver(() => {
      if (stickToBottom.current) {
        el.scrollTop = el.scrollHeight;
      }
    });

    observer.observe(el, {
      childList: true,
      subtree: true,
      characterData: true,
    });

    return () => observer.disconnect();
  }, []);

  // Find the index of the last user message (start of the last turn)
  const lastUserMsgId = useMemo(() => {
    for (let i = messages.length - 1; i >= 0; i--) {
      if (messages[i].role === 'user') return messages[i].id;
    }
    return null;
  }, [messages]);

  const handleUndoLastTurn = useCallback(async () => {
    if (!activeSessionId) return;
    try {
      await apiFetch(`/api/undo/${activeSessionId}`, { method: 'POST' });
      // Optimistic removal — backend will also confirm via undo_complete WS event
      removeLastTurn(activeSessionId);
    } catch (e) {
      logger.error('Undo failed:', e);
    }
  }, [activeSessionId, removeLastTurn]);

  return (
    <Box
      ref={scrollContainerRef}
      sx={{
        flex: 1,
        overflow: 'auto',
        px: { xs: 0.5, sm: 1, md: 2 },
        py: { xs: 2, md: 3 },
      }}
    >
      <Stack
        spacing={3}
        sx={{
          maxWidth: 880,
          mx: 'auto',
          width: '100%',
        }}
      >
        {/* Always show the welcome message at the top */}
        <WelcomeMessage />

        {messages.length > 0 && (
          messages.map((msg) => (
            <MessageBubble
              key={msg.id}
              message={msg}
              isLastTurn={msg.id === lastUserMsgId}
              onUndoTurn={handleUndoLastTurn}
              isProcessing={isProcessing}
              isStreaming={isProcessing && msg.id === currentTurnMessageId}
            />
          ))
        )}

        {/* Show thinking dots only when processing but no streaming message yet */}
        {isProcessing && !currentTurnMessageId && <ThinkingIndicator />}

        {/* Sentinel — keeps scroll anchor at the bottom */}
        <div />
      </Stack>
    </Box>
  );
}
