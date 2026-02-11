import { Box, Stack, Avatar, Typography } from '@mui/material';
import SmartToyOutlinedIcon from '@mui/icons-material/SmartToyOutlined';
import MarkdownContent from './MarkdownContent';
import ToolCallGroup from './ToolCallGroup';
import type { Message } from '@/types/agent';

interface AssistantMessageProps {
  message: Message;
  /** True when this message is actively receiving streaming chunks. */
  isStreaming?: boolean;
}

export default function AssistantMessage({ message, isStreaming = false }: AssistantMessageProps) {
  const renderSegments = () => {
    if (message.segments && message.segments.length > 0) {
      // Find the index of the last text segment (that's the one being streamed)
      let lastTextIdx = -1;
      for (let i = message.segments.length - 1; i >= 0; i--) {
        if (message.segments[i].type === 'text') {
          lastTextIdx = i;
          break;
        }
      }

      return message.segments.map((segment, idx) => {
        if (segment.type === 'text' && segment.content) {
          return (
            <MarkdownContent
              key={idx}
              content={segment.content}
              isStreaming={isStreaming && idx === lastTextIdx}
            />
          );
        }
        if (segment.type === 'tools' && segment.tools && segment.tools.length > 0) {
          return <ToolCallGroup key={idx} tools={segment.tools} />;
        }
        return null;
      });
    }

    // Fallback: render raw content
    if (message.content) {
      return <MarkdownContent content={message.content} isStreaming={isStreaming} />;
    }

    return null;
  };

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
        {/* Role label + timestamp */}
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
          <Typography
            variant="caption"
            sx={{
              fontSize: '0.66rem',
              color: 'var(--muted-text)',
              opacity: 0.6,
            }}
          >
            {new Date(message.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
          </Typography>
        </Stack>

        {/* Message bubble */}
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
          {renderSegments()}
        </Box>
      </Box>
    </Stack>
  );
}
