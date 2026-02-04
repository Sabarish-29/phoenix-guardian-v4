-- ═══════════════════════════════════════════════════════════════════════════════
-- PHOENIX GUARDIAN - ATTACKER INTELLIGENCE DATABASE SCHEMA
-- ═══════════════════════════════════════════════════════════════════════════════
-- 
-- This schema stores:
-- 1. Legal honeytokens deployed by the deception system
-- 2. Attacker fingerprints collected from beacon triggers
-- 3. Honeytoken interactions (views, downloads, exfiltration attempts)
-- 4. Attack campaigns for coordinated threat detection
--
-- Legal Compliance:
-- - All honeytokens use ONLY legal identifiers
-- - MRN range: 900000-999999 (hospital-internal only)
-- - Phone: 555-01XX (FCC reserved for fiction)
-- - NO SSN fields (never stored)
--
-- Created: 2026-01-31
-- Version: 1.0.0
-- ═══════════════════════════════════════════════════════════════════════════════

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ═══════════════════════════════════════════════════════════════════════════════
-- TABLE: honeytokens
-- Stores deployed legal honeytokens (fake patient records)
-- ═══════════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS honeytokens (
    -- Primary identifier
    honeytoken_id VARCHAR(64) PRIMARY KEY,
    
    -- Patient data (all fictional - legal compliance)
    mrn VARCHAR(20) NOT NULL,
    name VARCHAR(100) NOT NULL,
    age INTEGER NOT NULL CHECK (age >= 0 AND age <= 150),
    gender CHAR(1) NOT NULL CHECK (gender IN ('M', 'F')),
    
    -- Contact information (legal: FCC reserved phone, non-routable email)
    phone VARCHAR(20) NOT NULL,
    email VARCHAR(100) NOT NULL,
    address VARCHAR(200) NOT NULL,
    city VARCHAR(100) NOT NULL,
    state VARCHAR(2) NOT NULL,
    zip_code VARCHAR(10) NOT NULL,
    
    -- Medical data (conditions, medications, allergies as JSONB)
    medical_data JSONB NOT NULL DEFAULT '{}',
    
    -- Deployment metadata
    attack_type VARCHAR(50) NOT NULL DEFAULT 'unknown',
    deployment_timestamp TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    deployment_strategy VARCHAR(30) NOT NULL DEFAULT 'IMMEDIATE',
    session_id VARCHAR(100),
    attacker_ip VARCHAR(45),  -- Supports IPv6
    
    -- Beacon tracking
    beacon_url TEXT,
    beacon_triggered BOOLEAN NOT NULL DEFAULT FALSE,
    trigger_count INTEGER NOT NULL DEFAULT 0,
    
    -- Audit timestamps
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    
    -- Legal compliance constraints
    -- MRN must be in honeytoken range (900000-999999)
    CONSTRAINT valid_mrn_format CHECK (mrn ~ '^MRN-9[0-9]{5}$'),
    
    -- Phone must be FCC-reserved fiction range (555-01XX)
    CONSTRAINT valid_phone_format CHECK (phone ~ '^555-01[0-9]{2}$'),
    
    -- Email must use non-routable .internal domain
    CONSTRAINT valid_email_domain CHECK (email LIKE '%.internal')
);

-- Indexes for honeytokens
CREATE INDEX IF NOT EXISTS idx_honeytokens_mrn ON honeytokens(mrn);
CREATE INDEX IF NOT EXISTS idx_honeytokens_attack_type ON honeytokens(attack_type);
CREATE INDEX IF NOT EXISTS idx_honeytokens_deployment_timestamp ON honeytokens(deployment_timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_honeytokens_session_id ON honeytokens(session_id);
CREATE INDEX IF NOT EXISTS idx_honeytokens_beacon_triggered ON honeytokens(beacon_triggered) WHERE beacon_triggered = TRUE;

-- ═══════════════════════════════════════════════════════════════════════════════
-- TABLE: attacker_fingerprints
-- Stores browser/network fingerprints of attackers who triggered honeytokens
-- ═══════════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS attacker_fingerprints (
    -- Primary identifier
    fingerprint_id VARCHAR(64) PRIMARY KEY,
    
    -- Foreign key to triggered honeytoken
    honeytoken_id VARCHAR(64) REFERENCES honeytokens(honeytoken_id) ON DELETE CASCADE,
    
    -- Network attribution
    ip_address VARCHAR(45) NOT NULL,  -- Supports IPv6
    ip_country VARCHAR(2),
    ip_region VARCHAR(100),
    ip_city VARCHAR(100),
    ip_latitude DECIMAL(10, 7),
    ip_longitude DECIMAL(10, 7),
    ip_isp VARCHAR(200),
    ip_organization VARCHAR(200),
    ip_asn INTEGER,  -- Autonomous System Number
    reverse_dns VARCHAR(255),
    
    -- Browser attribution
    user_agent TEXT,
    browser_fingerprint VARCHAR(64),  -- SHA-256 hash of browser characteristics
    canvas_fingerprint TEXT,  -- Canvas rendering signature
    webgl_vendor VARCHAR(100),
    webgl_renderer VARCHAR(100),
    
    -- System attribution
    screen_resolution VARCHAR(20),
    color_depth INTEGER,
    platform VARCHAR(50),
    language VARCHAR(20),
    timezone VARCHAR(50),
    installed_fonts TEXT[],  -- Array of detected fonts
    plugins TEXT[],  -- Array of browser plugins
    
    -- Behavioral attribution (JSONB for flexibility)
    typing_patterns JSONB DEFAULT '{}',
    mouse_movements JSONB DEFAULT '{}',
    scroll_behavior JSONB DEFAULT '{}',
    
    -- Timing information
    first_interaction TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    beacon_trigger_time TIMESTAMP WITH TIME ZONE,
    session_duration_seconds FLOAT,
    
    -- Context
    referrer TEXT,
    entry_point TEXT,
    attack_type VARCHAR(50),
    
    -- Threat intelligence flags
    is_tor_exit_node BOOLEAN DEFAULT FALSE,
    is_known_vpn BOOLEAN DEFAULT FALSE,
    is_datacenter_ip BOOLEAN DEFAULT FALSE,
    threat_score INTEGER DEFAULT 0 CHECK (threat_score >= 0 AND threat_score <= 100),
    
    -- Audit timestamps
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Indexes for attacker_fingerprints
CREATE INDEX IF NOT EXISTS idx_fingerprints_ip_address ON attacker_fingerprints(ip_address);
CREATE INDEX IF NOT EXISTS idx_fingerprints_browser_fingerprint ON attacker_fingerprints(browser_fingerprint);
CREATE INDEX IF NOT EXISTS idx_fingerprints_attack_type ON attacker_fingerprints(attack_type);
CREATE INDEX IF NOT EXISTS idx_fingerprints_first_interaction ON attacker_fingerprints(first_interaction DESC);
CREATE INDEX IF NOT EXISTS idx_fingerprints_ip_country ON attacker_fingerprints(ip_country);
CREATE INDEX IF NOT EXISTS idx_fingerprints_ip_asn ON attacker_fingerprints(ip_asn);
CREATE INDEX IF NOT EXISTS idx_fingerprints_honeytoken_id ON attacker_fingerprints(honeytoken_id);
CREATE INDEX IF NOT EXISTS idx_fingerprints_threat_score ON attacker_fingerprints(threat_score DESC);

-- ═══════════════════════════════════════════════════════════════════════════════
-- TABLE: honeytoken_interactions
-- Logs every interaction with a honeytoken (view, download, copy, exfiltrate)
-- ═══════════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS honeytoken_interactions (
    -- Primary identifier (auto-increment)
    interaction_id SERIAL PRIMARY KEY,
    
    -- Foreign keys
    honeytoken_id VARCHAR(64) NOT NULL REFERENCES honeytokens(honeytoken_id) ON DELETE CASCADE,
    fingerprint_id VARCHAR(64) REFERENCES attacker_fingerprints(fingerprint_id) ON DELETE SET NULL,
    
    -- Interaction details
    interaction_type VARCHAR(20) NOT NULL,
    interaction_timestamp TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    
    -- Network context
    ip_address VARCHAR(45),
    user_agent TEXT,
    session_id VARCHAR(100),
    
    -- Raw beacon data (full payload for forensic analysis)
    raw_data JSONB DEFAULT '{}',
    
    -- Audit
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    
    -- Constraint: valid interaction types
    CONSTRAINT valid_interaction_type CHECK (
        interaction_type IN ('view', 'download', 'copy', 'exfiltrate', 'beacon_trigger')
    )
);

-- Indexes for honeytoken_interactions
CREATE INDEX IF NOT EXISTS idx_interactions_honeytoken_id ON honeytoken_interactions(honeytoken_id);
CREATE INDEX IF NOT EXISTS idx_interactions_fingerprint_id ON honeytoken_interactions(fingerprint_id);
CREATE INDEX IF NOT EXISTS idx_interactions_timestamp ON honeytoken_interactions(interaction_timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_interactions_type ON honeytoken_interactions(interaction_type);
CREATE INDEX IF NOT EXISTS idx_interactions_ip_address ON honeytoken_interactions(ip_address);

-- ═══════════════════════════════════════════════════════════════════════════════
-- TABLE: attack_campaigns
-- Tracks coordinated attack campaigns (multiple attackers, same infrastructure)
-- ═══════════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS attack_campaigns (
    -- Primary identifier
    campaign_id VARCHAR(64) PRIMARY KEY,
    
    -- Campaign metadata
    campaign_name VARCHAR(200) NOT NULL,
    description TEXT,
    
    -- Related fingerprints (array of IDs)
    fingerprint_ids VARCHAR(64)[] DEFAULT '{}',
    
    -- Timeline
    first_seen TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    last_seen TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    
    -- Coordination indicators
    shared_asn INTEGER,
    shared_ip_range CIDR,  -- Common IP range (e.g., 203.0.113.0/24)
    similar_browser_fps VARCHAR(64)[],  -- Browser fingerprints with high similarity
    temporal_clustering JSONB DEFAULT '{}',  -- Timing patterns
    
    -- Assessment
    severity VARCHAR(10) NOT NULL DEFAULT 'medium',
    status VARCHAR(20) NOT NULL DEFAULT 'active',
    notes TEXT,
    
    -- Audit timestamps
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT valid_severity CHECK (severity IN ('low', 'medium', 'high', 'critical')),
    CONSTRAINT valid_status CHECK (status IN ('active', 'mitigated', 'closed'))
);

-- Indexes for attack_campaigns
CREATE INDEX IF NOT EXISTS idx_campaigns_status ON attack_campaigns(status);
CREATE INDEX IF NOT EXISTS idx_campaigns_severity ON attack_campaigns(severity);
CREATE INDEX IF NOT EXISTS idx_campaigns_first_seen ON attack_campaigns(first_seen DESC);
CREATE INDEX IF NOT EXISTS idx_campaigns_shared_asn ON attack_campaigns(shared_asn);

-- ═══════════════════════════════════════════════════════════════════════════════
-- TRIGGERS: Auto-update updated_at timestamps
-- ═══════════════════════════════════════════════════════════════════════════════

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply trigger to all tables with updated_at
DROP TRIGGER IF EXISTS update_honeytokens_updated_at ON honeytokens;
CREATE TRIGGER update_honeytokens_updated_at
    BEFORE UPDATE ON honeytokens
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_fingerprints_updated_at ON attacker_fingerprints;
CREATE TRIGGER update_fingerprints_updated_at
    BEFORE UPDATE ON attacker_fingerprints
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_campaigns_updated_at ON attack_campaigns;
CREATE TRIGGER update_campaigns_updated_at
    BEFORE UPDATE ON attack_campaigns
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ═══════════════════════════════════════════════════════════════════════════════
-- VIEWS: Common queries for dashboards and reporting
-- ═══════════════════════════════════════════════════════════════════════════════

-- View: Recent attacks (last 7 days)
CREATE OR REPLACE VIEW recent_attacks AS
SELECT 
    f.fingerprint_id,
    f.ip_address,
    f.ip_country,
    f.attack_type,
    f.threat_score,
    f.first_interaction,
    h.honeytoken_id,
    h.mrn,
    h.deployment_strategy
FROM attacker_fingerprints f
LEFT JOIN honeytokens h ON f.honeytoken_id = h.honeytoken_id
WHERE f.first_interaction >= NOW() - INTERVAL '7 days'
ORDER BY f.first_interaction DESC;

-- View: High threat attackers (score >= 70)
CREATE OR REPLACE VIEW high_threat_attackers AS
SELECT 
    fingerprint_id,
    ip_address,
    ip_country,
    ip_city,
    ip_isp,
    ip_asn,
    attack_type,
    threat_score,
    is_tor_exit_node,
    is_known_vpn,
    is_datacenter_ip,
    first_interaction
FROM attacker_fingerprints
WHERE threat_score >= 70
ORDER BY threat_score DESC, first_interaction DESC;

-- View: Honeytoken effectiveness metrics
CREATE OR REPLACE VIEW honeytoken_effectiveness AS
SELECT 
    h.honeytoken_id,
    h.attack_type,
    h.deployment_strategy,
    h.deployment_timestamp,
    h.beacon_triggered,
    h.trigger_count,
    COUNT(DISTINCT f.fingerprint_id) AS unique_attackers,
    COUNT(DISTINCT f.ip_address) AS unique_ips,
    COUNT(i.interaction_id) AS total_interactions
FROM honeytokens h
LEFT JOIN attacker_fingerprints f ON h.honeytoken_id = f.honeytoken_id
LEFT JOIN honeytoken_interactions i ON h.honeytoken_id = i.honeytoken_id
GROUP BY h.honeytoken_id
ORDER BY h.trigger_count DESC;

-- ═══════════════════════════════════════════════════════════════════════════════
-- SAMPLE QUERIES (for reference)
-- ═══════════════════════════════════════════════════════════════════════════════

-- Query: Find repeat attackers (same IP, multiple attempts in 30 days)
-- SELECT 
--     ip_address,
--     COUNT(*) AS attempt_count,
--     ARRAY_AGG(DISTINCT attack_type) AS attack_types,
--     ARRAY_AGG(fingerprint_id) AS fingerprint_ids,
--     MIN(first_interaction) AS first_seen,
--     MAX(first_interaction) AS last_seen
-- FROM attacker_fingerprints
-- WHERE first_interaction >= NOW() - INTERVAL '30 days'
-- GROUP BY ip_address
-- HAVING COUNT(*) > 1
-- ORDER BY attempt_count DESC;

-- Query: Attack distribution by country
-- SELECT 
--     ip_country,
--     COUNT(*) AS attack_count,
--     ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) AS percentage
-- FROM attacker_fingerprints
-- WHERE ip_country IS NOT NULL
-- GROUP BY ip_country
-- ORDER BY attack_count DESC
-- LIMIT 20;

-- Query: Most common attack types
-- SELECT 
--     attack_type,
--     COUNT(*) AS count,
--     ROUND(AVG(threat_score), 2) AS avg_threat_score
-- FROM attacker_fingerprints
-- WHERE attack_type IS NOT NULL
-- GROUP BY attack_type
-- ORDER BY count DESC;

-- Query: Coordinated attacks (same ASN, multiple IPs, similar timing)
-- SELECT 
--     ip_asn,
--     COUNT(DISTINCT ip_address) AS unique_ips,
--     COUNT(*) AS total_attempts,
--     ARRAY_AGG(DISTINCT ip_address) AS ip_addresses,
--     MIN(first_interaction) AS first_seen,
--     MAX(first_interaction) AS last_seen
-- FROM attacker_fingerprints
-- WHERE ip_asn IS NOT NULL
--   AND first_interaction >= NOW() - INTERVAL '24 hours'
-- GROUP BY ip_asn
-- HAVING COUNT(DISTINCT ip_address) >= 3
-- ORDER BY unique_ips DESC;

-- Query: Browser fingerprint matches (potential VPN hopping)
-- SELECT 
--     browser_fingerprint,
--     COUNT(DISTINCT ip_address) AS unique_ips,
--     ARRAY_AGG(DISTINCT ip_address) AS ip_addresses,
--     ARRAY_AGG(fingerprint_id) AS fingerprint_ids
-- FROM attacker_fingerprints
-- WHERE browser_fingerprint IS NOT NULL
-- GROUP BY browser_fingerprint
-- HAVING COUNT(DISTINCT ip_address) > 1
-- ORDER BY unique_ips DESC;

-- ═══════════════════════════════════════════════════════════════════════════════
-- END OF SCHEMA
-- ═══════════════════════════════════════════════════════════════════════════════
