-- ============================================
-- DATABASE INITIALIZATION SQL
-- ============================================
-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Grant necessary permissions
GRANT ALL PRIVILEGES ON DATABASE nlp_platform TO nlp_admin;
