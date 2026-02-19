"""
V5 Agent Configuration — February 2026.

Settings for the 3 new V5 agents:
- ZebraHunterAgent (rare disease detection via Orphadata)
- SilentVoiceAgent (non-verbal pain detection via vitals z-score)
- TreatmentShadowAgent (long-term drug harm detection via OpenFDA)

Follows the existing @dataclass + from_env() pattern used by
SMTPConfig, SlackConfig, etc. in production_config.py.

This file is completely independent — it does NOT modify any
existing config classes or settings.
"""

import os
import logging
from dataclasses import dataclass
from typing import Dict, Any

logger = logging.getLogger(__name__)


@dataclass
class OrphadataConfig:
    """Orphadata API settings for ZebraHunterAgent."""

    api_key: str = ""
    base_url: str = "https://api.orphadata.com"

    @classmethod
    def from_env(cls) -> "OrphadataConfig":
        """Load Orphadata config from environment."""
        return cls(
            api_key=os.getenv("ORPHADATA_API_KEY", ""),
            base_url=os.getenv("ORPHADATA_BASE_URL", "https://api.orphadata.com"),
        )

    def is_configured(self) -> bool:
        """Check if Orphadata API key is present and not a placeholder."""
        return bool(
            self.api_key
            and self.api_key != "your_orphadata_api_key_here"
        )

    def to_dict(self, mask_secrets: bool = True) -> Dict[str, Any]:
        return {
            "api_key": "***" if mask_secrets and self.api_key else self.api_key,
            "base_url": self.base_url,
            "configured": self.is_configured(),
        }


@dataclass
class OpenFDAConfig:
    """OpenFDA API settings for TreatmentShadowAgent."""

    base_url: str = "https://api.fda.gov"
    drug_event_endpoint: str = "/drug/event.json"

    @classmethod
    def from_env(cls) -> "OpenFDAConfig":
        """Load OpenFDA config from environment."""
        return cls(
            base_url=os.getenv("OPENFDA_BASE_URL", "https://api.fda.gov"),
            drug_event_endpoint=os.getenv(
                "OPENFDA_DRUG_EVENT_ENDPOINT", "/drug/event.json"
            ),
        )

    @property
    def drug_event_url(self) -> str:
        """Full URL for the drug adverse events endpoint."""
        return f"{self.base_url}{self.drug_event_endpoint}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "base_url": self.base_url,
            "drug_event_endpoint": self.drug_event_endpoint,
            "drug_event_url": self.drug_event_url,
        }


@dataclass
class TreatmentShadowConfig:
    """Config for TreatmentShadowAgent trend analysis."""

    trend_threshold_pct: float = -20.0
    min_lab_results: int = 2

    @classmethod
    def from_env(cls) -> "TreatmentShadowConfig":
        """Load TreatmentShadow config from environment."""
        return cls(
            trend_threshold_pct=float(
                os.getenv("SHADOW_TREND_THRESHOLD_PCT", "-20")
            ),
            min_lab_results=int(os.getenv("SHADOW_MIN_LAB_RESULTS", "2")),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trend_threshold_pct": self.trend_threshold_pct,
            "min_lab_results": self.min_lab_results,
        }


@dataclass
class SilentVoiceConfig:
    """Config for SilentVoiceAgent baseline and alerting."""

    baseline_window_minutes: int = 120
    zscore_threshold: float = 2.5
    monitor_interval_seconds: int = 60

    @classmethod
    def from_env(cls) -> "SilentVoiceConfig":
        """Load SilentVoice config from environment."""
        return cls(
            baseline_window_minutes=int(
                os.getenv("SILENT_VOICE_BASELINE_WINDOW_MINUTES", "120")
            ),
            zscore_threshold=float(
                os.getenv("SILENT_VOICE_ZSCORE_THRESHOLD", "2.5")
            ),
            monitor_interval_seconds=int(
                os.getenv("SILENT_VOICE_MONITOR_INTERVAL_SECONDS", "60")
            ),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "baseline_window_minutes": self.baseline_window_minutes,
            "zscore_threshold": self.zscore_threshold,
            "monitor_interval_seconds": self.monitor_interval_seconds,
        }


@dataclass
class GhostProtocolConfig:
    """Config for Ghost Protocol cluster detection (ZebraHunterAgent)."""

    min_cluster: int = 2
    ttl_days: int = 30

    @classmethod
    def from_env(cls) -> "GhostProtocolConfig":
        """Load Ghost Protocol config from environment."""
        return cls(
            min_cluster=int(os.getenv("GHOST_PROTOCOL_MIN_CLUSTER", "2")),
            ttl_days=int(os.getenv("GHOST_PROTOCOL_TTL_DAYS", "30")),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "min_cluster": self.min_cluster,
            "ttl_days": self.ttl_days,
        }


@dataclass
class DemoConfig:
    """Demo mode settings — cached responses for hackathon demos."""

    enabled: bool = False
    cache_ttl_seconds: int = 3600

    @classmethod
    def from_env(cls) -> "DemoConfig":
        """Load demo config from environment."""
        return cls(
            enabled=os.getenv("DEMO_MODE", "false").lower() == "true",
            cache_ttl_seconds=int(os.getenv("DEMO_CACHE_TTL_SECONDS", "3600")),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "enabled": self.enabled,
            "cache_ttl_seconds": self.cache_ttl_seconds,
        }


@dataclass
class V5AgentSettings:
    """
    Unified settings for all 3 V5 agents — February 2026.

    Usage:
        from phoenix_guardian.config.v5_agent_config import v5_settings
        print(v5_settings.orphadata.base_url)
        print(v5_settings.silent_voice.zscore_threshold)
    """

    orphadata: OrphadataConfig
    openfda: OpenFDAConfig
    treatment_shadow: TreatmentShadowConfig
    silent_voice: SilentVoiceConfig
    ghost_protocol: GhostProtocolConfig
    demo: DemoConfig

    @classmethod
    def from_env(cls) -> "V5AgentSettings":
        """Load all V5 settings from environment."""
        return cls(
            orphadata=OrphadataConfig.from_env(),
            openfda=OpenFDAConfig.from_env(),
            treatment_shadow=TreatmentShadowConfig.from_env(),
            silent_voice=SilentVoiceConfig.from_env(),
            ghost_protocol=GhostProtocolConfig.from_env(),
            demo=DemoConfig.from_env(),
        )

    def to_dict(self, mask_secrets: bool = True) -> Dict[str, Any]:
        return {
            "orphadata": self.orphadata.to_dict(mask_secrets=mask_secrets),
            "openfda": self.openfda.to_dict(),
            "treatment_shadow": self.treatment_shadow.to_dict(),
            "silent_voice": self.silent_voice.to_dict(),
            "ghost_protocol": self.ghost_protocol.to_dict(),
            "demo": self.demo.to_dict(),
        }


# ── Instantiate V5 settings — import this in new agents ────────────────────
v5_settings = V5AgentSettings.from_env()
