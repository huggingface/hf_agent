import { useCallback } from 'react';
import {
  Box,
  List,
  ListItem,
  ListItemButton,
  ListItemText,
  ListItemSecondaryAction,
  IconButton,
  Typography,
  Button,
  Divider,
  Chip,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import DeleteIcon from '@mui/icons-material/Delete';
import ChatIcon from '@mui/icons-material/Chat';
import { useSessionStore } from '@/store/sessionStore';
import { useAgentStore } from '@/store/agentStore';

interface SessionSidebarProps {
  onClose?: () => void;
}

export default function SessionSidebar({ onClose }: SessionSidebarProps) {
  const { sessions, activeSessionId, createSession, deleteSession, switchSession } =
    useSessionStore();
  const { clearMessages } = useAgentStore();

  const handleNewSession = useCallback(async () => {
    try {
      const response = await fetch('/api/session', { method: 'POST' });
      const data = await response.json();
      createSession(data.session_id);
      onClose?.();
    } catch (e) {
      console.error('Failed to create session:', e);
    }
  }, [createSession, onClose]);

  const handleDeleteSession = useCallback(
    async (sessionId: string, e: React.MouseEvent) => {
      e.stopPropagation();
      try {
        await fetch(`/api/session/${sessionId}`, { method: 'DELETE' });
        deleteSession(sessionId);
        clearMessages(sessionId);
      } catch (e) {
        console.error('Failed to delete session:', e);
      }
    },
    [deleteSession, clearMessages]
  );

  const handleSelectSession = useCallback(
    (sessionId: string) => {
      switchSession(sessionId);
      onClose?.();
    },
    [switchSession, onClose]
  );

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    const now = new Date();
    const isToday = date.toDateString() === now.toDateString();
    if (isToday) {
      return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    }
    return date.toLocaleDateString([], { month: 'short', day: 'numeric' });
  };

  return (
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      {/* Header */}
      <Box sx={{ p: 2, borderBottom: 1, borderColor: 'divider' }}>
        <Typography variant="h6" sx={{ mb: 2 }}>
          Sessions
        </Typography>
        <Button
          fullWidth
          variant="contained"
          startIcon={<AddIcon />}
          onClick={handleNewSession}
        >
          New Session
        </Button>
      </Box>

      {/* Session List */}
      <Box sx={{ flex: 1, overflow: 'auto' }}>
        {sessions.length === 0 ? (
          <Box sx={{ p: 3, textAlign: 'center' }}>
            <ChatIcon sx={{ fontSize: 48, color: 'text.secondary', mb: 1 }} />
            <Typography variant="body2" color="text.secondary">
              No sessions yet
            </Typography>
            <Typography variant="caption" color="text.secondary">
              Create a new session to get started
            </Typography>
          </Box>
        ) : (
          <List disablePadding>
            {[...sessions].reverse().map((session) => (
              <ListItem key={session.id} disablePadding divider>
                <ListItemButton
                  selected={session.id === activeSessionId}
                  onClick={() => handleSelectSession(session.id)}
                  sx={{
                    '&.Mui-selected': {
                      bgcolor: 'action.selected',
                      '&:hover': {
                        bgcolor: 'action.selected',
                      },
                    },
                  }}
                >
                  <ListItemText
                    primary={
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <Typography variant="body2" noWrap>
                          {session.title}
                        </Typography>
                        {session.isActive && (
                          <Chip
                            label="active"
                            size="small"
                            color="success"
                            sx={{ height: 18, fontSize: '0.65rem' }}
                          />
                        )}
                      </Box>
                    }
                    secondary={formatDate(session.createdAt)}
                  />
                  <ListItemSecondaryAction>
                    <IconButton
                      edge="end"
                      size="small"
                      onClick={(e) => handleDeleteSession(session.id, e)}
                    >
                      <DeleteIcon fontSize="small" />
                    </IconButton>
                  </ListItemSecondaryAction>
                </ListItemButton>
              </ListItem>
            ))}
          </List>
        )}
      </Box>

      {/* Footer */}
      <Divider />
      <Box sx={{ p: 2 }}>
        <Typography variant="caption" color="text.secondary">
          {sessions.length} session{sessions.length !== 1 ? 's' : ''}
        </Typography>
      </Box>
    </Box>
  );
}
