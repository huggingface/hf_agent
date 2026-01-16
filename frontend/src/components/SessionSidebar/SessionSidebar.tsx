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
  Tooltip,
} from '@mui/material';
import DeleteIcon from '@mui/icons-material/Delete';
import UndoIcon from '@mui/icons-material/Undo';
import FiberManualRecordIcon from '@mui/icons-material/FiberManualRecord';
import { useSessionStore } from '@/store/sessionStore';
import { useAgentStore } from '@/store/agentStore';

interface SessionSidebarProps {
  onClose?: () => void;
}

const StatusDiode = ({ connected }: { connected: boolean }) => (
  <Box
    sx={{
      width: 8,
      height: 8,
      borderRadius: '50%',
      bgcolor: connected ? 'success.main' : 'error.main',
      boxShadow: connected ? '0 0 0 0 rgba(46, 160, 67, 0.7)' : 'none',
      animation: connected ? 'pulse 2s infinite' : 'none',
      '@keyframes pulse': {
        '0%': {
          transform: 'scale(0.95)',
          boxShadow: '0 0 0 0 rgba(46, 160, 67, 0.7)',
        },
        '70%': {
          transform: 'scale(1)',
          boxShadow: '0 0 0 4px rgba(46, 160, 67, 0)',
        },
        '100%': {
          transform: 'scale(0.95)',
          boxShadow: '0 0 0 0 rgba(46, 160, 67, 0)',
        },
      },
    }}
  />
);

export default function SessionSidebar({ onClose }: SessionSidebarProps) {
  const { sessions, activeSessionId, createSession, deleteSession, switchSession } =
    useSessionStore();
  const { clearMessages, isConnected, isProcessing } = useAgentStore();

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

  const handleUndo = useCallback(async () => {
    if (!activeSessionId) return;
    try {
      await fetch(`/api/undo/${activeSessionId}`, { method: 'POST' });
    } catch (e) {
      console.error('Undo failed:', e);
    }
  }, [activeSessionId]);

  const formatTime = (dateString: string) => {
    return new Date(dateString).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  };

  return (
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      {/* Header */}
      <Box sx={{ p: 2, borderBottom: 1, borderColor: 'divider', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
        <Box sx={{ mb: 2 }}>
          <img 
            src="/hf-log-only-white.png" 
            alt="HF Agent" 
            style={{ height: '32px', objectFit: 'contain' }} 
          />
        </Box>

        {/* System Info / Status */}
        <Box sx={{ mb: 2, display: 'flex', alignItems: 'center', gap: 1 }}>
          <Typography variant="caption" color="text.secondary" sx={{ fontFamily: 'monospace' }}>
            {isConnected ? 'Connected' : 'Disconnected'}
          </Typography>
          <StatusDiode connected={isConnected} />
        </Box>

        <Button
          fullWidth
          variant="outlined"
          onClick={handleNewSession}
          sx={{ justifyContent: 'center' }}
        >
          Create Session
        </Button>
      </Box>

      {/* Session List */}
      <Box sx={{ flex: 1, overflow: 'auto' }}>
        {sessions.length === 0 ? (
          <Box sx={{ p: 3, textAlign: 'center' }}>
            <Typography variant="body2" color="text.secondary" sx={{ fontFamily: 'monospace' }}>
              NO ACTIVE SESSIONS
            </Typography>
            <Typography variant="caption" color="text.secondary">
              Initialize a new session to begin
            </Typography>
          </Box>
        ) : (
          <List disablePadding>
            {[...sessions].reverse().map((session, index) => {
              const sessionNumber = sessions.length - index;
              return (
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
                        <Typography variant="body2" sx={{ fontFamily: 'monospace', fontWeight: 600 }}>
                          SESSION {String(sessionNumber).padStart(3, '0')}
                        </Typography>
                      }
                      secondary={
                        <Typography variant="caption" sx={{ fontFamily: 'monospace', display: 'flex', alignItems: 'center', gap: 1 }}>
                          <span style={{ color: session.isActive ? 'var(--mui-palette-success-main)' : 'var(--mui-palette-text-secondary)' }}>
                            {session.isActive ? 'RUNNING' : 'STOPPED'}
                          </span>
                          <span>·</span>
                          <span>{formatTime(session.createdAt)}</span>
                        </Typography>
                      }
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
              );
            })}
          </List>
        )}
      </Box>

      {/* Footer */}
      <Divider />
      <Box sx={{ p: 2, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <Typography variant="caption" color="text.secondary" sx={{ fontFamily: 'monospace' }}>
          {sessions.length} SESSION{sessions.length !== 1 ? 'S' : ''}
        </Typography>
        <Tooltip title="Undo last turn">
          <span>
            <IconButton
              onClick={handleUndo}
              disabled={!activeSessionId || isProcessing}
              size="small"
            >
              <UndoIcon fontSize="small" />
            </IconButton>
          </span>
        </Tooltip>
      </Box>
    </Box>
  );
}
