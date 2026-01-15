import { useEffect, useRef } from 'react';
import { Box, Typography, CircularProgress } from '@mui/material';
import MessageBubble from './MessageBubble';
import type { Message } from '@/types/agent';

interface MessageListProps {
  messages: Message[];
  isProcessing: boolean;
}

export default function MessageList({ messages, isProcessing }: MessageListProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  return (
    <Box
      sx={{
        flex: 1,
        overflow: 'auto',
        p: 2,
        display: 'flex',
        flexDirection: 'column',
        gap: 2,
      }}
    >
      {messages.length === 0 ? (
        <Box
          sx={{
            flex: 1,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          <Typography color="text.secondary">
            Start a conversation by typing a message below
          </Typography>
        </Box>
      ) : (
        messages.map((message) => (
          <MessageBubble key={message.id} message={message} />
        ))
      )}
      {isProcessing && (
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, px: 2 }}>
          <CircularProgress size={16} />
          <Typography variant="body2" color="text.secondary">
            Processing...
          </Typography>
        </Box>
      )}
      <div ref={bottomRef} />
    </Box>
  );
}
