import React from 'react';
import { Box, Button, Typography, Paper, CircularProgress, Alert, IconButton } from '@mui/material';
import GoogleIcon from '@mui/icons-material/Google';
import CloseIcon from '@mui/icons-material/Close';
import { useAuth } from './AuthContext';

interface LoginPageProps {
  isReconnect?: boolean;
  onCancel?: () => void;
}

const LoginPage: React.FC<LoginPageProps> = ({ isReconnect = false, onCancel }) => {
  const { login, loading, error } = useAuth();

  if (loading) {
    return (
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          minHeight: '100vh',
          bgcolor: 'background.default',
        }}
      >
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box
      sx={{
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        minHeight: '100vh',
        bgcolor: 'background.default',
      }}
    >
      <Paper
        elevation={3}
        sx={{
          p: 4,
          maxWidth: 400,
          width: '100%',
          mx: 2,
          textAlign: 'center',
          borderRadius: 2,
          position: 'relative',
        }}
      >
        {isReconnect && onCancel && (
          <IconButton
            onClick={onCancel}
            sx={{ position: 'absolute', top: 8, right: 8 }}
            aria-label="Cancel"
          >
            <CloseIcon />
          </IconButton>
        )}

        <Typography variant="h4" component="h1" gutterBottom sx={{ fontWeight: 600 }}>
          {isReconnect ? 'Reconnect Gmail' : 'Mail Organizer'}
        </Typography>
        
        <Typography variant="body1" color="text.secondary" sx={{ mb: 4 }}>
          {isReconnect 
            ? 'Your Gmail connection has expired. Please sign in again to continue syncing your emails.'
            : 'Sign in with your Google account to access and organize your Gmail'
          }
        </Typography>

        {error && (
          <Alert severity="error" sx={{ mb: 3, textAlign: 'left' }}>
            {error}
          </Alert>
        )}

        <Button
          variant="contained"
          size="large"
          startIcon={<GoogleIcon />}
          onClick={login}
          sx={{
            py: 1.5,
            px: 4,
            textTransform: 'none',
            fontSize: '1rem',
            fontWeight: 500,
            bgcolor: '#4285f4',
            '&:hover': {
              bgcolor: '#357abd',
            },
          }}
        >
          {isReconnect ? 'Reconnect with Google' : 'Sign in with Google'}
        </Button>

        <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 4 }}>
          {isReconnect 
            ? 'This will refresh your Gmail access permissions.'
            : 'This application requires read-only access to your Gmail to organize and classify your emails.'
          }
        </Typography>
      </Paper>
    </Box>
  );
};

export default LoginPage;
