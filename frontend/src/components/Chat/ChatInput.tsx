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
      <Box sx={{ maxWidth: '880px', mx: 'auto', width: '100%', px: 2 }}>
        <Box
          className="composer"
          sx={{
            display: 'flex',
            gap: '10px',
            alignItems: 'flex-start',
            bgcolor: 'rgba(255,255,255,0.01)',
            borderRadius: 'var(--radius-md)',
            p: '12px',
            border: '1px solid rgba(255,255,255,0.03)',
            transition: 'box-shadow 0.2s ease, border-color 0.2s ease',
            '&:focus-within': {
                borderColor: 'var(--accent-yellow)',
                boxShadow: 'var(--focus)',
            }
          }}
        >
          <TextField
            fullWidth
            multiline
            maxRows={6}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask anything..."
            disabled={disabled}
            variant="standard"
            InputProps={{
                disableUnderline: true,
                sx: {
                    color: 'var(--text)',
                    fontSize: '15px',
                    fontFamily: 'inherit',
                    padding: 0,
                    lineHeight: 1.5,
                    minHeight: '56px',
                    alignItems: 'flex-start',
                }
            }}
            sx={{
                flex: 1,
                '& .MuiInputBase-root': {
                    p: 0,
                    backgroundColor: 'transparent',
                },
                '& textarea': {
                    resize: 'none',
                    padding: '0 !important',
                }
            }}
          />
          <IconButton
            onClick={handleSend}
            disabled={disabled || !input.trim()}
            sx={{
              mt: 1,
              p: 1,
              borderRadius: '10px',
              color: 'var(--muted-text)',
              transition: 'all 0.2s',
              '&:hover': {
                color: 'var(--accent-yellow)',
                bgcolor: 'rgba(255,255,255,0.05)',
              },
              '&.Mui-disabled': {
                opacity: 0.3,
              },
            }}
          >
            {disabled ? <CircularProgress size={20} color="inherit" /> : <ArrowUpwardIcon fontSize="small" />}
          </IconButton>
        </Box>
        
        {/* Powered By Badge */}
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', mt: 1.5, gap: 0.8, opacity: 0.5 }}>
          <Typography variant="caption" sx={{ fontSize: '10px', color: 'var(--muted-text)', textTransform: 'uppercase', letterSpacing: '0.05em', fontWeight: 500 }}>
            powered by
          </Typography>
          <img src="/claude-logo.png" alt="Claude" style={{ height: '12px', objectFit: 'contain' }} />
          <Typography variant="caption" sx={{ fontSize: '10px', color: 'var(--text)', fontWeight: 600, letterSpacing: '0.02em' }}>
            claude-opus-4-5-20251101
          </Typography>
        </Box>
      </Box>
    </Box>
  );
}
