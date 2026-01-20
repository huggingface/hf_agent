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
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column', bgcolor: 'var(--panel)' }}>
      {/* Header - Fixed 60px to align */}
      <Box sx={{ 
        height: '60px', 
        display: 'flex', 
        alignItems: 'center', 
        justifyContent: 'space-between', 
        px: 2,
        borderBottom: '1px solid rgba(255,255,255,0.03)'
      }}>
        <Typography variant="caption" sx={{ fontWeight: 600, color: 'var(--muted-text)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
          {panelContent?.title || 'Code Panel'}
        </Typography>
        <IconButton size="small" onClick={() => setRightPanelOpen(false)} sx={{ color: 'var(--muted-text)' }}>
          <CloseIcon fontSize="small" />
        </IconButton>
      </Box>

      {!panelContent ? (
        <Box sx={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', p: 4 }}>
          <Typography variant="body2" color="text.secondary" sx={{ opacity: 0.5 }}>
            NO DATA LOADED
          </Typography>
        </Box>
      ) : (
        <Box sx={{ flex: 1, overflow: 'auto', p: 2 }}>
          <Box 
            className="code-panel"
            sx={{
                background: '#0A0B0C',
                borderRadius: 'var(--radius-md)',
                padding: '18px',
                border: '1px solid rgba(255,255,255,0.03)',
                fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, "Roboto Mono", monospace',
                fontSize: '13px',
                lineHeight: 1.55,
                height: '100%',
                overflow: 'auto',
            }}
          >
            {panelContent.content ? (
                panelContent.language === 'python' ? (
                <SyntaxHighlighter
                    language="python"
                    style={vscDarkPlus}
                    customStyle={{
                    margin: 0,
                    padding: 0,
                    background: 'transparent',
                    fontSize: '13px',
                    fontFamily: 'inherit',
                    }}
                    wrapLines={true}
                    wrapLongLines={true}
                >
                    {panelContent.content}
                </SyntaxHighlighter>
                ) : (
                <Box component="pre" sx={{ 
                    m: 0, 
                    fontFamily: 'inherit', 
                    color: 'var(--text)',
                    whiteSpace: 'pre-wrap',
                    wordBreak: 'break-all'
                }}>
                    <code>{panelContent.content}</code>
                </Box>
                )
            ) : (
                <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', opacity: 0.5 }}>
                <Typography variant="caption">
                    NO CONTENT TO DISPLAY
                </Typography>
                </Box>
            )}
          </Box>
        </Box>
      )}
    </Box>
  );
}
