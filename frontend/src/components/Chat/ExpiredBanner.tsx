/**
 * Shown inline in a chat when the backend no longer recognizes the
 * session id (typically: Space was restarted). Lets the user remove the
 * unavailable local session from the sidebar and start over.
 */
import { useCallback } from 'react';
import { Box, Button, Typography } from '@mui/material';
import { useSessionStore } from '@/store/sessionStore';
import { useAgentStore } from '@/store/agentStore';

interface Props {
  sessionId: string;
}

export default function ExpiredBanner({ sessionId }: Props) {
  const { deleteSession } = useSessionStore();

  const handleStartOver = useCallback(() => {
    useAgentStore.getState().clearSessionState(sessionId);
    deleteSession(sessionId);
  }, [sessionId, deleteSession]);

  return (
    <Box
      sx={{
        mx: { xs: 2, md: 'auto' },
        my: 2,
        maxWidth: 720,
        p: 2.5,
        borderRadius: 2,
        border: '1px solid',
        borderColor: 'divider',
        bgcolor: 'background.paper',
        boxShadow: '0 1px 3px rgba(0,0,0,0.06)',
      }}
    >
      <Typography variant="body1" sx={{ fontWeight: 600, mb: 0.5 }}>
        Session unavailable
      </Typography>
      <Typography variant="body2" sx={{ color: 'text.secondary', mb: 2 }}>
        This session is no longer available in the running Space. Start fresh
        to continue.
      </Typography>
      <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
        <Button
          variant="contained"
          onClick={handleStartOver}
          sx={{ textTransform: 'none' }}
        >
          Start fresh
        </Button>
      </Box>
    </Box>
  );
}
