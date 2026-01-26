import { useCallback, useRef, useEffect } from 'react';
import {
  Box,
  Drawer,
  Typography,
  IconButton,
} from '@mui/material';
import MenuIcon from '@mui/icons-material/Menu';
import ChevronLeftIcon from '@mui/icons-material/ChevronLeft';
import DragIndicatorIcon from '@mui/icons-material/DragIndicator';

import { useSessionStore } from '@/store/sessionStore';
import { useAgentStore } from '@/store/agentStore';
import { useLayoutStore } from '@/store/layoutStore';
import { useAgentWebSocket } from '@/hooks/useAgentWebSocket';
import SessionSidebar from '@/components/SessionSidebar/SessionSidebar';
import CodePanel from '@/components/CodePanel/CodePanel';
import ChatInput from '@/components/Chat/ChatInput';
import MessageList from '@/components/Chat/MessageList';
import type { Message } from '@/types/agent';

const DRAWER_WIDTH = 260;

export default function AppLayout() {
  const { activeSessionId } = useSessionStore();
  const { isConnected, isProcessing, getMessages, addMessage } = useAgentStore();
  const { 
    isLeftSidebarOpen, 
    isRightPanelOpen, 
    rightPanelWidth,
    setRightPanelWidth,
    toggleLeftSidebar, 
    toggleRightPanel 
  } = useLayoutStore();

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

  const messages = activeSessionId ? getMessages(activeSessionId) : [];

  useAgentWebSocket({
    sessionId: activeSessionId,
    onReady: () => console.log('Agent ready'),
    onError: (error) => console.error('Agent error:', error),
  });

  const handleSendMessage = useCallback(
    async (text: string) => {
      if (!activeSessionId || !text.trim()) return;
      
      const userMsg: Message = {
        id: `user_${Date.now()}`,
        role: 'user',
        content: text.trim(),
        timestamp: new Date().toISOString(),
      };
      addMessage(activeSessionId, userMsg);

      try {
        await fetch('/api/submit', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            session_id: activeSessionId,
            text: text.trim(),
          }),
        });
      } catch (e) {
        console.error('Send failed:', e);
      }
    },
    [activeSessionId, addMessage]
  );

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
              bgcolor: 'var(--panel)', // Ensure correct background matches sidebar
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
        {/* Top Header Bar (Fixed) */}
        <Box sx={{ 
          height: '60px',
          px: 1, 
          display: 'flex', 
          alignItems: 'center', 
          borderBottom: 1, 
          borderColor: 'divider',
          bgcolor: 'background.default',
          zIndex: 1200,
        }}>
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

          <IconButton 
            onClick={toggleRightPanel} 
            size="small" 
            sx={{ visibility: isRightPanelOpen ? 'hidden' : 'visible' }}
          >
            <MenuIcon />
          </IconButton>
        </Box>

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
          {activeSessionId ? (
            <>
              <MessageList messages={messages} isProcessing={isProcessing} />
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
              }}
            >
              <Typography variant="h5" color="text.secondary" sx={{ fontFamily: 'monospace' }}>
                NO SESSION SELECTED
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ fontFamily: 'monospace' }}>
                Initialize a session via the sidebar
              </Typography>
            </Box>
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
    </Box>
  );
}
