"""
Attacker Intelligence Database - PostgreSQL Storage Layer.

This module provides persistent storage for:
- Legal honeytokens (fake patient records)
- Attacker fingerprints (browser/network attribution)
- Honeytoken interactions (views, downloads, exfiltration attempts)
- Attack campaigns (coordinated threat detection)

All data is stored with connection pooling for high-concurrency environments.

Legal Compliance:
- NO SSN fields (never stored)
- MRN range: 900000-999999 (hospital-internal only)
- Phone: 555-01XX (FCC reserved for fiction)
- Email: .internal domain (non-routable)

Example:
    from phoenix_guardian.security.attacker_intelligence_db import AttackerIntelligenceDB
    
    db = AttackerIntelligenceDB("postgresql://user:pass@localhost/phoenix")
    
    # Store honeytoken
    db.store_honeytoken(honeytoken, deployment_metadata)
    
    # Find repeat attackers
    attackers = db.find_repeat_attackers(time_window_days=30)
"""

import json
import logging
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List, Tuple, Generator
from dataclasses import asdict

try:
    import psycopg2
    from psycopg2 import pool, sql
    from psycopg2.extras import RealDictCursor, Json
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False
    psycopg2 = None
    pool = None
    sql = None
    RealDictCursor = None
    Json = None

from phoenix_guardian.security.honeytoken_generator import (
    LegalHoneytoken,
    AttackerFingerprint
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# EXCEPTIONS
# ═══════════════════════════════════════════════════════════════════════════════

class DatabaseError(Exception):
    """Base exception for database errors."""
    pass


class ConnectionError(DatabaseError):
    """Raised when database connection fails."""
    pass


class QueryError(DatabaseError):
    """Raised when a query fails."""
    pass


class IntegrityError(DatabaseError):
    """Raised when data integrity is violated."""
    pass


# ═══════════════════════════════════════════════════════════════════════════════
# ATTACKER INTELLIGENCE DATABASE
# ═══════════════════════════════════════════════════════════════════════════════

class AttackerIntelligenceDB:
    """
    PostgreSQL-backed storage for attacker intelligence.
    
    Features:
    - Connection pooling (configurable size)
    - Thread-safe operations
    - Automatic reconnection on connection loss
    - Parameterized queries (SQL injection prevention)
    
    Attributes:
        pool: psycopg2 connection pool
        connection_string: Database connection URL
        pool_size: Maximum concurrent connections
        
    Example:
        db = AttackerIntelligenceDB(
            connection_string="postgresql://user:pass@localhost/phoenix",
            pool_size=10
        )
        
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM honeytokens")
    """
    
    def __init__(
        self,
        connection_string: str,
        pool_size: int = 10,
        use_mock: bool = False
    ):
        """
        Initialize the database connection pool.
        
        Args:
            connection_string: PostgreSQL connection URL
            pool_size: Maximum concurrent connections (default: 10)
            use_mock: If True, use mock database for testing
        """
        self.connection_string = connection_string
        self.pool_size = pool_size
        self.use_mock = use_mock
        self._pool = None
        
        # Mock storage for testing without real database
        self._mock_honeytokens: Dict[str, Dict] = {}
        self._mock_fingerprints: Dict[str, Dict] = {}
        self._mock_interactions: List[Dict] = []
        self._mock_campaigns: Dict[str, Dict] = {}
        self._mock_interaction_id = 0
        
        if not use_mock and PSYCOPG2_AVAILABLE:
            self._init_pool()
        
        logger.info(
            f"AttackerIntelligenceDB initialized "
            f"(pool_size={pool_size}, mock={use_mock})"
        )
    
    def _init_pool(self):
        """Initialize the connection pool."""
        if not PSYCOPG2_AVAILABLE:
            raise ConnectionError("psycopg2 is not installed")
        
        try:
            self._pool = pool.SimpleConnectionPool(
                minconn=1,
                maxconn=self.pool_size,
                dsn=self.connection_string
            )
            logger.info("Database connection pool initialized")
        except Exception as e:
            logger.error(f"Failed to initialize connection pool: {e}")
            raise ConnectionError(f"Failed to connect to database: {e}")
    
    @contextmanager
    def get_connection(self) -> Generator:
        """
        Get a database connection from the pool.
        
        Yields:
            psycopg2 connection object
            
        Auto-commits on success, rolls back on error.
        """
        if self.use_mock:
            # Yield a mock connection for testing
            yield MockConnection()
            return
        
        if not self._pool:
            raise ConnectionError("Connection pool not initialized")
        
        conn = None
        try:
            conn = self._pool.getconn()
            yield conn
            conn.commit()
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Database error: {e}")
            raise QueryError(f"Query failed: {e}")
        finally:
            if conn:
                self._pool.putconn(conn)
    
    def execute_sql(self, sql_script: str) -> None:
        """
        Execute a SQL script (e.g., schema creation).
        
        Args:
            sql_script: SQL statements to execute
        """
        if self.use_mock:
            logger.info("Mock: Executed SQL script")
            return
        
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(sql_script)
        
        logger.info("Executed SQL script successfully")
    
    def close(self) -> None:
        """Close all database connections."""
        if self._pool:
            self._pool.closeall()
            logger.info("Database connections closed")
    
    # ═══════════════════════════════════════════════════════════════════════════
    # WRITE OPERATIONS
    # ═══════════════════════════════════════════════════════════════════════════
    
    def store_honeytoken(
        self,
        honeytoken: LegalHoneytoken,
        deployment_metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Store a honeytoken in the database.
        
        Args:
            honeytoken: LegalHoneytoken object to store
            deployment_metadata: Additional deployment info (strategy, session_id)
            
        Returns:
            True on success, False if already exists
        """
        metadata = deployment_metadata or {}
        
        # Prepare medical data as JSONB
        medical_data = {
            'conditions': honeytoken.conditions,
            'medications': honeytoken.medications,
            'allergies': honeytoken.allergies
        }
        
        if self.use_mock:
            # Mock storage
            if honeytoken.honeytoken_id in self._mock_honeytokens:
                return False
            
            self._mock_honeytokens[honeytoken.honeytoken_id] = {
                'honeytoken_id': honeytoken.honeytoken_id,
                'mrn': honeytoken.mrn,
                'name': honeytoken.name,
                'age': honeytoken.age,
                'gender': honeytoken.gender,
                'phone': honeytoken.phone,
                'email': honeytoken.email,
                'address': honeytoken.address,
                'city': honeytoken.city,
                'state': honeytoken.state,
                'zip_code': honeytoken.zip_code,
                'medical_data': medical_data,
                'attack_type': honeytoken.attack_type,
                'deployment_timestamp': honeytoken.deployment_timestamp,
                'deployment_strategy': metadata.get('deployment_strategy', 'IMMEDIATE'),
                'session_id': metadata.get('session_id') or honeytoken.session_id,
                'attacker_ip': honeytoken.attacker_ip,
                'beacon_url': honeytoken.beacon_url,
                'beacon_triggered': honeytoken.status == 'triggered',
                'trigger_count': honeytoken.trigger_count,
                'created_at': datetime.now(timezone.utc),
                'updated_at': datetime.now(timezone.utc)
            }
            
            logger.info(f"Stored honeytoken: {honeytoken.honeytoken_id}")
            return True
        
        # Real database storage
        query = """
            INSERT INTO honeytokens (
                honeytoken_id, mrn, name, age, gender,
                phone, email, address, city, state, zip_code,
                medical_data, attack_type, deployment_timestamp,
                deployment_strategy, session_id, attacker_ip,
                beacon_url, beacon_triggered, trigger_count
            ) VALUES (
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s
            )
            ON CONFLICT (honeytoken_id) DO NOTHING
            RETURNING honeytoken_id
        """
        
        params = (
            honeytoken.honeytoken_id,
            honeytoken.mrn,
            honeytoken.name,
            honeytoken.age,
            honeytoken.gender,
            honeytoken.phone,
            honeytoken.email,
            honeytoken.address,
            honeytoken.city,
            honeytoken.state,
            honeytoken.zip_code,
            Json(medical_data),
            honeytoken.attack_type,
            honeytoken.deployment_timestamp,
            metadata.get('deployment_strategy', 'IMMEDIATE'),
            honeytoken.session_id,
            honeytoken.attacker_ip,
            honeytoken.beacon_url,
            honeytoken.status == 'triggered',
            honeytoken.trigger_count
        )
        
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(query, params)
                    result = cursor.fetchone()
                    
                    if result:
                        logger.info(f"Stored honeytoken: {honeytoken.honeytoken_id}")
                        return True
                    else:
                        logger.warning(f"Honeytoken already exists: {honeytoken.honeytoken_id}")
                        return False
        except Exception as e:
            logger.error(f"Failed to store honeytoken: {e}")
            raise QueryError(f"Failed to store honeytoken: {e}")
    
    def store_fingerprint(self, fingerprint: AttackerFingerprint) -> bool:
        """
        Store an attacker fingerprint in the database.
        
        Args:
            fingerprint: AttackerFingerprint object to store
            
        Returns:
            True on success
        """
        if self.use_mock:
            # Mock storage
            self._mock_fingerprints[fingerprint.fingerprint_id] = {
                'fingerprint_id': fingerprint.fingerprint_id,
                'honeytoken_id': fingerprint.honeytoken_id,
                'ip_address': fingerprint.ip_address,
                'ip_country': fingerprint.ip_geolocation.get('country') if fingerprint.ip_geolocation else None,
                'ip_region': fingerprint.ip_geolocation.get('region') if fingerprint.ip_geolocation else None,
                'ip_city': fingerprint.ip_geolocation.get('city') if fingerprint.ip_geolocation else None,
                'ip_latitude': fingerprint.ip_geolocation.get('lat') if fingerprint.ip_geolocation else None,
                'ip_longitude': fingerprint.ip_geolocation.get('lon') if fingerprint.ip_geolocation else None,
                'ip_isp': fingerprint.ip_geolocation.get('isp') if fingerprint.ip_geolocation else None,
                'ip_organization': fingerprint.ip_geolocation.get('org') if fingerprint.ip_geolocation else None,
                'ip_asn': fingerprint.ip_geolocation.get('asn') if fingerprint.ip_geolocation else None,
                'user_agent': fingerprint.user_agent,
                'browser_fingerprint': fingerprint.compute_hash(),
                'canvas_fingerprint': fingerprint.canvas_fingerprint,
                'webgl_vendor': fingerprint.webgl_vendor,
                'webgl_renderer': fingerprint.webgl_renderer,
                'screen_resolution': fingerprint.screen_resolution,
                'color_depth': fingerprint.color_depth,
                'platform': fingerprint.platform,
                'language': fingerprint.language,
                'timezone': fingerprint.timezone,
                'installed_fonts': fingerprint.installed_fonts,
                'plugins': fingerprint.plugins,
                'typing_patterns': {},
                'mouse_movements': {},
                'scroll_behavior': {},
                'first_interaction': fingerprint.timestamp,
                'beacon_trigger_time': fingerprint.timestamp,
                'is_tor_exit_node': False,
                'is_known_vpn': False,
                'is_datacenter_ip': False,
                'threat_score': 0,
                'attack_type': None,
                'created_at': datetime.now(timezone.utc),
                'updated_at': datetime.now(timezone.utc)
            }
            
            logger.info(f"Stored fingerprint: {fingerprint.fingerprint_id}")
            return True
        
        # Real database storage
        geo = fingerprint.ip_geolocation or {}
        
        query = """
            INSERT INTO attacker_fingerprints (
                fingerprint_id, honeytoken_id, ip_address,
                ip_country, ip_region, ip_city,
                ip_latitude, ip_longitude, ip_isp, ip_organization, ip_asn,
                user_agent, browser_fingerprint, canvas_fingerprint,
                webgl_vendor, webgl_renderer,
                screen_resolution, color_depth, platform, language, timezone,
                installed_fonts, plugins,
                typing_patterns, mouse_movements, scroll_behavior,
                first_interaction, beacon_trigger_time,
                is_tor_exit_node, is_known_vpn, is_datacenter_ip, threat_score
            ) VALUES (
                %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, %s,
                %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s,
                %s, %s, %s,
                %s, %s,
                %s, %s, %s, %s
            )
            ON CONFLICT (fingerprint_id) DO UPDATE SET
                updated_at = NOW()
            RETURNING fingerprint_id
        """
        
        params = (
            fingerprint.fingerprint_id,
            fingerprint.honeytoken_id,
            fingerprint.ip_address,
            geo.get('country'),
            geo.get('region'),
            geo.get('city'),
            geo.get('lat'),
            geo.get('lon'),
            geo.get('isp'),
            geo.get('org'),
            geo.get('asn'),
            fingerprint.user_agent,
            fingerprint.compute_hash(),
            fingerprint.canvas_fingerprint,
            fingerprint.webgl_vendor,
            fingerprint.webgl_renderer,
            fingerprint.screen_resolution,
            fingerprint.color_depth,
            fingerprint.platform,
            fingerprint.language,
            fingerprint.timezone,
            fingerprint.installed_fonts,
            fingerprint.plugins,
            Json({}),  # typing_patterns
            Json({}),  # mouse_movements
            Json({}),  # scroll_behavior
            fingerprint.timestamp,
            fingerprint.timestamp,
            False,  # is_tor_exit_node
            False,  # is_known_vpn
            False,  # is_datacenter_ip
            0       # threat_score
        )
        
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(query, params)
                    logger.info(f"Stored fingerprint: {fingerprint.fingerprint_id}")
                    return True
        except Exception as e:
            logger.error(f"Failed to store fingerprint: {e}")
            raise QueryError(f"Failed to store fingerprint: {e}")
    
    def record_interaction(
        self,
        honeytoken_id: str,
        interaction_data: Dict[str, Any]
    ) -> int:
        """
        Record an interaction with a honeytoken.
        
        Args:
            honeytoken_id: ID of the honeytoken that was accessed
            interaction_data: {
                'interaction_type': 'view' | 'download' | 'copy' | 'exfiltrate' | 'beacon_trigger',
                'ip_address': str,
                'user_agent': str,
                'session_id': str,
                'fingerprint_id': Optional[str],
                'raw_data': Dict (full beacon payload)
            }
            
        Returns:
            interaction_id (auto-generated)
        """
        if self.use_mock:
            self._mock_interaction_id += 1
            interaction = {
                'interaction_id': self._mock_interaction_id,
                'honeytoken_id': honeytoken_id,
                'fingerprint_id': interaction_data.get('fingerprint_id'),
                'interaction_type': interaction_data.get('interaction_type', 'view'),
                'interaction_timestamp': datetime.now(timezone.utc),
                'ip_address': interaction_data.get('ip_address'),
                'user_agent': interaction_data.get('user_agent'),
                'session_id': interaction_data.get('session_id'),
                'raw_data': interaction_data.get('raw_data', {}),
                'created_at': datetime.now(timezone.utc)
            }
            self._mock_interactions.append(interaction)
            
            # Update honeytoken trigger status
            if honeytoken_id in self._mock_honeytokens:
                self._mock_honeytokens[honeytoken_id]['beacon_triggered'] = True
                self._mock_honeytokens[honeytoken_id]['trigger_count'] += 1
            
            logger.info(f"Recorded interaction {self._mock_interaction_id} for {honeytoken_id}")
            return self._mock_interaction_id
        
        # Real database storage
        query = """
            INSERT INTO honeytoken_interactions (
                honeytoken_id, fingerprint_id, interaction_type,
                ip_address, user_agent, session_id, raw_data
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING interaction_id
        """
        
        update_honeytoken = """
            UPDATE honeytokens 
            SET beacon_triggered = TRUE, 
                trigger_count = trigger_count + 1,
                updated_at = NOW()
            WHERE honeytoken_id = %s
        """
        
        params = (
            honeytoken_id,
            interaction_data.get('fingerprint_id'),
            interaction_data.get('interaction_type', 'view'),
            interaction_data.get('ip_address'),
            interaction_data.get('user_agent'),
            interaction_data.get('session_id'),
            Json(interaction_data.get('raw_data', {}))
        )
        
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(query, params)
                    result = cursor.fetchone()
                    interaction_id = result[0]
                    
                    # Update honeytoken
                    cursor.execute(update_honeytoken, (honeytoken_id,))
                    
                    logger.info(f"Recorded interaction {interaction_id} for {honeytoken_id}")
                    return interaction_id
        except Exception as e:
            logger.error(f"Failed to record interaction: {e}")
            raise QueryError(f"Failed to record interaction: {e}")
    
    # ═══════════════════════════════════════════════════════════════════════════
    # READ OPERATIONS
    # ═══════════════════════════════════════════════════════════════════════════
    
    def get_fingerprint(self, fingerprint_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a fingerprint by ID.
        
        Args:
            fingerprint_id: Unique fingerprint identifier
            
        Returns:
            Fingerprint data as dict, or None if not found
        """
        if self.use_mock:
            return self._mock_fingerprints.get(fingerprint_id)
        
        query = """
            SELECT * FROM attacker_fingerprints
            WHERE fingerprint_id = %s
        """
        
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute(query, (fingerprint_id,))
                    result = cursor.fetchone()
                    return dict(result) if result else None
        except Exception as e:
            logger.error(f"Failed to get fingerprint: {e}")
            raise QueryError(f"Failed to get fingerprint: {e}")
    
    def get_fingerprints_by_ip(self, ip_address: str) -> List[Dict[str, Any]]:
        """
        Find all fingerprints from a specific IP address.
        
        Args:
            ip_address: IP address to search for
            
        Returns:
            List of fingerprint records
        """
        if self.use_mock:
            return [
                fp for fp in self._mock_fingerprints.values()
                if fp.get('ip_address') == ip_address
            ]
        
        query = """
            SELECT * FROM attacker_fingerprints
            WHERE ip_address = %s
            ORDER BY first_interaction DESC
        """
        
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute(query, (ip_address,))
                    return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Failed to get fingerprints by IP: {e}")
            raise QueryError(f"Failed to get fingerprints by IP: {e}")
    
    def get_fingerprints_by_browser(
        self,
        browser_fingerprint: str
    ) -> List[Dict[str, Any]]:
        """
        Find all fingerprints with matching browser fingerprint.
        
        Useful for detecting VPN hopping (same browser, different IPs).
        
        Args:
            browser_fingerprint: SHA-256 hash of browser characteristics
            
        Returns:
            List of fingerprint records
        """
        if self.use_mock:
            return [
                fp for fp in self._mock_fingerprints.values()
                if fp.get('browser_fingerprint') == browser_fingerprint
            ]
        
        query = """
            SELECT * FROM attacker_fingerprints
            WHERE browser_fingerprint = %s
            ORDER BY first_interaction DESC
        """
        
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute(query, (browser_fingerprint,))
                    return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Failed to get fingerprints by browser: {e}")
            raise QueryError(f"Failed to get fingerprints by browser: {e}")
    
    def get_honeytoken(self, honeytoken_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a honeytoken by ID.
        
        Args:
            honeytoken_id: Unique honeytoken identifier
            
        Returns:
            Honeytoken data as dict, or None if not found
        """
        if self.use_mock:
            return self._mock_honeytokens.get(honeytoken_id)
        
        query = """
            SELECT * FROM honeytokens
            WHERE honeytoken_id = %s
        """
        
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute(query, (honeytoken_id,))
                    result = cursor.fetchone()
                    return dict(result) if result else None
        except Exception as e:
            logger.error(f"Failed to get honeytoken: {e}")
            raise QueryError(f"Failed to get honeytoken: {e}")
    
    def get_honeytokens_by_session(self, session_id: str) -> List[Dict[str, Any]]:
        """
        Retrieve all honeytokens for a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            List of honeytoken data dicts
        """
        if self.use_mock:
            return [
                ht for ht in self._mock_honeytokens.values()
                if ht.get('session_id') == session_id
            ]
        
        query = """
            SELECT * FROM honeytokens
            WHERE session_id = %s
            ORDER BY deployment_timestamp
        """
        
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute(query, (session_id,))
                    return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Failed to get honeytokens by session: {e}")
            raise QueryError(f"Failed to get honeytokens by session: {e}")
    
    def get_fingerprints_by_honeytoken(self, honeytoken_id: str) -> List[Dict[str, Any]]:
        """
        Retrieve all fingerprints associated with a honeytoken.
        
        Args:
            honeytoken_id: Honeytoken identifier
            
        Returns:
            List of fingerprint data dicts
        """
        if self.use_mock:
            return [
                fp for fp in self._mock_fingerprints.values()
                if fp.get('honeytoken_id') == honeytoken_id
            ]
        
        query = """
            SELECT * FROM attacker_fingerprints
            WHERE honeytoken_id = %s
            ORDER BY first_interaction
        """
        
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute(query, (honeytoken_id,))
                    return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Failed to get fingerprints by honeytoken: {e}")
            raise QueryError(f"Failed to get fingerprints by honeytoken: {e}")
    
    def get_interactions_by_session(self, session_id: str) -> List[Dict[str, Any]]:
        """
        Retrieve all interactions for a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            List of interaction data dicts
        """
        if self.use_mock:
            # Get honeytokens for this session
            session_hts = self.get_honeytokens_by_session(session_id)
            ht_ids = {ht.get('honeytoken_id') for ht in session_hts}
            
            # Return interactions for those honeytokens
            return [
                interaction for interaction in self._mock_interactions
                if interaction.get('honeytoken_id') in ht_ids
            ]
        
        query = """
            SELECT i.* FROM honeytoken_interactions i
            JOIN honeytokens h ON i.honeytoken_id = h.honeytoken_id
            WHERE h.session_id = %s
            ORDER BY i.interaction_timestamp
        """
        
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute(query, (session_id,))
                    return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Failed to get interactions by session: {e}")
            raise QueryError(f"Failed to get interactions by session: {e}")
    
    # ═══════════════════════════════════════════════════════════════════════════
    # THREAT INTELLIGENCE QUERIES
    # ═══════════════════════════════════════════════════════════════════════════
    
    def find_repeat_attackers(
        self,
        time_window_days: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Find repeat attackers (same IP, multiple attempts).
        
        Args:
            time_window_days: Look back period in days
            
        Returns:
            List of repeat attacker records:
            [
                {
                    'ip_address': str,
                    'attempt_count': int,
                    'attack_types': List[str],
                    'fingerprint_ids': List[str],
                    'first_seen': datetime,
                    'last_seen': datetime
                }
            ]
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=time_window_days)
        
        if self.use_mock:
            # Group by IP
            ip_groups: Dict[str, List[Dict]] = {}
            for fp in self._mock_fingerprints.values():
                ip = fp.get('ip_address')
                if ip:
                    if ip not in ip_groups:
                        ip_groups[ip] = []
                    ip_groups[ip].append(fp)
            
            # Filter to repeats
            results = []
            for ip, fps in ip_groups.items():
                if len(fps) > 1:
                    results.append({
                        'ip_address': ip,
                        'attempt_count': len(fps),
                        'attack_types': list(set(fp.get('attack_type') for fp in fps if fp.get('attack_type'))),
                        'fingerprint_ids': [fp['fingerprint_id'] for fp in fps],
                        'first_seen': min(fp.get('first_interaction', cutoff) for fp in fps),
                        'last_seen': max(fp.get('first_interaction', cutoff) for fp in fps)
                    })
            
            return sorted(results, key=lambda x: x['attempt_count'], reverse=True)
        
        query = """
            SELECT 
                ip_address,
                COUNT(*) AS attempt_count,
                ARRAY_AGG(DISTINCT attack_type) FILTER (WHERE attack_type IS NOT NULL) AS attack_types,
                ARRAY_AGG(fingerprint_id) AS fingerprint_ids,
                MIN(first_interaction) AS first_seen,
                MAX(first_interaction) AS last_seen
            FROM attacker_fingerprints
            WHERE first_interaction >= %s
            GROUP BY ip_address
            HAVING COUNT(*) > 1
            ORDER BY attempt_count DESC
        """
        
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute(query, (cutoff,))
                    return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Failed to find repeat attackers: {e}")
            raise QueryError(f"Failed to find repeat attackers: {e}")
    
    def get_attack_patterns_by_country(self) -> Dict[str, int]:
        """
        Get attack distribution by country.
        
        Returns:
            Dictionary mapping country codes to attack counts
        """
        if self.use_mock:
            country_counts: Dict[str, int] = {}
            for fp in self._mock_fingerprints.values():
                country = fp.get('ip_country')
                if country:
                    country_counts[country] = country_counts.get(country, 0) + 1
            return country_counts
        
        query = """
            SELECT ip_country, COUNT(*) AS attack_count
            FROM attacker_fingerprints
            WHERE ip_country IS NOT NULL
            GROUP BY ip_country
            ORDER BY attack_count DESC
        """
        
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(query)
                    return {row[0]: row[1] for row in cursor.fetchall()}
        except Exception as e:
            logger.error(f"Failed to get attack patterns by country: {e}")
            raise QueryError(f"Failed to get attack patterns by country: {e}")
    
    def get_most_common_attack_types(self) -> List[Tuple[str, int]]:
        """
        Get most common attack types.
        
        Returns:
            List of (attack_type, count) tuples, sorted by count descending
        """
        if self.use_mock:
            type_counts: Dict[str, int] = {}
            for fp in self._mock_fingerprints.values():
                atype = fp.get('attack_type')
                if atype:
                    type_counts[atype] = type_counts.get(atype, 0) + 1
            return sorted(type_counts.items(), key=lambda x: x[1], reverse=True)
        
        query = """
            SELECT attack_type, COUNT(*) AS count
            FROM attacker_fingerprints
            WHERE attack_type IS NOT NULL
            GROUP BY attack_type
            ORDER BY count DESC
        """
        
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(query)
                    return [(row[0], row[1]) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Failed to get attack types: {e}")
            raise QueryError(f"Failed to get attack types: {e}")
    
    def get_fingerprints_by_asn(self, asn: int) -> List[Dict[str, Any]]:
        """
        Find all fingerprints from a specific ASN.
        
        Args:
            asn: Autonomous System Number
            
        Returns:
            List of fingerprint records
        """
        if self.use_mock:
            return [
                fp for fp in self._mock_fingerprints.values()
                if fp.get('ip_asn') == asn
            ]
        
        query = """
            SELECT * FROM attacker_fingerprints
            WHERE ip_asn = %s
            ORDER BY first_interaction DESC
        """
        
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute(query, (asn,))
                    return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Failed to get fingerprints by ASN: {e}")
            raise QueryError(f"Failed to get fingerprints by ASN: {e}")
    
    def get_recent_fingerprints(
        self,
        hours: int = 24
    ) -> List[Dict[str, Any]]:
        """
        Get fingerprints from the last N hours.
        
        Args:
            hours: Lookback period in hours
            
        Returns:
            List of recent fingerprint records
        """
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        
        if self.use_mock:
            return [
                fp for fp in self._mock_fingerprints.values()
                if fp.get('first_interaction', datetime.min.replace(tzinfo=timezone.utc)) >= cutoff
            ]
        
        query = """
            SELECT * FROM attacker_fingerprints
            WHERE first_interaction >= %s
            ORDER BY first_interaction DESC
        """
        
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute(query, (cutoff,))
                    return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Failed to get recent fingerprints: {e}")
            raise QueryError(f"Failed to get recent fingerprints: {e}")
    
    def update_threat_score(
        self,
        fingerprint_id: str,
        threat_score: int
    ) -> bool:
        """
        Update the threat score for a fingerprint.
        
        Args:
            fingerprint_id: Fingerprint to update
            threat_score: New threat score (0-100)
            
        Returns:
            True on success
        """
        threat_score = max(0, min(100, threat_score))  # Clamp to 0-100
        
        if self.use_mock:
            if fingerprint_id in self._mock_fingerprints:
                self._mock_fingerprints[fingerprint_id]['threat_score'] = threat_score
                return True
            return False
        
        query = """
            UPDATE attacker_fingerprints
            SET threat_score = %s, updated_at = NOW()
            WHERE fingerprint_id = %s
        """
        
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(query, (threat_score, fingerprint_id))
                    return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Failed to update threat score: {e}")
            raise QueryError(f"Failed to update threat score: {e}")
    
    def generate_threat_intelligence_report(self, days: int = 7) -> str:
        """
        Generate a threat intelligence summary report.
        
        Args:
            days: Lookback period in days
            
        Returns:
            Formatted ASCII report string
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        
        # Gather statistics
        if self.use_mock:
            total_attacks = len([
                fp for fp in self._mock_fingerprints.values()
                if fp.get('first_interaction', datetime.min.replace(tzinfo=timezone.utc)) >= cutoff
            ])
            unique_ips = len(set(
                fp.get('ip_address') for fp in self._mock_fingerprints.values()
                if fp.get('first_interaction', datetime.min.replace(tzinfo=timezone.utc)) >= cutoff
            ))
            country_counts = self.get_attack_patterns_by_country()
            attack_types = self.get_most_common_attack_types()
        else:
            # Real database queries
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    # Total attacks
                    cursor.execute(
                        "SELECT COUNT(*) FROM attacker_fingerprints WHERE first_interaction >= %s",
                        (cutoff,)
                    )
                    total_attacks = cursor.fetchone()[0]
                    
                    # Unique IPs
                    cursor.execute(
                        "SELECT COUNT(DISTINCT ip_address) FROM attacker_fingerprints WHERE first_interaction >= %s",
                        (cutoff,)
                    )
                    unique_ips = cursor.fetchone()[0]
            
            country_counts = self.get_attack_patterns_by_country()
            attack_types = self.get_most_common_attack_types()
        
        # Format report
        report = []
        report.append("╔" + "═" * 58 + "╗")
        report.append("║" + " " * 10 + "THREAT INTELLIGENCE REPORT" + " " * 22 + "║")
        report.append("╠" + "═" * 58 + "╣")
        report.append(f"║ Report Period: Last {days} days".ljust(59) + "║")
        report.append(f"║ Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}".ljust(59) + "║")
        report.append("╠" + "═" * 58 + "╣")
        report.append("║ SUMMARY".ljust(59) + "║")
        report.append("╟" + "─" * 58 + "╢")
        report.append(f"║   Total Attacks: {total_attacks}".ljust(59) + "║")
        report.append(f"║   Unique IP Addresses: {unique_ips}".ljust(59) + "║")
        report.append("╠" + "═" * 58 + "╣")
        report.append("║ TOP COUNTRIES".ljust(59) + "║")
        report.append("╟" + "─" * 58 + "╢")
        
        for country, count in sorted(country_counts.items(), key=lambda x: x[1], reverse=True)[:5]:
            report.append(f"║   {country}: {count} attacks".ljust(59) + "║")
        
        report.append("╠" + "═" * 58 + "╣")
        report.append("║ TOP ATTACK TYPES".ljust(59) + "║")
        report.append("╟" + "─" * 58 + "╢")
        
        for attack_type, count in attack_types[:5]:
            report.append(f"║   {attack_type}: {count}".ljust(59) + "║")
        
        report.append("╚" + "═" * 58 + "╝")
        
        return "\n".join(report)


# ═══════════════════════════════════════════════════════════════════════════════
# MOCK CONNECTION (for testing without PostgreSQL)
# ═══════════════════════════════════════════════════════════════════════════════

class MockConnection:
    """Mock database connection for testing."""
    
    def __enter__(self):
        return self
    
    def __exit__(self, *args):
        pass
    
    def cursor(self, cursor_factory=None):
        return MockCursor()
    
    def commit(self):
        pass
    
    def rollback(self):
        pass


class MockCursor:
    """Mock database cursor for testing."""
    
    def __enter__(self):
        return self
    
    def __exit__(self, *args):
        pass
    
    def execute(self, query, params=None):
        pass
    
    def fetchone(self):
        return None
    
    def fetchall(self):
        return []
