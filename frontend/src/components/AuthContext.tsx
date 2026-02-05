/* eslint-disable react-refresh/only-export-components */
import { createContext, useContext, useState, useEffect, useCallback, ReactNode } from 'react';

interface AuthState {
  authenticated: boolean;
  email: string | null;
  loading: boolean;
  error: string | null;
}

interface AuthContextType extends AuthState {
  login: () => void;
  logout: () => Promise<void>;
  checkAuth: () => Promise<void>;
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
    loading: true,
    error: null,
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
      
      setState({
        authenticated: data.authenticated,
        email: data.email,
        loading: false,
        error: null,
      });
    } catch (err) {
      console.error('Auth check failed:', err);
      setState({
        authenticated: false,
        email: null,
        loading: false,
        error: err instanceof Error ? err.message : 'Authentication check failed',
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

  const login = useCallback(() => {
    // Redirect to backend OAuth endpoint
    // Backend will redirect back to the frontend base URL after successful auth
    window.location.href = '/api/auth/login';
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
        loading: false,
        error: null,
      });
    } catch (err) {
      console.error('Logout failed:', err);
      // Still clear local state even if server request fails
      setState({
        authenticated: false,
        email: null,
        loading: false,
        error: err instanceof Error ? err.message : 'Logout failed',
      });
    }
  }, []);

  const value: AuthContextType = {
    ...state,
    login,
    logout,
    checkAuth,
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
};

export default AuthProvider;
