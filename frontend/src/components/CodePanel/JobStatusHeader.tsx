import { Box, Chip, Link } from '@mui/material';
import LaunchIcon from '@mui/icons-material/Launch';
import CloudQueueIcon from '@mui/icons-material/CloudQueue';
import HourglassEmptyIcon from '@mui/icons-material/HourglassEmpty';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import ErrorIcon from '@mui/icons-material/Error';
import CancelIcon from '@mui/icons-material/Cancel';
import type { JobStatus } from '@/store/agentStore';

interface JobStatusHeaderProps {
  job: JobStatus;
}

const statusConfig: Record<JobStatus['status'], {
  label: string;
  color: string;
  bgColor: string;
  icon: React.ReactNode;
}> = {
  queued: {
    label: 'Queued',
    color: '#FFA726',
    bgColor: 'rgba(255, 167, 38, 0.15)',
    icon: <CloudQueueIcon sx={{ fontSize: 14 }} />,
  },
  pending: {
    label: 'Pending',
    color: '#FFA726',
    bgColor: 'rgba(255, 167, 38, 0.15)',
    icon: <HourglassEmptyIcon sx={{ fontSize: 14 }} />,
  },
  running: {
    label: 'Running',
    color: '#42A5F5',
    bgColor: 'rgba(66, 165, 245, 0.15)',
    icon: <PlayArrowIcon sx={{ fontSize: 14 }} />,
  },
  completed: {
    label: 'Completed',
    color: '#66BB6A',
    bgColor: 'rgba(102, 187, 106, 0.15)',
    icon: <CheckCircleIcon sx={{ fontSize: 14 }} />,
  },
  failed: {
    label: 'Failed',
    color: '#EF5350',
    bgColor: 'rgba(239, 83, 80, 0.15)',
    icon: <ErrorIcon sx={{ fontSize: 14 }} />,
  },
  canceled: {
    label: 'Canceled',
    color: '#BDBDBD',
    bgColor: 'rgba(189, 189, 189, 0.15)',
    icon: <CancelIcon sx={{ fontSize: 14 }} />,
  },
  error: {
    label: 'Error',
    color: '#EF5350',
    bgColor: 'rgba(239, 83, 80, 0.15)',
    icon: <ErrorIcon sx={{ fontSize: 14 }} />,
  },
};

export default function JobStatusHeader({ job }: JobStatusHeaderProps) {
  const config = statusConfig[job.status] || statusConfig.pending;

  return (
    <Box
      sx={{
        bgcolor: 'rgba(0, 0, 0, 0.3)',
        borderBottom: '1px solid rgba(255, 255, 255, 0.05)',
        px: 2,
        py: 1.5,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: 2,
      }}
    >
      {/* Left side: Status + Hardware */}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
        {/* Status badge */}
        <Chip
          icon={config.icon as React.ReactElement}
          label={config.label}
          size="small"
          sx={{
            height: 26,
            bgcolor: config.bgColor,
            color: config.color,
            border: `1px solid ${config.color}40`,
            fontWeight: 600,
            fontSize: '0.7rem',
            textTransform: 'uppercase',
            letterSpacing: '0.03em',
            '& .MuiChip-icon': {
              color: config.color,
              ml: 0.5,
            },
          }}
        />

        {/* Hardware badge */}
        <Chip
          label={job.hardware}
          size="small"
          sx={{
            height: 24,
            bgcolor: job.isGpu ? 'rgba(156, 39, 176, 0.15)' : 'rgba(255, 255, 255, 0.05)',
            color: job.isGpu ? '#BA68C8' : 'var(--muted-text)',
            border: job.isGpu ? '1px solid rgba(156, 39, 176, 0.3)' : '1px solid rgba(255, 255, 255, 0.1)',
            fontWeight: 500,
            fontSize: '0.65rem',
            textTransform: 'uppercase',
          }}
        />
      </Box>

      {/* Right side: Link to HF Jobs */}
      <Link
        href={job.url}
        target="_blank"
        rel="noopener noreferrer"
        sx={{
          display: 'flex',
          alignItems: 'center',
          gap: 0.75,
          color: 'var(--accent-yellow)',
          fontSize: '0.8rem',
          fontWeight: 600,
          textDecoration: 'none',
          px: 2,
          py: 0.75,
          borderRadius: 1,
          bgcolor: 'rgba(255, 193, 7, 0.1)',
          border: '1px solid rgba(255, 193, 7, 0.25)',
          transition: 'all 0.15s ease',
          '&:hover': {
            bgcolor: 'rgba(255, 193, 7, 0.2)',
            borderColor: 'rgba(255, 193, 7, 0.4)',
          },
        }}
      >
        <LaunchIcon sx={{ fontSize: 16 }} />
        View on HF Jobs
      </Link>
    </Box>
  );
}
