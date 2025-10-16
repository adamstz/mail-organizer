import React from 'react';
import { ThemeProvider, CssBaseline, Container, AppBar, Toolbar, Typography } from '@mui/material';
import { createTheme } from '@mui/material/styles';
import EmailList from './components/EmailList';

const theme = createTheme({
  palette: {
    mode: 'light',
    primary: {
      main: '#1976d2',
    },
  },
});

const App: React.FC = () => {
  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <AppBar position="static">
        <Toolbar>
          <Typography variant="h6" component="div">
            Organize Mail
          </Typography>
        </Toolbar>
      </AppBar>
      <Container 
        maxWidth={false} 
        disableGutters 
        sx={{ 
          height: '100vh',
          width: '100vw',
          bgcolor: 'grey.100',
          display: 'flex',
          flexDirection: 'column',
          p: 0
        }}
      >
        <EmailList />
      </Container>
    </ThemeProvider>
  );
};

export default App;