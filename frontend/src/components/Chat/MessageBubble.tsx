import { Box, Paper, Typography } from '@mui/material';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import ApprovalFlow from './ApprovalFlow';
import type { Message, TraceLog } from '@/types/agent';
import { useAgentStore } from '@/store/agentStore';
import { useLayoutStore } from '@/store/layoutStore';

interface MessageBubbleProps {
  message: Message;
}

// Render a tools segment with clickable tool calls
function ToolsSegment({ tools }: { tools: TraceLog[] }) {
  const { showToolOutput } = useAgentStore();
  const { setRightPanelOpen } = useLayoutStore();

  const handleToolClick = (log: TraceLog) => {
    if (log.completed && log.output) {
      showToolOutput(log);
      setRightPanelOpen(true);
    }
  };

  return (
    <Box
      sx={{
        bgcolor: 'rgba(0,0,0,0.3)',
        borderRadius: 1,
        p: 1.5,
        border: 1,
        borderColor: 'rgba(255,255,255,0.05)',
        my: 1.5,
      }}
    >
      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5 }}>
        {tools.map((log) => {
          const isClickable = log.completed && log.output;
          return (
            <Typography
              key={log.id}
              variant="caption"
              component="div"
              onClick={() => handleToolClick(log)}
              sx={{
                color: 'var(--muted-text)',
                fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, monospace',
                fontSize: '0.75rem',
                display: 'flex',
                alignItems: 'center',
                gap: 0.5,
                cursor: isClickable ? 'pointer' : 'default',
                borderRadius: 0.5,
                px: 0.5,
                mx: -0.5,
                transition: 'background-color 0.15s ease',
                '&:hover': isClickable ? {
                  bgcolor: 'rgba(255,255,255,0.05)',
                } : {},
              }}
            >
              <span style={{
                color: log.completed
                  ? (log.success === false ? '#F87171' : '#FDB022')
                  : 'inherit',
                fontSize: '0.85rem',
              }}>
                {log.completed ? (log.success === false ? '✗' : '✓') : '•'}
              </span>
              <span style={{
                fontWeight: 600,
                color: isClickable ? 'rgba(255, 255, 255, 0.9)' : 'inherit',
                textDecoration: isClickable ? 'underline' : 'none',
                textDecorationColor: 'rgba(255,255,255,0.3)',
                textUnderlineOffset: '2px',
              }}>
                {log.tool}
              </span>
              {!log.completed && <span style={{ opacity: 0.6 }}>...</span>}
              {isClickable && (
                <span style={{
                  opacity: 0.4,
                  fontSize: '0.65rem',
                  marginLeft: 'auto',
                }}>
                  click to view
                </span>
              )}
            </Typography>
          );
        })}
      </Box>
    </Box>
  );
}

// Markdown styles
const markdownStyles = {
  '& p': { m: 0, mb: 1, '&:last-child': { mb: 0 } },
  '& pre': {
    bgcolor: 'rgba(0,0,0,0.5)',
    p: 1.5,
    borderRadius: 1,
    overflow: 'auto',
    fontSize: '0.85rem',
    border: '1px solid rgba(255,255,255,0.05)',
  },
  '& code': {
    bgcolor: 'rgba(255,255,255,0.05)',
    px: 0.5,
    py: 0.25,
    borderRadius: 0.5,
    fontSize: '0.85rem',
    fontFamily: '"JetBrains Mono", monospace',
  },
  '& pre code': { bgcolor: 'transparent', p: 0 },
  '& a': {
    color: 'var(--accent-yellow)',
    textDecoration: 'none',
    '&:hover': { textDecoration: 'underline' },
  },
  '& ul, & ol': { pl: 2, my: 1 },
  '& table': {
    borderCollapse: 'collapse',
    width: '100%',
    my: 2,
    fontSize: '0.875rem',
  },
  '& th': {
    borderBottom: '1px solid rgba(255,255,255,0.1)',
    textAlign: 'left',
    p: 1,
    bgcolor: 'rgba(255,255,255,0.02)',
  },
  '& td': {
    borderBottom: '1px solid rgba(255,255,255,0.05)',
    p: 1,
  },
};

export default function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === 'user';
  const isAssistant = message.role === 'assistant';

  if (message.approval) {
    return (
      <Box sx={{ width: '100%', maxWidth: '880px', mx: 'auto', my: 2 }}>
        <ApprovalFlow message={message} />
      </Box>
    );
  }

  // Render segments chronologically if available, otherwise fall back to content
  const renderContent = () => {
    if (message.segments && message.segments.length > 0) {
      return message.segments.map((segment, idx) => {
        if (segment.type === 'text' && segment.content) {
          return (
            <Box key={idx} sx={markdownStyles}>
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{segment.content}</ReactMarkdown>
            </Box>
          );
        }
        if (segment.type === 'tools' && segment.tools && segment.tools.length > 0) {
          return <ToolsSegment key={idx} tools={segment.tools} />;
        }
        return null;
      });
    }
    // Fallback: just render content
    return (
      <Box sx={markdownStyles}>
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown>
      </Box>
    );
  };

  return (
    <Box
      sx={{
        display: 'flex',
        justifyContent: isUser ? 'flex-end' : 'flex-start',
        width: '100%',
        maxWidth: '880px',
        mx: 'auto',
      }}
    >
      <Paper
        elevation={0}
        className={`message ${isUser ? 'user' : isAssistant ? 'assistant' : ''}`}
        sx={{
          p: '14px 18px',
          margin: '10px 0',
          maxWidth: '100%',
          borderRadius: 'var(--radius-lg)',
          borderTopLeftRadius: isAssistant ? '6px' : undefined,
          lineHeight: 1.45,
          boxShadow: 'var(--shadow-1)',
          border: '1px solid rgba(255,255,255,0.03)',
          background: 'linear-gradient(180deg, rgba(255,255,255,0.015), transparent)',
        }}
      >
        {renderContent()}

        <Typography
          className="meta"
          variant="caption"
          sx={{ display: 'block', textAlign: 'right', mt: 1, fontSize: '11px', opacity: 0.5 }}
        >
          {new Date(message.timestamp).toLocaleTimeString()}
        </Typography>
      </Paper>
    </Box>
  );
}
