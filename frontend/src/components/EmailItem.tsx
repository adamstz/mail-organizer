import React from 'react';
import {
  ListItem,
  ListItemText,
  IconButton,
  Collapse,
  Typography,
  Box,
  Chip,
} from '@mui/material';
import {
  Delete as DeleteIcon,
  ExpandMore as ExpandMoreIcon,
  ExpandLess as ExpandLessIcon,
} from '@mui/icons-material';
import { Email } from '../types/email';

const getPriorityColor = (priority: Email['priority']): 'error' | 'warning' | 'success' | 'default' => {
  switch (priority.toLowerCase()) {
    case 'high':
      return 'error';
    case 'medium':
      return 'warning';
    case 'low':
      return 'success';
    case 'unclassified':
      return 'default';
    default:
      return 'default';
  }
};

interface EmailItemProps {
  email: Email;
  isExpanded: boolean;
  onExpand: (id: number) => void;
  onDelete: (id: number) => void;
}

const EmailItem: React.FC<EmailItemProps> = ({ email, isExpanded, onExpand, onDelete }) => {
  return (
    <React.Fragment>
      <ListItem
        alignItems="flex-start"
        sx={{
          cursor: 'pointer',
          '&:hover': { backgroundColor: 'action.hover' },
          borderBottom: '1px solid',
          borderColor: 'divider',
          bgcolor: 'background.paper',
          mb: 2,
          borderRadius: 1,
          p: 2,
          boxShadow: 1,
        }}
      >
        <Box sx={{ display: 'flex', flexDirection: 'column', flexGrow: 1 }}>
          <Box
            sx={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              width: '100%',
            }}
            onClick={() => onExpand(email.id)}
          >
            <ListItemText
              primary={
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
                  <Typography variant="subtitle1">{email.subject}</Typography>
                  <Chip
                    label={email.priority}
                    size="small"
                    color={getPriorityColor(email.priority)}
                  />
                  {email.classificationLabels && email.classificationLabels.length > 0 && (
                    <>
                      {email.classificationLabels.map((label, idx) => (
                        <Chip
                          key={idx}
                          label={label}
                          size="small"
                          variant="outlined"
                          sx={{ fontSize: '0.7rem' }}
                        />
                      ))}
                    </>
                  )}
                </Box>
              }
              secondary={
                <Typography
                  variant="body2"
                  color="text.secondary"
                  sx={{ mt: 1 }}
                >
                  {email.summary}
                </Typography>
              }
            />
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <Typography variant="caption" color="text.secondary">
                {email.date}
              </Typography>
              {isExpanded ? (
                <ExpandLessIcon />
              ) : (
                <ExpandMoreIcon />
              )}
            </Box>
          </Box>
        </Box>
        <IconButton
          edge="end"
          aria-label="delete"
          onClick={() => onDelete(email.id)}
          sx={{ ml: 2 }}
        >
          <DeleteIcon />
        </IconButton>
      </ListItem>
      <Collapse in={isExpanded} timeout="auto" unmountOnExit>
        <Box sx={{ p: 3, backgroundColor: 'grey.50' }}>
          <Box sx={{ mb: 2 }}>
            <Typography variant="subtitle2" color="text.secondary" sx={{ fontWeight: 'bold' }}>
              Subject:
            </Typography>
            <Typography variant="body1" sx={{ mb: 1 }}>
              {email.subject}
            </Typography>
          </Box>
          
          <Box sx={{ mb: 2 }}>
            <Typography variant="subtitle2" color="text.secondary" sx={{ fontWeight: 'bold' }}>
              Date:
            </Typography>
            <Typography variant="body1" sx={{ mb: 1 }}>
              {email.date}
            </Typography>
          </Box>
          
          <Box>
            <Typography variant="subtitle2" color="text.secondary" sx={{ fontWeight: 'bold', mb: 1 }}>
              Body:
            </Typography>
            <Typography variant="body1" whiteSpace="pre-line">
              {email.body}
            </Typography>
          </Box>
        </Box>
      </Collapse>
    </React.Fragment>
  );
};

export default EmailItem;
