"""
Tests for Monitoring Collector (CC4, CC7).

Tests collection of availability, performance, and backup evidence.
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

from phoenix_guardian.compliance.monitoring_collector import (
    MonitoringCollector,
)
from phoenix_guardian.compliance.evidence_types import (
    AvailabilityEvidence,
    PerformanceEvidence,
    TSCCriterion,
    EvidenceType,
    EvidenceSource,
)

