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
} from '@mui/material';
import MenuIcon from '@mui/icons-material/Menu';
import ChevronLeftIcon from '@mui/icons-material/ChevronLeft';
import DragIndicatorIcon from '@mui/icons-material/DragIndicator';
import AccountCircleIcon from '@mui/icons-material/AccountCircle';
import SettingsIcon from '@mui/icons-material/Settings';
import LogoutIcon from '@mui/icons-material/Logout';

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
import { SetupPrompt } from '@/components/Onboarding';
import { SettingsModal } from '@/components/Settings';
import type { Message } from '@/types/agent';

const API_BASE = import.meta.env.DEV ? 'http://127.0.0.1:7860' : '';
const DRAWER_WIDTH = 260;

export default function AppLayout() {
  const { activeSessionId, sessions, isLoading: sessionsLoading, loadSessions, createSession } = useSessionStore();
  const { isConnected, isProcessing, messages, addMessage, clearMessages, setPlan, setPanelContent } = useAgentStore();
  const {
    isLeftSidebarOpen,
    isRightPanelOpen,
    rightPanelWidth,
    setRightPanelWidth,
    toggleLeftSidebar,
    toggleRightPanel
  } = useLayoutStore();
  const { user, isLoading: authLoading, getAuthHeaders, isAuthenticated, logout } = useAuthStore();

  const [userMenuAnchor, setUserMenuAnchor] = useState<null | HTMLElement>(null);
  const [showSettings, setShowSettings] = useState(false);
  const [isCreatingSession, setIsCreatingSession] = useState(false);

  const isResizing = useRef(false);

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

  // Load sessions when authenticated
  useEffect(() => {
    if (isAuthenticated() && !sessionsLoading && sessions.length === 0) {
      loadSessions();
    }
  }, [isAuthenticated, sessionsLoading, sessions.length, loadSessions]);

  useAgentEvents({
    sessionId: activeSessionId,
    onReady: () => console.log('Agent ready'),
    onError: (error) => console.error('Agent error:', error),
  });

  const handleSendMessage = useCallback(
    async (text: string) => {
      if (!activeSessionId || !text.trim()) return;

      // Check if user has Anthropic key
      if (isAuthenticated() && !user?.has_anthropic_key) {
        setShowSettings(true);
        return;
      }

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
    [activeSessionId, addMessage, getAuthHeaders, isAuthenticated, user]
  );

  const handleLogout = async () => {
    setUserMenuAnchor(null);
    await logout();
  };

  const handleOpenSettings = () => {
    setUserMenuAnchor(null);
    setShowSettings(true);
  };

  const handleStartSession = useCallback(async () => {
    setIsCreatingSession(true);
    try {
      const sessionId = await createSession();
      if (sessionId) {
        clearMessages();
        setPlan([]);
        setPanelContent(null);
      }
    } catch (e) {
      console.error('Failed to create session:', e);
    } finally {
      setIsCreatingSession(false);
    }
  }, [createSession, clearMessages, setPlan, setPanelContent]);

  // Show loading spinner while auth is loading
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

  // Show welcome screen for unauthenticated users
  if (!isAuthenticated()) {
    return <WelcomeScreen />;
  }

  // Show loading while sessions are being fetched
  if (sessionsLoading) {
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

  // Show setup prompt only if:
  // 1. No API key (always need to set that up first)
  // 2. No sessions exist AND no active session (first time user)
  const needsApiKey = !user?.has_anthropic_key;
  const noSessionsAtAll = sessions.length === 0 && !activeSessionId;

  if (needsApiKey || noSessionsAtAll) {
    return (
      <Box sx={{ width: '100%', height: '100%', display: 'flex', flexDirection: 'column' }}>
        {/* Minimal header for setup screens */}
        <Box
          sx={{
            height: '60px',
            px: 2,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            borderBottom: 1,
            borderColor: 'divider',
            bgcolor: 'background.default',
          }}
        >
          <img
            src="/hf-logo-white.png"
            alt="Hugging Face"
            style={{ height: '32px', objectFit: 'contain' }}
          />
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <IconButton onClick={handleOpenSettings} size="small">
              <SettingsIcon />
            </IconButton>
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
          </Box>
        </Box>

        {/* Setup content */}
        <Box sx={{ flex: 1 }}>
          <SetupPrompt
            hasApiKey={!needsApiKey}
            onOpenSettings={handleOpenSettings}
            onStartSession={handleStartSession}
            isCreatingSession={isCreatingSession}
          />
        </Box>

        <SettingsModal open={showSettings} onClose={() => setShowSettings(false)} />
      </Box>
    );
  }

  // Full app layout for authenticated users with active session
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
            <IconButton onClick={handleOpenSettings} size="small">
              <SettingsIcon />
            </IconButton>
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

        {/* Chat Area */}
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
          <MessageList messages={messages} isProcessing={isProcessing} />
          <ChatInput onSend={handleSendMessage} disabled={isProcessing || !isConnected} />
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
