import React, { useEffect, useState } from 'react';
import { Box, ToggleButton, ToggleButtonGroup, TextField, InputAdornment, Chip, Stack, Typography, Button, Select, MenuItem, FormControl, InputLabel, Alert, Snackbar, CircularProgress } from '@mui/material';
import { Search as SearchIcon, ArrowUpward as ArrowUpIcon, ArrowDownward as ArrowDownIcon, ExpandMore as ExpandMoreIcon, ExpandLess as ExpandLessIcon, Refresh as RefreshIcon, Delete as DeleteIcon, CheckBoxOutlineBlank as CheckBoxOutlineBlankIcon } from '@mui/icons-material';
import { logger } from '../utils/logger';
import ConfirmDialog from './ConfirmDialog';

interface EmailToolbarProps {
  searchQuery: string;
  onSearchChange: (query: string) => void;
  sortOrder: 'recent' | 'oldest';
  onSortToggle: () => void;
  filters: {
    priority: string | null;
    labels: string[];
    status: 'all' | 'classified' | 'unclassified';
  };
  onStatusChange: (_event: React.MouseEvent<HTMLElement>, newStatus: 'all' | 'classified' | 'unclassified' | null) => void;
  onClearAllFilters: () => void;
  onLabelFilter: (label: string) => void;
  onPriorityFilter: (priority: string) => void;
  selectedModel: string;
  onModelChange: (model: string) => void;
  selectedIds?: Set<string>;
  onClearSelection?: () => void;
}

interface Label {
  name: string;
  count: number;
}

const EmailToolbar: React.FC<EmailToolbarProps> = ({
  searchQuery,
  onSearchChange,
  sortOrder,
  onSortToggle,
  filters,
  onStatusChange,
  onClearAllFilters,
  onLabelFilter,
  onPriorityFilter,
  selectedModel,
  onModelChange,
  selectedIds = new Set(),
  onClearSelection,
}) => {
  const [labels, setLabels] = useState<Label[]>([]);
  const [loading, setLoading] = useState(false);
  const [showAllLabels, setShowAllLabels] = useState(false);
  const [models, setModels] = useState<Array<{ name: string; size: number }>>([]);
  const [ollamaError, setOllamaError] = useState<string | null>(null);
  const [startingOllama, setStartingOllama] = useState(false);
  const MAX_VISIBLE_LABELS = 6; // Number of labels to show before collapsing

  // Bulk delete state
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [deleteLoading, setDeleteLoading] = useState(false);
  const [deleteSnackbar, setDeleteSnackbar] = useState<{ open: boolean; message: string; severity: 'success' | 'error' }>({
    open: false,
    message: '',
    severity: 'success',
  });

  // Bulk delete handlers
  const handleBulkDeleteClick = () => {
    if (selectedIds.size > 0) {
      setDeleteDialogOpen(true);
    }
  };

  const handleBulkDeleteConfirm = async () => {
    setDeleteLoading(true);
    const ids = Array.from(selectedIds);
    logger.info(`Deleting ${ids.length} emails`);

    try {
      const response = await fetch('/api/messages/batch', {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ids }),
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const result = await response.json();
      const deletedCount = result.deleted || ids.length;
      const failedCount = result.failed?.length || 0;

      if (failedCount > 0) {
        setDeleteSnackbar({
          open: true,
          message: `Deleted ${deletedCount} emails, ${failedCount} failed`,
          severity: 'error',
        });
      } else {
        setDeleteSnackbar({
          open: true,
          message: `${deletedCount} email${deletedCount !== 1 ? 's' : ''} moved to trash`,
          severity: 'success',
        });
      }

      // Clear selection and trigger refresh
      onClearSelection?.();
      // Trigger page refresh by forcing re-render
      window.dispatchEvent(new CustomEvent('emails-deleted'));
    } catch (err) {
      logger.error('Bulk delete failed:', err);
      setDeleteSnackbar({
        open: true,
        message: 'Failed to delete emails',
        severity: 'error',
      });
    } finally {
      setDeleteLoading(false);
      setDeleteDialogOpen(false);
    }
  };

  const handleBulkDeleteCancel = () => {
    setDeleteDialogOpen(false);
  };

  // Wrapper functions to add logging
  const handlePriorityFilterClick = (priority: string) => {
    logger.info(`User clicked priority filter: ${priority}`);
    onPriorityFilter(priority);
  };

  const handleLabelFilterClick = (label: string) => {
    console.log('handleLabelFilterClick called with:', label);
    logger.info(`User clicked label filter: ${label}`);
    onLabelFilter(label);
  };

  const handleStatusChange = (event: React.MouseEvent<HTMLElement>, newStatus: 'all' | 'classified' | 'unclassified' | null) => {
    if (newStatus !== null) {
      logger.info(`User changed status filter to: ${newStatus}`);
      onStatusChange(event, newStatus);
    }
  };

  const handleClearAllFilters = () => {
    logger.info('User clicked clear all filters');
    onClearAllFilters();
  };

  const handleSortToggle = () => {
    logger.info(`User toggled sort order from ${sortOrder} to ${sortOrder === 'recent' ? 'oldest' : 'recent'}`);
    onSortToggle();
  };

  const handleSearchChange = (query: string) => {
    if (query.trim()) {
      logger.info(`User searching for: ${query}`);
    }
    onSearchChange(query);
  };

  const handleModelChange = async (model: string) => {
    logger.info(`User selected model: ${model}`);
    
    try {
      const response = await fetch('/api/set-model', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model }),
      });
      
      if (!response.ok) {
        throw new Error('Failed to set model');
      }
      
      const result = await response.json();
      logger.info(`Model changed successfully: ${result.message}`);
      onModelChange(model);
    } catch (error) {
      logger.error('Failed to set model', error);
      // Still update UI even if API call fails
      onModelChange(model);
    }
  };



  const fetchModels = async () => {
    try {
      const res = await fetch('/models');
      if (res.ok) {
        const data = await res.json();
        const fetchedModels = data.models || [];
        setModels(fetchedModels);
        setOllamaError(null);
      } else if (res.status === 503) {
        const data = await res.json();
        setOllamaError(data.detail || 'Ollama service not available');
        setModels([]);
      }
    } catch (err) {
      console.error('Failed to fetch models:', err);
      setOllamaError('Failed to connect to Ollama');
      setModels([]);
    }
  };

  const handleStartOllama = async () => {
    setStartingOllama(true);
    logger.info('User requested to start Ollama');
    try {
      const res = await fetch('/api/ollama/start', { method: 'POST' });
      if (res.ok) {
        logger.info('Ollama start request successful');
        // Wait a bit then refetch models
        setTimeout(() => {
          fetchModels();
          setStartingOllama(false);
        }, 3000);
      } else {
        const data = await res.json();
        setOllamaError(data.detail || 'Failed to start Ollama');
        setStartingOllama(false);
      }
    } catch (err) {
      console.error('Failed to start Ollama:', err);
      setOllamaError('Failed to start Ollama service');
      setStartingOllama(false);
    }
  };

  useEffect(() => {
    async function fetchLabels() {
      setLoading(true);
      try {
        const res = await fetch('/labels');
        if (res.ok) {
          const data = await res.json();
          setLabels(data.labels || []);
        } else {
          setLabels([]);
        }
      } catch (err) {
        // Failed to fetch labels - backend may not be running
        setLabels([]);
      } finally {
        setLoading(false);
      }
    }

    fetchLabels();
    fetchModels();
  }, []);

  return (
    <Box sx={{ mb: 2 }}>
      {/* Bulk Selection Bar - shown when items are selected */}
      {selectedIds.size > 0 && (
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            gap: 2,
            mb: 2,
            p: 1.5,
            bgcolor: 'primary.main',
            borderRadius: 1,
            color: 'primary.contrastText',
          }}
        >
          <Typography variant="body2" sx={{ fontWeight: 'medium' }}>
            {selectedIds.size} email{selectedIds.size !== 1 ? 's' : ''} selected
          </Typography>
          <Button
            size="small"
            variant="outlined"
            startIcon={<CheckBoxOutlineBlankIcon />}
            onClick={onClearSelection}
            sx={{
              color: 'inherit',
              borderColor: 'rgba(255,255,255,0.5)',
              '&:hover': { borderColor: 'white', bgcolor: 'rgba(255,255,255,0.1)' },
            }}
          >
            Clear Selection
          </Button>
          <Button
            size="small"
            variant="contained"
            color="error"
            startIcon={deleteLoading ? <CircularProgress size={16} color="inherit" /> : <DeleteIcon />}
            onClick={handleBulkDeleteClick}
            disabled={deleteLoading}
          >
            {deleteLoading ? 'Deleting...' : 'Delete Selected'}
          </Button>
        </Box>
      )}

      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, flexWrap: 'wrap', mb: 2 }}>
        <FormControl size="small" sx={{ minWidth: 150 }} error={!!ollamaError}>
          <InputLabel>LLM Model</InputLabel>
          <Select
            value={selectedModel}
            label="LLM Model"
            onChange={(e) => handleModelChange(e.target.value)}
            disabled={models.length === 0}
          >
            {models.map((model) => (
              <MenuItem key={model.name} value={model.name}>
                {model.name}
              </MenuItem>
            ))}
          </Select>
        </FormControl>

        {ollamaError && (
          <>
            <Alert severity="warning" sx={{ py: 0, alignItems: 'center' }}>
              {ollamaError}
            </Alert>
            <Button
              variant="contained"
              size="small"
              startIcon={startingOllama ? <RefreshIcon className="spin" /> : <RefreshIcon />}
              onClick={handleStartOllama}
              disabled={startingOllama}
            >
              {startingOllama ? 'Starting...' : 'Start Ollama'}
            </Button>
          </>
        )}

        <TextField
          size="small"
          placeholder="Search emails..."
          value={searchQuery}
          onChange={(e) => handleSearchChange(e.target.value)}
          sx={{ minWidth: 250 }}
          InputProps={{
            startAdornment: (
              <InputAdornment position="start">
                <SearchIcon />
              </InputAdornment>
            ),
          }}
        />

        <Chip
          icon={sortOrder === 'recent' ? <ArrowDownIcon /> : <ArrowUpIcon />}
          label={sortOrder === 'recent' ? 'Newest First' : 'Oldest First'}
          onClick={handleSortToggle}
          variant="outlined"
          sx={{
            cursor: 'pointer',
            '&:hover': { bgcolor: 'action.hover' }
          }}
        />

        <ToggleButtonGroup
          value={filters.status}
          exclusive
          onChange={handleStatusChange}
          size="small"
          aria-label="classification status filter"
        >
          <ToggleButton value="all" aria-label="all messages">
            All
          </ToggleButton>
          <ToggleButton value="classified" aria-label="classified messages">
            Classified
          </ToggleButton>
          <ToggleButton value="unclassified" aria-label="unclassified messages">
            Unclassified
          </ToggleButton>
        </ToggleButtonGroup>

        {/* Priority filter chips */}
        <Box sx={{ display: 'flex', gap: 1 }}>
          <Chip
            label="🔴 High"
            onClick={() => handlePriorityFilterClick('high')}
            variant={filters.priority === 'high' ? 'filled' : 'outlined'}
            color={filters.priority === 'high' ? 'error' : 'default'}
            size="small"
            sx={{ cursor: 'pointer', '&:hover': { bgcolor: 'action.hover' } }}
          />
          <Chip
            label="🟡 Normal"
            onClick={() => handlePriorityFilterClick('normal')}
            variant={filters.priority === 'normal' ? 'filled' : 'outlined'}
            color={filters.priority === 'normal' ? 'primary' : 'default'}
            size="small"
            sx={{ cursor: 'pointer', '&:hover': { bgcolor: 'action.hover' } }}
          />
          <Chip
            label="🟢 Low"
            onClick={() => handlePriorityFilterClick('low')}
            variant={filters.priority === 'low' ? 'filled' : 'outlined'}
            color={filters.priority === 'low' ? 'success' : 'default'}
            size="small"
            sx={{ cursor: 'pointer', '&:hover': { bgcolor: 'action.hover' } }}
          />
        </Box>

        {filters.labels.length > 0 && (
          <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
            {filters.labels.map((label) => (
              <Chip
                key={label}
                label={label}
                onDelete={() => handleLabelFilterClick(label)}
                color="primary"
                size="small"
              />
            ))}
          </Box>
        )}
        {filters.priority && (
          <Chip
            label={`Priority: ${filters.priority}`}
            onDelete={() => handlePriorityFilterClick(filters.priority!)}
            color="secondary"
            variant="outlined"
            size="small"
          />
        )}
        {(filters.labels.length > 0 || filters.priority || filters.status !== 'all') && (
          <Chip
            label="Clear all filters"
            onClick={handleClearAllFilters}
            variant="filled"
            color="error"
            size="small"
          />
        )}
      </Box>

      {/* Label filter chips - always show section if we've loaded */}
      {!loading && (
        <Box>
          <Typography variant="caption" color="text.secondary" sx={{ mb: 1, display: 'block' }}>
            Filter by label: {labels.length === 0 && '(no labels found)'}
          </Typography>
          {labels.length > 0 && (
            <Stack direction="row" spacing={1} sx={{ flexWrap: 'wrap', gap: 1, alignItems: 'center' }}>
              {/* Sort labels by count (most popular first) and show only top N if not expanded */}
              {labels
                .sort((a, b) => b.count - a.count)
                .slice(0, showAllLabels ? labels.length : MAX_VISIBLE_LABELS)
                .map((label) => {
                  const isSelected = filters.labels.includes(label.name);
                  return (
                    <Chip
                      key={label.name}
                      label={`${label.name} (${label.count})`}
                      onClick={() => handleLabelFilterClick(label.name)}
                      variant={isSelected ? 'filled' : 'outlined'}
                      color={isSelected ? 'primary' : 'default'}
                      size="small"
                      sx={{
                        cursor: 'pointer',
                        '&:hover': { bgcolor: 'action.hover' }
                      }}
                    />
                  );
                })}

              {/* Show expand/collapse button if there are more labels than MAX_VISIBLE_LABELS */}
              {labels.length > MAX_VISIBLE_LABELS && (
                <Button
                  size="small"
                  onClick={() => setShowAllLabels(!showAllLabels)}
                  startIcon={showAllLabels ? <ExpandLessIcon /> : <ExpandMoreIcon />}
                  sx={{
                    textTransform: 'none',
                    minWidth: 'auto',
                    px: 1
                  }}
                >
                  {showAllLabels ? 'Show less' : `Show ${labels.length - MAX_VISIBLE_LABELS} more`}
                </Button>
              )}
            </Stack>
          )}
        </Box>
      )}
      {loading && (
        <Typography variant="caption" color="text.secondary">
          Loading labels...
        </Typography>
      )}

      {/* Bulk Delete Confirmation Dialog */}
      <ConfirmDialog
        open={deleteDialogOpen}
        title={`Delete ${selectedIds.size} Email${selectedIds.size !== 1 ? 's' : ''}?`}
        message={`${selectedIds.size} email${selectedIds.size !== 1 ? 's' : ''} will be moved to trash. You can recover them from Gmail's trash folder.`}
        confirmText="Move to Trash"
        cancelText="Cancel"
        loading={deleteLoading}
        onConfirm={handleBulkDeleteConfirm}
        onCancel={handleBulkDeleteCancel}
      />

      {/* Delete Feedback Snackbar */}
      <Snackbar
        open={deleteSnackbar.open}
        autoHideDuration={4000}
        onClose={() => setDeleteSnackbar(prev => ({ ...prev, open: false }))}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'left' }}
      >
        <Alert
          onClose={() => setDeleteSnackbar(prev => ({ ...prev, open: false }))}
          severity={deleteSnackbar.severity}
          sx={{ width: '100%' }}
        >
          {deleteSnackbar.message}
        </Alert>
      </Snackbar>
    </Box>
  );
};

export default EmailToolbar;
