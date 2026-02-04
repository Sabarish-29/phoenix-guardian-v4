"""
Phoenix Guardian - Network Policy Enforcement
IP whitelisting, VPN requirements, and network isolation.
Version: 1.0.0

This module provides:
- IP whitelist validation
- VPN requirement enforcement
- Network CIDR utilities
- Firewall rule generation
- Network policy validation
"""

from dataclasses import dataclass, field
from enum import Enum
from ipaddress import ip_address, ip_network, IPv4Address, IPv6Address
from typing import Any, Dict, List, Optional, Set, Tuple, Union
import logging
import re

logger = logging.getLogger(__name__)


# ==============================================================================
# Exceptions
# ==============================================================================

class NetworkPolicyError(Exception):
    """Base exception for network policy errors."""
    pass


class IPNotAllowedError(NetworkPolicyError):
    """IP address not in allowed list."""
    pass


class VPNRequiredError(NetworkPolicyError):
    """VPN connection is required but not detected."""
    pass


class InvalidCIDRError(NetworkPolicyError):
    """Invalid CIDR notation."""
    pass


# ==============================================================================
# Enumerations
# ==============================================================================

class NetworkZone(Enum):
    """Network security zones."""
    INTERNET = "internet"        # Public internet
    DMZ = "dmz"                  # Demilitarized zone
    INTERNAL = "internal"        # Internal hospital network
    RESTRICTED = "restricted"    # Restricted/secure zone
    MANAGEMENT = "management"    # Management network


class ConnectionType(Enum):
    """Connection type for access."""
    DIRECT = "direct"            # Direct connection
    VPN = "vpn"                  # VPN tunnel
    PRIVATE_LINK = "private_link"  # Cloud private link
    INTERNAL = "internal"        # Internal network


# ==============================================================================
# IP Validation Utilities
# ==============================================================================

def is_valid_ip(ip_str: str) -> bool:
    """Check if string is a valid IP address."""
    try:
        ip_address(ip_str)
        return True
    except ValueError:
        return False


def is_valid_cidr(cidr_str: str) -> bool:
    """Check if string is a valid CIDR notation."""
    try:
        ip_network(cidr_str, strict=False)
        return True
    except ValueError:
        return False


def parse_cidr_list(cidr_list: List[str]) -> List:
    """Parse list of CIDR strings to ip_network objects."""
    networks = []
    for cidr in cidr_list:
        try:
            networks.append(ip_network(cidr, strict=False))
        except ValueError as e:
            raise InvalidCIDRError(f"Invalid CIDR: {cidr}") from e
    return networks


def ip_in_networks(ip_str: str, networks: List[str]) -> bool:
    """Check if IP address is in any of the networks."""
    try:
        ip = ip_address(ip_str)
        for cidr in networks:
            network = ip_network(cidr, strict=False)
            if ip in network:
                return True
        return False
    except ValueError:
        return False


def get_ip_zone(ip_str: str) -> NetworkZone:
    """Determine network zone for an IP address."""
    try:
        ip = ip_address(ip_str)
        
        # RFC 1918 private ranges
        private_ranges = [
            ip_network("10.0.0.0/8"),
            ip_network("172.16.0.0/12"),
            ip_network("192.168.0.0/16"),
        ]
        
        # Loopback
        if ip.is_loopback:
            return NetworkZone.MANAGEMENT
        
        # Private ranges
        for net in private_ranges:
            if ip in net:
                return NetworkZone.INTERNAL
        
        # Link-local
        if ip.is_link_local:
            return NetworkZone.INTERNAL
        
        # Everything else is internet
        return NetworkZone.INTERNET
        
    except ValueError:
        return NetworkZone.INTERNET


# ==============================================================================
# Network Policy Data Classes
# ==============================================================================

@dataclass
class NetworkPolicy:
    """
    Network access policy for a tenant.
    
    Defines allowed IPs, VPN requirements, and network rules.
    """
    name: str
    description: str = ""
    
    # IP Whitelisting
    allowed_cidrs: Tuple[str, ...] = field(default_factory=tuple)
    blocked_cidrs: Tuple[str, ...] = field(default_factory=tuple)
    
    # VPN Settings
    vpn_required: bool = True
    vpn_provider: str = ""  # e.g., "cisco_anyconnect", "openvpn"
    vpn_subnet: str = ""    # VPN client subnet
    
    # Connection types allowed
    allowed_connection_types: Tuple[ConnectionType, ...] = field(
        default_factory=lambda: (ConnectionType.VPN, ConnectionType.INTERNAL)
    )
    
    # Ingress rules
    ingress_ports: Tuple[int, ...] = (443,)
    ingress_protocols: Tuple[str, ...] = ("tcp",)
    
    # Egress rules
    egress_allowed_domains: Tuple[str, ...] = field(default_factory=tuple)
    egress_blocked_domains: Tuple[str, ...] = field(default_factory=tuple)
    egress_allowed_ports: Tuple[int, ...] = (443, 80)
    
    # Rate limiting
    rate_limit_per_minute: int = 1000
    rate_limit_per_ip: int = 100
    
    # Logging
    log_all_connections: bool = True
    log_blocked_only: bool = False
    
    def validate(self) -> List[str]:
        """Validate network policy configuration."""
        errors = []
        
        # Validate CIDRs
        for cidr in self.allowed_cidrs:
            if not is_valid_cidr(cidr):
                errors.append(f"Invalid allowed CIDR: {cidr}")
        
        for cidr in self.blocked_cidrs:
            if not is_valid_cidr(cidr):
                errors.append(f"Invalid blocked CIDR: {cidr}")
        
        if self.vpn_required and self.vpn_subnet:
            if not is_valid_cidr(self.vpn_subnet):
                errors.append(f"Invalid VPN subnet: {self.vpn_subnet}")
        
        # Validate ports
        for port in self.ingress_ports:
            if not 1 <= port <= 65535:
                errors.append(f"Invalid ingress port: {port}")
        
        for port in self.egress_allowed_ports:
            if not 1 <= port <= 65535:
                errors.append(f"Invalid egress port: {port}")
        
        return errors
    
    def is_ip_allowed(self, ip_str: str) -> bool:
        """Check if IP is allowed by policy."""
        # Check blocked list first
        if ip_in_networks(ip_str, list(self.blocked_cidrs)):
            return False
        
        # If allowed list is empty, allow all non-blocked
        if not self.allowed_cidrs:
            return True
        
        # Check allowed list
        return ip_in_networks(ip_str, list(self.allowed_cidrs))
    
    def check_access(
        self,
        source_ip: str,
        connection_type: ConnectionType = ConnectionType.DIRECT
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if access is allowed.
        
        Returns:
            Tuple of (allowed: bool, reason: Optional[str])
        """
        # Check IP whitelist
        if not self.is_ip_allowed(source_ip):
            return False, f"IP {source_ip} not in allowed list"
        
        # Check VPN requirement
        if self.vpn_required:
            if connection_type not in [ConnectionType.VPN, ConnectionType.INTERNAL]:
                # Check if IP is in VPN subnet
                if self.vpn_subnet and not ip_in_networks(source_ip, [self.vpn_subnet]):
                    return False, "VPN connection required"
        
        # Check connection type
        if connection_type not in self.allowed_connection_types:
            return False, f"Connection type {connection_type.value} not allowed"
        
        return True, None


@dataclass
class AccessAttempt:
    """Record of an access attempt."""
    source_ip: str
    destination_port: int
    timestamp: str
    connection_type: ConnectionType
    allowed: bool
    reason: Optional[str] = None
    user_agent: Optional[str] = None
    request_path: Optional[str] = None
    tenant_id: Optional[str] = None


# ==============================================================================
# Network Policy Enforcer
# ==============================================================================

class NetworkPolicyEnforcer:
    """
    Enforces network policies for tenant access.
    
    Validates incoming connections against tenant network policies
    and logs all access attempts.
    """
    
    def __init__(self, policy: NetworkPolicy):
        self.policy = policy
        self._access_log: List[AccessAttempt] = []
        self._blocked_ips: Set[str] = set()
        self._rate_limits: Dict[str, List[float]] = {}
    
    def check_access(
        self,
        source_ip: str,
        destination_port: int = 443,
        connection_type: ConnectionType = ConnectionType.DIRECT,
        user_agent: Optional[str] = None,
        request_path: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if access is allowed and log the attempt.
        
        Args:
            source_ip: Source IP address
            destination_port: Destination port
            connection_type: Type of connection
            user_agent: Optional user agent string
            request_path: Optional request path
            tenant_id: Optional tenant identifier
        
        Returns:
            Tuple of (allowed: bool, reason: Optional[str])
        """
        from datetime import datetime
        
        # Check rate limiting first
        if self._is_rate_limited(source_ip):
            reason = "Rate limit exceeded"
            self._log_attempt(
                source_ip, destination_port, connection_type,
                False, reason, user_agent, request_path, tenant_id
            )
            return False, reason
        
        # Check if IP is temporarily blocked
        if source_ip in self._blocked_ips:
            reason = "IP temporarily blocked"
            self._log_attempt(
                source_ip, destination_port, connection_type,
                False, reason, user_agent, request_path, tenant_id
            )
            return False, reason
        
        # Check port
        if destination_port not in self.policy.ingress_ports:
            reason = f"Port {destination_port} not allowed"
            self._log_attempt(
                source_ip, destination_port, connection_type,
                False, reason, user_agent, request_path, tenant_id
            )
            return False, reason
        
        # Check network policy
        allowed, reason = self.policy.check_access(source_ip, connection_type)
        
        # Log the attempt
        self._log_attempt(
            source_ip, destination_port, connection_type,
            allowed, reason, user_agent, request_path, tenant_id
        )
        
        return allowed, reason
    
    def _is_rate_limited(self, source_ip: str) -> bool:
        """Check if IP is rate limited."""
        import time
        
        now = time.time()
        window = 60  # 1 minute window
        
        if source_ip not in self._rate_limits:
            self._rate_limits[source_ip] = []
        
        # Remove old entries
        self._rate_limits[source_ip] = [
            t for t in self._rate_limits[source_ip]
            if now - t < window
        ]
        
        # Check limit
        if len(self._rate_limits[source_ip]) >= self.policy.rate_limit_per_ip:
            return True
        
        # Add current request
        self._rate_limits[source_ip].append(now)
        return False
    
    def _log_attempt(
        self,
        source_ip: str,
        destination_port: int,
        connection_type: ConnectionType,
        allowed: bool,
        reason: Optional[str],
        user_agent: Optional[str],
        request_path: Optional[str],
        tenant_id: Optional[str],
    ) -> None:
        """Log access attempt."""
        from datetime import datetime
        
        # Only log if configured
        if not self.policy.log_all_connections and allowed:
            if self.policy.log_blocked_only:
                return
        
        attempt = AccessAttempt(
            source_ip=source_ip,
            destination_port=destination_port,
            timestamp=datetime.now().isoformat(),
            connection_type=connection_type,
            allowed=allowed,
            reason=reason,
            user_agent=user_agent,
            request_path=request_path,
            tenant_id=tenant_id,
        )
        
        self._access_log.append(attempt)
        
        # Log to standard logger
        log_level = logging.INFO if allowed else logging.WARNING
        logger.log(
            log_level,
            f"Access {'ALLOWED' if allowed else 'DENIED'}: "
            f"{source_ip}:{destination_port} via {connection_type.value}"
            f"{f' - {reason}' if reason else ''}"
        )
    
    def block_ip(self, ip_str: str, duration_minutes: int = 60) -> None:
        """Temporarily block an IP address."""
        self._blocked_ips.add(ip_str)
        logger.warning(f"Blocked IP {ip_str} for {duration_minutes} minutes")
        
        # In production, would schedule unblock
    
    def unblock_ip(self, ip_str: str) -> None:
        """Unblock an IP address."""
        self._blocked_ips.discard(ip_str)
        logger.info(f"Unblocked IP {ip_str}")
    
    def get_access_log(
        self,
        limit: int = 100,
        allowed_only: bool = False,
        blocked_only: bool = False,
    ) -> List[AccessAttempt]:
        """Get access log entries."""
        log = self._access_log[-limit:]
        
        if allowed_only:
            log = [a for a in log if a.allowed]
        elif blocked_only:
            log = [a for a in log if not a.allowed]
        
        return log
    
    def get_blocked_ips(self) -> Set[str]:
        """Get currently blocked IPs."""
        return self._blocked_ips.copy()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get access statistics."""
        total = len(self._access_log)
        allowed = sum(1 for a in self._access_log if a.allowed)
        blocked = total - allowed
        
        unique_ips = set(a.source_ip for a in self._access_log)
        blocked_unique = set(a.source_ip for a in self._access_log if not a.allowed)
        
        return {
            "total_attempts": total,
            "allowed": allowed,
            "blocked": blocked,
            "allow_rate": allowed / total if total > 0 else 0,
            "unique_ips": len(unique_ips),
            "unique_blocked_ips": len(blocked_unique),
            "currently_blocked": len(self._blocked_ips),
        }


# ==============================================================================
# Kubernetes Network Policy Generator
# ==============================================================================

class K8sNetworkPolicyGenerator:
    """
    Generates Kubernetes NetworkPolicy resources from tenant configuration.
    """
    
    def __init__(self, tenant_id: str, namespace: str):
        self.tenant_id = tenant_id
        self.namespace = namespace
    
    def generate_ingress_policy(
        self,
        policy: NetworkPolicy,
        app_labels: Dict[str, str],
    ) -> Dict[str, Any]:
        """Generate Kubernetes ingress NetworkPolicy."""
        ingress_rules = []
        
        # Add CIDR-based rules
        if policy.allowed_cidrs:
            cidr_rule = {
                "from": [
                    {"ipBlock": {"cidr": cidr}}
                    for cidr in policy.allowed_cidrs
                ],
                "ports": [
                    {"protocol": proto.upper(), "port": port}
                    for port in policy.ingress_ports
                    for proto in policy.ingress_protocols
                ]
            }
            ingress_rules.append(cidr_rule)
        
        return {
            "apiVersion": "networking.k8s.io/v1",
            "kind": "NetworkPolicy",
            "metadata": {
                "name": f"{self.tenant_id}-ingress",
                "namespace": self.namespace,
                "labels": {
                    "app.kubernetes.io/name": "phoenix-guardian",
                    "app.kubernetes.io/component": "network-policy",
                    "phoenix-guardian/tenant": self.tenant_id,
                }
            },
            "spec": {
                "podSelector": {"matchLabels": app_labels},
                "policyTypes": ["Ingress"],
                "ingress": ingress_rules if ingress_rules else [{}],
            }
        }
    
    def generate_egress_policy(
        self,
        policy: NetworkPolicy,
        app_labels: Dict[str, str],
    ) -> Dict[str, Any]:
        """Generate Kubernetes egress NetworkPolicy."""
        egress_rules = []
        
        # Allow egress to specific ports
        egress_rules.append({
            "to": [],  # To any destination
            "ports": [
                {"protocol": "TCP", "port": port}
                for port in policy.egress_allowed_ports
            ]
        })
        
        # Allow DNS
        egress_rules.append({
            "to": [],
            "ports": [
                {"protocol": "UDP", "port": 53},
                {"protocol": "TCP", "port": 53},
            ]
        })
        
        return {
            "apiVersion": "networking.k8s.io/v1",
            "kind": "NetworkPolicy",
            "metadata": {
                "name": f"{self.tenant_id}-egress",
                "namespace": self.namespace,
                "labels": {
                    "app.kubernetes.io/name": "phoenix-guardian",
                    "app.kubernetes.io/component": "network-policy",
                    "phoenix-guardian/tenant": self.tenant_id,
                }
            },
            "spec": {
                "podSelector": {"matchLabels": app_labels},
                "policyTypes": ["Egress"],
                "egress": egress_rules,
            }
        }
    
    def generate_deny_all_policy(
        self,
        app_labels: Dict[str, str],
    ) -> Dict[str, Any]:
        """Generate deny-all baseline NetworkPolicy."""
        return {
            "apiVersion": "networking.k8s.io/v1",
            "kind": "NetworkPolicy",
            "metadata": {
                "name": f"{self.tenant_id}-deny-all",
                "namespace": self.namespace,
                "labels": {
                    "app.kubernetes.io/name": "phoenix-guardian",
                    "app.kubernetes.io/component": "network-policy",
                    "phoenix-guardian/tenant": self.tenant_id,
                }
            },
            "spec": {
                "podSelector": {"matchLabels": app_labels},
                "policyTypes": ["Ingress", "Egress"],
                # Empty ingress/egress = deny all
            }
        }
    
    def generate_all_policies(
        self,
        policy: NetworkPolicy,
        app_labels: Dict[str, str],
    ) -> List[Dict[str, Any]]:
        """Generate all NetworkPolicy resources for tenant."""
        return [
            self.generate_deny_all_policy(app_labels),
            self.generate_ingress_policy(policy, app_labels),
            self.generate_egress_policy(policy, app_labels),
        ]


# ==============================================================================
# Default Policies
# ==============================================================================

# Strict policy for production
STRICT_POLICY = NetworkPolicy(
    name="strict",
    description="Strict network policy for production deployments",
    allowed_cidrs=(),  # Must be configured per-tenant
    vpn_required=True,
    allowed_connection_types=(ConnectionType.VPN,),
    ingress_ports=(443,),
    ingress_protocols=("tcp",),
    egress_allowed_ports=(443,),
    rate_limit_per_minute=500,
    rate_limit_per_ip=50,
    log_all_connections=True,
)

# Standard policy for most deployments
STANDARD_POLICY = NetworkPolicy(
    name="standard",
    description="Standard network policy for hospital deployments",
    allowed_cidrs=("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"),
    vpn_required=True,
    allowed_connection_types=(ConnectionType.VPN, ConnectionType.INTERNAL),
    ingress_ports=(443, 8443),
    ingress_protocols=("tcp",),
    egress_allowed_ports=(443, 80),
    egress_allowed_domains=("api.anthropic.com", "api.openai.com"),
    rate_limit_per_minute=1000,
    rate_limit_per_ip=100,
    log_all_connections=True,
)

# Permissive policy for development
DEVELOPMENT_POLICY = NetworkPolicy(
    name="development",
    description="Permissive policy for development environments",
    allowed_cidrs=("0.0.0.0/0",),  # Allow all
    vpn_required=False,
    allowed_connection_types=(
        ConnectionType.DIRECT,
        ConnectionType.VPN,
        ConnectionType.INTERNAL,
    ),
    ingress_ports=(80, 443, 8000, 8080, 8443),
    ingress_protocols=("tcp",),
    egress_allowed_ports=(80, 443, 5432, 6379),
    rate_limit_per_minute=10000,
    rate_limit_per_ip=1000,
    log_all_connections=False,
    log_blocked_only=True,
)


def get_policy_for_environment(environment: str) -> NetworkPolicy:
    """Get default network policy for environment."""
    policies = {
        "production": STRICT_POLICY,
        "staging": STANDARD_POLICY,
        "development": DEVELOPMENT_POLICY,
    }
    return policies.get(environment.lower(), STANDARD_POLICY)


def create_policy_from_tenant_config(tenant_config) -> NetworkPolicy:
    """Create NetworkPolicy from TenantConfig."""
    return NetworkPolicy(
        name=f"{tenant_config.tenant_id}-policy",
        description=f"Network policy for {tenant_config.hospital_name}",
        allowed_cidrs=tenant_config.network.allowed_ips,
        vpn_required=tenant_config.network.vpn_required,
        allowed_connection_types=(
            ConnectionType.VPN if tenant_config.network.vpn_required
            else ConnectionType.DIRECT,
            ConnectionType.INTERNAL,
        ),
        ingress_ports=tenant_config.network.ingress_allowed_ports,
        ingress_protocols=("tcp",),
        egress_allowed_domains=tenant_config.network.egress_allowed_domains,
        log_all_connections=True,
    )
