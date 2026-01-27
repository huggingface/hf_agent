import { useRef, useEffect, useMemo } from 'react';
import { Box, Typography, IconButton, Tabs, Tab } from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import RadioButtonUncheckedIcon from '@mui/icons-material/RadioButtonUnchecked';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import PlayCircleOutlineIcon from '@mui/icons-material/PlayCircleOutline';
import CodeIcon from '@mui/icons-material/Code';
import TerminalIcon from '@mui/icons-material/Terminal';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { useAgentStore } from '@/store/agentStore';
import { useLayoutStore } from '@/store/layoutStore';
import { processLogs } from '@/utils/logProcessor';

export default function CodePanel() {
  const { panelContent, panelTabs, activePanelTab, setActivePanelTab, plan } = useAgentStore();
  const { setRightPanelOpen } = useLayoutStore();
  const scrollRef = useRef<HTMLDivElement>(null);

  // Get the active tab content, or fall back to panelContent for backwards compatibility
  const activeTab = panelTabs.find(t => t.id === activePanelTab);
  const currentContent = activeTab || panelContent;

  const displayContent = useMemo(() => {
    if (!currentContent?.content) return '';
    // Apply log processing only for text/logs, not for code/json
    if (!currentContent.language || currentContent.language === 'text') {
      return processLogs(currentContent.content);
    }
    return currentContent.content;
  }, [currentContent?.content, currentContent?.language]);

  useEffect(() => {
    // Auto-scroll only for logs tab
    if (scrollRef.current && activePanelTab === 'logs') {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [displayContent, activePanelTab]);

  const hasTabs = panelTabs.length > 0;

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
        {hasTabs ? (
          <Tabs
            value={activePanelTab || panelTabs[0]?.id}
            onChange={(_, newValue) => setActivePanelTab(newValue)}
            sx={{
              minHeight: 36,
              '& .MuiTabs-indicator': {
                backgroundColor: 'var(--accent-primary)',
              },
              '& .MuiTab-root': {
                minHeight: 36,
                minWidth: 'auto',
                px: 2,
                py: 0.5,
                fontSize: '0.75rem',
                fontWeight: 600,
                textTransform: 'uppercase',
                letterSpacing: '0.05em',
                color: 'var(--muted-text)',
                '&.Mui-selected': {
                  color: 'var(--text)',
                },
              },
            }}
          >
            {panelTabs.map((tab) => (
              <Tab
                key={tab.id}
                value={tab.id}
                label={tab.title}
                icon={tab.id === 'script' ? <CodeIcon sx={{ fontSize: 16 }} /> : <TerminalIcon sx={{ fontSize: 16 }} />}
                iconPosition="start"
              />
            ))}
          </Tabs>
        ) : (
          <Typography variant="caption" sx={{ fontWeight: 600, color: 'var(--muted-text)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            {currentContent?.title || 'Code Panel'}
          </Typography>
        )}
        <IconButton size="small" onClick={() => setRightPanelOpen(false)} sx={{ color: 'var(--muted-text)' }}>
          <CloseIcon fontSize="small" />
        </IconButton>
      </Box>

      {/* Main Content Area */}
      <Box sx={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
        {!currentContent ? (
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
              {currentContent.content ? (
                currentContent.language === 'python' ? (
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
