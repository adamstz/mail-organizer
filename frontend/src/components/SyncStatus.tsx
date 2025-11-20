import React, { useState, useEffect } from 'react';
import {
  Box,
  Button,
  Chip,
  Badge,
  LinearProgress,
  Snackbar,
  Alert,
  Typography,
  Stack,
  Paper,
  IconButton,
  Collapse,
  Tooltip,
} from '@mui/material';
import CloudSyncIcon from '@mui/icons-material/CloudSync';
import CategoryIcon from '@mui/icons-material/Category';
import RefreshIcon from '@mui/icons-material/Refresh';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ExpandLessIcon from '@mui/icons-material/ExpandLess';

interface ProgressInfo {
  status: 'idle' | 'running' | 'completed' | 'error';
  total: number;
  processed: number;
  errors: number;
  message?: string;
  started_at?: string;
  completed_at?: string;
}

interface SyncStatusData {
  gmail_total: number;
  db_total: number;
  not_synced: number;
  unclassified: number;
  unembedded: number;
  pull_progress: ProgressInfo;
  classify_progress: ProgressInfo;
}

interface SyncStatusProps {
  onRefresh?: () => void;
}

const SyncStatus: React.FC<SyncStatusProps> = ({ onRefresh }) => {
  const [status, setStatus] = useState<SyncStatusData | null>(null);
  const [loading, setLoading] = useState(false);
  const [isExpanded, setIsExpanded] = useState(true);
  const [snackbar, setSnackbar] = useState<{
    open: boolean;
    message: string;
    severity: 'success' | 'error' | 'info';
  }>({ open: false, message: '', severity: 'info' });

  const isAnyOperationRunning = status?.pull_progress.status === 'running' || 
                                 status?.classify_progress.status === 'running';

  // Fetch sync status
  const fetchStatus = async () => {
    try {
      const response = await fetch('/api/sync-status');
      if (!response.ok) {
        throw new Error('Failed to fetch sync status');
      }
      const data = await response.json();
      setStatus(data);
    } catch (error) {
      console.error('Error fetching sync status:', error);
    }
  };

  // Poll sync status - 2s when operations running, 30s when idle
  useEffect(() => {
    fetchStatus(); // Initial load
    
    const interval = setInterval(() => {
      fetchStatus();
    }, isAnyOperationRunning ? 2000 : 30000);

    return () => clearInterval(interval);
  }, [isAnyOperationRunning]);

  // Handle pull sync
  const handlePullSync = async () => {
    setLoading(true);
    try {
      const response = await fetch('/api/sync/pull', {
        method: 'POST',
      });
      
      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to start pull sync');
      }

      const result = await response.json();
      setSnackbar({
        open: true,
        message: result.message || 'Pull sync started',
        severity: 'info',
      });
      
      // Fetch status immediately to show progress
      fetchStatus();
    } catch (error) {
      setSnackbar({
        open: true,
        message: error instanceof Error ? error.message : 'Failed to start pull sync',
        severity: 'error',
      });
    } finally {
      setLoading(false);
    }
  };

  // Handle classify & embed sync
  const handleClassifySync = async () => {
    setLoading(true);
    try {
      const response = await fetch('/api/sync/classify', {
        method: 'POST',
      });
      
      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to start classify sync');
      }

      const result = await response.json();
      setSnackbar({
        open: true,
        message: result.message || 'Classify & embed sync started',
        severity: 'info',
      });
      
      // Fetch status immediately to show progress
      fetchStatus();
    } catch (error) {
      setSnackbar({
        open: true,
        message: error instanceof Error ? error.message : 'Failed to start classify sync',
        severity: 'error',
      });
    } finally {
      setLoading(false);
    }
  };

  // Show completion notifications
  useEffect(() => {
    if (status?.pull_progress.status === 'completed' && status.pull_progress.completed_at) {
      setSnackbar({
        open: true,
        message: `Pulled ${status.pull_progress.processed} messages from Gmail`,
        severity: 'success',
      });
      if (onRefresh) {
        onRefresh();
      }
    }
    
    if (status?.classify_progress.status === 'completed' && status.classify_progress.completed_at) {
      setSnackbar({
        open: true,
        message: `Classified and embedded ${status.classify_progress.processed} messages`,
        severity: 'success',
      });
      if (onRefresh) {
        onRefresh();
      }
    }

    if (status?.pull_progress.status === 'error') {
      setSnackbar({
        open: true,
        message: status.pull_progress.message || 'Pull sync failed',
        severity: 'error',
      });
    }

    if (status?.classify_progress.status === 'error') {
      setSnackbar({
        open: true,
        message: status.classify_progress.message || 'Classify sync failed',
        severity: 'error',
      });
    }
  }, [status?.pull_progress.status, status?.classify_progress.status]);

  const renderProgress = (progress: ProgressInfo, label: string) => {
    if (progress.status === 'running') {
      const percentage = progress.total > 0 ? (progress.processed / progress.total) * 100 : 0;
      return (
        <Box sx={{ width: '100%', mt: 1 }}>
          <Typography variant="caption" color="text.secondary">
            {label}: {progress.processed} / {progress.total}
            {progress.errors > 0 && ` (${progress.errors} errors)`}
          </Typography>
          <LinearProgress variant="determinate" value={percentage} />
        </Box>
      );
    }
    return null;
  };

  if (!status) {
    return (
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
        <RefreshIcon sx={{ animation: 'spin 1s linear infinite' }} />
        <Typography variant="body2">Loading sync status...</Typography>
      </Box>
    );
  }

  return (
    <Paper elevation={2} sx={{ p: 2, mb: 2 }}>
      <Stack spacing={2}>
        {/* Header Row - Always Visible */}
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, flexWrap: 'wrap', justifyContent: 'space-between' }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, flexWrap: 'wrap', flexGrow: 1 }}>
            <Typography variant="h6">Sync Status</Typography>
            
            <Badge badgeContent={status.not_synced} color="warning">
              <Chip
                label="Not Synced"
                size="small"
                color={status.not_synced > 0 ? 'warning' : 'default'}
              />
            </Badge>
            
            <Badge badgeContent={status.unclassified} color="error">
              <Chip
                label="Unclassified"
                size="small"
                color={status.unclassified > 0 ? 'error' : 'default'}
              />
            </Badge>
            
            {!isExpanded && (
              <Box sx={{ display: 'flex', gap: 1 }}>
                <Button
                  variant="outlined"
                  size="small"
                  startIcon={<CloudSyncIcon />}
                  onClick={handlePullSync}
                  disabled={loading || status.pull_progress.status === 'running' || status.not_synced === 0}
                >
                  Pull ({status.not_synced})
                </Button>

                <Button
                  variant="outlined"
                  size="small"
                  startIcon={<CategoryIcon />}
                  onClick={handleClassifySync}
                  disabled={loading || status.classify_progress.status === 'running' || status.unclassified === 0}
                >
                  Classify ({status.unclassified})
                </Button>
              </Box>
            )}
          </Box>
          
          <Tooltip title={isExpanded ? "Collapse" : "Expand"}>
            <IconButton onClick={() => setIsExpanded(!isExpanded)} size="small">
              {isExpanded ? <ExpandLessIcon /> : <ExpandMoreIcon />}
            </IconButton>
          </Tooltip>
        </Box>

        {/* Collapsible Details */}
        <Collapse in={isExpanded}>
          <Stack spacing={2}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, flexWrap: 'wrap' }}>
              <Chip
                label={`Gmail: ${status.gmail_total}`}
                size="small"
                color="default"
              />
              
              <Chip
                label={`Database: ${status.db_total}`}
                size="small"
                color="default"
              />
            </Box>

            <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
              <Button
                variant="contained"
                color="primary"
                startIcon={<CloudSyncIcon />}
                onClick={handlePullSync}
                disabled={loading || status.pull_progress.status === 'running' || status.not_synced === 0}
              >
                Sync from Gmail ({status.not_synced})
              </Button>

              <Button
                variant="contained"
                color="secondary"
                startIcon={<CategoryIcon />}
                onClick={handleClassifySync}
                disabled={loading || status.classify_progress.status === 'running' || status.unclassified === 0}
              >
                Classify & Embed ({status.unclassified})
              </Button>
            </Box>

            {renderProgress(status.pull_progress, 'Pulling from Gmail')}
            {renderProgress(status.classify_progress, 'Classifying & Embedding')}
          </Stack>
        </Collapse>

        <Snackbar
          open={snackbar.open}
          autoHideDuration={6000}
          onClose={() => setSnackbar({ ...snackbar, open: false })}
          anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
        >
          <Alert
            onClose={() => setSnackbar({ ...snackbar, open: false })}
            severity={snackbar.severity}
            variant="filled"
          >
            {snackbar.message}
          </Alert>
        </Snackbar>
      </Stack>
    </Paper>
  );
};

export default SyncStatus;
