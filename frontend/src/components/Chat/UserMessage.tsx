import { Box, Stack, Typography, Avatar, IconButton, Tooltip } from '@mui/material';
import PersonOutlineIcon from '@mui/icons-material/PersonOutline';
import CloseIcon from '@mui/icons-material/Close';
import type { Message } from '@/types/agent';

interface UserMessageProps {
  message: Message;
  /** True if this message starts the last turn. */
  isLastTurn?: boolean;
  /** Callback to remove the last turn. */
  onUndoTurn?: () => void;
  /** Whether the agent is currently processing (disables undo). */
  isProcessing?: boolean;
}

export default function UserMessage({
  message,
  isLastTurn = false,
  onUndoTurn,
  isProcessing = false,
}: UserMessageProps) {
  const showUndo = isLastTurn && !isProcessing && !!onUndoTurn;

  return (
    <Stack
      direction="row"
      spacing={1.5}
      justifyContent="flex-end"
      alignItems="flex-start"
      sx={{
        // Show the undo button when hovering the entire row
        '& .undo-btn': {
          opacity: 0,
          transition: 'opacity 0.15s ease',
        },
        '&:hover .undo-btn': {
          opacity: 1,
        },
      }}
    >
      {/* Undo button — visible on hover, left of the bubble */}
      {showUndo && (
        <Box className="undo-btn" sx={{ display: 'flex', alignItems: 'center', mt: 0.75 }}>
          <Tooltip title="Remove this turn" placement="left">
            <IconButton
              onClick={onUndoTurn}
              size="small"
              sx={{
                width: 24,
                height: 24,
                color: 'var(--muted-text)',
                '&:hover': {
                  color: 'var(--accent-red)',
                  bgcolor: 'rgba(244,67,54,0.08)',
                },
              }}
            >
              <CloseIcon sx={{ fontSize: 14 }} />
            </IconButton>
          </Tooltip>
        </Box>
      )}

      <Box
        sx={{
          maxWidth: { xs: '88%', md: '72%' },
          bgcolor: 'var(--surface)',
          borderRadius: 1.5,
          borderTopRightRadius: 4,
          px: { xs: 1.5, md: 2.5 },
          py: 1.5,
          border: '1px solid var(--border)',
        }}
      >
        <Typography
          variant="body1"
          sx={{
            fontSize: '0.925rem',
            lineHeight: 1.65,
            color: 'var(--text)',
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-word',
          }}
        >
          {message.content}
        </Typography>

        <Typography
          variant="caption"
          sx={{
            display: 'block',
            textAlign: 'right',
            mt: 1,
            fontSize: '0.68rem',
            color: 'var(--muted-text)',
            opacity: 0.7,
          }}
        >
          {new Date(message.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
        </Typography>
      </Box>

      <Avatar
        sx={{
          width: 28,
          height: 28,
          bgcolor: 'var(--hover-bg)',
          border: '1px solid var(--border)',
          flexShrink: 0,
          mt: 0.5,
        }}
      >
        <PersonOutlineIcon sx={{ fontSize: 16, color: 'var(--muted-text)' }} />
      </Avatar>
    </Stack>
  );
}
