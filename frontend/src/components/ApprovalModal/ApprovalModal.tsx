import { useState, useCallback } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Box,
  Typography,
  Checkbox,
  FormControlLabel,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  TextField,
  Chip,
} from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import WarningIcon from '@mui/icons-material/Warning';
import { useAgentStore } from '@/store/agentStore';

interface ApprovalModalProps {
  sessionId: string | null;
}

interface ApprovalState {
  [toolCallId: string]: {
    approved: boolean;
    feedback: string;
  };
}

export default function ApprovalModal({ sessionId }: ApprovalModalProps) {
  const { pendingApprovals, setPendingApprovals } = useAgentStore();
  const [approvalState, setApprovalState] = useState<ApprovalState>({});

  const isOpen = pendingApprovals !== null && pendingApprovals.tools.length > 0;

  const handleApprovalChange = useCallback(
    (toolCallId: string, approved: boolean) => {
      setApprovalState((prev) => ({
        ...prev,
        [toolCallId]: {
          ...prev[toolCallId],
          approved,
          feedback: prev[toolCallId]?.feedback || '',
        },
      }));
    },
    []
  );

  const handleFeedbackChange = useCallback(
    (toolCallId: string, feedback: string) => {
      setApprovalState((prev) => ({
        ...prev,
        [toolCallId]: {
          ...prev[toolCallId],
          feedback,
        },
      }));
    },
    []
  );

  const handleSubmit = useCallback(async () => {
    if (!sessionId || !pendingApprovals) return;

    const approvals = pendingApprovals.tools.map((tool) => ({
      tool_call_id: tool.tool_call_id,
      approved: approvalState[tool.tool_call_id]?.approved ?? false,
      feedback: approvalState[tool.tool_call_id]?.feedback || null,
    }));

    try {
      await fetch('/api/approve', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: sessionId,
          approvals,
        }),
      });
      setPendingApprovals(null);
      setApprovalState({});
    } catch (e) {
      console.error('Approval submission failed:', e);
    }
  }, [sessionId, pendingApprovals, approvalState, setPendingApprovals]);

  const handleApproveAll = useCallback(() => {
    if (!pendingApprovals) return;
    const newState: ApprovalState = {};
    pendingApprovals.tools.forEach((tool) => {
      newState[tool.tool_call_id] = { approved: true, feedback: '' };
    });
    setApprovalState(newState);
  }, [pendingApprovals]);

  const handleRejectAll = useCallback(() => {
    if (!pendingApprovals) return;
    const newState: ApprovalState = {};
    pendingApprovals.tools.forEach((tool) => {
      newState[tool.tool_call_id] = { approved: false, feedback: '' };
    });
    setApprovalState(newState);
  }, [pendingApprovals]);

  if (!isOpen || !pendingApprovals) return null;

  const approvedCount = Object.values(approvalState).filter((s) => s.approved).length;

  return (
    <Dialog
      open={isOpen}
      maxWidth="md"
      fullWidth
      PaperProps={{
        sx: { bgcolor: 'background.paper' },
      }}
    >
      <DialogTitle sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
        <WarningIcon color="warning" />
        Approval Required
        <Chip
          label={`${pendingApprovals.count} tool${pendingApprovals.count > 1 ? 's' : ''}`}
          size="small"
          sx={{ ml: 1 }}
        />
      </DialogTitle>
      <DialogContent dividers>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          The following tool calls require your approval before execution:
        </Typography>
        {pendingApprovals.tools.map((tool, index) => (
          <Accordion key={tool.tool_call_id} defaultExpanded={index === 0}>
            <AccordionSummary expandIcon={<ExpandMoreIcon />}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, width: '100%' }}>
                <FormControlLabel
                  control={
                    <Checkbox
                      checked={approvalState[tool.tool_call_id]?.approved ?? false}
                      onChange={(e) => {
                        e.stopPropagation();
                        handleApprovalChange(tool.tool_call_id, e.target.checked);
                      }}
                      onClick={(e) => e.stopPropagation()}
                    />
                  }
                  label=""
                  sx={{ m: 0 }}
                />
                <Chip label={tool.tool} size="small" color="primary" variant="outlined" />
                <Typography variant="body2" color="text.secondary" sx={{ ml: 'auto' }}>
                  {approvalState[tool.tool_call_id]?.approved ? 'Approved' : 'Pending'}
                </Typography>
              </Box>
            </AccordionSummary>
            <AccordionDetails>
              <Typography variant="subtitle2" gutterBottom>
                Arguments:
              </Typography>
              <Box
                component="pre"
                sx={{
                  bgcolor: 'background.default',
                  p: 1.5,
                  borderRadius: 1,
                  overflow: 'auto',
                  fontSize: '0.8rem',
                  maxHeight: 200,
                }}
              >
                {JSON.stringify(tool.arguments, null, 2)}
              </Box>
              {!approvalState[tool.tool_call_id]?.approved && (
                <TextField
                  fullWidth
                  size="small"
                  label="Feedback (optional)"
                  placeholder="Explain why you're rejecting this..."
                  value={approvalState[tool.tool_call_id]?.feedback || ''}
                  onChange={(e) => handleFeedbackChange(tool.tool_call_id, e.target.value)}
                  sx={{ mt: 2 }}
                />
              )}
            </AccordionDetails>
          </Accordion>
        ))}
      </DialogContent>
      <DialogActions sx={{ px: 3, py: 2 }}>
        <Button onClick={handleRejectAll} color="error" variant="outlined">
          Reject All
        </Button>
        <Button onClick={handleApproveAll} color="success" variant="outlined">
          Approve All
        </Button>
        <Box sx={{ flex: 1 }} />
        <Typography variant="body2" color="text.secondary" sx={{ mr: 2 }}>
          {approvedCount} of {pendingApprovals.count} approved
        </Typography>
        <Button onClick={handleSubmit} variant="contained" color="primary">
          Submit
        </Button>
      </DialogActions>
    </Dialog>
  );
}
