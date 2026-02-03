import { useCallback, useRef, useEffect, useState } from 'react';
import {
  Box,
  Drawer,
  IconButton,
  Avatar,
  Menu,
  MenuItem,
  Typography,
  CircularProgress,
  Button,
} from '@mui/material';
import MenuIcon from '@mui/icons-material/Menu';
import ChevronLeftIcon from '@mui/icons-material/ChevronLeft';
import DragIndicatorIcon from '@mui/icons-material/DragIndicator';
import AccountCircleIcon from '@mui/icons-material/AccountCircle';
import SettingsIcon from '@mui/icons-material/Settings';
import LogoutIcon from '@mui/icons-material/Logout';
import RefreshIcon from '@mui/icons-material/Refresh';

import { useSessionStore } from '@/store/sessionStore';
import { useAgentStore } from '@/store/agentStore';
import { useLayoutStore } from '@/store/layoutStore';
import { useAuthStore } from '@/store/authStore';
import { useAgentEvents } from '@/hooks/useAgentEvents';
import SessionSidebar from '@/components/SessionSidebar/SessionSidebar';
import CodePanel from '@/components/CodePanel/CodePanel';
import ChatInput from '@/components/Chat/ChatInput';
import MessageList from '@/components/Chat/MessageList';
import { WelcomeScreen } from '@/components/Welcome';
import { SettingsModal } from '@/components/Settings';
import type { Message } from '@/types/agent';

const API_BASE = import.meta.env.DEV ? 'http://127.0.0.1:7860' : '';
const DRAWER_WIDTH = 260;

export default function AppLayout() {
  // Session store - using new state machine
  const {
    sessions,
    sessionsLoading,
    sessionsLoaded,
    phase,
    loadSessions,
    createSession,
    selectSession,
    getActiveSessionId,
  } = useSessionStore();

  // Agent store
  const { isConnected, isProcessing, messages, addMessage } = useAgentStore();

  // Layout store
  const {
    isLeftSidebarOpen,
    isRightPanelOpen,
    rightPanelWidth,
    setRightPanelWidth,
    toggleLeftSidebar,
    toggleRightPanel
  } = useLayoutStore();

  // Auth store - subscribe to user directly to track auth state changes
  const { user, isLoading: authLoading, getAuthHeaders, isAuthenticated, logout } = useAuthStore();
  const isAuthed = isAuthenticated(); // Compute once to use in effects

  // Local state
  const [userMenuAnchor, setUserMenuAnchor] = useState<null | HTMLElement>(null);
  const [showSettings, setShowSettings] = useState(false);

  const isResizing = useRef(false);

  // Connect SSE - hook internally manages phase checking
  useAgentEvents();

  // Panel resize handlers
  const startResizing = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    isResizing.current = true;
    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', stopResizing);
    document.body.style.cursor = 'col-resize';
  }, []);

  const stopResizing = useCallback(() => {
    isResizing.current = false;
    document.removeEventListener('mousemove', handleMouseMove);
    document.removeEventListener('mouseup', stopResizing);
    document.body.style.cursor = 'default';
  }, []);

  const handleMouseMove = useCallback((e: MouseEvent) => {
    if (!isResizing.current) return;
    const newWidth = window.innerWidth - e.clientX;
    const maxWidth = window.innerWidth * 0.8;
    const minWidth = 300;
    if (newWidth > minWidth && newWidth < maxWidth) {
      setRightPanelWidth(newWidth);
    }
  }, [setRightPanelWidth]);

  useEffect(() => {
    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', stopResizing);
    };
  }, [handleMouseMove, stopResizing]);

  // Load sessions when authenticated (and auth is complete)
  useEffect(() => {
    if (isAuthed && !authLoading && !sessionsLoaded && !sessionsLoading) {
      console.log('[AppLayout] Auth complete, loading sessions...');
      loadSessions();
    }
  }, [isAuthed, authLoading, sessionsLoaded, sessionsLoading, loadSessions]);

  // Auto-create first session when:
  // - Authenticated
  // - Sessions loaded
  // - No sessions exist
  // - Phase is idle (not already loading/creating)
  useEffect(() => {
    if (
      isAuthed &&
      sessionsLoaded &&
      sessions.length === 0 &&
      phase.status === 'idle'
    ) {
      console.log('[AppLayout] No sessions found, creating first session...');
      createSession();
    }
  }, [isAuthed, sessionsLoaded, sessions.length, phase.status, createSession]);

  // Send message handler
  const handleSendMessage = useCallback(
    async (text: string) => {
      const activeSessionId = getActiveSessionId();
      if (!activeSessionId || !text.trim()) return;

      const userMsg: Message = {
        id: `user_${Date.now()}`,
        role: 'user',
        content: text.trim(),
        timestamp: new Date().toISOString(),
      };
      addMessage(userMsg);

      try {
        await fetch(`${API_BASE}/api/submit`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            ...getAuthHeaders(),
          },
          body: JSON.stringify({
            session_id: activeSessionId,
            text: text.trim(),
          }),
        });
      } catch (e) {
        console.error('Send failed:', e);
      }
    },
    [getActiveSessionId, addMessage, getAuthHeaders]
  );

  const handleLogout = async () => {
    setUserMenuAnchor(null);
    await logout();
  };

  const handleOpenSettings = () => {
    setUserMenuAnchor(null);
    setShowSettings(true);
  };

  // Render: Auth loading
  if (authLoading) {
    return (
      <Box
        sx={{
          width: '100%',
          height: '100%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          background: 'var(--bg)',
        }}
      >
        <CircularProgress />
      </Box>
    );
  }

  // Render: Not authenticated
  if (!isAuthed) {
    return <WelcomeScreen />;
  }

  // Derive UI state from phase
  const isSessionLoading = phase.status === 'loading';
  const isSessionReady = phase.status === 'ready' || phase.status === 'active';
  const isSessionError = phase.status === 'error';
  const isIdle = phase.status === 'idle';

  // Determine if chat input should be disabled
  const isChatDisabled = isProcessing || !isConnected || !isSessionReady;

  return (
    <Box sx={{ display: 'flex', width: '100%', height: '100%' }}>
      {/* Left Sidebar Drawer */}
      <Box
        component="nav"
        sx={{
          width: { md: isLeftSidebarOpen ? DRAWER_WIDTH : 0 },
          flexShrink: { md: 0 },
          transition: isResizing.current ? 'none' : 'width 0.2s',
          overflow: 'hidden',
        }}
      >
        <Drawer
          variant="persistent"
          sx={{
            display: { xs: 'none', md: 'block' },
            '& .MuiDrawer-paper': {
              boxSizing: 'border-box',
              width: DRAWER_WIDTH,
              borderRight: '1px solid',
              borderColor: 'divider',
              top: 0,
              height: '100%',
              bgcolor: 'var(--panel)',
            },
          }}
          open={isLeftSidebarOpen}
        >
          <SessionSidebar />
        </Drawer>
      </Box>

      {/* Main Content Area */}
      <Box
        sx={{
          flexGrow: 1,
          height: '100%',
          display: 'flex',
          flexDirection: 'column',
          transition: isResizing.current ? 'none' : 'width 0.2s',
          position: 'relative',
          overflow: 'hidden',
        }}
      >
        {/* Top Header Bar */}
        <Box
          sx={{
            height: '60px',
            px: 1,
            display: 'flex',
            alignItems: 'center',
            borderBottom: 1,
            borderColor: 'divider',
            bgcolor: 'background.default',
            zIndex: 1200,
          }}
        >
          <IconButton onClick={toggleLeftSidebar} size="small">
            {isLeftSidebarOpen ? <ChevronLeftIcon /> : <MenuIcon />}
          </IconButton>

          <Box sx={{ flex: 1, display: 'flex', justifyContent: 'center' }}>
            <img
              src="/hf-logo-white.png"
              alt="Hugging Face"
              style={{ height: '40px', objectFit: 'contain' }}
            />
          </Box>

          {/* User Section */}
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <IconButton
              onClick={(e) => setUserMenuAnchor(e.currentTarget)}
              size="small"
            >
              {user?.picture ? (
                <Avatar src={user.picture} sx={{ width: 32, height: 32 }} />
              ) : (
                <AccountCircleIcon />
              )}
            </IconButton>
            <Menu
              anchorEl={userMenuAnchor}
              open={Boolean(userMenuAnchor)}
              onClose={() => setUserMenuAnchor(null)}
            >
              <MenuItem disabled>
                <Typography variant="body2">{user?.name || user?.username}</Typography>
              </MenuItem>
              <MenuItem onClick={handleOpenSettings}>
                <SettingsIcon sx={{ mr: 1 }} fontSize="small" />
                Settings
              </MenuItem>
              <MenuItem onClick={handleLogout}>
                <LogoutIcon sx={{ mr: 1 }} fontSize="small" />
                Logout
              </MenuItem>
            </Menu>

            <IconButton
              onClick={toggleRightPanel}
              size="small"
              sx={{ visibility: isRightPanelOpen ? 'hidden' : 'visible' }}
            >
              <MenuIcon />
            </IconButton>
          </Box>
        </Box>

        {/* Chat Area - Content depends on phase */}
        <Box
          component="main"
          className="chat-pane"
          sx={{
            flexGrow: 1,
            display: 'flex',
            flexDirection: 'column',
            overflow: 'hidden',
            background: 'linear-gradient(180deg, var(--bg), var(--panel))',
            padding: '24px',
          }}
        >
          {/* Idle state - no session selected */}
          {isIdle && sessions.length > 0 && (
            <Box sx={{
              flex: 1,
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 2,
            }}>
              <Typography variant="h6" sx={{ color: 'var(--muted-text)' }}>
                Select a session to continue
              </Typography>
              <Typography variant="body2" sx={{ color: 'var(--muted-text)' }}>
                Or create a new session from the sidebar
              </Typography>
            </Box>
          )}

          {/* Loading state */}
          {isSessionLoading && (
            <Box sx={{
              flex: 1,
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 2,
            }}>
              <CircularProgress />
              <Typography variant="body2" sx={{ color: 'var(--muted-text)' }}>
                Loading session...
              </Typography>
            </Box>
          )}

          {/* Error state */}
          {isSessionError && (
            <Box sx={{
              flex: 1,
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 2,
            }}>
              <Typography variant="h6" sx={{ color: 'var(--accent-red)' }}>
                Failed to load session
              </Typography>
              <Typography variant="body2" sx={{ color: 'var(--muted-text)' }}>
                {phase.status === 'error' ? phase.error : 'Unknown error'}
              </Typography>
              <Button
                variant="outlined"
                startIcon={<RefreshIcon />}
                onClick={() => {
                  if (phase.status === 'error' && phase.sessionId !== '_new_') {
                    selectSession(phase.sessionId);
                  } else {
                    createSession();
                  }
                }}
                sx={{ mt: 2 }}
              >
                Retry
              </Button>
            </Box>
          )}

          {/* Ready/Active state - show chat */}
          {isSessionReady && (
            <>
              <MessageList messages={messages} isProcessing={isProcessing} />
              <ChatInput onSend={handleSendMessage} disabled={isChatDisabled} />
            </>
          )}
        </Box>
      </Box>

      {/* Resize Handle */}
      {isRightPanelOpen && (
        <Box
          onMouseDown={startResizing}
          sx={{
            width: '4px',
            cursor: 'col-resize',
            bgcolor: 'divider',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            transition: 'background-color 0.2s',
            zIndex: 1300,
            overflow: 'hidden',
            '&:hover': {
              bgcolor: 'primary.main',
            },
          }}
        >
          <DragIndicatorIcon
            sx={{
              fontSize: '0.8rem',
              color: 'text.secondary',
              pointerEvents: 'none',
            }}
          />
        </Box>
      )}

      {/* Right Panel Drawer */}
      <Box
        component="nav"
        sx={{
          width: { md: isRightPanelOpen ? rightPanelWidth : 0 },
          flexShrink: { md: 0 },
          transition: isResizing.current ? 'none' : 'width 0.2s',
          overflow: 'hidden',
        }}
      >
        <Drawer
          anchor="right"
          variant="persistent"
          sx={{
            display: { xs: 'none', md: 'block' },
            '& .MuiDrawer-paper': {
              boxSizing: 'border-box',
              width: rightPanelWidth,
              borderLeft: 'none',
              top: 0,
              height: '100%',
              bgcolor: 'var(--panel)',
            },
          }}
          open={isRightPanelOpen}
        >
          <CodePanel />
        </Drawer>
      </Box>

      {/* Settings Modal */}
      <SettingsModal open={showSettings} onClose={() => setShowSettings(false)} />
    </Box>
  );
}
