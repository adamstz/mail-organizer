// Tests for the top-level App component.
//
// Verifies basic render behavior and that the main UI pieces are present:
// - header text 'Organize Mail' is rendered
// - the EmailList component (sample email text) appears in the DOM
//
// These are lightweight smoke tests to ensure the app shell mounts
// and integrates the EmailList component.
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import App from '../../App';
import exampleEmails from '../exampleEmails';

describe('App Component', () => {
  const fetchMock = vi.fn();
  const originalFetch = global.fetch;

  beforeEach(() => {
    global.fetch = fetchMock;
    fetchMock.mockReset();
    fetchMock.mockImplementation((url) => {
      const urlStr = url.toString();

      // Mock auth status - return authenticated
      if (urlStr.includes('/api/auth/status')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ authenticated: true, email: 'test@example.com' }),
        });
      }

      // Mock current model
      if (urlStr.includes('/api/current-model')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ model: 'test-model' }),
        });
      }

      // Mock messages endpoint
      if (urlStr.includes('/messages') && !urlStr.includes('/body')) {
        return Promise.resolve({
          ok: true,
          headers: { get: () => 'application/json' },
          json: () => Promise.resolve({ data: exampleEmails, total: exampleEmails.length }),
          text: () => Promise.resolve(JSON.stringify({ data: exampleEmails, total: exampleEmails.length })),
        });
      }

      // Mock frontend-log (ignore)
      if (urlStr.includes('/api/frontend-log')) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
      }

      // Default: return empty success
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({}),
      });
    });
  });

  afterEach(() => {
    global.fetch = originalFetch;
    vi.restoreAllMocks();
  });

  it('renders header with correct title', async () => {
    render(<App />);
    expect(await screen.findByText('Organize Mail')).toBeInTheDocument();
  });

  // Smoke test: verifies the EmailList component mounts and renders a
  // sample email from the fixture so integration between App and
  // EmailList is validated.
  it('renders email list component', async () => {
    render(<App />);
    expect(await screen.findByText('Project Update Meeting')).toBeInTheDocument();
  });
});