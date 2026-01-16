import { Box, Paper, Typography, Chip } from '@mui/material';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { Message } from '@/types/agent';

interface MessageBubbleProps {
  message: Message;
}

export default function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === 'user';
  const isTool = message.role === 'tool';

  const getBgColor = () => {
    if (isUser) return 'background.paper';
    if (isTool) return 'background.default';
    return 'transparent';
  };

  return (
    <Box
      sx={{
        display: 'flex',
        justifyContent: isUser ? 'flex-end' : 'flex-start',
        width: '100%',
      }}
    >
      <Paper
        elevation={0}
        sx={{
          p: isTool ? 2 : isUser ? 1.5 : 1,
          maxWidth: isTool ? '100%' : '80%',
          width: isTool ? '100%' : 'auto',
          bgcolor: getBgColor(),
          border: (!isUser && !isTool) ? 0 : 1,
          borderColor: 'divider',
          borderRadius: isUser ? 2 : undefined,
        }}
      >
        {isTool && (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
            <Typography variant="caption" color="text.secondary">
              Tool
            </Typography>
            {message.toolName && (
              <Chip
                label={message.toolName}
                size="small"
                variant="outlined"
                sx={{ ml: 1, height: 20, fontSize: '0.7rem' }}
              />
            )}
          </Box>
        )}

        {/* Persisted Trace Logs */}
        {message.trace && message.trace.length > 0 && (
          <Box
            sx={{
              bgcolor: 'background.default',
              borderRadius: 1,
              p: 1.5,
              border: 1,
              borderColor: 'divider',
              width: '100%',
              mb: 2,
            }}
          >
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5 }}>
              {message.trace.map((log) => (
                <Typography
                  key={log.id}
                  variant="caption"
                  component="div"
                  sx={{ color: 'common.white', fontFamily: 'monospace', fontSize: '0.75rem' }}
                >
                  &gt; {log.text}
                </Typography>
              ))}
            </Box>
          </Box>
        )}

        <Box
          sx={{
            '& p': { m: 0 },
            '& pre': {
              bgcolor: 'background.default',
              p: 1.5,
              borderRadius: 1,
              overflow: 'auto',
              fontSize: '0.85rem',
            },
            '& code': {
              bgcolor: 'background.default',
              px: 0.5,
              py: 0.25,
              borderRadius: 0.5,
              fontSize: '0.85rem',
              fontFamily: '"JetBrains Mono", monospace',
            },
            '& pre code': {
              bgcolor: 'transparent',
              p: 0,
            },
            '& a': {
              color: 'inherit',
              textDecoration: 'underline',
            },
            '& ul, & ol': {
              pl: 2,
              my: 1,
            },
            '& table': {
              borderCollapse: 'collapse',
              width: '100%',
              my: 2,
              fontSize: '0.875rem',
            },
            '& th': {
              borderBottom: '1px solid',
              borderColor: 'divider',
              textAlign: 'left',
              p: 1,
              bgcolor: 'action.hover',
            },
            '& td': {
              borderBottom: '1px solid',
              borderColor: 'divider',
              p: 1,
            },
          }}
        >
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown>
        </Box>
      </Paper>
    </Box>
  );
}
