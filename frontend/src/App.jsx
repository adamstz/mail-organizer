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

function App() {
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
      <Container maxWidth={false}>
        <EmailList />
      </Container>
    </ThemeProvider>
  )
}

export default App
