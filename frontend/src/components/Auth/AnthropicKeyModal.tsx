import { useState } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Button,
  Alert,
  CircularProgress,
  Typography,
  Box,
} from '@mui/material';
import { useAuthStore } from '@/store/authStore';

interface AnthropicKeyModalProps {
  open: boolean;
  onClose: () => void;
}

export function AnthropicKeyModal({ open, onClose }: AnthropicKeyModalProps) {
  const [apiKey, setApiKey] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const { setAnthropicKey } = useAuthStore();

  const handleSubmit = async () => {
    if (!apiKey.trim()) {
      setError('Please enter your API key');
      return;
    }

    setIsSubmitting(true);
    setError(null);

    const success = await setAnthropicKey(apiKey.trim());

    setIsSubmitting(false);

    if (success) {
      setApiKey('');
      onClose();
    } else {
      setError('Failed to validate API key. Please check and try again.');
    }
  };

  const handleClose = () => {
    setApiKey('');
    setError(null);
    onClose();
  };

  return (
    <Dialog open={open} onClose={handleClose} maxWidth="sm" fullWidth>
      <DialogTitle>Anthropic API Key Required</DialogTitle>
      <DialogContent>
        <Box sx={{ mb: 2 }}>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            To use the AI agent, you need to provide your own Anthropic API key.
            Your key is stored securely and only used for this session.
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
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

        {error && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {error}
          </Alert>
        )}

        <TextField
          autoFocus
          fullWidth
          label="Anthropic API Key"
          type="password"
          value={apiKey}
          onChange={(e) => setApiKey(e.target.value)}
          placeholder="sk-ant-..."
          disabled={isSubmitting}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !isSubmitting) {
              handleSubmit();
            }
          }}
        />
      </DialogContent>
      <DialogActions>
        <Button onClick={handleClose} disabled={isSubmitting}>
          Cancel
        </Button>
        <Button
          onClick={handleSubmit}
          variant="contained"
          disabled={isSubmitting || !apiKey.trim()}
        >
          {isSubmitting ? <CircularProgress size={20} /> : 'Save Key'}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
