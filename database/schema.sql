-- =========================
-- 1. USERS
-- =========================
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100),
    email VARCHAR(150) UNIQUE,
    password_hash TEXT,
    role VARCHAR(20) CHECK (role IN ('admin','agent','buyer')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =========================
-- 2. CHAT SESSIONS
-- =========================
CREATE TABLE chat_sessions (
    id SERIAL PRIMARY KEY,
    user_id INT REFERENCES users(id) ON DELETE CASCADE,
    session_title VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =========================
-- 3. AI RESPONSES (CHAT HISTORY)
-- =========================
CREATE TABLE ai_responses (
    id SERIAL PRIMARY KEY,
    session_id INT REFERENCES chat_sessions(id) ON DELETE CASCADE,
    user_id INT REFERENCES users(id) ON DELETE CASCADE,
    query TEXT,
    response TEXT,
    tool_used VARCHAR(50), -- retrieval / summary / comparison / market / investment
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =========================
-- 4. DOCUMENTS (RAG + ACCESS CONTROL)
-- =========================
CREATE TABLE documents (
    id SERIAL PRIMARY KEY,
    title VARCHAR(255),
    file_path TEXT,
    doc_type VARCHAR(50), -- property / market / legal
    uploaded_by INT REFERENCES users(id),
    access_role VARCHAR(20), -- admin / agent / buyer
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =========================
-- 5. PROPERTIES (STRUCTURED FILTERING)
-- =========================
CREATE TABLE properties (
    id SERIAL PRIMARY KEY,
    title VARCHAR(255),
    location VARCHAR(150),
    price NUMERIC,
    bedrooms INT,
    document_id INT REFERENCES documents(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =========================
-- INDEXES (OPTIONAL BUT GOOD)
-- =========================
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_properties_location ON properties(location);
CREATE INDEX idx_properties_price ON properties(price);
CREATE INDEX idx_chat_user ON chat_sessions(user_id);
CREATE INDEX idx_ai_user ON ai_responses(user_id);
CREATE INDEX idx_documents_role ON documents(access_role);