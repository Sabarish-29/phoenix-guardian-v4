"""
Phoenix Guardian SentinelQ Deception Pipeline.

Complete integration pipeline: Detection → Deception → Evidence → Alerting

This module provides end-to-end integration with SentinelQAgent for:
1. Attack detection
2. Intelligent honeytoken deployment
3. Attacker fingerprinting
4. Evidence collection
5. Real-time alerting

Day 75: Full System Integration
"""

import uuid
import socket
import logging
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Callable

from phoenix_guardian.security.honeytoken_generator import (
    HoneytokenGenerator,
    LegalHoneytoken,
    AttackerFingerprint,
    AttackType,
    HoneytokenStatus
)
from phoenix_guardian.security.deception_agent import (
    DeceptionAgent,
    DeceptionDecision,
    DeceptionStrategy,
    DeploymentTiming
)
from phoenix_guardian.security.attacker_intelligence_db import AttackerIntelligenceDB
from phoenix_guardian.security.evidence_packager import EvidencePackager
from phoenix_guardian.security.alerting import (
    RealTimeAlerting,
    SecurityAlert,
    AlertSeverity,
    AlertChannel
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# AUTO-EVIDENCE THRESHOLDS
# ═══════════════════════════════════════════════════════════════════════════════

# Number of honeytokens that must be triggered to auto-generate evidence package
AUTO_EVIDENCE_THRESHOLD = 3

# Alert escalation thresholds
ESCALATION_THRESHOLDS = {
    'honeytokens_per_hour': 3,      # 3+ honeytokens/hour → WARNING
    'data_exfiltration': 1,          # Any exfiltration → HIGH
    'repeat_ip_attempts': 3,         # 3+ from same IP → HIGH
    'coordinated_attack': 5,         # 5+ IPs from same ASN → CRITICAL
}


# ═══════════════════════════════════════════════════════════════════════════════
# SENTINELQ DECEPTION PIPELINE
# ═══════════════════════════════════════════════════════════════════════════════

class SentinelQDeceptionPipeline:
    """
    Complete integration pipeline: Detection → Deception → Evidence → Alerting.
    
    Workflow:
    1. SentinelQAgent detects attack
    2. DeceptionAgent decides deployment strategy
    3. Honeytokens injected into response
    4. User receives modified response
    5. If honeytoken accessed:
       a. ForensicBeacon triggers
       b. AttackerFingerprint created
       c. Evidence stored in DB
       d. Real-time alert sent
       e. Evidence package auto-generated (if threshold met)
    
    This is the main integration point that ties together all honeytoken
    system components for production deployment.
    """
    
    def __init__(
        self,
        deception_agent: Optional[DeceptionAgent] = None,
        db: Optional[AttackerIntelligenceDB] = None,
        evidence_packager: Optional[EvidencePackager] = None,
        alerting: Optional[RealTimeAlerting] = None,
        auto_evidence_threshold: int = AUTO_EVIDENCE_THRESHOLD
    ):
        """
        Initialize SentinelQ Deception Pipeline.
        
        Args:
            deception_agent: DeceptionAgent instance (creates default if None)
            db: AttackerIntelligenceDB instance (creates mock if None)
            evidence_packager: EvidencePackager instance (creates if None)
            alerting: RealTimeAlerting instance (creates if None)
            auto_evidence_threshold: Number of honeytokens to trigger auto-evidence
        """
        # Initialize components (create defaults if not provided)
        if deception_agent is None:
            generator = HoneytokenGenerator()
            deception_agent = DeceptionAgent(generator)
        
        if db is None:
            db = AttackerIntelligenceDB(
                connection_string="postgresql://localhost/phoenix",
                use_mock=True
            )
        
        self.deception_agent = deception_agent
        self.db = db
        
        # Initialize evidence packager with threat analyzer
        if evidence_packager is None:
            from phoenix_guardian.security.threat_intelligence import ThreatIntelligenceAnalyzer
            threat_analyzer = ThreatIntelligenceAnalyzer(db)
            evidence_packager = EvidencePackager(db, threat_analyzer)
        
        self.evidence_packager = evidence_packager
        
        # Initialize alerting
        if alerting is None:
            alerting = RealTimeAlerting()
        
        self.alerting = alerting
        
        # Configuration
        self.auto_evidence_threshold = auto_evidence_threshold
        
        # Track active sessions
        self.active_sessions: Dict[str, Dict[str, Any]] = {}
        
        # Callbacks for external integrations
        self._on_honeytoken_deployed: List[Callable] = []
        self._on_beacon_triggered: List[Callable] = []
        self._on_evidence_generated: List[Callable] = []
        
        logger.info("SentinelQDeceptionPipeline initialized")
    
    # ═══════════════════════════════════════════════════════════════════════════
    # MAIN QUERY PROCESSING PIPELINE
    # ═══════════════════════════════════════════════════════════════════════════
    
    def process_query(
        self,
        user_query: str,
        session_id: str,
        ip_address: str,
        user_agent: str,
        additional_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Complete query processing pipeline with deception.
        
        This is the main entry point for processing user queries through
        the deception pipeline.
        
        Args:
            user_query: Original user query
            session_id: Session identifier
            ip_address: User IP address
            user_agent: User agent string
            additional_context: Optional additional context
        
        Returns:
            Dictionary containing:
            - response: The response text (potentially with honeytokens)
            - is_attack: Whether an attack was detected
            - honeytokens_deployed: List of deployed honeytoken IDs
            - decision: DeceptionDecision if attack detected
        """
        result = {
            'response': '',
            'is_attack': False,
            'honeytokens_deployed': [],
            'decision': None,
            'attack_type': None
        }
        
        # Initialize session tracking
        if session_id not in self.active_sessions:
            self.active_sessions[session_id] = {
                'start_time': datetime.now(timezone.utc),
                'queries': 0,
                'honeytokens_triggered': [],
                'attack_detections': []
            }
        
        self.active_sessions[session_id]['queries'] += 1
        
        # 1. Run attack detection
        attack_result = self._detect_attack(user_query, session_id, ip_address)
        
        # 2. If no attack detected, return normal response
        if not attack_result.get('is_attack'):
            result['response'] = self._generate_normal_response(user_query)
            return result
        
        # 3. Attack detected - prepare for deception
        result['is_attack'] = True
        result['attack_type'] = attack_result.get('attack_type')
        
        self.active_sessions[session_id]['attack_detections'].append({
            'timestamp': datetime.now(timezone.utc),
            'attack_type': attack_result['attack_type'],
            'confidence': attack_result.get('confidence', 0.0)
        })
        
        attack_analysis = {
            'attack_type': attack_result['attack_type'],
            'confidence': attack_result.get('confidence', 0.5),
            'session_id': session_id,
            'attacker_ip': ip_address,
            'context': {
                'query': user_query,
                'detected_patterns': attack_result.get('patterns_detected', []),
                'severity': attack_result.get('severity', 'medium'),
                'user_agent': user_agent
            }
        }
        
        # 4. Get deployment decision
        decision = self.deception_agent.decide_deployment(attack_analysis)
        result['decision'] = decision
        
        # 5. If deploying honeytokens
        if decision.should_deploy:
            context = {
                'session_id': session_id,
                'attack_type': attack_result['attack_type'],
                'attacker_ip': ip_address,
                'user_agent': user_agent
            }
            
            # Deploy honeytokens
            honeytokens = self.deception_agent.deploy_honeytoken(decision, context)
            
            # Store in database
            for ht in honeytokens:
                self.db.store_honeytoken(ht, {
                    'attack_type': attack_result['attack_type'],
                    'deployment_strategy': decision.strategy.value,
                    'session_id': session_id,
                    'confidence': decision.confidence_score
                })
                result['honeytokens_deployed'].append(ht.honeytoken_id)
            
            # Generate response with honeytokens
            normal_response = self._generate_normal_response(user_query)
            
            modified_response = self._inject_honeytokens(
                original_response=normal_response,
                honeytokens=honeytokens,
                strategy=decision.strategy
            )
            
            result['response'] = modified_response
            
            # Send INFO alert
            self.alerting.trigger_alert(
                severity=AlertSeverity.INFO,
                title=f"Honeytoken Deployed - {attack_result['attack_type']}",
                description=(
                    f"{len(honeytokens)} honeytoken(s) deployed in response to "
                    f"{attack_result['attack_type']} attack from IP {ip_address}"
                ),
                context={
                    'session_id': session_id,
                    'attack_type': attack_result['attack_type'],
                    'confidence': decision.confidence_score,
                    'honeytokens': [ht.honeytoken_id for ht in honeytokens],
                    'attacker_ip': ip_address
                },
                channels=[AlertChannel.SLACK, AlertChannel.SYSLOG]
            )
            
            # Trigger callbacks
            for callback in self._on_honeytoken_deployed:
                try:
                    callback(honeytokens, decision, attack_analysis)
                except Exception as e:
                    logger.error(f"Deployment callback error: {e}")
        
        else:
            # No deployment - return normal response
            result['response'] = self._generate_normal_response(user_query)
        
        return result
    
    # ═══════════════════════════════════════════════════════════════════════════
    # BEACON TRIGGER HANDLING
    # ═══════════════════════════════════════════════════════════════════════════
    
    def handle_beacon_trigger(
        self,
        honeytoken_id: str,
        beacon_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Handle forensic beacon trigger (honeytoken accessed).
        
        This is called when an attacker accesses a honeytoken and the
        embedded JavaScript beacon executes, sending back fingerprint data.
        
        Args:
            honeytoken_id: ID of triggered honeytoken
            beacon_data: Data from JavaScript beacon containing:
                - ip_address: Attacker IP
                - user_agent: Browser user agent
                - canvas_fingerprint: Canvas fingerprint hash
                - webgl_vendor: WebGL vendor string
                - webgl_renderer: WebGL renderer string
                - screen_resolution: Screen dimensions
                - color_depth: Color depth
                - platform: OS platform
                - language: Browser language
                - timezone: Browser timezone
                - installed_fonts: List of installed fonts
                - session_id: Session identifier
                - typing_patterns: Keystroke dynamics
                - mouse_movements: Mouse movement patterns
                - scroll_behavior: Scroll patterns
                - referrer: HTTP referrer
                - entry_point: How user arrived
                - session_duration: Time on page
        
        Returns:
            Dictionary containing:
            - fingerprint_id: Created fingerprint ID
            - alert_id: Generated alert ID
            - evidence_package_id: If auto-generated, package ID
        """
        result = {
            'fingerprint_id': None,
            'alert_id': None,
            'evidence_package_id': None
        }
        
        session_id = beacon_data.get('session_id', 'unknown')
        
        # 1. Geolocate IP
        ip_address = beacon_data.get('ip_address')
        geolocation = self._geolocate_ip(ip_address) if ip_address else {}
        
        # 2. Reverse DNS lookup
        reverse_dns = self._reverse_dns_lookup(ip_address) if ip_address else None
        
        # 3. Create AttackerFingerprint
        fingerprint = AttackerFingerprint(
            fingerprint_id=str(uuid.uuid4()),
            honeytoken_id=honeytoken_id,
            ip_address=ip_address,
            ip_geolocation=geolocation,
            user_agent=beacon_data.get('user_agent', ''),
            canvas_fingerprint=beacon_data.get('canvas_fingerprint', ''),
            webgl_vendor=beacon_data.get('webgl_vendor', ''),
            webgl_renderer=beacon_data.get('webgl_renderer', ''),
            screen_resolution=beacon_data.get('screen_resolution', ''),
            color_depth=beacon_data.get('color_depth', 0),
            platform=beacon_data.get('platform', ''),
            language=beacon_data.get('language', ''),
            timezone=beacon_data.get('timezone', ''),
            installed_fonts=beacon_data.get('installed_fonts', []),
            plugins=beacon_data.get('plugins', []),
            timestamp=datetime.now(timezone.utc),
            access_pattern={
                'reverse_dns': reverse_dns,
                'session_duration': beacon_data.get('session_duration', 0),
                'referrer': beacon_data.get('referrer'),
                'entry_point': beacon_data.get('entry_point', 'Unknown')
            },
            behavioral_data={
                'attack_type': beacon_data.get('attack_type', 'unknown'),
                'typing_patterns': beacon_data.get('typing_patterns'),
                'mouse_movements': beacon_data.get('mouse_movements'),
                'scroll_behavior': beacon_data.get('scroll_behavior'),
                'browser_fingerprint': beacon_data.get('browser_fingerprint')
            }
        )
        
        result['fingerprint_id'] = fingerprint.fingerprint_id
        
        # 4. Store fingerprint in database
        self.db.store_fingerprint(fingerprint)
        
        # 5. Record interaction
        interaction_data = {
            'interaction_type': 'beacon_trigger',
            'timestamp': datetime.now(timezone.utc),
            'ip_address': ip_address,
            'user_agent': beacon_data.get('user_agent'),
            'session_id': session_id,
            'raw_data': beacon_data
        }
        
        self.db.record_interaction(honeytoken_id, interaction_data)
        
        # 6. Track in deception agent
        self.deception_agent.track_honeytoken_interaction(
            honeytoken_id=honeytoken_id,
            interaction_data=interaction_data
        )
        
        # 7. Update session tracking
        if session_id in self.active_sessions:
            self.active_sessions[session_id]['honeytokens_triggered'].append({
                'honeytoken_id': honeytoken_id,
                'fingerprint_id': fingerprint.fingerprint_id,
                'timestamp': datetime.now(timezone.utc)
            })
        
        # 8. Determine alert severity
        severity = self._determine_alert_severity(
            session_id=session_id,
            ip_address=ip_address,
            beacon_data=beacon_data
        )
        
        # 9. Send alert
        alert = self.alerting.trigger_alert(
            severity=severity,
            title="🚨 HONEYTOKEN TRIGGERED - Active Data Breach Attempt",
            description=(
                f"Attacker accessed honeytoken {honeytoken_id} from IP {ip_address}. "
                f"Browser fingerprint captured. Session: {session_id}"
            ),
            context={
                'honeytoken_id': honeytoken_id,
                'fingerprint_id': fingerprint.fingerprint_id,
                'attacker_ip': ip_address,
                'session_id': session_id,
                'attack_type': beacon_data.get('attack_type', 'unknown'),
                'geolocation': geolocation
            },
            channels=[AlertChannel.EMAIL, AlertChannel.SLACK, AlertChannel.PAGERDUTY]
        )
        
        result['alert_id'] = alert.alert_id
        
        # 10. Check if evidence package should be auto-generated
        if session_id and session_id != 'unknown':
            try:
                session_honeytokens = self.db.get_honeytokens_by_session(session_id)
                honeytokens_count = len(session_honeytokens)
                
                if honeytokens_count >= self.auto_evidence_threshold:
                    # Auto-generate evidence package
                    try:
                        package = self.evidence_packager.collect_evidence_for_session(session_id)
                        result['evidence_package_id'] = package.package_id
                        
                        # Send CRITICAL alert with evidence package
                        self.alerting.trigger_alert(
                            severity=AlertSeverity.CRITICAL,
                            title="🚨🚨 CRITICAL - Evidence Package Auto-Generated",
                            description=(
                                f"Threshold exceeded ({honeytokens_count} honeytokens). "
                                f"Evidence package ready for law enforcement. "
                                f"Case Number: {package.case_number}"
                            ),
                            context={
                                'session_id': session_id,
                                'package_id': package.package_id,
                                'case_number': package.case_number,
                                'honeytokens_triggered': honeytokens_count,
                                'attacker_ip': ip_address
                            },
                            channels=[AlertChannel.EMAIL, AlertChannel.PAGERDUTY]
                        )
                        
                        # Trigger callbacks
                        for callback in self._on_evidence_generated:
                            try:
                                callback(package)
                            except Exception as e:
                                logger.error(f"Evidence callback error: {e}")
                        
                        logger.info(f"Auto-generated evidence package: {package.package_id}")
                        
                    except Exception as e:
                        logger.error(f"Error generating evidence package: {e}")
                        
            except Exception as e:
                logger.error(f"Error checking session honeytokens: {e}")
        
        # 11. Trigger beacon callbacks
        for callback in self._on_beacon_triggered:
            try:
                callback(fingerprint, beacon_data)
            except Exception as e:
                logger.error(f"Beacon callback error: {e}")
        
        logger.info(f"Beacon trigger handled: {honeytoken_id} -> {fingerprint.fingerprint_id}")
        return result
    
    # ═══════════════════════════════════════════════════════════════════════════
    # HELPER METHODS
    # ═══════════════════════════════════════════════════════════════════════════
    
    def _detect_attack(
        self,
        query: str,
        session_id: str,
        ip_address: str
    ) -> Dict[str, Any]:
        """
        Detect attacks using SentinelQAgent or ML detector.
        
        Args:
            query: User query to analyze
            session_id: Session identifier
            ip_address: User IP address
        
        Returns:
            Attack detection result dictionary
        """
        try:
            # Try to use SentinelQAgent if available
            from phoenix_guardian.agents.sentinelq_agent import SentinelQAgent
            
            sentinelq = SentinelQAgent()
            result = sentinelq.detect_attack(
                query=query,
                session_id=session_id,
                ip_address=ip_address
            )
            return result
            
        except ImportError:
            # Fall back to ML detector
            try:
                from phoenix_guardian.security.ml_detector import MLThreatDetector
                
                detector = MLThreatDetector()
                detection = detector.detect_threat(query)
                
                return {
                    'is_attack': detection.is_threat,
                    'attack_type': detection.threat_category.value if detection.threat_category else 'unknown',
                    'confidence': detection.confidence,
                    'patterns_detected': detection.pattern_matches,
                    'severity': 'high' if detection.confidence > 0.8 else 'medium'
                }
                
            except ImportError:
                # Final fallback - simple pattern matching
                return self._simple_attack_detection(query)
    
    def _simple_attack_detection(self, query: str) -> Dict[str, Any]:
        """
        Simple pattern-based attack detection fallback.
        
        Args:
            query: Query to analyze
        
        Returns:
            Attack detection result
        """
        query_lower = query.lower()
        
        attack_patterns = {
            'prompt_injection': [
                'ignore all previous',
                'ignore your instructions',
                'disregard',
                'new instructions',
                'system prompt',
                'jailbreak',
                'dan mode',
                'developer mode'
            ],
            'data_exfiltration': [
                'show me all patients',
                'list all records',
                'export database',
                'dump data',
                'all ssn',
                'all social security'
            ],
            'pii_extraction': [
                'social security number',
                'credit card',
                'patient address',
                'date of birth',
                'medical record'
            ]
        }
        
        for attack_type, patterns in attack_patterns.items():
            for pattern in patterns:
                if pattern in query_lower:
                    return {
                        'is_attack': True,
                        'attack_type': attack_type,
                        'confidence': 0.7,
                        'patterns_detected': [pattern],
                        'severity': 'medium'
                    }
        
        return {
            'is_attack': False,
            'attack_type': None,
            'confidence': 0.0,
            'patterns_detected': [],
            'severity': 'none'
        }
    
    def _generate_normal_response(self, query: str) -> str:
        """
        Generate normal response to query.
        
        In production, this would call the actual LLM/AI system.
        
        Args:
            query: User query
        
        Returns:
            Response string
        """
        # Placeholder - in production, call actual AI system
        return f"I'll help you with: {query}"
    
    def _inject_honeytokens(
        self,
        original_response: str,
        honeytokens: List[LegalHoneytoken],
        strategy: DeceptionStrategy
    ) -> str:
        """
        Inject honeytokens into response based on strategy.
        
        Args:
            original_response: Original response text
            honeytokens: List of honeytokens to inject
            strategy: Deployment strategy
        
        Returns:
            Modified response with honeytokens
        """
        try:
            from phoenix_guardian.agents.sentinelq_integration import SentinelQDeceptionBridge
            
            bridge = SentinelQDeceptionBridge(self.deception_agent)
            return bridge.inject_honeytokens_into_response(
                original_response,
                honeytokens,
                strategy
            )
        except ImportError:
            # Fallback injection
            return self._simple_injection(original_response, honeytokens, strategy)
    
    def _simple_injection(
        self,
        original_response: str,
        honeytokens: List[LegalHoneytoken],
        strategy: DeceptionStrategy
    ) -> str:
        """
        Simple honeytoken injection fallback.
        
        Args:
            original_response: Original response
            honeytokens: Honeytokens to inject
            strategy: Deployment strategy
        
        Returns:
            Modified response
        """
        if not honeytokens:
            return original_response
        
        # Build honeytoken display
        ht_lines = []
        
        if strategy == DeceptionStrategy.FULL_DECEPTION:
            ht_lines.append("\n\n---\nPATIENT RECORDS FOUND:\n")
        else:
            ht_lines.append("\n\n---\nAdditional Records:\n")
        
        for ht in honeytokens:
            ht_lines.append(f"Name: {ht.name}")
            ht_lines.append(f"MRN: {ht.mrn}")
            ht_lines.append(f"DOB: {ht.dob}")
            ht_lines.append(f"Phone: {ht.phone}")
            ht_lines.append(f"Email: {ht.email}")
            ht_lines.append("")
        
        return original_response + "\n".join(ht_lines)
    
    def _determine_alert_severity(
        self,
        session_id: str,
        ip_address: str,
        beacon_data: Dict[str, Any]
    ) -> AlertSeverity:
        """
        Determine appropriate alert severity.
        
        Args:
            session_id: Session identifier
            ip_address: Attacker IP
            beacon_data: Beacon data
        
        Returns:
            Appropriate AlertSeverity
        """
        severity = AlertSeverity.HIGH  # Default for beacon trigger
        
        # Check for repeat offender
        try:
            existing_fps = self.db.get_fingerprints_by_ip(ip_address)
            if len(existing_fps) >= ESCALATION_THRESHOLDS['repeat_ip_attempts']:
                severity = AlertSeverity.CRITICAL
        except:
            pass
        
        # Check for data exfiltration
        attack_type = beacon_data.get('attack_type', '').lower()
        if 'exfiltration' in attack_type or 'extraction' in attack_type:
            severity = AlertSeverity.CRITICAL
        
        # Check session history
        if session_id in self.active_sessions:
            session = self.active_sessions[session_id]
            triggered_count = len(session.get('honeytokens_triggered', []))
            
            if triggered_count >= ESCALATION_THRESHOLDS['honeytokens_per_hour']:
                severity = AlertSeverity.CRITICAL
        
        return severity
    
    def _geolocate_ip(self, ip: str) -> Dict[str, Any]:
        """
        Geolocate IP address.
        
        In production, use MaxMind GeoIP2 or similar service.
        
        Args:
            ip: IP address to geolocate
        
        Returns:
            Geolocation dictionary
        """
        # TODO: Integrate with real geolocation API (MaxMind GeoIP2)
        # For now, return mock data
        
        if not ip:
            return {}
        
        # Check for private IPs
        if ip.startswith(('10.', '172.', '192.168.', '127.')):
            return {
                'country': 'PRIVATE',
                'region': 'LAN',
                'city': 'Internal Network',
                'latitude': 0,
                'longitude': 0,
                'isp': 'Internal',
                'organization': 'Internal',
                'asn': 0
            }
        
        # Mock geolocation for external IPs
        return {
            'country': 'US',
            'region': 'CA',
            'city': 'Los Angeles',
            'latitude': '34.0522',
            'longitude': '-118.2437',
            'isp': 'Example ISP',
            'organization': 'Example Org',
            'asn': 12345
        }
    
    def _reverse_dns_lookup(self, ip: str) -> Optional[str]:
        """
        Perform reverse DNS lookup.
        
        Args:
            ip: IP address to lookup
        
        Returns:
            Hostname if found, None otherwise
        """
        if not ip:
            return None
        
        try:
            hostname, _, _ = socket.gethostbyaddr(ip)
            return hostname
        except (socket.herror, socket.gaierror):
            return None
        except Exception as e:
            logger.debug(f"Reverse DNS lookup failed for {ip}: {e}")
            return None
    
    # ═══════════════════════════════════════════════════════════════════════════
    # CALLBACK REGISTRATION
    # ═══════════════════════════════════════════════════════════════════════════
    
    def on_honeytoken_deployed(self, callback: Callable):
        """
        Register callback for honeytoken deployment events.
        
        Args:
            callback: Function(honeytokens, decision, attack_analysis)
        """
        self._on_honeytoken_deployed.append(callback)
    
    def on_beacon_triggered(self, callback: Callable):
        """
        Register callback for beacon trigger events.
        
        Args:
            callback: Function(fingerprint, beacon_data)
        """
        self._on_beacon_triggered.append(callback)
    
    def on_evidence_generated(self, callback: Callable):
        """
        Register callback for evidence package generation.
        
        Args:
            callback: Function(evidence_package)
        """
        self._on_evidence_generated.append(callback)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # SESSION MANAGEMENT
    # ═══════════════════════════════════════════════════════════════════════════
    
    def get_session_info(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get information about an active session.
        
        Args:
            session_id: Session identifier
        
        Returns:
            Session info dictionary or None
        """
        return self.active_sessions.get(session_id)
    
    def get_active_sessions(self) -> List[str]:
        """
        Get list of active session IDs.
        
        Returns:
            List of session IDs
        """
        return list(self.active_sessions.keys())
    
    def clear_session(self, session_id: str):
        """
        Clear session from tracking.
        
        Args:
            session_id: Session to clear
        """
        if session_id in self.active_sessions:
            del self.active_sessions[session_id]
    
    # ═══════════════════════════════════════════════════════════════════════════
    # STATISTICS AND REPORTING
    # ═══════════════════════════════════════════════════════════════════════════
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get pipeline statistics.
        
        Returns:
            Statistics dictionary
        """
        total_sessions = len(self.active_sessions)
        total_attacks = sum(
            len(s.get('attack_detections', []))
            for s in self.active_sessions.values()
        )
        total_honeytokens = sum(
            len(s.get('honeytokens_triggered', []))
            for s in self.active_sessions.values()
        )
        total_alerts = len(self.alerting.alert_history)
        total_packages = len(self.evidence_packager.packages)
        
        return {
            'active_sessions': total_sessions,
            'attacks_detected': total_attacks,
            'honeytokens_triggered': total_honeytokens,
            'alerts_generated': total_alerts,
            'evidence_packages': total_packages,
            'unacknowledged_alerts': len(self.alerting.get_unacknowledged_alerts())
        }
