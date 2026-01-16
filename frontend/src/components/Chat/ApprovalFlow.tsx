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
    <Box sx={{ 
      mt: 0, 
      mb: 4, 
      px: 2, 
      width: '100%',
      alignSelf: 'center'
    }}>
      <Typography variant="subtitle2" sx={{ fontFamily: 'monospace', mb: 2, fontWeight: 600 }}>
        ACTION REQUIRED ({currentIndex + 1}/{pendingApprovals.count}) : The agent wants to execute <Box component="span" sx={{ color: 'primary.main' }}>{currentTool.tool}</Box>
      </Typography>

      <Box component="pre" sx={{ 
        bgcolor: 'background.default', 
        p: 1.5, 
        borderRadius: 0.5, 
        fontSize: '0.75rem', 
        fontFamily: 'monospace',
        overflow: 'auto',
        maxHeight: 150,
        mb: 2,
        border: 1,
        borderColor: 'divider'
      }}>
        {JSON.stringify(currentTool.arguments, null, 2)}
      </Box>

      <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
        <TextField
          fullWidth
          size="small"
          placeholder="Feedback for rejection (optional)"
          value={feedback}
          onChange={(e) => setFeedback(e.target.value)}
          variant="outlined"
          sx={{ 
            flex: 1,
            '& .MuiOutlinedInput-root': { fontFamily: 'monospace', fontSize: '0.8rem', height: '36px' }
          }}
        />
        
        <Button 
          variant="outlined" 
          color="error" 
          onClick={() => handleResolve(false)}
          sx={{ fontFamily: 'monospace', height: '36px', px: 3 }}
        >
          REJECT
        </Button>
        <Button 
          variant="contained" 
          color="success" 
          onClick={() => handleResolve(true)}
          sx={{ color: 'white', fontFamily: 'monospace', height: '36px', px: 3 }}
        >
          APPROVE
        </Button>
      </Box>
    </Box>
  );
}
