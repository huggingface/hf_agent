import { useState, useCallback, useEffect } from 'react';
import { Box, Typography, Button, TextField, IconButton, Link } from '@mui/material';
import SendIcon from '@mui/icons-material/Send';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import CancelIcon from '@mui/icons-material/Cancel';
import LaunchIcon from '@mui/icons-material/Launch';
import { useAgentStore } from '@/store/agentStore';
import { useLayoutStore } from '@/store/layoutStore';
import { useSessionStore } from '@/store/sessionStore';
import type { Message, ToolApproval } from '@/types/agent';

interface ApprovalFlowProps {
  message: Message;
}

export default function ApprovalFlow({ message }: ApprovalFlowProps) {
  const { setPanelContent, setPanelTab, setActivePanelTab, clearPanelTabs, updateMessage } = useAgentStore();
  const { setRightPanelOpen, setLeftSidebarOpen } = useLayoutStore();
  const { activeSessionId } = useSessionStore();
  const [currentIndex, setCurrentIndex] = useState(0);
  const [feedback, setFeedback] = useState('');
  const [decisions, setDecisions] = useState<ToolApproval[]>([]);

  const approvalData = message.approval;
  
  if (!approvalData) return null;

  const { batch, status } = approvalData;

  // Parse toolOutput to extract job info (URL, status, logs)
  let logsContent = '';
  let showLogsButton = false;
  let jobUrl = '';
  let jobId = '';
  let jobStatus = '';
  let jobFailed = false;

  if (message.toolOutput) {
    // Extract job URL: **View at:** https://...
    const urlMatch = message.toolOutput.match(/\*\*View at:\*\*\s*(https:\/\/[^\s\n]+)/);
    if (urlMatch) {
      jobUrl = urlMatch[1];
    }

    // Extract job ID: **Job ID:** ...
    const idMatch = message.toolOutput.match(/\*\*Job ID:\*\*\s*([^\s\n]+)/);
    if (idMatch) {
      jobId = idMatch[1];
    }

    // Extract job status: **Final Status:** ...
    const statusMatch = message.toolOutput.match(/\*\*Final Status:\*\*\s*([^\n]+)/);
    if (statusMatch) {
      jobStatus = statusMatch[1].trim();
      jobFailed = jobStatus.toLowerCase().includes('error') || jobStatus.toLowerCase().includes('failed');
    }

    // Extract logs
    if (message.toolOutput.includes('**Logs:**')) {
      const parts = message.toolOutput.split('**Logs:**');
      if (parts.length > 1) {
        const logsPart = parts[1].trim();
        const codeBlockMatch = logsPart.match(/```([\s\S]*?)```/);
        if (codeBlockMatch) {
          logsContent = codeBlockMatch[1].trim();
          showLogsButton = true;
        }
      }
    }
  }

  // Sync right panel with current tool
  useEffect(() => {
    if (!batch || currentIndex >= batch.tools.length) return;
    
    // Only auto-open panel if pending
    if (status !== 'pending') return;
    
    const tool = batch.tools[currentIndex];
    const args = tool.arguments as any;

    if (tool.tool === 'hf_jobs' && (args.operation === 'run' || args.operation === 'scheduled run') && args.script) {
      setPanelContent({
        title: 'Compute Job Script',
        content: args.script,
        language: 'python',
        parameters: args
      });
      // Don't auto-open if already resolved
    } else if (tool.tool === 'hf_repo_files' && args.operation === 'upload' && args.content) {
      setPanelContent({
        title: `File Upload: ${args.path || 'unnamed'}`,
        content: args.content,
        parameters: args
      });
    }
  }, [currentIndex, batch, status, setPanelContent]);

  const handleResolve = useCallback(async (approved: boolean) => {
    if (!batch || !activeSessionId) return;

    const currentTool = batch.tools[currentIndex];
    const newDecisions = [
      ...decisions,
      {
        tool_call_id: currentTool.tool_call_id,
        approved,
        feedback: approved ? null : feedback || 'Rejected by user',
      },
    ];

    if (currentIndex < batch.tools.length - 1) {
      setDecisions(newDecisions);
      setCurrentIndex(currentIndex + 1);
      setFeedback('');
    } else {
      // All tools in batch resolved
      try {
        await fetch('/api/approve', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            session_id: activeSessionId,
            approvals: newDecisions,
          }),
        });
        
        // Update message status
        updateMessage(activeSessionId, message.id, {
            approval: {
                ...approvalData!,
                status: approved ? 'approved' : 'rejected',
                decisions: newDecisions
            }
        });
        
      } catch (e) {
        console.error('Approval submission failed:', e);
      }
    }
  }, [activeSessionId, message.id, batch, currentIndex, feedback, decisions, approvalData, updateMessage]);

  if (!batch || currentIndex >= batch.tools.length) return null;

  const currentTool = batch.tools[currentIndex];

  // Check if script contains push_to_hub or upload_file
  const args = currentTool.arguments as any;
  const containsPushToHub = currentTool.tool === 'hf_jobs' && args.script && (args.script.includes('push_to_hub') || args.script.includes('upload_file'));

  const getToolDescription = (toolName: string, args: any) => {
    if (toolName === 'hf_jobs') {
      return (
        <Box sx={{ flex: 1 }}>
          <Typography variant="body2" sx={{ color: 'var(--muted-text)' }}>
            The agent wants to execute <Box component="span" sx={{ color: 'var(--accent-yellow)', fontWeight: 500 }}>hf_jobs</Box> on{' '}
            <Box component="span" sx={{ fontWeight: 500, color: 'var(--text)' }}>{args.hardware_flavor || 'default'}</Box> with a timeout of{' '}
            <Box component="span" sx={{ fontWeight: 500, color: 'var(--text)' }}>{args.timeout || '30m'}</Box>
          </Typography>
        </Box>
      );
    }
    return (
      <Typography variant="body2" sx={{ color: 'var(--muted-text)', flex: 1 }}>
        The agent wants to execute <Box component="span" sx={{ color: 'var(--accent-yellow)', fontWeight: 500 }}>{toolName}</Box>
      </Typography>
    );
  };

  const showCode = () => {
    const args = currentTool.arguments as any;
    if (currentTool.tool === 'hf_jobs' && args.script) {
      // Clear existing tabs and set up script tab (and logs if available)
      clearPanelTabs();
      setPanelTab({
        id: 'script',
        title: 'Script',
        content: args.script,
        language: 'python',
        parameters: args
      });
      // If logs are available (job completed), also add logs tab
      if (logsContent) {
        setPanelTab({
          id: 'logs',
          title: 'Logs',
          content: logsContent,
          language: 'text'
        });
      }
      setActivePanelTab('script');
      setRightPanelOpen(true);
      setLeftSidebarOpen(false);
    } else {
      setPanelContent({
        title: `Tool: ${currentTool.tool}`,
        content: JSON.stringify(args, null, 2),
        language: 'json',
        parameters: args
      });
      setRightPanelOpen(true);
      setLeftSidebarOpen(false);
    }
  };

  const handleViewLogs = (e: React.MouseEvent) => {
    e.stopPropagation();
    const args = currentTool.arguments as any;
    // Set up both tabs so user can switch between script and logs
    clearPanelTabs();
    if (currentTool.tool === 'hf_jobs' && args.script) {
      setPanelTab({
        id: 'script',
        title: 'Script',
        content: args.script,
        language: 'python',
        parameters: args
      });
    }
    setPanelTab({
      id: 'logs',
      title: 'Logs',
      content: logsContent,
      language: 'text'
    });
    setActivePanelTab('logs');
    setRightPanelOpen(true);
    setLeftSidebarOpen(false);
  };

  return (
    <Box 
      className="action-card"
      sx={{ 
        width: '100%',
        padding: '18px',
        borderRadius: 'var(--radius-md)',
        background: 'linear-gradient(180deg, rgba(255,255,255,0.015), transparent)',
        border: '1px solid rgba(255,255,255,0.03)',
        display: 'flex',
        flexDirection: 'column',
        gap: '12px',
        opacity: status !== 'pending' && !showLogsButton ? 0.8 : 1
      }}
    >
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
         <Typography variant="subtitle2" sx={{ fontWeight: 600, color: 'var(--text)' }}>
            {status === 'pending' ? 'Approval Required' : status === 'approved' ? 'Approved' : 'Rejected'}
         </Typography>
         <Typography variant="caption" sx={{ color: 'var(--muted-text)' }}>
            ({currentIndex + 1}/{batch.count})
         </Typography>
         {status === 'approved' && <CheckCircleIcon sx={{ fontSize: 18, color: 'var(--accent-green)' }} />}
         {status === 'rejected' && <CancelIcon sx={{ fontSize: 18, color: 'var(--accent-red)' }} />}
      </Box>

      <Box 
        onClick={showCode}
        sx={{ 
            display: 'flex', 
            alignItems: 'center', 
            gap: 1, 
            cursor: 'pointer',
            p: 1.5,
            borderRadius: '8px',
            bgcolor: 'rgba(0,0,0,0.2)',
            border: '1px solid rgba(255,255,255,0.05)',
            transition: 'all 0.2s',
            '&:hover': {
                bgcolor: 'rgba(255,255,255,0.03)',
                borderColor: 'var(--accent-primary)',
            }
        }}
      >
        {getToolDescription(currentTool.tool, currentTool.arguments)}
        <OpenInNewIcon sx={{ fontSize: 16, color: 'var(--muted-text)', opacity: 0.7 }} />
      </Box>

      {currentTool.tool === 'hf_jobs' && (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5 }}>
          {/* Show specific job URL if available (after execution), otherwise generic link */}
          {jobUrl ? (
            <Link
              href={jobUrl}
              target="_blank"
              rel="noopener noreferrer"
              sx={{
                display: 'flex',
                alignItems: 'center',
                gap: 0.5,
                color: 'var(--accent-primary)',
                fontSize: '0.8rem',
                textDecoration: 'none',
                opacity: 0.9,
                '&:hover': {
                  opacity: 1,
                  textDecoration: 'underline',
                }
              }}
            >
              <LaunchIcon sx={{ fontSize: 14 }} />
              View job{jobId ? ` (${jobId.substring(0, 8)}...)` : ''} on Hugging Face
            </Link>
          ) : (
            <Link
              href="https://huggingface.co/settings/jobs"
              target="_blank"
              rel="noopener noreferrer"
              sx={{
                display: 'flex',
                alignItems: 'center',
                gap: 0.5,
                color: 'var(--muted-text)',
                fontSize: '0.8rem',
                textDecoration: 'none',
                opacity: 0.7,
                '&:hover': {
                  opacity: 1,
                  textDecoration: 'underline',
                }
              }}
            >
              <LaunchIcon sx={{ fontSize: 14 }} />
              View all jobs on Hugging Face
            </Link>
          )}

          {/* Show job status if available */}
          {jobStatus && (
            <Typography
              variant="caption"
              sx={{
                color: jobFailed ? 'var(--accent-red)' : 'var(--accent-green)',
                fontSize: '0.75rem',
                fontWeight: 500,
              }}
            >
              Status: {jobStatus}
            </Typography>
          )}
        </Box>
      )}

      {containsPushToHub && (
        <Typography variant="caption" sx={{ color: 'var(--accent-green)', fontSize: '0.75rem', opacity: 0.8, px: 0.5 }}>
          We've detected the result will be pushed to hub.
        </Typography>
      )}

      {/* Show script/logs buttons for completed jobs */}
      {status !== 'pending' && currentTool.tool === 'hf_jobs' && (args.script || showLogsButton) && (
        <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
          {args.script && (
            <Button
              variant="outlined"
              size="small"
              startIcon={<OpenInNewIcon />}
              onClick={showCode}
              sx={{
                textTransform: 'none',
                borderColor: 'rgba(255,255,255,0.1)',
                color: 'var(--muted-text)',
                fontSize: '0.75rem',
                py: 0.5,
                '&:hover': {
                  borderColor: 'var(--accent-primary)',
                  color: 'var(--accent-primary)',
                  bgcolor: 'rgba(255,255,255,0.03)'
                }
              }}
            >
              View Script
            </Button>
          )}
          {showLogsButton && (
            <Button
              variant="outlined"
              size="small"
              startIcon={<OpenInNewIcon />}
              onClick={handleViewLogs}
              sx={{
                textTransform: 'none',
                borderColor: 'rgba(255,255,255,0.1)',
                color: 'var(--accent-primary)',
                fontSize: '0.75rem',
                py: 0.5,
                '&:hover': {
                  borderColor: 'var(--accent-primary)',
                  bgcolor: 'rgba(255,255,255,0.03)'
                }
              }}
            >
              View Logs
            </Button>
          )}
        </Box>
      )}

      {status === 'pending' && (
      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
        <Box sx={{ display: 'flex', gap: 1 }}>
            <TextField
                fullWidth
                size="small"
                placeholder="Feedback (optional)"
                value={feedback}
                onChange={(e) => setFeedback(e.target.value)}
                variant="outlined"
                sx={{ 
                    '& .MuiOutlinedInput-root': { 
                        bgcolor: 'rgba(0,0,0,0.2)',
                        fontFamily: 'inherit',
                        fontSize: '0.9rem' 
                    }
                }}
            />
            <IconButton 
                onClick={() => handleResolve(false)}
                disabled={!feedback}
                title="Reject with feedback"
                sx={{ 
                    color: 'var(--accent-red)',
                    border: '1px solid rgba(255,255,255,0.05)',
                    borderRadius: '8px',
                    width: 40,
                    height: 40,
                    '&:hover': {
                        bgcolor: 'rgba(224, 90, 79, 0.1)',
                        borderColor: 'var(--accent-red)',
                    },
                    '&.Mui-disabled': {
                        color: 'rgba(255,255,255,0.1)',
                        borderColor: 'rgba(255,255,255,0.02)'
                    }
                }}
            >
                <SendIcon fontSize="small" />
            </IconButton>
        </Box>
        
        <Box className="action-buttons" sx={{ display: 'flex', gap: '10px' }}>
            <Button 
            className="btn-reject"
            onClick={() => handleResolve(false)}
            sx={{ 
                flex: 1,
                background: 'transparent',
                border: '1px solid rgba(255,255,255,0.05)',
                color: 'var(--accent-red)',
                padding: '10px 14px',
                borderRadius: '10px',
                '&:hover': {
                    bgcolor: 'rgba(224, 90, 79, 0.05)',
                    borderColor: 'var(--accent-red)',
                }
            }}
            >
            Reject
            </Button>
            <Button 
            className="btn-approve"
            onClick={() => handleResolve(true)}
            sx={{ 
                flex: 1,
                background: 'transparent',
                border: '1px solid rgba(255,255,255,0.05)',
                color: 'var(--accent-green)',
                padding: '10px 14px',
                borderRadius: '10px',
                '&:hover': {
                    bgcolor: 'rgba(47, 204, 113, 0.05)',
                    borderColor: 'var(--accent-green)',
                }
            }}
            >
            Approve
            </Button>
        </Box>
      </Box>
      )}
      
      {status === 'rejected' && decisions.some(d => d.feedback) && (
        <Typography variant="body2" sx={{ color: 'var(--accent-red)', mt: 1 }}>
            Feedback: {decisions.find(d => d.feedback)?.feedback}
        </Typography>
      )}
    </Box>
  );
}