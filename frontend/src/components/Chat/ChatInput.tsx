import { useState, useCallback, useEffect, useRef, KeyboardEvent } from 'react';
import { Box, TextField, IconButton, CircularProgress, Typography, Menu, MenuItem, ListItemIcon, ListItemText, Chip } from '@mui/material';
import ArrowUpwardIcon from '@mui/icons-material/ArrowUpward';
import ArrowDropDownIcon from '@mui/icons-material/ArrowDropDown';
import StopIcon from '@mui/icons-material/Stop';
import { apiFetch } from '@/utils/api';

interface ModelOption {
  id: string;
  label: string;
  description: string;
  avatarUrl: string;
  providerLabel?: string;
  recommended?: boolean;
}

const FALLBACK_MODELS: ModelOption[] = [
  {
    id: 'anthropic/claude-opus-4-6',
    label: 'Claude Opus 4.6',
    description: 'Anthropic',
    avatarUrl: 'https://huggingface.co/api/avatars/Anthropic',
    providerLabel: 'Anthropic',
    recommended: true,
  },
  {
    id: 'MiniMaxAI/MiniMax-M2.7',
    label: 'MiniMax M2.7',
    description: 'HF Router',
    avatarUrl: 'https://huggingface.co/api/avatars/MiniMaxAI',
    providerLabel: 'Hugging Face Router',
    recommended: true,
  },
  {
    id: 'moonshotai/Kimi-K2.6',
    label: 'Kimi K2.6',
    description: 'HF Router',
    avatarUrl: 'https://huggingface.co/api/avatars/moonshotai',
    providerLabel: 'Hugging Face Router',
  },
  {
    id: 'zai-org/GLM-5.1',
    label: 'GLM 5.1',
    description: 'HF Router',
    avatarUrl: 'https://huggingface.co/api/avatars/zai-org',
    providerLabel: 'Hugging Face Router',
  },
];

const toModelOption = (value: any): ModelOption | null => {
  if (!value || !value.id || !value.label) return null;
  return {
    id: String(value.id),
    label: String(value.label),
    description: String(value.description || value.providerLabel || ''),
    avatarUrl: String(value.avatarUrl || 'https://huggingface.co/api/avatars/huggingface'),
    providerLabel: value.providerLabel ? String(value.providerLabel) : undefined,
    recommended: Boolean(value.recommended),
  };
};

interface ChatInputProps {
  sessionId?: string;
  onSend: (text: string) => void;
  onStop?: () => void;
  isProcessing?: boolean;
  disabled?: boolean;
  placeholder?: string;
}

export default function ChatInput({ sessionId, onSend, onStop, isProcessing = false, disabled = false, placeholder = 'Ask anything...' }: ChatInputProps) {
  const [input, setInput] = useState('');
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const [modelOptions, setModelOptions] = useState<ModelOption[]>(FALLBACK_MODELS);
  const [selectedModelPath, setSelectedModelPath] = useState<string>(FALLBACK_MODELS[0].id);
  const [modelAnchorEl, setModelAnchorEl] = useState<null | HTMLElement>(null);

  useEffect(() => {
    let cancelled = false;

    apiFetch('/api/config/model')
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (cancelled || !data) return;

        const rawAvailable = Array.isArray(data.available) ? data.available : [];
        const available = rawAvailable
          .map(toModelOption)
          .filter((value: ModelOption | null): value is ModelOption => value !== null);

        if (available.length > 0) {
          setModelOptions(available);
        }
        if (typeof data.current === 'string' && data.current) {
          setSelectedModelPath(data.current);
        }
      })
      .catch(() => { /* ignore */ });

    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    if (!sessionId) return;

    let cancelled = false;
    apiFetch(`/api/session/${sessionId}`)
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (cancelled) return;
        if (typeof data?.model === 'string' && data.model) {
          setSelectedModelPath(data.model);
        }
      })
      .catch(() => { /* ignore */ });

    return () => { cancelled = true; };
  }, [sessionId]);

  const selectedModel = modelOptions.find((model) => model.id === selectedModelPath)
    || toModelOption({ id: selectedModelPath, label: selectedModelPath, description: '', avatarUrl: 'https://huggingface.co/api/avatars/huggingface' })
    || modelOptions[0];

  useEffect(() => {
    if (!disabled && !isProcessing && inputRef.current) {
      inputRef.current.focus();
    }
  }, [disabled, isProcessing]);

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
    [handleSend],
  );

  const handleModelClick = (event: React.MouseEvent<HTMLElement>) => {
    setModelAnchorEl(event.currentTarget);
  };

  const handleModelClose = () => {
    setModelAnchorEl(null);
  };

  const handleSelectModel = async (modelPath: string) => {
    handleModelClose();
    if (!sessionId) return;

    try {
      const res = await apiFetch(`/api/session/${sessionId}/model`, {
        method: 'POST',
        body: JSON.stringify({ model: modelPath }),
      });
      if (res.ok) {
        setSelectedModelPath(modelPath);
      }
    } catch {
      // ignore
    }
  };

  return (
    <Box
      sx={{
        pb: { xs: 2, md: 4 },
        pt: { xs: 1, md: 2 },
        position: 'relative',
        zIndex: 10,
      }}
    >
      <Box sx={{ maxWidth: '880px', mx: 'auto', width: '100%', px: { xs: 0, sm: 1, md: 2 } }}>
        <Box
          className="composer"
          sx={{
            display: 'flex',
            gap: '10px',
            alignItems: 'flex-start',
            bgcolor: 'var(--composer-bg)',
            borderRadius: 'var(--radius-md)',
            p: '12px',
            border: '1px solid var(--border)',
            transition: 'box-shadow 0.2s ease, border-color 0.2s ease',
            '&:focus-within': {
              borderColor: 'var(--accent-yellow)',
              boxShadow: 'var(--focus)',
            },
          }}
        >
          <TextField
            fullWidth
            multiline
            maxRows={6}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={placeholder}
            disabled={disabled || isProcessing}
            variant="standard"
            inputRef={inputRef}
            InputProps={{
              disableUnderline: true,
              sx: {
                color: 'var(--text)',
                fontSize: '15px',
                fontFamily: 'inherit',
                padding: 0,
                lineHeight: 1.5,
                minHeight: { xs: '44px', md: '56px' },
                alignItems: 'flex-start',
              },
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
              },
            }}
          />
          {isProcessing ? (
            <IconButton
              onClick={onStop}
              sx={{
                mt: 1,
                p: 1.5,
                borderRadius: '10px',
                color: 'var(--muted-text)',
                transition: 'all 0.2s',
                position: 'relative',
                '&:hover': {
                  bgcolor: 'var(--hover-bg)',
                  color: 'var(--accent-red)',
                },
              }}
            >
              <Box sx={{ position: 'relative', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <CircularProgress size={28} thickness={3} sx={{ color: 'inherit', position: 'absolute' }} />
                <StopIcon sx={{ fontSize: 16 }} />
              </Box>
            </IconButton>
          ) : (
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
                  bgcolor: 'var(--hover-bg)',
                },
                '&.Mui-disabled': {
                  opacity: 0.3,
                },
              }}
            >
              <ArrowUpwardIcon fontSize="small" />
            </IconButton>
          )}
        </Box>

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
              opacity: 1,
            },
          }}
        >
          <Typography variant="caption" sx={{ fontSize: '10px', color: 'var(--muted-text)', textTransform: 'uppercase', letterSpacing: '0.05em', fontWeight: 500 }}>
            powered by
          </Typography>
          <img
            src={selectedModel.avatarUrl}
            alt={selectedModel.label}
            style={{ height: '14px', width: '14px', objectFit: 'contain', borderRadius: '2px' }}
          />
          <Typography variant="caption" sx={{ fontSize: '10px', color: 'var(--text)', fontWeight: 600, letterSpacing: '0.02em' }}>
            {selectedModel.label}
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
              },
            },
          }}
        >
          {modelOptions.map((model) => (
            <MenuItem
              key={model.id}
              onClick={() => handleSelectModel(model.id)}
              selected={selectedModelPath === model.id}
              sx={{
                py: 1.5,
                '&.Mui-selected': {
                  bgcolor: 'rgba(255,255,255,0.05)',
                },
              }}
            >
              <ListItemIcon>
                <img
                  src={model.avatarUrl}
                  alt={model.label}
                  style={{ width: 24, height: 24, borderRadius: '4px', objectFit: 'cover' }}
                />
              </ListItemIcon>
              <ListItemText
                primary={(
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    {model.label}
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
                )}
                secondary={model.description || model.providerLabel}
                secondaryTypographyProps={{
                  sx: { fontSize: '12px', color: 'var(--muted-text)' },
                }}
              />
            </MenuItem>
          ))}
        </Menu>
      </Box>
    </Box>
  );
}
