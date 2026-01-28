import { useCallback, useEffect } from 'react';
import {
  Box,
  List,
  ListItem,
  IconButton,
  Typography,
  Button,
  Tooltip,
  CircularProgress,
} from '@mui/material';
import DeleteIcon from '@mui/icons-material/Delete';
import UndoIcon from '@mui/icons-material/Undo';
import { useSessionStore } from '@/store/sessionStore';
import { useAgentStore } from '@/store/agentStore';
import { useAuthStore } from '@/store/authStore';

const API_BASE = import.meta.env.DEV ? 'http://127.0.0.1:7860' : '';

interface SessionSidebarProps {
  onClose?: () => void;
}

const StatusDiode = ({ connected }: { connected: boolean }) => (
  <Box
    sx={{
      width: 10,
      height: 10,
      borderRadius: '50%',
      bgcolor: connected ? 'var(--accent-green)' : 'var(--accent-red)',
      boxShadow: connected ? '0 0 6px rgba(47, 204, 113, 0.4)' : 'none',
      transition: 'all 0.3s ease',
    }}
  />
);

const RunningIndicator = () => (
  <Box
    className="running-indicator"
    sx={{
      width: 10,
      height: 10,
      borderRadius: '50%',
      bgcolor: 'var(--accent-yellow)',
      boxShadow: '0 0 6px rgba(199,165,0,0.18)',
    }}
  />
);

export default function SessionSidebar({ onClose }: SessionSidebarProps) {
  const {
    sessions,
    activeSessionId,
    createSession,
    deleteSession,
    switchSession,
    persistedSessions,
    isLoadingPersisted,
    loadPersistedSessions,
    resumeSession,
  } = useSessionStore();
  const { clearMessages, isConnected, isProcessing, setPlan, setPanelContent } = useAgentStore();
  const { getAuthHeaders, isAuthenticated } = useAuthStore();

  // Load persisted sessions on mount if authenticated
  useEffect(() => {
    if (isAuthenticated()) {
      loadPersistedSessions();
    }
  }, [isAuthenticated, loadPersistedSessions]);

  const handleNewSession = useCallback(async () => {
    try {
      // Use the new async createSession which includes auth headers
      const sessionId = await createSession();
      if (sessionId) {
        setPlan([]);
        setPanelContent(null);
        onClose?.();
      }
    } catch (e) {
      console.error('Failed to create session:', e);
    }
  }, [createSession, setPlan, setPanelContent, onClose]);

  const handleDeleteSession = useCallback(
    async (sessionId: string, e: React.MouseEvent) => {
      e.stopPropagation();
      try {
        await deleteSession(sessionId);
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
      setPlan([]);
      setPanelContent(null);
      onClose?.();
    },
    [switchSession, setPlan, setPanelContent, onClose]
  );

  const handleUndo = useCallback(async () => {
    if (!activeSessionId) return;
    try {
      await fetch(`${API_BASE}/api/undo/${activeSessionId}`, {
        method: 'POST',
        headers: getAuthHeaders(),
      });
    } catch (e) {
      console.error('Undo failed:', e);
    }
  }, [activeSessionId, getAuthHeaders]);

  const handleResumeSession = useCallback(async (sessionId: string) => {
    try {
      const newSessionId = await resumeSession(sessionId);
      if (newSessionId) {
        setPlan([]);
        setPanelContent(null);
        onClose?.();
      }
    } catch (e) {
      console.error('Failed to resume session:', e);
    }
  }, [resumeSession, setPlan, setPanelContent, onClose]);

  // Combine active and persisted sessions into unified list
  const inMemorySessionIds = new Set(sessions.map(s => s.id));

  // Create unified session items
  type UnifiedSession = {
    id: string;
    title: string;
    createdAt: string;
    isActive: boolean;
    isPersisted: boolean;
    messageCount?: number;
  };

  const unifiedSessions: UnifiedSession[] = [
    // In-memory sessions
    ...sessions.map((s, index) => ({
      id: s.id,
      title: s.title || `Session ${String(sessions.length - index).padStart(2, '0')}`,
      createdAt: s.createdAt,
      isActive: s.isActive,
      isPersisted: false,
    })),
    // Persisted sessions not in memory
    ...persistedSessions
      .filter(ps => !inMemorySessionIds.has(ps.session_id))
      .map(ps => ({
        id: ps.session_id,
        title: ps.title || `Session ${ps.session_id.slice(0, 8)}`,
        createdAt: ps.created_at,
        isActive: false,
        isPersisted: true,
        messageCount: ps.message_count,
      })),
  ].sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime());

  const formatTime = (dateString: string) => {
    const date = new Date(dateString);
    const now = new Date();
    const isToday = date.toDateString() === now.toDateString();
    if (isToday) {
      return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    }
    return date.toLocaleDateString([], { month: 'short', day: 'numeric' });
  };

  const handleSessionClick = useCallback((session: UnifiedSession) => {
    if (session.isPersisted) {
      handleResumeSession(session.id);
    } else {
      handleSelectSession(session.id);
    }
  }, [handleResumeSession, handleSelectSession]);

  return (
    <Box className="sidebar" sx={{ height: '100%', display: 'flex', flexDirection: 'column', bgcolor: 'var(--panel)' }}>
      {/* Header - Aligned with AppLayout 60px */}
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
        {/* System Info / Status */}
        <Box sx={{ mb: 2, display: 'flex', alignItems: 'center', gap: 1 }}>
          <StatusDiode connected={isConnected} />
          <Typography variant="caption" sx={{ color: 'var(--muted-text)', fontFamily: 'inherit' }}>
            {isConnected ? 'System Online' : 'Disconnected'}
          </Typography>
        </Box>

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
          {isLoadingPersisted && (
            <Box sx={{ display: 'flex', justifyContent: 'center', py: 2 }}>
              <CircularProgress size={20} sx={{ color: 'var(--muted-text)' }} />
            </Box>
          )}
          <List disablePadding sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
            {unifiedSessions.map((session) => {
              const isSelected = session.id === activeSessionId;
              return (
                <ListItem
                  key={session.id}
                  disablePadding
                  className="session-item"
                  onClick={() => handleSessionClick(session)}
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
                      {session.isActive && <RunningIndicator />}
                      <Typography className="time" variant="caption" sx={{ fontSize: '12px', color: 'var(--muted-text)' }}>
                        {formatTime(session.createdAt)}
                        {session.messageCount !== undefined && ` · ${session.messageCount} msgs`}
                      </Typography>
                    </Box>
                  </Box>

                  {!session.isPersisted && (
                    <IconButton
                      className="delete-btn"
                      size="small"
                      onClick={(e) => handleDeleteSession(session.id, e)}
                      sx={{ color: 'var(--muted-text)', '&:hover': { color: 'var(--accent-red)' } }}
                    >
                      <DeleteIcon fontSize="small" />
                    </IconButton>
                  )}
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
            {sessions.length} active
          </Typography>
          <Tooltip title="Undo last turn">
            <span>
              <IconButton
                onClick={handleUndo}
                disabled={!activeSessionId || isProcessing}
                size="small"
                sx={{ color: 'var(--muted-text)', '&:hover': { color: 'var(--text)' } }}
              >
                <UndoIcon fontSize="small" />
              </IconButton>
            </span>
          </Tooltip>
        </Box>
      </Box>
    </Box>
  );
}
