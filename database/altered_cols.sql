ALTER TABLE documents ADD COLUMN IF NOT EXISTS agent_id INT REFERENCES users(id);

CREATE INDEX idx_docs_agent ON documents(agent_id);

-- 1. Remove existing default (SERIAL sequence)
ALTER TABLE users
ALTER COLUMN id DROP DEFAULT;

-- 2. Add identity
ALTER TABLE users
ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY;