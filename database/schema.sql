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
-- 5. PROPERTIES (STRUCTURED FILTERING WITH PRICE VISIBILITY)
-- =========================
CREATE TABLE properties (
    id SERIAL PRIMARY KEY,
    title VARCHAR(255),
    location VARCHAR(150),
    actual_price NUMERIC,
    quoted_price NUMERIC,
    bedrooms INT,
    bathrooms INT,
    area_sqft NUMERIC,
    property_type VARCHAR(50), -- residential / commercial / land
    document_id INT REFERENCES documents(id),
    agent_id INT REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =========================
-- 6. AGENT-PROPERTY ASSIGNMENTS (RBAC)
-- =========================
CREATE TABLE agent_properties (
    id SERIAL PRIMARY KEY,
    agent_id INT REFERENCES users(id) ON DELETE CASCADE,
    property_id INT REFERENCES properties(id) ON DELETE CASCADE,
    assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(agent_id, property_id)
);

-- =========================
-- 7. USER PREFERENCES
-- =========================
CREATE TABLE user_preferences (
    id SERIAL PRIMARY KEY,
    user_id INT UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    location_preference VARCHAR(255),
    budget_min NUMERIC,
    budget_max NUMERIC,
    property_type VARCHAR(50),
    preferred_features TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =========================
-- 8. INVESTMENT ANALYSIS RESULTS
-- =========================
CREATE TABLE investment_analysis (
    id SERIAL PRIMARY KEY,
    user_id INT REFERENCES users(id) ON DELETE CASCADE,
    property_id INT REFERENCES properties(id) ON DELETE CASCADE,
    investment_location VARCHAR(255),
    profit_potential NUMERIC,
    risk_level VARCHAR(20), -- low / medium / high
    roi_percentage NUMERIC,
    rental_yield_percentage NUMERIC,
    market_appreciation_rate NUMERIC,
    analysis_details JSONB, -- store detailed features and metrics
    analysis_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =========================
-- INDEXES (PERFORMANCE)
-- =========================
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_properties_location ON properties(location);
CREATE INDEX idx_properties_agent ON properties(agent_id);
CREATE INDEX idx_chat_user ON chat_sessions(user_id);
CREATE INDEX idx_ai_user ON ai_responses(user_id);
CREATE INDEX idx_documents_role ON documents(access_role);
CREATE INDEX idx_agent_properties ON agent_properties(agent_id);
CREATE INDEX idx_user_preferences ON user_preferences(user_id);
CREATE INDEX idx_investment_user ON investment_analysis(user_id);
CREATE INDEX idx_investment_property ON investment_analysis(property_id);