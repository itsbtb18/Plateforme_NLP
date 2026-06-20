-- ============================================
-- DATABASE INITIALIZATION SQL
-- ============================================

-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Grant necessary permissions
GRANT ALL PRIVILEGES ON DATABASE nlp_platform TO nlp_admin;

-- Add missing columns ONLY if tables already exist
-- (Tables are created by Django migrations, not here)
DO $$
BEGIN
    -- chat_sessions columns
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'chat_sessions') THEN
        ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS title VARCHAR(255);
        ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS preferred_language VARCHAR(10);
        ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE;
        ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS summary TEXT;
        ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS pdf_context TEXT;
        ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS pdf_filename VARCHAR(255);
    END IF;

    -- chat_messages columns
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'chat_messages') THEN
        ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS token_count INTEGER;
    END IF;
END $$;