import { useCallback, useRef, useEffect } from 'react';
import {
  Avatar,
  Box,
  Drawer,
  Typography,
  IconButton,
  Alert,
  AlertTitle,
  useMediaQuery,
  useTheme,
} from '@mui/material';
import MenuIcon from '@mui/icons-material/Menu';
import ChevronLeftIcon from '@mui/icons-material/ChevronLeft';
import DragIndicatorIcon from '@mui/icons-material/DragIndicator';
import DarkModeOutlinedIcon from '@mui/icons-material/DarkModeOutlined';
import LightModeOutlinedIcon from '@mui/icons-material/LightModeOutlined';
import { logger } from '@/utils/logger';

import { useSessionStore } from '@/store/sessionStore';
import { useAgentStore } from '@/store/agentStore';
import { useLayoutStore } from '@/store/layoutStore';
import { useAgentWebSocket } from '@/hooks/useAgentWebSocket';
import SessionSidebar from '@/components/SessionSidebar/SessionSidebar';
import CodePanel from '@/components/CodePanel/CodePanel';
import ChatInput from '@/components/Chat/ChatInput';
import MessageList from '@/components/Chat/MessageList';
import WelcomeScreen from '@/components/WelcomeScreen/WelcomeScreen';
import { apiFetch } from '@/utils/api';
import type { Message } from '@/types/agent';

const DRAWER_WIDTH = 260;

export default function AppLayout() {
  const { sessions, activeSessionId, deleteSession, updateSessionTitle } = useSessionStore();
  const { isConnected, isProcessing, getMessages, addMessage, setProcessing, llmHealthError, setLlmHealthError, user } = useAgentStore();
  const { 
    isLeftSidebarOpen, 
    isRightPanelOpen, 
    rightPanelWidth,
    themeMode,
    setRightPanelWidth,
    setLeftSidebarOpen,
    toggleLeftSidebar, 
    toggleTheme,
  } = useLayoutStore();

  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));

  const isResizing = useRef(false);

  const handleMouseMove = useCallback((e: MouseEvent) => {
    if (!isResizing.current) return;
    const newWidth = window.innerWidth - e.clientX;
    const maxWidth = window.innerWidth * 0.6;
    const minWidth = 300;
    if (newWidth > minWidth && newWidth < maxWidth) {
      setRightPanelWidth(newWidth);
    }
  }, [setRightPanelWidth]);

  const stopResizing = useCallback(() => {
    isResizing.current = false;
    document.removeEventListener('mousemove', handleMouseMove);
    document.removeEventListener('mouseup', stopResizing);
    document.body.style.cursor = 'default';
  }, [handleMouseMove]);

  const startResizing = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    isResizing.current = true;
    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', stopResizing);
    document.body.style.cursor = 'col-resize';
  }, [handleMouseMove, stopResizing]);

  useEffect(() => {
    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', stopResizing);
    };
  }, [handleMouseMove, stopResizing]);

  // ── LLM health check on mount ───────────────────────────────────
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await apiFetch('/api/health/llm');
        const data = await res.json();
        if (!cancelled && data.status === 'error') {
          setLlmHealthError({
            error: data.error || 'Unknown LLM error',
            errorType: data.error_type || 'unknown',
            model: data.model,
          });
        } else if (!cancelled) {
          setLlmHealthError(null);
        }
      } catch {
        // Backend unreachable — not an LLM issue, ignore
      }
    })();
    return () => { cancelled = true; };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const messages = activeSessionId ? getMessages(activeSessionId) : [];
  const hasAnySessions = sessions.length > 0;

  useAgentWebSocket({
    sessionId: activeSessionId,
    onReady: () => logger.log('Agent ready'),
    onError: (error) => logger.error('Agent error:', error),
    onSessionDead: (deadSessionId) => {
      logger.log('Removing dead session:', deadSessionId);
      deleteSession(deadSessionId);
    },
  });

  const handleSendMessage = useCallback(
    async (text: string) => {
      if (!activeSessionId || !text.trim() || isProcessing) return;
      
      // Lock input immediately to prevent double-sends
      setProcessing(true);

      const userMsg: Message = {
        id: `user_${Date.now()}`,
        role: 'user',
        content: text.trim(),
        timestamp: new Date().toISOString(),
      };
      addMessage(activeSessionId, userMsg);

      // Auto-title the session from the first user message (async, non-blocking)
      const currentMessages = getMessages(activeSessionId);
      const isFirstMessage = currentMessages.filter((m) => m.role === 'user').length <= 1;
      if (isFirstMessage) {
        const sessionId = activeSessionId;
        apiFetch('/api/title', {
          method: 'POST',
          body: JSON.stringify({ session_id: sessionId, text: text.trim() }),
        })
          .then((res) => res.json())
          .then((data) => {
            if (data.title) updateSessionTitle(sessionId, data.title);
          })
          .catch(() => {
            const raw = text.trim();
            updateSessionTitle(sessionId, raw.length > 40 ? raw.slice(0, 40) + '…' : raw);
          });
      }

      try {
        await apiFetch('/api/submit', {
          method: 'POST',
          body: JSON.stringify({
            session_id: activeSessionId,
            text: text.trim(),
          }),
        });
      } catch (e) {
        logger.error('Send failed:', e);
      }
    },
    [activeSessionId, addMessage, getMessages, updateSessionTitle, isProcessing, setProcessing]
  );

  // Close sidebar on mobile after selecting a session
  const handleSidebarClose = useCallback(() => {
    if (isMobile) setLeftSidebarOpen(false);
  }, [isMobile, setLeftSidebarOpen]);

  // ── LLM error banner (shared) ─────────────────────────────────────
  const llmBanner = llmHealthError && (
    <Alert
      severity="error"
      variant="filled"
      onClose={() => setLlmHealthError(null)}
      sx={{ borderRadius: 0, flexShrink: 0, '& .MuiAlert-message': { flex: 1 } }}
    >
      <AlertTitle sx={{ fontWeight: 700, fontSize: '0.85rem' }}>
        {llmHealthError.errorType === 'credits'
          ? 'API Credits Exhausted'
          : llmHealthError.errorType === 'auth'
          ? 'Invalid API Key'
          : llmHealthError.errorType === 'rate_limit'
          ? 'Rate Limited'
          : llmHealthError.errorType === 'network'
          ? 'LLM Provider Unreachable'
          : 'LLM Error'}
      </AlertTitle>
      <Typography variant="body2" sx={{ fontSize: '0.8rem', opacity: 0.9 }}>
        Model: <strong>{llmHealthError.model}</strong> — {llmHealthError.error.slice(0, 200)}
      </Typography>
    </Alert>
  );

  // ── Welcome screen: no sessions at all ────────────────────────────
  if (!hasAnySessions) {
    return (
      <Box sx={{ width: '100%', height: '100%', display: 'flex', flexDirection: 'column' }}>
        {llmBanner}
        <WelcomeScreen />
      </Box>
    );
  }

  // ── Sidebar drawer ────────────────────────────────────────────────
  const sidebarDrawer = (
    <Drawer
      variant={isMobile ? 'temporary' : 'persistent'}
      anchor="left"
      open={isLeftSidebarOpen}
      onClose={() => setLeftSidebarOpen(false)}
      ModalProps={{ keepMounted: true }} // Better mobile perf
      sx={{
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
    >
      <SessionSidebar onClose={handleSidebarClose} />
    </Drawer>
  );

  // ── Main chat interface ───────────────────────────────────────────
  return (
    <Box sx={{ display: 'flex', width: '100%', height: '100%' }}>
      {/* ── Left Sidebar ─────────────────────────────────────────── */}
      {isMobile ? (
        // Mobile: temporary overlay drawer (no reserved width)
        sidebarDrawer
      ) : (
        // Desktop: persistent drawer with reserved width
        <Box
          component="nav"
          sx={{
            width: isLeftSidebarOpen ? DRAWER_WIDTH : 0,
            flexShrink: 0,
            transition: isResizing.current ? 'none' : 'width 0.2s',
            overflow: 'hidden',
          }}
        >
          {sidebarDrawer}
        </Box>
      )}

      {/* ── Main Content (header + chat + code panel) ────────────── */}
      <Box
        sx={{
          flexGrow: 1,
          height: '100%',
          display: 'flex',
          flexDirection: 'column',
          transition: isResizing.current ? 'none' : 'width 0.2s',
          overflow: 'hidden',
          minWidth: 0,
        }}
      >
        {/* ── Top Header Bar ─────────────────────────────────────── */}
        <Box sx={{ 
          height: { xs: 52, md: 60 },
          px: { xs: 1, md: 2 }, 
          display: 'flex', 
          alignItems: 'center', 
          borderBottom: 1, 
          borderColor: 'divider',
          bgcolor: 'background.default',
          zIndex: 1200,
          flexShrink: 0,
        }}>
          <IconButton onClick={toggleLeftSidebar} size="small">
            {isLeftSidebarOpen && !isMobile ? <ChevronLeftIcon /> : <MenuIcon />}
          </IconButton>
          
          <Box sx={{ flex: 1, display: 'flex', justifyContent: 'center', alignItems: 'center', gap: 0.75 }}>
            <Box
              component="img"
              src="https://huggingface.co/front/assets/huggingface_logo-noborder.svg"
              alt="HF"
              sx={{ width: { xs: 20, md: 22 }, height: { xs: 20, md: 22 } }}
            />
            <Typography
              variant="subtitle1"
              sx={{
                fontWeight: 700,
                color: 'var(--text)',
                letterSpacing: '-0.01em',
                fontSize: { xs: '0.88rem', md: '0.95rem' },
              }}
            >
              HF Agent
            </Typography>
          </Box>

          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
            <IconButton
              onClick={toggleTheme}
              size="small"
              sx={{
                color: 'text.secondary',
                '&:hover': { color: 'primary.main' },
              }}
            >
              {themeMode === 'dark' ? <LightModeOutlinedIcon fontSize="small" /> : <DarkModeOutlinedIcon fontSize="small" />}
            </IconButton>

            {user?.picture ? (
              <Avatar
                src={user.picture}
                alt={user.username || 'User'}
                sx={{ width: 28, height: 28, ml: 0.5 }}
              />
            ) : user?.username ? (
              <Avatar
                sx={{
                  width: 28,
                  height: 28,
                  ml: 0.5,
                  bgcolor: 'primary.main',
                  fontSize: '0.75rem',
                  fontWeight: 700,
                }}
              >
                {user.username[0].toUpperCase()}
              </Avatar>
            ) : null}
          </Box>
        </Box>

        {/* ── LLM Health Error Banner ────────────────────────────── */}
        {llmBanner}

        {/* ── Chat + Code Panel ──────────────────────────────────── */}
        <Box
          sx={{
            flexGrow: 1,
            display: 'flex',
            overflow: 'hidden',
          }}
        >
          {/* Chat area */}
          <Box
            component="main"
            className="chat-pane"
            sx={{
              flexGrow: 1,
              display: 'flex',
              flexDirection: 'column',
              overflow: 'hidden',
              background: 'var(--body-gradient)',
              p: { xs: 1.5, sm: 2, md: 3 },
              minWidth: 0,
            }}
          >
            {activeSessionId ? (
              <>
                <MessageList messages={messages} isProcessing={isProcessing} />
                {!isConnected && messages.length > 0 && (
                  <Box sx={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: 1,
                    py: 1,
                    px: { xs: 1, md: 2 },
                    mb: 1,
                    borderRadius: 'var(--radius-md)',
                    bgcolor: 'rgba(255, 171, 0, 0.08)',
                    border: '1px solid rgba(255, 171, 0, 0.2)',
                  }}>
                    <Typography variant="body2" sx={{ color: 'var(--accent-yellow)', fontFamily: 'monospace', fontSize: { xs: '0.7rem', md: '0.8rem' } }}>
                      Session expired — create a new session to continue.
                    </Typography>
                  </Box>
                )}
                <ChatInput
                  onSend={handleSendMessage}
                  disabled={isProcessing || !isConnected}
                />
              </>
            ) : (
              <Box
                sx={{
                  flex: 1,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  flexDirection: 'column',
                  gap: 2,
                  px: 2,
                }}
              >
                <Typography variant="h5" color="text.secondary" sx={{ fontFamily: 'monospace', fontSize: { xs: '1rem', md: '1.5rem' } }}>
                  NO SESSION SELECTED
                </Typography>
                <Typography variant="body2" color="text.secondary" sx={{ fontFamily: 'monospace', fontSize: { xs: '0.75rem', md: '0.875rem' } }}>
                  Initialize a session via the sidebar
                </Typography>
              </Box>
            )}
          </Box>

          {/* Code panel — inline on desktop, overlay drawer on mobile */}
          {isRightPanelOpen && !isMobile && (
            <>
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
                  flexShrink: 0,
                  '&:hover': { bgcolor: 'primary.main' },
                }}
              >
                <DragIndicatorIcon 
                  sx={{ fontSize: '0.8rem', color: 'text.secondary', pointerEvents: 'none' }} 
                />
              </Box>
              <Box
                sx={{
                  width: rightPanelWidth,
                  flexShrink: 0,
                  height: '100%',
                  overflow: 'hidden',
                  borderLeft: '1px solid',
                  borderColor: 'divider',
                  bgcolor: 'var(--panel)',
                }}
              >
                <CodePanel />
              </Box>
            </>
          )}
        </Box>
      </Box>

      {/* Code panel — drawer overlay on mobile */}
      {isMobile && (
        <Drawer
          anchor="bottom"
          open={isRightPanelOpen}
          onClose={() => useLayoutStore.getState().setRightPanelOpen(false)}
          sx={{
            '& .MuiDrawer-paper': {
              height: '75vh',
              borderTopLeftRadius: 16,
              borderTopRightRadius: 16,
              bgcolor: 'var(--panel)',
            },
          }}
        >
          <CodePanel />
        </Drawer>
      )}
    </Box>
  );
}
