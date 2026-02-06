/**
 * Get the API base URL for making requests or navigation.
 * 
 * In development, this uses VITE_API_URL or defaults to http://localhost:8000.
 * In production (when served from same origin), this returns an empty string
 * so relative paths work correctly.
 */
export function getApiBaseUrl(): string {
  // Check for explicit API URL override
  const envApiUrl = import.meta.env.VITE_API_URL;
  if (envApiUrl) {
    return envApiUrl;
  }
  
  // In development mode, default to localhost:8000
  if (import.meta.env.DEV) {
    return 'http://localhost:8000';
  }
  
  // In production, assume API is served from same origin
  return '';
}

/**
 * Get the full URL for an API endpoint.
 * Use this for navigation (window.location.href) where Vite proxy doesn't apply.
 */
export function getApiUrl(path: string): string {
  const baseUrl = getApiBaseUrl();
  // Ensure path starts with /
  const normalizedPath = path.startsWith('/') ? path : `/${path}`;
  return `${baseUrl}${normalizedPath}`;
}
