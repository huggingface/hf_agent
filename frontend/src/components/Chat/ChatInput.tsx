import { useState, useCallback, KeyboardEvent } from 'react';
import { Box, TextField, IconButton, CircularProgress, Typography, Menu, MenuItem, ListItemIcon, ListItemText, Snackbar, Alert } from '@mui/material';
import ArrowUpwardIcon from '@mui/icons-material/ArrowUpward';
import AutoAwesomeIcon from '@mui/icons-material/AutoAwesome';
import { useSessionStore } from '@/store/sessionStore';
import { useAuthStore } from '@/store/authStore';
import { useAgentStore } from '@/store/agentStore';

interface ChatInputProps {
  onSend: (text: string) => void;
  disabled?: boolean;
}

export default function ChatInput({ onSend, disabled = false }: ChatInputProps) {
  const [input, setInput] = useState('');
  const [modelAnchorEl, setModelAnchorEl] = useState<null | HTMLElement>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const { switchModel, createSession } = useSessionStore();
  const { user } = useAuthStore();
  const { clearMessages, setPlan, setPanelContent } = useAgentStore();
  const [currentModel, setCurrentModel] = useState<'qwen' | 'anthropic'>('qwen');

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

  const handleModelClick = (event: React.MouseEvent<HTMLElement>) => {
    setModelAnchorEl(event.currentTarget);
  };

  const handleModelClose = () => {
    setModelAnchorEl(null);
  };

  const handleSwitchModel = async (model: 'qwen' | 'anthropic') => {
    // Check if user has Anthropic API key when switching to Claude
    if (model === 'anthropic' && !user?.has_anthropic_key) {
      setErrorMessage('Please set your Anthropic API key in Settings before using Claude models');
      handleModelClose();
      return;
    }

    const modelName = model === 'qwen'
      ? 'huggingface/novita/deepseek-ai/DeepSeek-V3.1'
      : 'anthropic/claude-opus-4-5-20251101';

    const success = await switchModel(modelName);
    if (success) {
      setCurrentModel(model);
      // Create a new session when switching models (following AppLayout pattern)
      const sessionId = await createSession();
      if (sessionId) {
        clearMessages();
        setPlan([]);
        setPanelContent(null);
      }
    }
    handleModelClose();
  };

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
        <Box 
          onClick={handleModelClick}
          sx={{ 
            display: 'flex', 
            alignItems: 'center', 
            justifyContent: 'center', 
            mt: 1.5, 
            gap: 0.8, 
            opacity: 0.6,
            cursor: 'pointer',
            transition: 'opacity 0.2s',
            '&:hover': {
              opacity: 1
            }
          }}
        >
          <Typography variant="caption" sx={{ fontSize: '10px', color: 'var(--muted-text)', textTransform: 'uppercase', letterSpacing: '0.05em', fontWeight: 500 }}>
            powered by
          </Typography>
          <img
            src={currentModel === 'qwen' ? "/deepseek-logo.png" : "/claude-logo.png"}
            alt={currentModel === 'qwen' ? "DeepSeek" : "Claude"}
            style={{ height: '14px', objectFit: 'contain', borderRadius: currentModel === 'qwen' ? '2px' : 0 }}
          />
          <Typography variant="caption" sx={{ fontSize: '10px', color: 'var(--text)', fontWeight: 600, letterSpacing: '0.02em' }}>
            {currentModel === 'qwen' ? "DeepSeek-V3.1" : "Claude Opus 4.5"}
          </Typography>
        </Box>

        <Menu
          anchorEl={modelAnchorEl}
          open={Boolean(modelAnchorEl)}
          onClose={handleModelClose}
          anchorOrigin={{
            vertical: 'top',
            horizontal: 'center',
          }}
          transformOrigin={{
            vertical: 'bottom',
            horizontal: 'center',
          }}
          PaperProps={{
            sx: {
              bgcolor: 'var(--panel)',
              border: '1px solid var(--divider)',
              mb: 1
            }
          }}
        >
          <MenuItem 
            onClick={() => handleSwitchModel('qwen')}
            selected={currentModel === 'qwen'}
          >
            <ListItemIcon>
              <img src="/deepseek-logo.png" style={{ width: 20, height: 20, borderRadius: '2px' }} />
            </ListItemIcon>
            <ListItemText primary="DeepSeek V3.1 (HF)" secondary="Via Novita provider" />
          </MenuItem>
          <MenuItem
            onClick={() => handleSwitchModel('anthropic')}
            selected={currentModel === 'anthropic'}
          >
            <ListItemIcon>
              <img src="/claude-logo.png" style={{ width: 20, height: 20 }} />
            </ListItemIcon>
            <ListItemText primary="Claude Opus 4.5" secondary="Requires Anthropic API Key" />
          </MenuItem>
        </Menu>

        {/* Error message snackbar */}
        <Snackbar
          open={!!errorMessage}
          autoHideDuration={4000}
          onClose={() => setErrorMessage(null)}
          anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
        >
          <Alert onClose={() => setErrorMessage(null)} severity="warning" sx={{ width: '100%' }}>
            {errorMessage}
          </Alert>
        </Snackbar>
      </Box>
    </Box>
  );
}
