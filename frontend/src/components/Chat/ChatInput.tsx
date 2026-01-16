import { useState, useCallback, KeyboardEvent } from 'react';
import { Box, TextField, IconButton, CircularProgress, Typography } from '@mui/material';
import ArrowUpwardIcon from '@mui/icons-material/ArrowUpward';

interface ChatInputProps {
  onSend: (text: string) => void;
  disabled?: boolean;
}

export default function ChatInput({ onSend, disabled = false }: ChatInputProps) {
  const [input, setInput] = useState('');

  const handleSend = useCallback(() => {
    if (input.trim() && !disabled) {
      onSend(input);
      setInput('');
    }
  }, [input, disabled, onSend]);

  const handleKeyDown = useCallback(
    (e: KeyboardEvent<HTMLDivElement>) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        handleSend();
      }
    },
    [handleSend]
  );

  return (
    <Box
      sx={{
        pb: 4,
        pt: 2,
        position: 'relative',
        zIndex: 10,
      }}
    >
      <Box sx={{ maxWidth: 'md', mx: 'auto', width: '100%', px: 2 }}>
        {/* Input Label and Divider */}
        <Box sx={{ display: 'flex', alignItems: 'center', mb: 1, gap: 2 }}>
          <Typography variant="caption" sx={{ fontFamily: 'monospace', fontWeight: 600, color: 'text.secondary', letterSpacing: '0.05em' }}>
            INPUT
          </Typography>
          <Box sx={{ flex: 1, height: '1px', bgcolor: 'divider' }} />
        </Box>

        <Box
          sx={{
            display: 'flex',
            gap: 1,
            alignItems: 'center',
            bgcolor: 'background.paper',
            borderRadius: 1,
            boxShadow: 4,
            p: 1,
            border: 1,
            borderColor: 'divider',
          }}
        >
          <TextField
            fullWidth
            multiline
            maxRows={6}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask anything"
            disabled={disabled}
            variant="outlined"
            size="small"
            sx={{
              '& .MuiOutlinedInput-root': {
                padding: '9px 12px',
                lineHeight: '1.4',
                fontFamily: 'monospace',
              },
              '& .MuiInputBase-input': {
                fontFamily: 'monospace',
              },
              '& .MuiOutlinedInput-notchedOutline': {
                border: 'none',
              },
            }}
          />
          <IconButton
            onClick={handleSend}
            disabled={disabled || !input.trim()}
            sx={{
              border: 1,
              borderColor: 'divider',
              borderRadius: 1,
              color: 'text.secondary',
              transition: 'all 0.2s',
              '&:hover': {
                borderColor: 'primary.main',
                color: 'primary.main',
                bgcolor: 'transparent',
              },
              '&.Mui-disabled': {
                borderColor: 'divider',
                opacity: 0.5,
              },
            }}
          >
            {disabled ? <CircularProgress size={24} color="inherit" /> : <ArrowUpwardIcon fontSize="small" />}
          </IconButton>
        </Box>
      </Box>
    </Box>
  );
}
