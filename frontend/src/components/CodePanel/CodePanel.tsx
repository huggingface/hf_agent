import { useRef, useEffect, useMemo } from 'react';
import { Box, Typography, IconButton } from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import RadioButtonUncheckedIcon from '@mui/icons-material/RadioButtonUnchecked';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import PlayCircleOutlineIcon from '@mui/icons-material/PlayCircleOutline';
import CodeIcon from '@mui/icons-material/Code';
import TerminalIcon from '@mui/icons-material/Terminal';
import ArticleIcon from '@mui/icons-material/Article';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { useAgentStore } from '@/store/agentStore';
import { useLayoutStore } from '@/store/layoutStore';
import { processLogs } from '@/utils/logProcessor';

export default function CodePanel() {
  const { panelContent, panelTabs, activePanelTab, setActivePanelTab, removePanelTab, plan } = useAgentStore();
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
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, flexWrap: 'wrap' }}>
            {panelTabs.map((tab) => {
              const isActive = activePanelTab === tab.id;
              // Choose icon based on tab type
              let icon = <TerminalIcon sx={{ fontSize: 14 }} />;
              if (tab.id === 'script' || tab.language === 'python') {
                icon = <CodeIcon sx={{ fontSize: 14 }} />;
              } else if (tab.id === 'tool_output' || tab.language === 'markdown' || tab.language === 'json') {
                icon = <ArticleIcon sx={{ fontSize: 14 }} />;
              }
              return (
                <Box
                  key={tab.id}
                  onClick={() => setActivePanelTab(tab.id)}
                  sx={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 0.5,
                    px: 1.5,
                    py: 0.75,
                    borderRadius: 1,
                    cursor: 'pointer',
                    fontSize: '0.7rem',
                    fontWeight: 600,
                    textTransform: 'uppercase',
                    letterSpacing: '0.05em',
                    color: isActive ? 'var(--text)' : 'var(--muted-text)',
                    bgcolor: isActive ? 'rgba(255,255,255,0.08)' : 'transparent',
                    border: '1px solid',
                    borderColor: isActive ? 'rgba(255,255,255,0.1)' : 'transparent',
                    transition: 'all 0.15s ease',
                    '&:hover': {
                      bgcolor: 'rgba(255,255,255,0.05)',
                    },
                  }}
                >
                  {icon}
                  <span>{tab.title}</span>
                  <Box
                    component="span"
                    onClick={(e) => {
                      e.stopPropagation();
                      removePanelTab(tab.id);
                    }}
                    sx={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      ml: 0.5,
                      width: 16,
                      height: 16,
                      borderRadius: '50%',
                      fontSize: '0.65rem',
                      opacity: 0.5,
                      '&:hover': {
                        opacity: 1,
                        bgcolor: 'rgba(255,255,255,0.1)',
                      },
                    }}
                  >
                    ✕
                  </Box>
                </Box>
              );
            })}
          </Box>
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
                ) : currentContent.language === 'json' ? (
                  <SyntaxHighlighter
                    language="json"
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
                ) : currentContent.language === 'markdown' ? (
                  <Box sx={{
                    color: 'var(--text)',
                    fontSize: '13px',
                    lineHeight: 1.6,
                    '& p': { m: 0, mb: 1.5, '&:last-child': { mb: 0 } },
                    '& pre': {
                      bgcolor: 'rgba(0,0,0,0.4)',
                      p: 1.5,
                      borderRadius: 1,
                      overflow: 'auto',
                      fontSize: '12px',
                      border: '1px solid rgba(255,255,255,0.05)',
                    },
                    '& code': {
                      bgcolor: 'rgba(255,255,255,0.05)',
                      px: 0.5,
                      py: 0.25,
                      borderRadius: 0.5,
                      fontSize: '12px',
                      fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, monospace',
                    },
                    '& pre code': { bgcolor: 'transparent', p: 0 },
                    '& a': {
                      color: 'var(--accent-yellow)',
                      textDecoration: 'none',
                      '&:hover': { textDecoration: 'underline' },
                    },
                    '& ul, & ol': { pl: 2.5, my: 1 },
                    '& li': { mb: 0.5 },
                    '& table': {
                      borderCollapse: 'collapse',
                      width: '100%',
                      my: 2,
                      fontSize: '12px',
                      fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, monospace',
                    },
                    '& th': {
                      borderBottom: '2px solid rgba(255,255,255,0.15)',
                      textAlign: 'left',
                      p: 1,
                      fontWeight: 600,
                    },
                    '& td': {
                      borderBottom: '1px solid rgba(255,255,255,0.05)',
                      p: 1,
                    },
                    '& h1, & h2, & h3, & h4': {
                      mt: 2,
                      mb: 1,
                      fontWeight: 600,
                    },
                    '& h1': { fontSize: '1.25rem' },
                    '& h2': { fontSize: '1.1rem' },
                    '& h3': { fontSize: '1rem' },
                    '& blockquote': {
                      borderLeft: '3px solid rgba(255,255,255,0.2)',
                      pl: 2,
                      ml: 0,
                      color: 'var(--muted-text)',
                    },
                  }}>
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>{displayContent}</ReactMarkdown>
                  </Box>
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
