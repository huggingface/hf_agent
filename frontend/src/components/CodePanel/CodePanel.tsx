import { useRef, useEffect, useMemo } from 'react';
import { Box, Typography, IconButton } from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import RadioButtonUncheckedIcon from '@mui/icons-material/RadioButtonUnchecked';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import PlayCircleOutlineIcon from '@mui/icons-material/PlayCircleOutline';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { useAgentStore } from '@/store/agentStore';
import { useLayoutStore } from '@/store/layoutStore';
import { processLogs } from '@/utils/logProcessor';

export default function CodePanel() {
  const { panelContent, plan } = useAgentStore();
  const { setRightPanelOpen } = useLayoutStore();
  const scrollRef = useRef<HTMLDivElement>(null);

  const displayContent = useMemo(() => {
    if (!panelContent?.content) return '';
    // Apply log processing only for text/logs, not for code/json
    if (!panelContent.language || panelContent.language === 'text') {
        return processLogs(panelContent.content);
    }
    return panelContent.content;
  }, [panelContent?.content, panelContent?.language]);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [displayContent]);

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

      {/* Main Content Area */}
      <Box sx={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
        {!panelContent ? (
            <Box sx={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', p: 4 }}>
            <Typography variant="body2" color="text.secondary" sx={{ opacity: 0.5 }}>
                NO DATA LOADED
            </Typography>
            </Box>
        ) : (
            <Box sx={{ flex: 1, overflow: 'hidden', p: 2 }}>
            <Box 
                ref={scrollRef}
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
                        {displayContent}
                    </SyntaxHighlighter>
                    ) : (
                    <Box component="pre" sx={{ 
                        m: 0, 
                        fontFamily: 'inherit', 
                        color: 'var(--text)',
                        whiteSpace: 'pre-wrap',
                        wordBreak: 'break-all'
                    }}>
                        <code>{displayContent}</code>
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

      {/* Plan Display at Bottom */}
      {plan && plan.length > 0 && (
        <Box sx={{ 
            borderTop: '1px solid rgba(255,255,255,0.03)',
            bgcolor: 'rgba(0,0,0,0.2)',
            maxHeight: '30%',
            display: 'flex',
            flexDirection: 'column'
        }}>
            <Box sx={{ p: 1.5, borderBottom: '1px solid rgba(255,255,255,0.03)', display: 'flex', alignItems: 'center', gap: 1 }}>
                <Typography variant="caption" sx={{ fontWeight: 600, color: 'var(--muted-text)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                    CURRENT PLAN
                </Typography>
            </Box>
            <Box sx={{ p: 2, overflow: 'auto', display: 'flex', flexDirection: 'column', gap: 1 }}>
                {plan.map((item) => (
                    <Box key={item.id} sx={{ display: 'flex', alignItems: 'flex-start', gap: 1.5 }}>
                        <Box sx={{ mt: 0.2 }}>
                            {item.status === 'completed' && <CheckCircleIcon sx={{ fontSize: 16, color: 'var(--accent-green)' }} />}
                            {item.status === 'in_progress' && <PlayCircleOutlineIcon sx={{ fontSize: 16, color: 'var(--accent-yellow)' }} />}
                            {item.status === 'pending' && <RadioButtonUncheckedIcon sx={{ fontSize: 16, color: 'var(--muted-text)', opacity: 0.5 }} />}
                        </Box>
                        <Typography 
                            variant="body2" 
                            sx={{ 
                                fontSize: '13px', 
                                fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, monospace',
                                color: item.status === 'completed' ? 'var(--muted-text)' : 'var(--text)',
                                textDecoration: item.status === 'completed' ? 'line-through' : 'none',
                                opacity: item.status === 'pending' ? 0.7 : 1
                            }}
                        >
                            {item.content}
                        </Typography>
                    </Box>
                ))}
            </Box>
        </Box>
      )}
    </Box>
  );
}
