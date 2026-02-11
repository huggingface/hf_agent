import { useCallback, useState } from 'react';
import { Box, Stack, Typography, Chip, Button, TextField, IconButton, Link } from '@mui/material';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline';
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline';
import MoreHorizIcon from '@mui/icons-material/MoreHoriz';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';
import HourglassEmptyIcon from '@mui/icons-material/HourglassEmpty';
import LaunchIcon from '@mui/icons-material/Launch';
import SendIcon from '@mui/icons-material/Send';
import { useAgentStore } from '@/store/agentStore';
import { useLayoutStore } from '@/store/layoutStore';
import { useSessionStore } from '@/store/sessionStore';
import { apiFetch } from '@/utils/api';
import { logger } from '@/utils/logger';
import type { TraceLog, ApprovalStatus } from '@/types/agent';

interface ToolCallGroupProps {
  tools: TraceLog[];
}

// ── Status icon based on tool state ─────────────────────────────────
function StatusIcon({ log }: { log: TraceLog }) {
  // Awaiting approval
  if (log.approvalStatus === 'pending') {
    return <HourglassEmptyIcon sx={{ fontSize: 16, color: 'var(--accent-yellow)' }} />;
  }
  // Rejected
  if (log.approvalStatus === 'rejected') {
    return <ErrorOutlineIcon sx={{ fontSize: 16, color: 'error.main' }} />;
  }
  // Running (not completed yet)
  if (!log.completed) {
    return (
      <MoreHorizIcon
        sx={{
          fontSize: 16,
          color: 'var(--muted-text)',
          animation: 'pulse 1.5s ease-in-out infinite',
          '@keyframes pulse': {
            '0%, 100%': { opacity: 0.4 },
            '50%': { opacity: 1 },
          },
        }}
      />
    );
  }
  // Failed
  if (log.success === false) {
    return <ErrorOutlineIcon sx={{ fontSize: 16, color: 'error.main' }} />;
  }
  // Completed successfully
  return <CheckCircleOutlineIcon sx={{ fontSize: 16, color: 'success.main' }} />;
}

// ── Status chip label ───────────────────────────────────────────────
function statusLabel(log: TraceLog): string | null {
  if (log.approvalStatus === 'pending') return 'awaiting approval';
  if (log.approvalStatus === 'rejected') return 'rejected';
  if (!log.completed) return 'running';
  return null;
}

function statusColor(log: TraceLog): string {
  if (log.approvalStatus === 'pending') return 'var(--accent-yellow)';
  if (log.approvalStatus === 'rejected') return 'var(--accent-red)';
  return 'var(--accent-yellow)';
}

// ── Inline approval UI ──────────────────────────────────────────────
function InlineApproval({
  log,
  onResolve,
}: {
  log: TraceLog;
  onResolve: (toolCallId: string, approved: boolean, feedback?: string) => void;
}) {
  const [feedback, setFeedback] = useState('');

  return (
    <Box sx={{ px: 1.5, py: 1.5, borderTop: '1px solid var(--tool-border)' }}>
      {/* Tool description */}
      {log.tool === 'hf_jobs' && log.args && (
        <Typography variant="body2" sx={{ color: 'var(--muted-text)', fontSize: '0.75rem', mb: 1.5 }}>
          Execute <Box component="span" sx={{ color: 'var(--accent-yellow)', fontWeight: 500 }}>{log.tool}</Box> on{' '}
          <Box component="span" sx={{ fontWeight: 500, color: 'var(--text)' }}>
            {String(log.args.hardware_flavor || 'default')}
          </Box>
          {log.args.timeout && (
            <> with timeout <Box component="span" sx={{ fontWeight: 500, color: 'var(--text)' }}>
              {String(log.args.timeout)}
            </Box></>
          )}
        </Typography>
      )}

      {/* Feedback + buttons */}
      <Box sx={{ display: 'flex', gap: 1, mb: 1 }}>
        <TextField
          fullWidth
          size="small"
          placeholder="Feedback (optional)"
          value={feedback}
          onChange={(e) => setFeedback(e.target.value)}
          variant="outlined"
          sx={{
            '& .MuiOutlinedInput-root': {
              bgcolor: 'rgba(0,0,0,0.15)',
              fontFamily: 'inherit',
              fontSize: '0.8rem',
            },
          }}
        />
        <IconButton
          onClick={() => onResolve(log.toolCallId || '', false, feedback || 'Rejected by user')}
          disabled={!feedback}
          size="small"
          sx={{
            color: 'var(--accent-red)',
            border: '1px solid rgba(255,255,255,0.05)',
            borderRadius: '6px',
            '&:hover': { bgcolor: 'rgba(224,90,79,0.1)', borderColor: 'var(--accent-red)' },
            '&.Mui-disabled': { color: 'rgba(255,255,255,0.1)' },
          }}
        >
          <SendIcon sx={{ fontSize: 14 }} />
        </IconButton>
      </Box>

      <Box sx={{ display: 'flex', gap: 1 }}>
        <Button
          size="small"
          onClick={() => onResolve(log.toolCallId || '', false, feedback || 'Rejected by user')}
          sx={{
            flex: 1,
            textTransform: 'none',
            border: '1px solid rgba(255,255,255,0.05)',
            color: 'var(--accent-red)',
            fontSize: '0.75rem',
            py: 0.75,
            borderRadius: '8px',
            '&:hover': { bgcolor: 'rgba(224,90,79,0.05)', borderColor: 'var(--accent-red)' },
          }}
        >
          Reject
        </Button>
        <Button
          size="small"
          onClick={() => onResolve(log.toolCallId || '', true)}
          sx={{
            flex: 1,
            textTransform: 'none',
            border: '1px solid rgba(255,255,255,0.05)',
            color: 'var(--accent-green)',
            fontSize: '0.75rem',
            py: 0.75,
            borderRadius: '8px',
            '&:hover': { bgcolor: 'rgba(47,204,113,0.05)', borderColor: 'var(--accent-green)' },
          }}
        >
          Approve
        </Button>
      </Box>
    </Box>
  );
}

// ── Main component ──────────────────────────────────────────────────
export default function ToolCallGroup({ tools }: ToolCallGroupProps) {
  const { showToolOutput, setPanelTab, setActivePanelTab, clearPanelTabs } = useAgentStore();
  const { setRightPanelOpen, setLeftSidebarOpen } = useLayoutStore();
  const { activeSessionId } = useSessionStore();

  const handleClick = useCallback(
    (log: TraceLog) => {
      // For hf_jobs with scripts, use tab system
      if (log.tool === 'hf_jobs' && log.args?.script) {
        clearPanelTabs();
        setPanelTab({
          id: 'script',
          title: 'Script',
          content: String(log.args.script),
          language: 'python',
        });
        if (log.jobLogs) {
          setPanelTab({
            id: 'logs',
            title: 'Logs',
            content: log.jobLogs,
            language: 'text',
          });
        }
        setActivePanelTab('script');
        setRightPanelOpen(true);
        setLeftSidebarOpen(false);
        return;
      }

      // Show output if completed, or args if still running
      if (log.completed && log.output) {
        showToolOutput(log);
      } else if (log.args) {
        const content = JSON.stringify(log.args, null, 2);
        showToolOutput({ ...log, output: content });
      } else {
        return;
      }
      setRightPanelOpen(true);
    },
    [showToolOutput, setRightPanelOpen, setLeftSidebarOpen, clearPanelTabs, setPanelTab, setActivePanelTab],
  );

  const handleApprovalResolve = useCallback(
    async (toolCallId: string, approved: boolean, feedback?: string) => {
      if (!activeSessionId) return;
      try {
        await apiFetch('/api/approve', {
          method: 'POST',
          body: JSON.stringify({
            session_id: activeSessionId,
            approvals: [{
              tool_call_id: toolCallId,
              approved,
              feedback: approved ? null : feedback || 'Rejected by user',
            }],
          }),
        });
        // The WebSocket will send back tool_output events which will update the trace
      } catch (e) {
        logger.error('Approval failed:', e);
      }
    },
    [activeSessionId],
  );

  return (
    <Box
      sx={{
        borderRadius: 2,
        border: '1px solid var(--tool-border)',
        bgcolor: 'var(--tool-bg)',
        overflow: 'hidden',
        my: 1,
      }}
    >
      <Stack divider={<Box sx={{ borderBottom: '1px solid var(--tool-border)' }} />}>
        {tools.map((log) => {
          const clickable = (log.completed && !!log.output) || !!log.args;
          const label = statusLabel(log);
          const isPendingApproval = log.approvalStatus === 'pending';

          return (
            <Box key={log.id}>
              {/* Main tool row */}
              <Stack
                direction="row"
                alignItems="center"
                spacing={1}
                onClick={() => !isPendingApproval && handleClick(log)}
                sx={{
                  px: 1.5,
                  py: 1,
                  cursor: isPendingApproval ? 'default' : clickable ? 'pointer' : 'default',
                  transition: 'background-color 0.15s',
                  '&:hover': clickable && !isPendingApproval ? { bgcolor: 'var(--hover-bg)' } : {},
                }}
              >
                <StatusIcon log={log} />

                <Typography
                  variant="body2"
                  sx={{
                    fontFamily: '"JetBrains Mono", ui-monospace, SFMono-Regular, monospace',
                    fontWeight: 600,
                    fontSize: '0.78rem',
                    color: 'var(--text)',
                    flex: 1,
                    minWidth: 0,
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                  }}
                >
                  {log.tool}
                </Typography>

                {/* Quick action links for completed jobs */}
                {log.completed && log.tool === 'hf_jobs' && log.args?.script && (
                  <Box sx={{ display: 'flex', gap: 0.5 }} onClick={(e) => e.stopPropagation()}>
                    <Typography
                      component="span"
                      onClick={() => handleClick(log)}
                      sx={{
                        fontSize: '0.68rem',
                        color: 'var(--muted-text)',
                        cursor: 'pointer',
                        px: 0.75,
                        py: 0.25,
                        borderRadius: 0.5,
                        '&:hover': { color: 'var(--accent-yellow)', bgcolor: 'var(--hover-bg)' },
                      }}
                    >
                      Script
                    </Typography>
                    {log.jobLogs && (
                      <Typography
                        component="span"
                        onClick={() => {
                          clearPanelTabs();
                          if (log.args?.script) {
                            setPanelTab({ id: 'script', title: 'Script', content: String(log.args.script), language: 'python' });
                          }
                          setPanelTab({ id: 'logs', title: 'Logs', content: log.jobLogs!, language: 'text' });
                          setActivePanelTab('logs');
                          setRightPanelOpen(true);
                          setLeftSidebarOpen(false);
                        }}
                        sx={{
                          fontSize: '0.68rem',
                          color: 'var(--accent-yellow)',
                          cursor: 'pointer',
                          px: 0.75,
                          py: 0.25,
                          borderRadius: 0.5,
                          '&:hover': { bgcolor: 'var(--hover-bg)' },
                        }}
                      >
                        Logs
                      </Typography>
                    )}
                  </Box>
                )}

                {label && (
                  <Chip
                    label={label}
                    size="small"
                    sx={{
                      height: 20,
                      fontSize: '0.65rem',
                      fontWeight: 600,
                      bgcolor: 'var(--accent-yellow-weak)',
                      color: statusColor(log),
                      letterSpacing: '0.03em',
                    }}
                  />
                )}

                {clickable && !isPendingApproval && (
                  <OpenInNewIcon sx={{ fontSize: 14, color: 'var(--muted-text)', opacity: 0.6 }} />
                )}
              </Stack>

              {/* Job status + link row */}
              {(log.jobUrl || log.jobStatus) && (
                <Box
                  sx={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 1.5,
                    px: 1.5,
                    py: 0.75,
                    borderTop: '1px solid var(--tool-border)',
                  }}
                >
                  {log.jobStatus && (
                    <Typography
                      variant="caption"
                      sx={{
                        color: log.success === false ? 'var(--accent-red)' : 'var(--accent-green)',
                        fontSize: '0.7rem',
                        fontWeight: 600,
                      }}
                    >
                      {log.jobStatus}
                    </Typography>
                  )}
                  {log.jobUrl && (
                    <Link
                      href={log.jobUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      onClick={(e) => e.stopPropagation()}
                      sx={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: 0.5,
                        color: 'var(--accent-yellow)',
                        fontSize: '0.68rem',
                        textDecoration: 'none',
                        '&:hover': { textDecoration: 'underline' },
                      }}
                    >
                      <LaunchIcon sx={{ fontSize: 12 }} />
                      View on HF
                    </Link>
                  )}
                </Box>
              )}

              {/* Inline approval UI (only when pending) */}
              {isPendingApproval && (
                <InlineApproval log={log} onResolve={handleApprovalResolve} />
              )}
            </Box>
          );
        })}
      </Stack>
    </Box>
  );
}
