import { Box, Typography, Button } from '@mui/material';
import KeyIcon from '@mui/icons-material/Key';

interface SetupPromptProps {
  onOpenSettings: () => void;
}

export default function SetupPrompt({ onOpenSettings }: SetupPromptProps) {
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
        <Box
          sx={{
            width: 80,
            height: 80,
            borderRadius: '50%',
            bgcolor: 'rgba(255, 210, 30, 0.1)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            mb: 2,
          }}
        >
          <KeyIcon sx={{ fontSize: 40, color: '#FFD21E' }} />
        </Box>

        <Typography
          variant="h5"
          sx={{
            fontWeight: 600,
            color: 'var(--text)',
            fontFamily: 'inherit',
          }}
        >
          Almost there!
        </Typography>

        <Typography
          variant="body1"
          sx={{
            color: 'var(--muted-text)',
            lineHeight: 1.7,
            maxWidth: 400,
          }}
        >
          To start using the AI agent, you need to add your Anthropic API key. Your key is stored securely and used
          only for your sessions.
        </Typography>

        <Button
          variant="contained"
          size="large"
          startIcon={<KeyIcon />}
          onClick={onOpenSettings}
          sx={{
            mt: 2,
            px: 4,
            py: 1.5,
            borderRadius: 'var(--radius-md)',
            textTransform: 'none',
            fontSize: '1rem',
            fontWeight: 600,
          }}
        >
          Add API Key
        </Button>

        <Typography
          variant="caption"
          sx={{
            color: 'var(--muted-text)',
            mt: 1,
          }}
        >
          Get your key from{' '}
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
    </Box>
  );
}
