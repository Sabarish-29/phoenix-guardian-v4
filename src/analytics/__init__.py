"""
Phoenix Guardian Enterprise Analytics Module.

Provides ROI calculations and executive reporting capabilities
for healthcare organizations using the Phoenix Guardian platform.
"""

from .roi_calculator import (
    ROIInput,
    ROIResult,
    ROICalculator,
    AVG_HEALTHCARE_BREACH_COST_USD,
    TRADITIONAL_DOC_TIME_MINUTES,
    PHYSICIAN_HOURLY_RATE_USD,
    DEFAULT_PLATFORM_COST_USD,
)
from .executive_report import ExecutiveReportGenerator

__all__ = [
    "ROIInput",
    "ROIResult",
    "ROICalculator",
    "ExecutiveReportGenerator",
    "AVG_HEALTHCARE_BREACH_COST_USD",
    "TRADITIONAL_DOC_TIME_MINUTES",
    "PHYSICIAN_HOURLY_RATE_USD",
    "DEFAULT_PLATFORM_COST_USD",
]
