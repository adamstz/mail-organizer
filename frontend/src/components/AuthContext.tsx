/* eslint-disable react-refresh/only-export-components */
import { createContext, useContext, useState, useEffect, useCallback, ReactNode } from 'react';
import { getApiUrl } from '../utils/api';
import { logger } from '../utils/logger';

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
      logger.info('[OAuth] Checking auth status...');
      setState((prev: AuthState) => ({ ...prev, loading: true, error: null }));

      const response = await fetch('/api/auth/status', {
        credentials: 'include', // Include cookies
      });

      logger.debug(`[OAuth] Auth status response: ${response.status}`);
      if (!response.ok) {
        throw new Error('Failed to check auth status');
      }

      const data = await response.json();
      logger.info(`[OAuth] Auth status: authenticated=${data.authenticated}, email=${data.email || 'none'}, gmail_connected=${data.gmail_connected}`);

      setState((prev: AuthState) => ({
        ...prev,
        authenticated: data.authenticated,
        email: data.email,
        gmailConnected: data.gmail_connected ?? false,
        loading: false,
        error: null,
      }));
    } catch (err) {
      logger.error(`[OAuth] Auth check failed: ${err instanceof Error ? err.message : String(err)}`);
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
    logger.info('[OAuth] AuthProvider mounted — checking auth status');
    checkAuth();

    // Check for auth error in URL (from OAuth callback)
    const params = new URLSearchParams(window.location.search);
    const authError = params.get('auth_error');
    if (authError) {
      logger.error(`[OAuth] Auth error from callback URL: ${decodeURIComponent(authError)}`);
      setState((prev: AuthState) => ({ ...prev, error: decodeURIComponent(authError) }));
      // Clean up URL
      window.history.replaceState({}, '', window.location.pathname);
    }
  }, [checkAuth]);

  const login = useCallback((force: boolean = false) => {
    // Redirect to backend OAuth endpoint
    // Backend will redirect back to the frontend base URL after successful auth
    const url = force ? getApiUrl('/api/auth/login?force=true') : getApiUrl('/api/auth/login');
    logger.info(`[OAuth] Initiating login — redirecting to ${url} (force=${force})`);
    window.location.href = url;
  }, []);

  const reconnectGmail = useCallback(() => {
    // Show the login page for Gmail reconnection
    logger.info('[OAuth] Gmail reconnect requested');
    setState((prev: AuthState) => ({ ...prev, showReconnect: true }));
  }, []);

  const cancelReconnect = useCallback(() => {
    // Hide the reconnect login page
    logger.info('[OAuth] Gmail reconnect cancelled');
    setState((prev: AuthState) => ({ ...prev, showReconnect: false }));
  }, []);

  const logout = useCallback(async () => {
    logger.info('[OAuth] Logging out...');

    // Clear local state immediately so the UI transitions without waiting for the network
    setState({
      authenticated: false,
      email: null,
      gmailConnected: false,
      loading: false,
      error: null,
      showReconnect: false,
    });

    // Fire server-side cookie clear in the background (non-blocking)
    fetch('/api/auth/logout', { method: 'POST', credentials: 'include' })
      .then(() => logger.info('[OAuth] Server-side logout complete — cookie cleared'))
      .catch((err) => logger.error(`[OAuth] Server-side logout failed: ${err instanceof Error ? err.message : String(err)}`));
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
