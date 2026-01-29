import { useCallback } from 'react';
import {
  Box,
  List,
  ListItem,
  IconButton,
  Typography,
  Button,
  CircularProgress,
} from '@mui/material';
import DeleteIcon from '@mui/icons-material/Delete';
import { useSessionStore } from '@/store/sessionStore';
import { useAgentStore } from '@/store/agentStore';

interface SessionSidebarProps {
  onClose?: () => void;
}

export default function SessionSidebar({ onClose }: SessionSidebarProps) {
  const {
    sessions,
    activeSessionId,
    isLoading,
    createSession,
    selectSession,
    deleteSession,
  } = useSessionStore();
  const { setPlan, setPanelContent, clearMessages } = useAgentStore();

  const handleNewSession = useCallback(async () => {
    const sessionId = await createSession();
    if (sessionId) {
      clearMessages();
      setPlan([]);
      setPanelContent(null);
      onClose?.();
    }
  }, [createSession, clearMessages, setPlan, setPanelContent, onClose]);

  const handleSelectSession = useCallback(
    async (sessionId: string) => {
      await selectSession(sessionId);
      setPlan([]);
      setPanelContent(null);
      onClose?.();
    },
    [selectSession, setPlan, setPanelContent, onClose]
  );

  const handleDeleteSession = useCallback(
    async (sessionId: string, e: React.MouseEvent) => {
      e.stopPropagation();
      await deleteSession(sessionId);
    },
    [deleteSession]
  );

  const formatTime = (dateString: string) => {
    const date = new Date(dateString);
    const now = new Date();
    const isToday = date.toDateString() === now.toDateString();
    if (isToday) {
      return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    }
    return date.toLocaleDateString([], { month: 'short', day: 'numeric' });
  };

  return (
    <Box className="sidebar" sx={{ height: '100%', display: 'flex', flexDirection: 'column', bgcolor: 'var(--panel)' }}>
      {/* Header */}
      <Box sx={{
        height: '60px',
        display: 'flex',
        alignItems: 'center',
        px: 2,
        borderBottom: '1px solid rgba(255,255,255,0.03)'
      }}>
        <Box className="brand-logo" sx={{ display: 'flex' }}>
          <img
            src="/hf-log-only-white.png"
            alt="HF Agent"
            style={{ height: '24px', objectFit: 'contain' }}
          />
        </Box>
      </Box>

      {/* Content */}
      <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column', p: 2, overflow: 'hidden' }}>
        <Button
          fullWidth
          className="create-session"
          onClick={handleNewSession}
          sx={{
            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'flex-start',
            gap: '10px',
            padding: '10px 14px',
            borderRadius: 'var(--radius-md)',
            border: '1px solid rgba(255,255,255,0.06)',
            bgcolor: 'transparent',
            color: 'var(--text)',
            fontWeight: 600,
            textTransform: 'none',
            mb: 3,
            '&:hover': {
              bgcolor: 'rgba(255,255,255,0.02)',
              border: '1px solid rgba(255,255,255,0.1)',
            },
            '&::before': {
              content: '""',
              width: '4px',
              height: '20px',
              background: 'linear-gradient(180deg, var(--accent-yellow), rgba(199,165,0,0.9))',
              borderRadius: '4px',
            }
          }}
        >
          New Session
        </Button>

        {/* Session List */}
        <Box sx={{ flex: 1, overflow: 'auto', mx: -1, px: 1 }}>
          {isLoading && (
            <Box sx={{ display: 'flex', justifyContent: 'center', py: 2 }}>
              <CircularProgress size={20} sx={{ color: 'var(--muted-text)' }} />
            </Box>
          )}
          <List disablePadding sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
            {[...sessions].sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()).map((session) => {
              const isSelected = session.id === activeSessionId;
              return (
                <ListItem
                  key={session.id}
                  disablePadding
                  className="session-item"
                  onClick={() => handleSelectSession(session.id)}
                  sx={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '12px',
                    padding: '10px',
                    borderRadius: 'var(--radius-md)',
                    bgcolor: isSelected ? 'rgba(255,255,255,0.05)' : 'transparent',
                    cursor: 'pointer',
                    transition: 'background 0.18s ease, transform 0.08s ease',
                    '&:hover': {
                      bgcolor: 'rgba(255,255,255,0.02)',
                      transform: 'translateY(-1px)',
                    },
                    '& .delete-btn': {
                      opacity: 0,
                      transition: 'opacity 0.2s',
                    },
                    '&:hover .delete-btn': {
                      opacity: 1,
                    }
                  }}
                >
                  <Box sx={{ flex: 1, overflow: 'hidden' }}>
                    <Typography variant="body2" sx={{ fontWeight: 500, color: 'var(--text)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                      {session.title}
                    </Typography>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 0.5 }}>
                      <Typography className="time" variant="caption" sx={{ fontSize: '12px', color: 'var(--muted-text)' }}>
                        {formatTime(session.createdAt)}
                      </Typography>
                    </Box>
                  </Box>

                  <IconButton
                    className="delete-btn"
                    size="small"
                    onClick={(e) => handleDeleteSession(session.id, e)}
                    sx={{ color: 'var(--muted-text)', '&:hover': { color: 'var(--accent-red)' } }}
                  >
                    <DeleteIcon fontSize="small" />
                  </IconButton>
                </ListItem>
              );
            })}
          </List>
        </Box>
      </Box>

      {/* Footer */}
      <Box sx={{ p: 2, borderTop: '1px solid rgba(255,255,255,0.03)' }}>
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <Typography variant="caption" className="small-note" sx={{ fontSize: '12px', color: 'var(--muted-text)' }}>
            {sessions.length} sessions
          </Typography>
        </Box>
      </Box>
    </Box>
  );
}
