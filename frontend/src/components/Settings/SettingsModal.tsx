import { useState } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  Box,
  Typography,
  TextField,
  Button,
  Alert,
  CircularProgress,
  Divider,
  IconButton,
} from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import KeyIcon from '@mui/icons-material/Key';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline';
import { useAuthStore } from '@/store/authStore';

interface SettingsModalProps {
  open: boolean;
  onClose: () => void;
}

export default function SettingsModal({ open, onClose }: SettingsModalProps) {
  const [apiKey, setApiKey] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isRemoving, setIsRemoving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const { user, setAnthropicKey, removeAnthropicKey } = useAuthStore();

  const handleSubmit = async () => {
    if (!apiKey.trim()) {
      setError('Please enter your API key');
      return;
    }

    setIsSubmitting(true);
    setError(null);
    setSuccess(null);

    const result = await setAnthropicKey(apiKey.trim());

    setIsSubmitting(false);

    if (result) {
      setApiKey('');
      setSuccess('API key saved successfully');
      setTimeout(() => setSuccess(null), 3000);
    } else {
      setError('Failed to validate API key. Please check and try again.');
    }
  };

  const handleRemoveKey = async () => {
    setIsRemoving(true);
    setError(null);
    setSuccess(null);

    await removeAnthropicKey();

    setIsRemoving(false);
    setSuccess('API key removed');
    setTimeout(() => setSuccess(null), 3000);
  };

  const handleClose = () => {
    setApiKey('');
    setError(null);
    setSuccess(null);
    onClose();
  };

  return (
    <Dialog
      open={open}
      onClose={handleClose}
      maxWidth="sm"
      fullWidth
      PaperProps={{
        sx: {
          bgcolor: 'var(--panel)',
          backgroundImage: 'none',
        },
      }}
    >
      <DialogTitle sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <Typography variant="h6" sx={{ fontWeight: 600 }}>
          Settings
        </Typography>
        <IconButton onClick={handleClose} size="small">
          <CloseIcon />
        </IconButton>
      </DialogTitle>

      <DialogContent>
        {/* API Keys Section */}
        <Box sx={{ mb: 3 }}>
          <Typography
            variant="subtitle2"
            sx={{ mb: 2, color: 'var(--muted-text)', textTransform: 'uppercase', letterSpacing: 1 }}
          >
            API Keys
          </Typography>

          <Divider sx={{ mb: 3, borderColor: 'rgba(255,255,255,0.1)' }} />

          {/* Current Key Status */}
          <Box sx={{ mb: 3 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
              <KeyIcon fontSize="small" sx={{ color: 'var(--muted-text)' }} />
              <Typography variant="body2" sx={{ fontWeight: 500 }}>
                Anthropic API Key
              </Typography>
            </Box>

            {user?.has_anthropic_key ? (
              <Box
                sx={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  p: 2,
                  borderRadius: 'var(--radius-md)',
                  bgcolor: 'rgba(47, 204, 113, 0.1)',
                  border: '1px solid rgba(47, 204, 113, 0.3)',
                }}
              >
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <CheckCircleIcon sx={{ color: 'var(--accent-green)', fontSize: 20 }} />
                  <Typography variant="body2" sx={{ color: 'var(--accent-green)' }}>
                    API key is configured
                  </Typography>
                </Box>
                <Button
                  size="small"
                  color="error"
                  startIcon={isRemoving ? <CircularProgress size={16} /> : <DeleteOutlineIcon />}
                  onClick={handleRemoveKey}
                  disabled={isRemoving}
                  sx={{ textTransform: 'none' }}
                >
                  Remove
                </Button>
              </Box>
            ) : (
              <Typography variant="body2" sx={{ color: 'var(--muted-text)', mb: 2 }}>
                No API key configured. Add your Anthropic API key to use the agent.
              </Typography>
            )}
          </Box>

          {/* Add Key Form (only show if no key configured) */}
          {!user?.has_anthropic_key && (
            <Box>
              <Typography variant="body2" sx={{ color: 'var(--muted-text)', mb: 2 }}>
                Add your API key:
              </Typography>

              {error && (
                <Alert severity="error" sx={{ mb: 2 }}>
                  {error}
                </Alert>
              )}

              {success && (
                <Alert severity="success" sx={{ mb: 2 }}>
                  {success}
                </Alert>
              )}

              <TextField
                fullWidth
                size="small"
                label="Anthropic API Key"
                type="password"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                placeholder="sk-ant-..."
                disabled={isSubmitting}
                sx={{ mb: 2 }}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !isSubmitting) {
                    handleSubmit();
                  }
                }}
              />

              <Button
                fullWidth
                variant="contained"
                onClick={handleSubmit}
                disabled={isSubmitting || !apiKey.trim()}
                sx={{
                  textTransform: 'none',
                  py: 1,
                }}
              >
                {isSubmitting ? <CircularProgress size={20} /> : 'Save Key'}
              </Button>

              <Typography variant="caption" sx={{ display: 'block', mt: 2, color: 'var(--muted-text)' }}>
                Get your API key from{' '}
                <a
                  href="https://console.anthropic.com/settings/keys"
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{ color: '#1976d2' }}
                >
                  console.anthropic.com
                </a>
              </Typography>
            </Box>
          )}
        </Box>
       
      </DialogContent>
    </Dialog>
  );
}
