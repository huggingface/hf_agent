import { Box, Typography, Button } from '@mui/material';
import KeyIcon from '@mui/icons-material/Key';
import RocketLaunchIcon from '@mui/icons-material/RocketLaunch';

interface SetupPromptProps {
  hasApiKey: boolean;
  onOpenSettings: () => void;
  onStartSession: () => void;
  isCreatingSession?: boolean;
}

export default function SetupPrompt({
  hasApiKey,
  onOpenSettings,
  onStartSession,
  isCreatingSession,
}: SetupPromptProps) {
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
        {!hasApiKey ? (
          <>
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
          </>
        ) : (
          <>
            <Box
              sx={{
                width: 80,
                height: 80,
                borderRadius: '50%',
                bgcolor: 'rgba(47, 204, 113, 0.1)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                mb: 2,
              }}
            >
              <RocketLaunchIcon sx={{ fontSize: 40, color: 'var(--accent-green)' }} />
            </Box>

            <Typography
              variant="h5"
              sx={{
                fontWeight: 600,
                color: 'var(--text)',
                fontFamily: 'inherit',
              }}
            >
              Ready to go!
            </Typography>

            <Typography
              variant="body1"
              sx={{
                color: 'var(--muted-text)',
                lineHeight: 1.7,
                maxWidth: 400,
              }}
            >
              Your account is set up. Start a new session to begin chatting with the ML engineering assistant.
            </Typography>

            <Button
              variant="contained"
              size="large"
              startIcon={<RocketLaunchIcon />}
              onClick={onStartSession}
              disabled={isCreatingSession}
              sx={{
                mt: 2,
                px: 4,
                py: 1.5,
                borderRadius: 'var(--radius-md)',
                textTransform: 'none',
                fontSize: '1rem',
                fontWeight: 600,
                background: 'linear-gradient(135deg, var(--accent-green) 0%, #1db954 100%)',
                '&:hover': {
                  background: 'linear-gradient(135deg, #3be07c 0%, #2ecc71 100%)',
                },
              }}
            >
              {isCreatingSession ? 'Starting...' : 'Start New Session'}
            </Button>
          </>
        )}
      </Box>
    </Box>
  );
}
