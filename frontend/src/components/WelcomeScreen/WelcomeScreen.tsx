import { useState, useCallback } from 'react';
import {
  Box,
  Typography,
  Button,
  CircularProgress,
  Alert,
} from '@mui/material';
import { useSessionStore } from '@/store/sessionStore';
import { useAgentStore } from '@/store/agentStore';
import { apiFetch } from '@/utils/api';
import { getStoredToken, triggerLogin } from '@/hooks/useAuth';
import { logger } from '@/utils/logger';

/** HF brand orange */
const HF_ORANGE = '#FF9D00';

export default function WelcomeScreen() {
  const { createSession } = useSessionStore();
  const { setPlan, setPanelContent, user } = useAgentStore();
  const [isCreating, setIsCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleStart = useCallback(async () => {
    if (isCreating) return;

    // In production (OAuth enabled): check for stored token, trigger login if missing
    // In dev mode (user already set by useAuth): skip login, go straight to session
    const isDevUser = user?.username === 'dev';
    if (!isDevUser && !getStoredToken()) {
      logger.log('No token — triggering OAuth login');
      await triggerLogin();
      return;
    }

    setIsCreating(true);
    setError(null);

    try {
      const response = await apiFetch('/api/session', { method: 'POST' });
      if (response.status === 503) {
        const data = await response.json();
        setError(data.detail || 'Server is at capacity. Please try again later.');
        return;
      }
      if (response.status === 401) {
        // Token expired — trigger re-login
        await triggerLogin();
        return;
      }
      if (!response.ok) {
        setError('Failed to create session. Please try again.');
        return;
      }
      const data = await response.json();
      createSession(data.session_id);
      setPlan([]);
      setPanelContent(null);
    } catch {
      // triggerLogin may redirect — don't show error
    } finally {
      setIsCreating(false);
    }
  }, [isCreating, createSession, setPlan, setPanelContent, user]);

  return (
    <Box
      sx={{
        width: '100%',
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'var(--body-gradient)',
        py: 8,
      }}
    >
      {/* HF Logo — large, centered */}
      <Box
        component="img"
        src="https://huggingface.co/front/assets/huggingface_logo-noborder.svg"
        alt="Hugging Face"
        sx={{
          width: 96,
          height: 96,
          mb: 3,
          display: 'block',
        }}
      />

      {/* Title */}
      <Typography
        variant="h2"
        sx={{
          fontWeight: 800,
          color: 'var(--text)',
          mb: 1.5,
          letterSpacing: '-0.02em',
          fontSize: { xs: '2rem', md: '2.8rem' },
        }}
      >
        ML Agent
      </Typography>

      {/* Description */}
      <Typography
        variant="body1"
        sx={{
          color: 'var(--muted-text)',
          maxWidth: 520,
          mb: 5,
          lineHeight: 1.8,
          fontSize: '0.95rem',
          textAlign: 'center',
          px: 2,
          '& strong': {
            color: 'var(--text)',
            fontWeight: 600,
          },
        }}
      >
        A general-purpose AI agent for <strong>machine learning engineering</strong>.
        It browses <strong>Hugging Face documentation</strong>, manages{' '}
        <strong>repositories</strong>, launches <strong>training jobs</strong>,
        and explores <strong>datasets</strong> — all through natural conversation.
      </Typography>

      {/* Start Button */}
      <Button
        variant="contained"
        size="large"
        onClick={handleStart}
        disabled={isCreating}
        startIcon={
          isCreating ? <CircularProgress size={20} color="inherit" /> : null
        }
        sx={{
          px: 5,
          py: 1.5,
          fontSize: '1rem',
          fontWeight: 700,
          textTransform: 'none',
          borderRadius: '12px',
          bgcolor: HF_ORANGE,
          color: '#000',
          boxShadow: '0 4px 24px rgba(255, 157, 0, 0.3)',
          transition: 'all 0.2s ease',
          '&:hover': {
            bgcolor: '#FFB340',
            boxShadow: '0 6px 32px rgba(255, 157, 0, 0.45)',
          },
          '&.Mui-disabled': {
            bgcolor: 'rgba(255, 157, 0, 0.35)',
            color: 'rgba(0,0,0,0.45)',
          },
        }}
      >
        {isCreating ? 'Initializing...' : 'Start Session'}
      </Button>

      {/* Error */}
      {error && (
        <Alert
          severity="warning"
          variant="outlined"
          onClose={() => setError(null)}
          sx={{
            mt: 3,
            maxWidth: 400,
            fontSize: '0.8rem',
            borderColor: HF_ORANGE,
            color: 'var(--text)',
          }}
        >
          {error}
        </Alert>
      )}

      {/* Footnote */}
      <Typography
        variant="caption"
        sx={{
          mt: 5,
          color: 'var(--muted-text)',
          opacity: 0.5,
          fontSize: '0.7rem',
        }}
      >
        Conversations are stored locally in your browser.
      </Typography>
    </Box>
  );
}
