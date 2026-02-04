"""
Phoenix Guardian - Alert Rules
Prometheus/Alertmanager alert rules for pilot monitoring.

Defines alerts for Phase 2 validation and operational health.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from enum import Enum
import logging

logger = logging.getLogger(__name__)


# ==============================================================================
# Enumerations
# ==============================================================================

class AlertSeverity(Enum):
    """Alert severity levels."""
    CRITICAL = "critical"                    # Page immediately, P1
    HIGH = "high"                            # Page, P2
    WARNING = "warning"                      # Notify, P3
    INFO = "info"                            # Log only


class AlertCategory(Enum):
    """Alert categories."""
    AVAILABILITY = "availability"
    PERFORMANCE = "performance"
    SECURITY = "security"
    QUALITY = "quality"
    SLA = "sla"
    BENCHMARK = "benchmark"


# ==============================================================================
# Data Classes
# ==============================================================================

@dataclass
class AlertRule:
    """
    A Prometheus alerting rule.
    """
    name: str
    expression: str
    severity: AlertSeverity
    summary: str
    description: str
    
    # Duration before firing
    for_duration: str = "5m"
    
    # Labels
    category: AlertCategory = AlertCategory.AVAILABILITY
    team: str = "platform"
    
    # Additional labels
    labels: Dict[str, str] = field(default_factory=dict)
    
    # Annotations
    annotations: Dict[str, str] = field(default_factory=dict)
    
    def to_prometheus_format(self) -> Dict[str, Any]:
        """Convert to Prometheus alerting rule format."""
        all_labels = {
            "severity": self.severity.value,
            "category": self.category.value,
            "team": self.team,
            **self.labels,
        }
        
        all_annotations = {
            "summary": self.summary,
            "description": self.description,
            **self.annotations,
        }
        
        return {
            "alert": self.name,
            "expr": self.expression,
            "for": self.for_duration,
            "labels": all_labels,
            "annotations": all_annotations,
        }


@dataclass
class AlertRuleSet:
    """
    A group of related alert rules.
    """
    name: str
    rules: List[AlertRule] = field(default_factory=list)
    
    # Evaluation interval
    interval: str = "30s"
    
    def add_rule(self, rule: AlertRule) -> None:
        """Add a rule to the set."""
        self.rules.append(rule)
    
    def to_prometheus_format(self) -> Dict[str, Any]:
        """Convert to Prometheus rule group format."""
        return {
            "name": self.name,
            "interval": self.interval,
            "rules": [r.to_prometheus_format() for r in self.rules],
        }
    
    def to_yaml_string(self) -> str:
        """Export as YAML string."""
        import json
        # Note: In production, use proper YAML library
        # This is a simplified JSON representation
        return json.dumps({"groups": [self.to_prometheus_format()]}, indent=2)


# ==============================================================================
# Phoenix Alert Rules
# ==============================================================================

class PhoenixAlertRules:
    """
    Pre-defined alert rules for Phoenix Guardian.
    
    Includes alerts for:
    - Phase 2 benchmark validation
    - Operational health
    - Security monitoring
    - SLA compliance
    
    Example:
        rules = PhoenixAlertRules()
        
        # Get all rule sets
        rule_sets = rules.get_all_rule_sets()
        
        # Export to Prometheus format
        for rule_set in rule_sets:
            print(rule_set.to_yaml_string())
    """
    
    def __init__(self, tenant_filter: str = ".*"):
        self._tenant_filter = tenant_filter
    
    # =========================================================================
    # Benchmark Alerts (Phase 2 Validation)
    # =========================================================================
    
    def get_benchmark_rules(self) -> AlertRuleSet:
        """
        Get alert rules for Phase 2 benchmark validation.
        
        These fire when we're falling below our promises.
        """
        rule_set = AlertRuleSet(name="phoenix_benchmarks")
        
        # Time Saved Below Target (12.3 min)
        rule_set.add_rule(AlertRule(
            name="PhoenixTimeSavedBelowTarget",
            expression=f'''
                avg(
                    phoenix_time_saved_minutes_sum{{tenant_id=~"{self._tenant_filter}"}}
                    / phoenix_time_saved_minutes_count{{tenant_id=~"{self._tenant_filter}"}}
                ) < 12.3
            '''.strip().replace('\n', ''),
            severity=AlertSeverity.WARNING,
            for_duration="30m",
            category=AlertCategory.BENCHMARK,
            summary="Time saved below Phase 2 target",
            description="Average time saved is {{ $value | humanize }}min, below target of 12.3min",
        ))
        
        # Time Saved Critically Low
        rule_set.add_rule(AlertRule(
            name="PhoenixTimeSavedCriticallyLow",
            expression=f'''
                avg(
                    phoenix_time_saved_minutes_sum{{tenant_id=~"{self._tenant_filter}"}}
                    / phoenix_time_saved_minutes_count{{tenant_id=~"{self._tenant_filter}"}}
                ) < 8
            '''.strip().replace('\n', ''),
            severity=AlertSeverity.HIGH,
            for_duration="15m",
            category=AlertCategory.BENCHMARK,
            summary="Time saved critically low",
            description="Average time saved is {{ $value | humanize }}min, significantly below target",
        ))
        
        # Satisfaction Below Target (4.3)
        rule_set.add_rule(AlertRule(
            name="PhoenixSatisfactionBelowTarget",
            expression=f'''
                avg(phoenix_physician_rating_average{{tenant_id=~"{self._tenant_filter}"}}) < 4.3
            '''.strip(),
            severity=AlertSeverity.WARNING,
            for_duration="1h",
            category=AlertCategory.BENCHMARK,
            summary="Physician satisfaction below target",
            description="Average satisfaction is {{ $value | humanize }}/5, below target of 4.3",
        ))
        
        # Satisfaction Critically Low
        rule_set.add_rule(AlertRule(
            name="PhoenixSatisfactionCriticallyLow",
            expression=f'''
                avg(phoenix_physician_rating_average{{tenant_id=~"{self._tenant_filter}"}}) < 3.5
            '''.strip(),
            severity=AlertSeverity.HIGH,
            for_duration="30m",
            category=AlertCategory.BENCHMARK,
            summary="Physician satisfaction critically low",
            description="Average satisfaction is {{ $value | humanize }}/5, requires immediate attention",
        ))
        
        # Detection Rate Below Target (97.4%)
        rule_set.add_rule(AlertRule(
            name="PhoenixDetectionRateBelowTarget",
            expression=f'''
                avg(phoenix_attack_detection_rate{{tenant_id=~"{self._tenant_filter}"}}) < 0.974
            '''.strip(),
            severity=AlertSeverity.HIGH,
            for_duration="15m",
            category=AlertCategory.BENCHMARK,
            team="security",
            summary="Attack detection rate below target",
            description="Detection rate is {{ $value | humanize }}%, below target of 97.4%",
        ))
        
        # AI Acceptance Below Target (85%)
        rule_set.add_rule(AlertRule(
            name="PhoenixAIAcceptanceBelowTarget",
            expression=f'''
                avg(phoenix_ai_acceptance_rate{{tenant_id=~"{self._tenant_filter}"}}) < 0.85
            '''.strip(),
            severity=AlertSeverity.WARNING,
            for_duration="1h",
            category=AlertCategory.BENCHMARK,
            summary="AI acceptance rate below target",
            description="AI acceptance is {{ $value | humanize }}%, below target of 85%",
        ))
        
        return rule_set
    
    # =========================================================================
    # Performance Alerts
    # =========================================================================
    
    def get_performance_rules(self) -> AlertRuleSet:
        """Get alert rules for performance monitoring."""
        rule_set = AlertRuleSet(name="phoenix_performance")
        
        # P95 Latency Above Target (200ms)
        rule_set.add_rule(AlertRule(
            name="PhoenixHighLatency",
            expression=f'''
                histogram_quantile(0.95,
                    sum(rate(phoenix_request_latency_seconds_bucket{{tenant_id=~"{self._tenant_filter}"}}[5m])) by (le)
                ) > 0.2
            '''.strip().replace('\n', ''),
            severity=AlertSeverity.WARNING,
            for_duration="10m",
            category=AlertCategory.PERFORMANCE,
            summary="P95 latency above target",
            description="P95 latency is {{ $value | humanize }}s, above target of 200ms",
        ))
        
        # P95 Latency Critical
        rule_set.add_rule(AlertRule(
            name="PhoenixCriticalLatency",
            expression=f'''
                histogram_quantile(0.95,
                    sum(rate(phoenix_request_latency_seconds_bucket{{tenant_id=~"{self._tenant_filter}"}}[5m])) by (le)
                ) > 0.5
            '''.strip().replace('\n', ''),
            severity=AlertSeverity.CRITICAL,
            for_duration="5m",
            category=AlertCategory.PERFORMANCE,
            summary="P95 latency critically high",
            description="P95 latency is {{ $value | humanize }}s, severely degraded performance",
        ))
        
        # Agent Error Rate High
        rule_set.add_rule(AlertRule(
            name="PhoenixAgentErrorRateHigh",
            expression=f'''
                sum(rate(phoenix_agent_invocations_total{{tenant_id=~"{self._tenant_filter}",status="failure"}}[5m]))
                / sum(rate(phoenix_agent_invocations_total{{tenant_id=~"{self._tenant_filter}"}}[5m]))
                > 0.05
            '''.strip().replace('\n', ''),
            severity=AlertSeverity.HIGH,
            for_duration="10m",
            category=AlertCategory.PERFORMANCE,
            summary="Agent error rate high",
            description="Agent error rate is {{ $value | humanize }}%, above 5% threshold",
        ))
        
        # Agent Error Rate Critical
        rule_set.add_rule(AlertRule(
            name="PhoenixAgentErrorRateCritical",
            expression=f'''
                sum(rate(phoenix_agent_invocations_total{{tenant_id=~"{self._tenant_filter}",status="failure"}}[5m]))
                / sum(rate(phoenix_agent_invocations_total{{tenant_id=~"{self._tenant_filter}"}}[5m]))
                > 0.2
            '''.strip().replace('\n', ''),
            severity=AlertSeverity.CRITICAL,
            for_duration="5m",
            category=AlertCategory.PERFORMANCE,
            summary="Agent error rate critical",
            description="Agent error rate is {{ $value | humanize }}%, system significantly degraded",
        ))
        
        # Agent Latency High
        rule_set.add_rule(AlertRule(
            name="PhoenixAgentLatencyHigh",
            expression=f'''
                histogram_quantile(0.95,
                    sum(rate(phoenix_agent_latency_seconds_bucket{{tenant_id=~"{self._tenant_filter}"}}[5m])) by (le, agent_type)
                ) > 2
            '''.strip().replace('\n', ''),
            severity=AlertSeverity.WARNING,
            for_duration="10m",
            category=AlertCategory.PERFORMANCE,
            summary="Agent latency high",
            description="Agent {{ $labels.agent_type }} P95 latency is {{ $value | humanize }}s",
        ))
        
        return rule_set
    
    # =========================================================================
    # Security Alerts
    # =========================================================================
    
    def get_security_rules(self) -> AlertRuleSet:
        """Get alert rules for security monitoring."""
        rule_set = AlertRuleSet(name="phoenix_security", interval="15s")
        
        # High Volume of Security Events
        rule_set.add_rule(AlertRule(
            name="PhoenixSecurityEventSpike",
            expression=f'''
                sum(rate(phoenix_security_events_total{{tenant_id=~"{self._tenant_filter}"}}[5m])) * 60 > 100
            '''.strip(),
            severity=AlertSeverity.HIGH,
            for_duration="5m",
            category=AlertCategory.SECURITY,
            team="security",
            summary="Security event spike detected",
            description="{{ $value | humanize }} security events per minute, possible attack in progress",
        ))
        
        # Critical Security Event
        rule_set.add_rule(AlertRule(
            name="PhoenixCriticalSecurityEvent",
            expression=f'''
                sum(rate(phoenix_security_events_total{{tenant_id=~"{self._tenant_filter}",event_type=~"data_exfiltration|jailbreak_attempt"}}[1m])) * 60 > 0
            '''.strip(),
            severity=AlertSeverity.CRITICAL,
            for_duration="0m",
            category=AlertCategory.SECURITY,
            team="security",
            summary="Critical security event detected",
            description="Detected {{ $labels.event_type }} attempt",
        ))
        
        # High False Positive Rate
        rule_set.add_rule(AlertRule(
            name="PhoenixHighFalsePositiveRate",
            expression=f'''
                sum(increase(phoenix_false_positives_total{{tenant_id=~"{self._tenant_filter}"}}[1h]))
                / sum(increase(phoenix_security_events_total{{tenant_id=~"{self._tenant_filter}",blocked="true"}}[1h]))
                > 0.05
            '''.strip().replace('\n', ''),
            severity=AlertSeverity.WARNING,
            for_duration="30m",
            category=AlertCategory.SECURITY,
            team="security",
            summary="High false positive rate",
            description="False positive rate is {{ $value | humanize }}%, impacting physician experience",
        ))
        
        # Many False Positives in Short Time
        rule_set.add_rule(AlertRule(
            name="PhoenixFalsePositiveSpike",
            expression=f'''
                sum(increase(phoenix_false_positives_total{{tenant_id=~"{self._tenant_filter}"}}[15m])) > 5
            '''.strip(),
            severity=AlertSeverity.HIGH,
            for_duration="0m",
            category=AlertCategory.SECURITY,
            team="security",
            summary="False positive spike",
            description="{{ $value }} false positives in 15 minutes, check ML model",
        ))
        
        return rule_set
    
    # =========================================================================
    # Availability Alerts
    # =========================================================================
    
    def get_availability_rules(self) -> AlertRuleSet:
        """Get alert rules for availability monitoring."""
        rule_set = AlertRuleSet(name="phoenix_availability")
        
        # No Encounters (Service Down)
        rule_set.add_rule(AlertRule(
            name="PhoenixNoEncounters",
            expression=f'''
                sum(rate(phoenix_encounters_total{{tenant_id=~"{self._tenant_filter}"}}[5m])) == 0
                and sum(phoenix_encounters_active{{tenant_id=~"{self._tenant_filter}"}}) == 0
            '''.strip().replace('\n', ''),
            severity=AlertSeverity.CRITICAL,
            for_duration="5m",
            category=AlertCategory.AVAILABILITY,
            summary="No encounters being processed",
            description="Phoenix Guardian appears to be down or unreachable",
        ))
        
        # Active Incidents
        rule_set.add_rule(AlertRule(
            name="PhoenixActiveP1Incident",
            expression=f'''
                sum(phoenix_incidents_active{{tenant_id=~"{self._tenant_filter}",priority="P1"}}) > 0
            '''.strip(),
            severity=AlertSeverity.CRITICAL,
            for_duration="0m",
            category=AlertCategory.AVAILABILITY,
            summary="Active P1 incident",
            description="There is an active P1 incident requiring immediate attention",
        ))
        
        rule_set.add_rule(AlertRule(
            name="PhoenixMultipleActiveIncidents",
            expression=f'''
                sum(phoenix_incidents_active{{tenant_id=~"{self._tenant_filter}"}}) >= 3
            '''.strip(),
            severity=AlertSeverity.HIGH,
            for_duration="5m",
            category=AlertCategory.AVAILABILITY,
            summary="Multiple active incidents",
            description="{{ $value }} active incidents, system stability at risk",
        ))
        
        return rule_set
    
    # =========================================================================
    # SLA Alerts
    # =========================================================================
    
    def get_sla_rules(self) -> AlertRuleSet:
        """Get alert rules for SLA compliance."""
        rule_set = AlertRuleSet(name="phoenix_sla")
        
        # SLA Error Budget Burn Rate
        rule_set.add_rule(AlertRule(
            name="PhoenixSLABudgetBurnHigh",
            expression=f'''
                (
                    1 - (
                        sum(rate(phoenix_encounters_total{{tenant_id=~"{self._tenant_filter}",status="completed"}}[1h]))
                        / sum(rate(phoenix_encounters_total{{tenant_id=~"{self._tenant_filter}"}}[1h]))
                    )
                ) * 720 > 1
            '''.strip().replace('\n', ''),
            severity=AlertSeverity.WARNING,
            for_duration="15m",
            category=AlertCategory.SLA,
            summary="SLA error budget burning fast",
            description="At current rate, monthly SLA budget will be exhausted in {{ $value | humanize }} hours",
        ))
        
        # Uptime Below Target
        rule_set.add_rule(AlertRule(
            name="PhoenixUptimeBelowTarget",
            expression=f'''
                avg_over_time(
                    (sum(phoenix_encounters_active{{tenant_id=~"{self._tenant_filter}"}}) > 0)[24h:1m]
                ) < 0.999
            '''.strip().replace('\n', ''),
            severity=AlertSeverity.HIGH,
            for_duration="0m",
            category=AlertCategory.SLA,
            summary="24h uptime below 99.9%",
            description="Rolling 24h uptime is {{ $value | humanize }}%, below 99.9% SLA",
        ))
        
        return rule_set
    
    # =========================================================================
    # Get All Rules
    # =========================================================================
    
    def get_all_rule_sets(self) -> List[AlertRuleSet]:
        """Get all alert rule sets."""
        return [
            self.get_benchmark_rules(),
            self.get_performance_rules(),
            self.get_security_rules(),
            self.get_availability_rules(),
            self.get_sla_rules(),
        ]
    
    def export_all_rules_yaml(self) -> str:
        """
        Export all rules as Prometheus alerting rules YAML.
        """
        import json
        
        groups = [rs.to_prometheus_format() for rs in self.get_all_rule_sets()]
        
        return json.dumps({"groups": groups}, indent=2)
    
    def get_alertmanager_config(self) -> Dict[str, Any]:
        """
        Get Alertmanager configuration for routing.
        """
        return {
            "global": {
                "resolve_timeout": "5m",
            },
            "route": {
                "group_by": ["alertname", "tenant_id"],
                "group_wait": "10s",
                "group_interval": "10s",
                "repeat_interval": "1h",
                "receiver": "default",
                "routes": [
                    {
                        "match": {"severity": "critical"},
                        "receiver": "pagerduty-critical",
                        "continue": True,
                    },
                    {
                        "match": {"severity": "high"},
                        "receiver": "pagerduty-high",
                    },
                    {
                        "match": {"category": "security"},
                        "receiver": "security-team",
                    },
                    {
                        "match": {"severity": "warning"},
                        "receiver": "slack-warnings",
                    },
                ],
            },
            "receivers": [
                {
                    "name": "default",
                    "slack_configs": [{
                        "channel": "#phoenix-alerts",
                        "send_resolved": True,
                    }],
                },
                {
                    "name": "pagerduty-critical",
                    "pagerduty_configs": [{
                        "service_key": "${PAGERDUTY_CRITICAL_KEY}",
                        "severity": "critical",
                    }],
                },
                {
                    "name": "pagerduty-high",
                    "pagerduty_configs": [{
                        "service_key": "${PAGERDUTY_HIGH_KEY}",
                        "severity": "error",
                    }],
                },
                {
                    "name": "security-team",
                    "slack_configs": [{
                        "channel": "#phoenix-security",
                        "send_resolved": True,
                    }],
                    "pagerduty_configs": [{
                        "service_key": "${PAGERDUTY_SECURITY_KEY}",
                    }],
                },
                {
                    "name": "slack-warnings",
                    "slack_configs": [{
                        "channel": "#phoenix-warnings",
                        "send_resolved": True,
                    }],
                },
            ],
        }
