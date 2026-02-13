import { useRef, useEffect, useMemo } from 'react';
import { Box, Stack, Typography, IconButton } from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import RadioButtonUncheckedIcon from '@mui/icons-material/RadioButtonUnchecked';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import PlayCircleOutlineIcon from '@mui/icons-material/PlayCircleOutline';
import CodeIcon from '@mui/icons-material/Code';
import TerminalIcon from '@mui/icons-material/Terminal';
import ArticleIcon from '@mui/icons-material/Article';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus, vs } from 'react-syntax-highlighter/dist/esm/styles/prism';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { useAgentStore } from '@/store/agentStore';
import { useLayoutStore } from '@/store/layoutStore';
import { processLogs } from '@/utils/logProcessor';

// ── Helpers ──────────────────────────────────────────────────────

function tabIcon(id: string, language?: string) {
  if (id === 'script' || language === 'python') return <CodeIcon sx={{ fontSize: 14 }} />;
  if (id === 'tool_output' || language === 'markdown' || language === 'json')
    return <ArticleIcon sx={{ fontSize: 14 }} />;
  return <TerminalIcon sx={{ fontSize: 14 }} />;
}

function PlanStatusIcon({ status }: { status: string }) {
  if (status === 'completed') return <CheckCircleIcon sx={{ fontSize: 16, color: 'var(--accent-green)' }} />;
  if (status === 'in_progress') return <PlayCircleOutlineIcon sx={{ fontSize: 16, color: 'var(--accent-yellow)' }} />;
  return <RadioButtonUncheckedIcon sx={{ fontSize: 16, color: 'var(--muted-text)', opacity: 0.5 }} />;
}

// ── Markdown styles (adapts via CSS vars) ────────────────────────
const markdownSx = {
  color: 'var(--text)',
  fontSize: '13px',
  lineHeight: 1.6,
  '& p': { m: 0, mb: 1.5, '&:last-child': { mb: 0 } },
  '& pre': {
    bgcolor: 'var(--code-bg)',
    p: 1.5,
    borderRadius: 1,
    overflow: 'auto',
    fontSize: '12px',
    border: '1px solid var(--tool-border)',
  },
  '& code': {
    bgcolor: 'var(--hover-bg)',
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
    borderBottom: '2px solid var(--border-hover)',
    textAlign: 'left',
    p: 1,
    fontWeight: 600,
  },
  '& td': {
    borderBottom: '1px solid var(--tool-border)',
    p: 1,
  },
  '& h1, & h2, & h3, & h4': { mt: 2, mb: 1, fontWeight: 600 },
  '& h1': { fontSize: '1.25rem' },
  '& h2': { fontSize: '1.1rem' },
  '& h3': { fontSize: '1rem' },
  '& blockquote': {
    borderLeft: '3px solid var(--accent-yellow)',
    pl: 2,
    ml: 0,
    color: 'var(--muted-text)',
  },
} as const;

// ── Component ────────────────────────────────────────────────────

export default function CodePanel() {
  const { panelContent, panelTabs, activePanelTab, setActivePanelTab, removePanelTab, plan } =
    useAgentStore();
  const { setRightPanelOpen, themeMode } = useLayoutStore();
  const scrollRef = useRef<HTMLDivElement>(null);

  const activeTab = panelTabs.find((t) => t.id === activePanelTab);
  const currentContent = activeTab || panelContent;
  const hasTabs = panelTabs.length > 0;

  const isDark = themeMode === 'dark';
  const syntaxTheme = isDark ? vscDarkPlus : vs;

  const displayContent = useMemo(() => {
    if (!currentContent?.content) return '';
    if (!currentContent.language || currentContent.language === 'text') {
      return processLogs(currentContent.content);
    }
    return currentContent.content;
  }, [currentContent?.content, currentContent?.language]);

  useEffect(() => {
    if (scrollRef.current && activePanelTab === 'logs') {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [displayContent, activePanelTab]);

  // ── Syntax-highlighted code block (DRY) ────────────────────────
  const renderSyntaxBlock = (language: string) => (
    <SyntaxHighlighter
      language={language}
      style={syntaxTheme}
      customStyle={{
        margin: 0,
        padding: 0,
        background: 'transparent',
        fontSize: '13px',
        fontFamily: 'inherit',
      }}
      wrapLines
      wrapLongLines
    >
      {displayContent}
    </SyntaxHighlighter>
  );

  // ── Content renderer ───────────────────────────────────────────
  const renderContent = () => {
    if (!currentContent?.content) {
      return (
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', opacity: 0.5 }}>
          <Typography variant="caption">NO CONTENT TO DISPLAY</Typography>
        </Box>
      );
    }

    if (currentContent.language === 'python') return renderSyntaxBlock('python');
    if (currentContent.language === 'json') return renderSyntaxBlock('json');

    if (currentContent.language === 'markdown') {
      return (
        <Box sx={markdownSx}>
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{displayContent}</ReactMarkdown>
        </Box>
      );
    }

    // Plain text / logs
    return (
      <Box
        component="pre"
        sx={{ m: 0, fontFamily: 'inherit', color: 'var(--text)', whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}
      >
        <code>{displayContent}</code>
      </Box>
    );
  };

  return (
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column', bgcolor: 'var(--panel)' }}>
      {/* ── Header (60 px, aligned with top bar) ────────────────── */}
      <Box
        sx={{
          height: 60,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          px: 2,
          borderBottom: '1px solid var(--border)',
          flexShrink: 0,
        }}
      >
        {hasTabs ? (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, flexWrap: 'wrap' }}>
            {panelTabs.map((tab) => {
              const isActive = activePanelTab === tab.id;
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
                    bgcolor: isActive ? 'var(--tab-active-bg)' : 'transparent',
                    border: '1px solid',
                    borderColor: isActive ? 'var(--tab-active-border)' : 'transparent',
                    transition: 'all 0.15s ease',
                    '&:hover': { bgcolor: 'var(--tab-hover-bg)' },
                  }}
                >
                  {tabIcon(tab.id, tab.language)}
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
                      '&:hover': { opacity: 1, bgcolor: 'var(--tab-close-hover)' },
                    }}
                  >
                    ✕
                  </Box>
                </Box>
              );
            })}
          </Box>
        ) : (
          <Typography
            variant="caption"
            sx={{ fontWeight: 600, color: 'var(--muted-text)', textTransform: 'uppercase', letterSpacing: '0.05em' }}
          >
            {currentContent?.title || 'Code Panel'}
          </Typography>
        )}

        <IconButton size="small" onClick={() => setRightPanelOpen(false)} sx={{ color: 'var(--muted-text)' }}>
          <CloseIcon fontSize="small" />
        </IconButton>
      </Box>

      {/* ── Main content area ─────────────────────────────────── */}
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
                bgcolor: 'var(--code-panel-bg)',
                borderRadius: 'var(--radius-md)',
                p: '18px',
                border: '1px solid var(--border)',
                fontFamily: '"JetBrains Mono", ui-monospace, SFMono-Regular, Menlo, Monaco, monospace',
                fontSize: '13px',
                lineHeight: 1.55,
                height: '100%',
                overflow: 'auto',
              }}
            >
              {renderContent()}
            </Box>
          </Box>
        )}
      </Box>

      {/* ── Plan display (bottom) ─────────────────────────────── */}
      {plan && plan.length > 0 && (
        <Box
          sx={{
            borderTop: '1px solid var(--border)',
            bgcolor: 'var(--plan-bg)',
            maxHeight: '30%',
            display: 'flex',
            flexDirection: 'column',
          }}
        >
          <Box
            sx={{
              p: 1.5,
              borderBottom: '1px solid var(--border)',
              display: 'flex',
              alignItems: 'center',
              gap: 1,
            }}
          >
            <Typography
              variant="caption"
              sx={{ fontWeight: 600, color: 'var(--muted-text)', textTransform: 'uppercase', letterSpacing: '0.05em' }}
            >
              CURRENT PLAN
            </Typography>
          </Box>

          <Stack spacing={1} sx={{ p: 2, overflow: 'auto' }}>
            {plan.map((item) => (
              <Stack key={item.id} direction="row" alignItems="flex-start" spacing={1.5}>
                <Box sx={{ mt: 0.2 }}>
                  <PlanStatusIcon status={item.status} />
                </Box>
                <Typography
                  variant="body2"
                  sx={{
                    fontSize: '13px',
                    fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, monospace',
                    color: item.status === 'completed' ? 'var(--muted-text)' : 'var(--text)',
                    textDecoration: item.status === 'completed' ? 'line-through' : 'none',
                    opacity: item.status === 'pending' ? 0.7 : 1,
                  }}
                >
                  {item.content}
                </Typography>
              </Stack>
            ))}
          </Stack>
        </Box>
      )}
    </Box>
  );
}
