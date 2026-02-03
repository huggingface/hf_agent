import { useState, useCallback, useEffect, KeyboardEvent } from 'react';
import { Box, TextField, IconButton, CircularProgress, Typography, Menu, MenuItem, ListItemIcon, ListItemText, Snackbar, Alert, Chip } from '@mui/material';
import ArrowUpwardIcon from '@mui/icons-material/ArrowUpward';
import ArrowDropDownIcon from '@mui/icons-material/ArrowDropDown';
import { useSessionStore } from '@/store/sessionStore';
import { useAuthStore } from '@/store/authStore';
import { useAgentStore } from '@/store/agentStore';

// Model configuration
interface ModelOption {
  id: string;
  name: string;
  description: string;
  provider: 'huggingface' | 'anthropic';
  modelPath: string; // Full path for API
  avatarUrl: string; // Logo URL
  recommended?: boolean;
  requiresApiKey?: boolean;
}

// Helper to get HF avatar URL from model ID
const getHfAvatarUrl = (modelId: string) => {
  const org = modelId.split('/')[0];
  return `https://huggingface.co/api/avatars/${org}`;
};

// Curated model list
const MODEL_OPTIONS: ModelOption[] = [
  {
    id: 'claude-opus',
    name: 'Claude Opus 4.5',
    description: 'Requires API Key',
    provider: 'anthropic',
    modelPath: 'anthropic/claude-opus-4-5-20251101',
    avatarUrl: '/claude-logo.png',
    recommended: true,
    requiresApiKey: true,
  },
  {
    id: 'minimax-m2.1',
    name: 'MiniMax M2.1',
    description: 'Via Novita',
    provider: 'huggingface',
    modelPath: 'huggingface/novita/MiniMaxAI/MiniMax-M2.1',
    avatarUrl: getHfAvatarUrl('MiniMaxAI/MiniMax-M2.1'),
    recommended: true,
  },
  {
    id: 'kimi-k2.5',
    name: 'Kimi K2.5',
    description: 'Via Novita',
    provider: 'huggingface',
    modelPath: 'huggingface/novita/moonshotai/Kimi-K2.5',
    avatarUrl: getHfAvatarUrl('moonshotai/Kimi-K2.5'),
  },
  {
    id: 'glm-4.7',
    name: 'GLM 4.7',
    description: 'Via Novita',
    provider: 'huggingface',
    modelPath: 'huggingface/novita/zai-org/GLM-4.7',
    avatarUrl: getHfAvatarUrl('zai-org/GLM-4.7'),
  },
  {
    id: 'deepseek-v3.2',
    name: 'DeepSeek V3.2',
    description: 'Via Novita',
    provider: 'huggingface',
    modelPath: 'huggingface/novita/deepseek-ai/DeepSeek-V3.2',
    avatarUrl: getHfAvatarUrl('deepseek-ai/DeepSeek-V3.2'),
  },
  {
    id: 'qwen3-coder-480b',
    name: 'Qwen3 Coder 480B',
    description: 'Via Nebius',
    provider: 'huggingface',
    modelPath: 'huggingface/nebius/Qwen/Qwen3-Coder-480B-A35B-Instruct',
    avatarUrl: getHfAvatarUrl('Qwen/Qwen3-Coder-480B-A35B-Instruct'),
  },
];

// Find model by path (for syncing with backend)
const findModelByPath = (path: string): ModelOption | undefined => {
  return MODEL_OPTIONS.find(m => m.modelPath === path || path?.includes(m.id));
};

interface ChatInputProps {
  onSend: (text: string) => void;
  disabled?: boolean;
}

export default function ChatInput({ onSend, disabled = false }: ChatInputProps) {
  const [input, setInput] = useState('');
  const [modelAnchorEl, setModelAnchorEl] = useState<null | HTMLElement>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const { switchModel, createSession, activeModelName } = useSessionStore();
  const { user } = useAuthStore();
  const { clearMessages, setPlan, setPanelContent } = useAgentStore();

  // Track selected model by ID
  const [selectedModelId, setSelectedModelId] = useState<string>('minimax-m2.1');

  // Sync selectedModelId with the active session's model
  useEffect(() => {
    if (activeModelName) {
      const model = findModelByPath(activeModelName);
      if (model) {
        setSelectedModelId(model.id);
      }
    }
  }, [activeModelName]);

  const selectedModel = MODEL_OPTIONS.find(m => m.id === selectedModelId) || MODEL_OPTIONS[0];

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

  const handleSwitchModel = async (model: ModelOption) => {
    // Check if user has Anthropic API key when switching to Claude
    if (model.requiresApiKey && !user?.has_anthropic_key) {
      setErrorMessage('Please set your Anthropic API key in Settings before using Claude models');
      handleModelClose();
      return;
    }

    const success = await switchModel(model.modelPath);
    if (success) {
      setSelectedModelId(model.id);
      // Create a new session when switching models
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
            slotProps={{
              input: {
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
            src={selectedModel.avatarUrl}
            alt={selectedModel.name}
            style={{ height: '14px', width: '14px', objectFit: 'contain', borderRadius: '2px' }}
          />
          <Typography variant="caption" sx={{ fontSize: '10px', color: 'var(--text)', fontWeight: 600, letterSpacing: '0.02em' }}>
            {selectedModel.name}
          </Typography>
          <ArrowDropDownIcon sx={{ fontSize: '14px', color: 'var(--muted-text)' }} />
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
          slotProps={{
            paper: {
              sx: {
                bgcolor: 'var(--panel)',
                border: '1px solid var(--divider)',
                mb: 1,
                maxHeight: '400px',
              }
            }
          }}
        >
          {MODEL_OPTIONS.map((model) => (
            <MenuItem
              key={model.id}
              onClick={() => handleSwitchModel(model)}
              selected={selectedModelId === model.id}
              sx={{
                py: 1.5,
                '&.Mui-selected': {
                  bgcolor: 'rgba(255,255,255,0.05)',
                }
              }}
            >
              <ListItemIcon>
                <img
                  src={model.avatarUrl}
                  alt={model.name}
                  style={{ width: 24, height: 24, borderRadius: '4px', objectFit: 'cover' }}
                />
              </ListItemIcon>
              <ListItemText
                primary={
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    {model.name}
                    {model.recommended && (
                      <Chip
                        label="Recommended"
                        size="small"
                        sx={{
                          height: '18px',
                          fontSize: '10px',
                          bgcolor: 'var(--accent-yellow)',
                          color: '#000',
                          fontWeight: 600,
                        }}
                      />
                    )}
                  </Box>
                }
                secondary={model.description}
                secondaryTypographyProps={{
                  sx: { fontSize: '12px', color: 'var(--muted-text)' }
                }}
              />
            </MenuItem>
          ))}
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
