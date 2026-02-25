-- ============================================
-- DATABASE INITIALIZATION SQL
-- ============================================
-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Grant necessary permissions
GRANT ALL PRIVILEGES ON DATABASE nlp_platform TO nlp_admin;

-- Add missing columns to chat tables (idempotent)
ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS title VARCHAR(255);
ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS preferred_language VARCHAR(10);
ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE;
ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS summary TEXT;
ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS token_count INTEGER;
