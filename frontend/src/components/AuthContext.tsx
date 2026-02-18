/* eslint-disable react-refresh/only-export-components */
import { createContext, useContext, useState, useEffect, useCallback, ReactNode } from 'react';
import { getApiUrl } from '../utils/api';

interface AuthState {
  authenticated: boolean;
  email: string | null;
  gmailConnected: boolean;
  loading: boolean;
  error: string | null;
  showReconnect: boolean;
}

interface AuthContextType extends AuthState {
  login: () => void;
  logout: () => Promise<void>;
  checkAuth: () => Promise<void>;
  reconnectGmail: () => void;
  cancelReconnect: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

interface AuthProviderProps {
  children: ReactNode;
}

export const AuthProvider = ({ children }: AuthProviderProps) => {
  const [state, setState] = useState<AuthState>({
    authenticated: false,
    email: null,
    gmailConnected: false,
    loading: true,
    error: null,
    showReconnect: false,
  });

  const checkAuth = useCallback(async () => {
    try {
      setState((prev: AuthState) => ({ ...prev, loading: true, error: null }));
      
      const response = await fetch('/api/auth/status', {
        credentials: 'include', // Include cookies
      });
      
      if (!response.ok) {
        throw new Error('Failed to check auth status');
      }
      
      const data = await response.json();
      
      setState((prev: AuthState) => ({
        ...prev,
        authenticated: data.authenticated,
        email: data.email,
        gmailConnected: data.gmail_connected ?? false,
        loading: false,
        error: null,
      }));
    } catch (err) {
      console.error('Auth check failed:', err);
      setState({
        authenticated: false,
        email: null,
        gmailConnected: false,
        loading: false,
        error: err instanceof Error ? err.message : 'Authentication check failed',
        showReconnect: false,
      });
    }
  }, []);

  // Check auth status on mount and when URL changes (for OAuth callback)
  useEffect(() => {
    checkAuth();
    
    // Check for auth error in URL (from OAuth callback)
    const params = new URLSearchParams(window.location.search);
    const authError = params.get('auth_error');
    if (authError) {
      setState((prev: AuthState) => ({ ...prev, error: decodeURIComponent(authError) }));
      // Clean up URL
      window.history.replaceState({}, '', window.location.pathname);
    }
  }, [checkAuth]);

  const login = useCallback((force: boolean = false) => {
    // Redirect to backend OAuth endpoint
    // Backend will redirect back to the frontend base URL after successful auth
    const url = force ? getApiUrl('/api/auth/login?force=true') : getApiUrl('/api/auth/login');
    window.location.href = url;
  }, []);

  const reconnectGmail = useCallback(() => {
    // Show the login page for Gmail reconnection
    setState((prev: AuthState) => ({ ...prev, showReconnect: true }));
  }, []);

  const cancelReconnect = useCallback(() => {
    // Hide the reconnect login page
    setState((prev: AuthState) => ({ ...prev, showReconnect: false }));
  }, []);

  const logout = useCallback(async () => {
    try {
      await fetch('/api/auth/logout', {
        method: 'POST',
        credentials: 'include',
      });
      
      setState({
        authenticated: false,
        email: null,
        gmailConnected: false,
        loading: false,
        error: null,
        showReconnect: false,
      });
    } catch (err) {
      console.error('Logout failed:', err);
      // Still clear local state even if server request fails
      setState({
        authenticated: false,
        email: null,
        gmailConnected: false,
        loading: false,
        error: err instanceof Error ? err.message : 'Logout failed',
        showReconnect: false,
      });
    }
  }, []);

  const value: AuthContextType = {
    ...state,
    login: () => login(state.showReconnect),  // Use force=true when reconnecting
    logout,
    checkAuth,
    reconnectGmail,
    cancelReconnect,
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
};

export default AuthProvider;
