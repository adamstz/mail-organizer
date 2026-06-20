import React, { useEffect, useState } from 'react';
import {
  Dialog, DialogTitle, DialogContent, DialogActions,
  Button, FormControl, InputLabel, Select, MenuItem,
  TextField, Alert, CircularProgress, Typography, Box, Chip,
} from '@mui/material';
import { CheckCircle as CheckIcon } from '@mui/icons-material';

interface LLMSettingsProps {
  open: boolean;
  onClose: () => void;
  onSaved: (provider: string, model: string) => void;
}

interface Settings {
  provider: string;
  model: string;
  has_api_key: boolean;
  supported_providers: string[];
}

const PROVIDER_LABELS: Record<string, string> = {
  ollama: 'Ollama (local)',
  openai: 'OpenAI',
  anthropic: 'Anthropic',
  rules: 'No AI (keyword rules)',
};

const OPENAI_MODELS = [
  'gpt-5.5',
  'gpt-5.4',
  'gpt-5.4-mini',
  'gpt-5.4-nano',
  'gpt-4.1',
  'gpt-4.1-mini',
  'gpt-4.1-nano',
  'gpt-4o',
  'gpt-4o-mini',
];
const ANTHROPIC_MODELS = [
  'claude-fable-5',
  'claude-opus-4-8',
  'claude-sonnet-4-6',
  'claude-haiku-4-5-20251001',
  'claude-opus-4-7',
  'claude-opus-4-6',
  'claude-sonnet-4-5-20250929',
];

const LLMSettings: React.FC<LLMSettingsProps> = ({ open, onClose, onSaved }) => {
  const [settings, setSettings] = useState<Settings | null>(null);
  const [provider, setProvider] = useState('ollama');
  const [model, setModel] = useState('');
  const [apiKey, setApiKey] = useState('');
  const [ollamaModels, setOllamaModels] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (!open) return;
    setLoading(true);
    setError(null);
    setSaved(false);
    fetch('/api/settings/llm')
      .then(r => r.json())
      .then((data: Settings) => {
        setSettings(data);
        setProvider(data.provider);
        setModel(data.model);
        setApiKey('');
      })
      .catch(() => setError('Failed to load settings'))
      .finally(() => setLoading(false));
  }, [open]);

  useEffect(() => {
    if (!open || provider !== 'ollama') return;
    fetch('/models')
      .then(r => r.json())
      .then(data => setOllamaModels((data.models || []).map((m: { name: string }) => m.name)))
      .catch(() => setOllamaModels([]));
  }, [open, provider]);

  const needsApiKey = provider === 'openai' || provider === 'anthropic';
  const staticModels = provider === 'openai' ? OPENAI_MODELS : provider === 'anthropic' ? ANTHROPIC_MODELS : [];

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    try {
      const res = await fetch('/api/settings/llm', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ provider, model, api_key: apiKey }),
      });
      if (!res.ok) {
        const d = await res.json();
        throw new Error(d.detail || 'Save failed');
      }
      setSaved(true);
      onSaved(provider, model);
      setTimeout(onClose, 800);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Save failed');
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>LLM Provider Settings</DialogTitle>
      <DialogContent>
        {loading && <Box sx={{ display: 'flex', justifyContent: 'center', py: 3 }}><CircularProgress /></Box>}

        {!loading && (
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2.5, pt: 1 }}>
            {error && <Alert severity="error">{error}</Alert>}
            {saved && <Alert severity="success" icon={<CheckIcon />}>Settings saved</Alert>}

            <FormControl fullWidth>
              <InputLabel>Provider</InputLabel>
              <Select value={provider} label="Provider" onChange={e => { setProvider(e.target.value); setModel(''); }}>
                {(settings?.supported_providers || ['ollama', 'openai', 'anthropic', 'rules']).map(p => (
                  <MenuItem key={p} value={p}>{PROVIDER_LABELS[p] ?? p}</MenuItem>
                ))}
              </Select>
            </FormControl>

            {needsApiKey && (
              <TextField
                label="API Key"
                type="password"
                value={apiKey}
                onChange={e => setApiKey(e.target.value)}
                fullWidth
                placeholder={settings?.has_api_key ? '(key already saved — leave blank to keep)' : 'Enter API key'}
                helperText={settings?.has_api_key && !apiKey ? 'A key is already stored.' : undefined}
              />
            )}

            {provider === 'ollama' && (
              ollamaModels.length > 0 ? (
                <FormControl fullWidth>
                  <InputLabel>Model</InputLabel>
                  <Select value={model} label="Model" onChange={e => setModel(e.target.value)}>
                    {ollamaModels.map(m => <MenuItem key={m} value={m}>{m}</MenuItem>)}
                  </Select>
                </FormControl>
              ) : (
                <Alert severity="warning">
                  No Ollama models found. Make sure Ollama is running on the host and has at least one model pulled.
                </Alert>
              )
            )}

            {staticModels.length > 0 && (
              <FormControl fullWidth>
                <InputLabel>Model</InputLabel>
                <Select value={model} label="Model" onChange={e => setModel(e.target.value)}>
                  {staticModels.map(m => <MenuItem key={m} value={m}>{m}</MenuItem>)}
                </Select>
              </FormControl>
            )}

            {provider === 'rules' && (
              <Typography variant="body2" color="text.secondary">
                Keyword-based classification — no API key or model needed. Use for testing or when no LLM is available.
              </Typography>
            )}

            {provider !== 'rules' && (
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <Typography variant="caption" color="text.secondary">Current:</Typography>
                <Chip size="small" label={`${PROVIDER_LABELS[settings?.provider ?? ''] ?? settings?.provider} / ${settings?.model || 'auto'}`} />
              </Box>
            )}
          </Box>
        )}
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} disabled={saving}>Cancel</Button>
        <Button
          variant="contained"
          onClick={handleSave}
          disabled={saving || loading || (needsApiKey && !apiKey && !settings?.has_api_key)}
        >
          {saving ? <CircularProgress size={18} sx={{ mr: 1 }} /> : null}
          Save
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default LLMSettings;
