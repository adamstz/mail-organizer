-- Migration: Add OAuth tokens table for storing Gmail authentication credentials
-- Uses PostgreSQL's pgcrypto extension for column-level encryption

-- Enable pgcrypto extension for encryption functions
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Create oauth_tokens table
-- The email column serves as the identity (no separate users table needed for single-user)
CREATE TABLE IF NOT EXISTS oauth_tokens (
    email TEXT PRIMARY KEY,
    -- Tokens are stored encrypted using pgp_sym_encrypt
    -- Decrypt with: pgp_sym_decrypt(access_token::bytea, 'secret_key')
    access_token BYTEA NOT NULL,
    refresh_token BYTEA NOT NULL,
    token_expiry TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Index for quick lookups
CREATE INDEX IF NOT EXISTS idx_oauth_tokens_email ON oauth_tokens(email);

-- Function to auto-update updated_at timestamp
CREATE OR REPLACE FUNCTION update_oauth_tokens_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to auto-update updated_at on row changes
DROP TRIGGER IF EXISTS oauth_tokens_updated_at ON oauth_tokens;
CREATE TRIGGER oauth_tokens_updated_at
    BEFORE UPDATE ON oauth_tokens
    FOR EACH ROW
    EXECUTE FUNCTION update_oauth_tokens_updated_at();

-- Comment on table for documentation
COMMENT ON TABLE oauth_tokens IS 'Stores encrypted OAuth tokens for Gmail API access. Email column is the user identity.';
COMMENT ON COLUMN oauth_tokens.access_token IS 'PGP-encrypted access token for Gmail API calls';
COMMENT ON COLUMN oauth_tokens.refresh_token IS 'PGP-encrypted refresh token for obtaining new access tokens';
