import { useState, useCallback, useEffect } from 'react';
import { Box, Typography, Button, TextField, Divider } from '@mui/material';
import { useAgentStore } from '@/store/agentStore';
import { useLayoutStore } from '@/store/layoutStore';

interface ApprovalFlowProps {
  sessionId: string;
}

export default function ApprovalFlow({ sessionId }: ApprovalFlowProps) {
  const { pendingApprovals, setPendingApprovals, setPanelContent } = useAgentStore();
  const { setRightPanelOpen, setLeftSidebarOpen } = useLayoutStore();
  const [currentIndex, setCurrentIndex] = useState(0);
  const [feedback, setFeedback] = useState('');
  const [decisions, setDecisions] = useState<Array<{ tool_call_id: string; approved: boolean; feedback: string | null }>>([]);

  // Reset local state when a new batch of approvals arrives
  useEffect(() => {
    setCurrentIndex(0);
    setFeedback('');
    setDecisions([]);
  }, [pendingApprovals]);

  // Sync right panel with current tool
  useEffect(() => {
    if (!pendingApprovals || currentIndex >= pendingApprovals.tools.length) return;
    
    const tool = pendingApprovals.tools[currentIndex];
    const args = tool.arguments as any;

    if (tool.tool === 'hf_jobs' && (args.operation === 'run' || args.operation === 'scheduled run') && args.script) {
      setPanelContent({
        title: 'Compute Job Script',
        content: args.script,
        language: 'python',
        parameters: args
      });
      setRightPanelOpen(true);
      setLeftSidebarOpen(false);
    } else if (tool.tool === 'hf_repo_files' && args.operation === 'upload' && args.content) {
      setPanelContent({
        title: `File Upload: ${args.path || 'unnamed'}`,
        content: args.content,
        parameters: args
      });
      setRightPanelOpen(true);
      setLeftSidebarOpen(false);
    } else {
      // For other tools, just show parameters in the panel
      setPanelContent({
        title: `Tool: ${tool.tool}`,
        content: '',
        parameters: args
      });
    }
  }, [currentIndex, pendingApprovals, setPanelContent, setRightPanelOpen, setLeftSidebarOpen]);

  const handleResolve = useCallback(async (approved: boolean) => {
    if (!pendingApprovals) return;

    const currentTool = pendingApprovals.tools[currentIndex];
    const newDecisions = [
      ...decisions,
      {
        tool_call_id: currentTool.tool_call_id,
        approved,
        feedback: approved ? null : feedback || 'Rejected by user',
      },
    ];

    if (currentIndex < pendingApprovals.tools.length - 1) {
      setDecisions(newDecisions);
      setCurrentIndex(currentIndex + 1);
      setFeedback('');
    } else {
      // All tools in batch resolved, submit to backend
      try {
        await fetch('/api/approve', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            session_id: sessionId,
            approvals: newDecisions,
          }),
        });
        setPendingApprovals(null);
      } catch (e) {
        console.error('Approval submission failed:', e);
      }
    }
  }, [sessionId, pendingApprovals, currentIndex, feedback, decisions, setPendingApprovals]);

  if (!pendingApprovals || currentIndex >= pendingApprovals.tools.length) return null;

  const currentTool = pendingApprovals.tools[currentIndex];

  return (
    <Box 
      className="action-card"
      sx={{ 
        mt: 2, 
        mb: 4, 
        width: '100%',
        alignSelf: 'center',
        padding: '18px',
        borderRadius: 'var(--radius-md)',
        background: 'linear-gradient(180deg, rgba(255,255,255,0.015), transparent)',
        border: '1px solid rgba(255,255,255,0.03)',
        display: 'flex',
        flexDirection: 'column',
        gap: '12px',
      }}
    >
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
         <Typography variant="subtitle2" sx={{ fontWeight: 600, color: 'var(--text)' }}>
            Approval Required
         </Typography>
         <Typography variant="caption" sx={{ color: 'var(--muted-text)' }}>
            ({currentIndex + 1}/{pendingApprovals.count})
         </Typography>
      </Box>

      <Typography variant="body2" sx={{ color: 'var(--muted-text)' }}>
        The agent wants to execute <Box component="span" sx={{ color: 'var(--accent-yellow)', fontWeight: 500 }}>{currentTool.tool}</Box>
      </Typography>

      <Box component="pre" sx={{ 
        bgcolor: 'rgba(0,0,0,0.3)', 
        p: 2, 
        borderRadius: '8px',
        fontSize: '0.8rem', 
        fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, monospace',
        overflow: 'auto',
        maxHeight: 200,
        border: '1px solid rgba(255,255,255,0.05)',
        margin: 0
      }}>
        {JSON.stringify(currentTool.arguments, null, 2)}
      </Box>

      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
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
    </Box>
  );
}
