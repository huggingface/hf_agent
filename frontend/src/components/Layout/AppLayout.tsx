import { useState, useCallback } from 'react';
import {
  Box,
  AppBar,
  Toolbar,
  Typography,
  IconButton,
  Drawer,
  useMediaQuery,
  useTheme,
  Button,
  Chip,
} from '@mui/material';
import MenuIcon from '@mui/icons-material/Menu';
import UndoIcon from '@mui/icons-material/Undo';
import CompressIcon from '@mui/icons-material/Compress';
import FiberManualRecordIcon from '@mui/icons-material/FiberManualRecord';

import { useSessionStore } from '@/store/sessionStore';
import { useAgentStore } from '@/store/agentStore';
import { useAgentWebSocket } from '@/hooks/useAgentWebSocket';
import SessionSidebar from '@/components/SessionSidebar/SessionSidebar';
import ChatInput from '@/components/Chat/ChatInput';
import MessageList from '@/components/Chat/MessageList';
import ApprovalModal from '@/components/ApprovalModal/ApprovalModal';

const DRAWER_WIDTH = 280;

export default function AppLayout() {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));
  const [mobileOpen, setMobileOpen] = useState(false);

  const { activeSessionId } = useSessionStore();
  const { isConnected, isProcessing, getMessages } = useAgentStore();

  const messages = activeSessionId ? getMessages(activeSessionId) : [];

  useAgentWebSocket({
    sessionId: activeSessionId,
    onReady: () => console.log('Agent ready'),
    onError: (error) => console.error('Agent error:', error),
  });

  const handleDrawerToggle = () => {
    setMobileOpen(!mobileOpen);
  };

  const handleUndo = useCallback(async () => {
    if (!activeSessionId) return;
    try {
      await fetch(`/api/undo/${activeSessionId}`, { method: 'POST' });
    } catch (e) {
      console.error('Undo failed:', e);
    }
  }, [activeSessionId]);

  const handleCompact = useCallback(async () => {
    if (!activeSessionId) return;
    try {
      await fetch(`/api/compact/${activeSessionId}`, { method: 'POST' });
    } catch (e) {
      console.error('Compact failed:', e);
    }
  }, [activeSessionId]);

  const handleSendMessage = useCallback(
    async (text: string) => {
      if (!activeSessionId || !text.trim()) return;
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
    [activeSessionId]
  );

  const drawer = <SessionSidebar onClose={() => setMobileOpen(false)} />;

  return (
    <Box sx={{ display: 'flex', width: '100%', height: '100%' }}>
      {/* App Bar */}
      <AppBar
        position="fixed"
        sx={{
          width: { md: `calc(100% - ${DRAWER_WIDTH}px)` },
          ml: { md: `${DRAWER_WIDTH}px` },
          bgcolor: 'background.paper',
          borderBottom: 1,
          borderColor: 'divider',
        }}
        elevation={0}
      >
        <Toolbar>
          <IconButton
            color="inherit"
            edge="start"
            onClick={handleDrawerToggle}
            sx={{ mr: 2, display: { md: 'none' } }}
          >
            <MenuIcon />
          </IconButton>
          <Typography variant="h6" noWrap component="div" sx={{ flexGrow: 1 }}>
            HF Agent
          </Typography>
          <Chip
            icon={
              <FiberManualRecordIcon
                sx={{
                  fontSize: 12,
                  color: isConnected ? 'success.main' : 'error.main',
                }}
              />
            }
            label={isConnected ? 'Connected' : 'Disconnected'}
            size="small"
            variant="outlined"
            sx={{ mr: 2 }}
          />
          <IconButton
            onClick={handleUndo}
            disabled={!activeSessionId || isProcessing}
            title="Undo last turn"
          >
            <UndoIcon />
          </IconButton>
          <IconButton
            onClick={handleCompact}
            disabled={!activeSessionId || isProcessing}
            title="Compact context"
          >
            <CompressIcon />
          </IconButton>
        </Toolbar>
      </AppBar>

      {/* Sidebar Drawer */}
      <Box
        component="nav"
        sx={{ width: { md: DRAWER_WIDTH }, flexShrink: { md: 0 } }}
      >
        {/* Mobile drawer */}
        <Drawer
          variant="temporary"
          open={mobileOpen}
          onClose={handleDrawerToggle}
          ModalProps={{ keepMounted: true }}
          sx={{
            display: { xs: 'block', md: 'none' },
            '& .MuiDrawer-paper': {
              boxSizing: 'border-box',
              width: DRAWER_WIDTH,
            },
          }}
        >
          {drawer}
        </Drawer>
        {/* Desktop drawer */}
        <Drawer
          variant="permanent"
          sx={{
            display: { xs: 'none', md: 'block' },
            '& .MuiDrawer-paper': {
              boxSizing: 'border-box',
              width: DRAWER_WIDTH,
            },
          }}
          open
        >
          {drawer}
        </Drawer>
      </Box>

      {/* Main Content */}
      <Box
        component="main"
        sx={{
          flexGrow: 1,
          width: { md: `calc(100% - ${DRAWER_WIDTH}px)` },
          height: '100%',
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        <Toolbar /> {/* Spacer for fixed AppBar */}
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
            <Typography variant="h5" color="text.secondary">
              No session selected
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Create a new session from the sidebar to get started
            </Typography>
          </Box>
        )}
      </Box>

      {/* Approval Modal */}
      <ApprovalModal sessionId={activeSessionId} />
    </Box>
  );
}
