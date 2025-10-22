import React, { useState } from 'react';
import {
  List,
  ListItem,
  ListItemText,
  IconButton,
  Collapse,
  Paper,
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

import exampleEmails from '../test/exampleEmails';
import { useEffect } from 'react';

const getPriorityColor = (priority: Email['priority']): 'error' | 'warning' | 'success' | 'default' => {
  switch (priority.toLowerCase()) {
    case 'high':
      return 'error';
    case 'medium':
      return 'warning';
    case 'low':
      return 'success';
    default:
      return 'default';
  }
};

const EmailList: React.FC = () => {
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [emails, setEmails] = useState<Email[]>(exampleEmails);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      setLoading(true);
      try {
        const res = await fetch('/messages?limit=50');
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const ct = res.headers.get('content-type') || '';
        let data: any = null;
        if (ct.includes('application/json')) {
          data = await res.json();
        } else {
          // backend not available or returned HTML (e.g. index.html) — handle gracefully
          const text = await res.text();
          throw new Error('Unexpected response from server: ' + (text.slice(0, 200)));
        }
  // helper: extract best possible Date object from backend message dict
        const parseMessageDate = (m: any): Date | null => {
          // common fields from different serializers
          const maybeNumber = m.internalDate ?? m.internal_date ?? m['internalDate'] ?? m['internal_date'];
          if (maybeNumber) {
            const n = Number(maybeNumber);
            if (!Number.isNaN(n)) return new Date(n);
          }

          // fetched timestamps (ISO)
          const maybeFetched = m.fetchedAt ?? m.fetched_at ?? m['fetchedAt'] ?? m['fetched_at'];
          if (maybeFetched) {
            const d = new Date(maybeFetched);
            if (!Number.isNaN(d.getTime())) return d;
          }

          // headers (Date header)
          const headers = m.headers ?? m['headers'];
          if (headers) {
            const headerDate = headers.Date ?? headers.date ?? headers['Date'] ?? headers['date'];
            if (headerDate) {
              const d = new Date(headerDate);
              if (!Number.isNaN(d.getTime())) return d;
            }
          }

          return null;
        };

        const formatter = new Intl.DateTimeFormat(undefined, {
          year: 'numeric',
          month: 'short',
          day: 'numeric',
          hour: 'numeric',
          minute: '2-digit',
        });

        // Decode HTML entities and strip invisible/control characters
        const decodeHtml = (input: string): string => {
          if (!input) return '';
          try {
            const txt = document.createElement('textarea');
            txt.innerHTML = input;
            return txt.value;
          } catch {
            return input;
          }
        };

        const sanitizeText = (input: string): string => {
          if (!input) return '';
          // decode HTML entities first (e.g. &#39; -> ')
          let out = decodeHtml(input);
          // remove invisible / format / control characters (zero-width spaces, BOM, etc.)
          // Using Unicode property escape to remove all Other/format/control characters.
          try {
            out = out.replace(/\p{C}/gu, '');
          } catch {
            // Fallback: remove common invisible chars
            out = out.replace(/[\u200B\u200C\u200D\uFEFF\u2060]/g, '');
            out = out.replace(/[\x00-\x1F\x7F]/g, '');
          }
          return out;
        };

        // map backend message dict to Email type
        const mapped: Email[] = data.map((m: any, idx: number) => {
          const d = parseMessageDate(m);
          const displayDate = d ? formatter.format(d) : '';
          const rawSubject = m.subject ?? m['subject'] ?? 'No subject';
          const rawSummary = m.snippet ?? '';
          const rawBody = m.payload ? JSON.stringify(m.payload) : (m.raw ? m.raw : '');

          return {
            id: idx + 1,
            subject: sanitizeText(String(rawSubject)),
            date: displayDate,
            priority: 'Low',
            summary: sanitizeText(String(rawSummary)),
            body: sanitizeText(String(rawBody)),
          };
        });
        setEmails(mapped);
      } catch (err: any) {
        setError(String(err));
        setEmails(exampleEmails);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  const handleExpand = (id: number): void => {
    setExpandedId(expandedId === id ? null : id);
  };

  const handleDelete = (id: number): void => {
    setEmails(emails.filter(email => email.id !== id));
  };

  return (
    <Paper 
      elevation={0} 
      sx={{ 
        width: "100%", 
        flexGrow: 1,
        bgcolor: 'transparent',
        height: '100%',
        overflow: 'auto',
        p: { xs: 1, sm: 2, md: 3 },
        display: 'flex',
        flexDirection: 'column'
      }}
    >
      {/* show small status line for loading/error (keeps variables used for TS) */}
      <Box sx={{ mb: 1 }}>
        {loading && (
          <Typography variant="caption" color="text.secondary">Loading messages…</Typography>
        )}
        {error && (
          <Typography variant="caption" color="error">{error}</Typography>
        )}
      </Box>

      <List sx={{ 
        width: '100%',
        mx: 'auto',
        minWidth: '100%'
      }}>
        {emails.map((email) => (
          <React.Fragment key={email.id}>
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
                  onClick={() => handleExpand(email.id)}
                >
                  <ListItemText
                    primary={
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <Typography variant="subtitle1">{email.subject}</Typography>
                        <Chip
                          label={email.priority}
                          size="small"
                          color={getPriorityColor(email.priority)}
                        />
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
                    {expandedId === email.id ? (
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
                onClick={() => handleDelete(email.id)}
                sx={{ ml: 2 }}
              >
                <DeleteIcon />
              </IconButton>
            </ListItem>
            <Collapse in={expandedId === email.id} timeout="auto" unmountOnExit>
              <Box sx={{ p: 3, backgroundColor: 'grey.50' }}>
                <Typography variant="body1" whiteSpace="pre-line">
                  {email.body}
                </Typography>
              </Box>
            </Collapse>
          </React.Fragment>
        ))}
      </List>
    </Paper>
  );
};

export default EmailList;