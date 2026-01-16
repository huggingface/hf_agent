import { Box, Typography, IconButton } from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { useAgentStore } from '@/store/agentStore';
import { useLayoutStore } from '@/store/layoutStore';

export default function CodePanel() {
  const { panelContent } = useAgentStore();
  const { setRightPanelOpen } = useLayoutStore();

  return (
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column', bgcolor: 'background.paper' }}>
      {/* Header - Always Visible */}
      <Box sx={{ p: 2, borderBottom: 1, borderColor: 'divider', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <Typography variant="caption" sx={{ fontFamily: 'monospace', fontWeight: 600, color: 'text.secondary', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
          {panelContent?.title || 'Code Panel'}
        </Typography>
        <IconButton size="small" onClick={() => setRightPanelOpen(false)}>
          <CloseIcon fontSize="small" />
        </IconButton>
      </Box>

      {!panelContent ? (
        <Box sx={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', p: 4 }}>
          <Typography variant="body2" color="text.secondary" sx={{ fontFamily: 'monospace', opacity: 0.5 }}>
            NO DATA LOADED
          </Typography>
        </Box>
      ) : (
        <Box sx={{ flex: 1, overflow: 'auto', bgcolor: 'background.default' }}>
          {panelContent.content ? (
            panelContent.language === 'python' ? (
              <SyntaxHighlighter
                language="python"
                style={vscDarkPlus}
                customStyle={{
                  margin: 0,
                  padding: '16px',
                  background: 'transparent',
                  fontSize: '0.8rem',
                  fontFamily: '"JetBrains Mono", monospace',
                }}
                wrapLines={true}
                wrapLongLines={true}
              >
                {panelContent.content}
              </SyntaxHighlighter>
            ) : (
              <Box sx={{ p: 2 }}>
                <Box component="pre" sx={{ 
                  m: 0, 
                  fontFamily: 'monospace', 
                  fontSize: '0.8rem', 
                  color: 'text.primary',
                  whiteSpace: 'pre-wrap',
                  wordBreak: 'break-all'
                }}>
                  <code>{panelContent.content}</code>
                </Box>
              </Box>
            )
          ) : (
            <Box sx={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', p: 4, opacity: 0.5 }}>
              <Typography variant="caption" sx={{ fontFamily: 'monospace' }}>
                NO CONTENT TO DISPLAY
              </Typography>
            </Box>
          )}
        </Box>
      )}
    </Box>
  );
}
