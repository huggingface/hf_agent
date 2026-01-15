import { Box, Paper, Typography, Chip } from '@mui/material';
import ReactMarkdown from 'react-markdown';
import PersonIcon from '@mui/icons-material/Person';
import SmartToyIcon from '@mui/icons-material/SmartToy';
import BuildIcon from '@mui/icons-material/Build';
import type { Message } from '@/types/agent';

interface MessageBubbleProps {
  message: Message;
}

export default function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === 'user';
  const isTool = message.role === 'tool';

  const getIcon = () => {
    if (isUser) return <PersonIcon fontSize="small" />;
    if (isTool) return <BuildIcon fontSize="small" />;
    return <SmartToyIcon fontSize="small" />;
  };

  const getBgColor = () => {
    if (isUser) return 'primary.dark';
    if (isTool) return 'background.default';
    return 'background.paper';
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
          p: 2,
          maxWidth: isTool ? '100%' : '80%',
          width: isTool ? '100%' : 'auto',
          bgcolor: getBgColor(),
          border: 1,
          borderColor: 'divider',
        }}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
          {getIcon()}
          <Typography variant="caption" color="text.secondary">
            {isUser ? 'You' : isTool ? 'Tool' : 'Assistant'}
          </Typography>
          {isTool && message.toolName && (
            <Chip
              label={message.toolName}
              size="small"
              variant="outlined"
              sx={{ ml: 1, height: 20, fontSize: '0.7rem' }}
            />
          )}
          <Typography variant="caption" color="text.secondary" sx={{ ml: 'auto' }}>
            {new Date(message.timestamp).toLocaleTimeString()}
          </Typography>
        </Box>
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
              color: 'primary.main',
            },
            '& ul, & ol': {
              pl: 2,
              my: 1,
            },
          }}
        >
          <ReactMarkdown>{message.content}</ReactMarkdown>
        </Box>
      </Paper>
    </Box>
  );
}
