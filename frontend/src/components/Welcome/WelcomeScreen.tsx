import { Box, Typography, Button } from '@mui/material';
import LoginIcon from '@mui/icons-material/Login';

const API_BASE = import.meta.env.DEV ? 'http://127.0.0.1:7860' : '';

export default function WelcomeScreen() {
  const handleLogin = () => {
    window.location.href = `${API_BASE}/auth/login`;
  };

  return (
    <Box
      sx={{
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'linear-gradient(180deg, var(--bg), var(--panel))',
        padding: 4,
      }}
    >
      <Box
        sx={{
          maxWidth: 480,
          textAlign: 'center',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: 3,
        }}
      >
        <img
          src="/hf-logo-white.png"
          alt="Hugging Face"
          style={{ height: '80px', objectFit: 'contain', marginBottom: '16px' }}
        />

        <Typography
          variant="h4"
          sx={{
            fontWeight: 600,
            color: 'var(--text)',
            fontFamily: 'inherit',
          }}
        >
          Welcome to HF Agent
        </Typography>

        <Typography
          variant="body1"
          sx={{
            color: 'var(--muted-text)',
            lineHeight: 1.7,
            maxWidth: 400,
          }}
        >
          Your AI-powered ML engineering assistant. Connect your Hugging Face account to get started with code generation, model exploration, and more.
        </Typography>

        <Button
          variant="contained"
          size="large"
          startIcon={<LoginIcon />}
          onClick={handleLogin}
          sx={{
            mt: 2,
            px: 4,
            py: 1.5,
            borderRadius: 'var(--radius-md)',
            textTransform: 'none',
            fontSize: '1rem',
            fontWeight: 600,
            background: 'linear-gradient(135deg, #FFD21E 0%, #FF9D00 100%)',
            color: '#000',
            '&:hover': {
              background: 'linear-gradient(135deg, #FFE55C 0%, #FFAE33 100%)',
            },
          }}
        >
          Sign in with Hugging Face
        </Button>

        <Typography
          variant="caption"
          sx={{
            color: 'var(--muted-text)',
            mt: 2,
            opacity: 0.7,
          }}
        >
          By signing in, you agree to our terms of service
        </Typography>
      </Box>
    </Box>
  );
}
