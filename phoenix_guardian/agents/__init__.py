"""Phoenix Guardian Agents Package.

This package contains all AI agents used in the Phoenix Guardian system:
- BaseAgent: Abstract foundation for all agents
- ScribeAgent: Generates SOAP notes from transcripts
- NavigatorAgent: Fetches patient context from EHR
- SafetyAgent: Detects adversarial prompts and validates outputs
- SentinelQAgent: Master security coordinator (Phase 2)
- CodingAgent: Medical coding assistant (Phase 2, Week 10)
- PriorAuthAgent: Insurance pre-authorization (Phase 2, Week 10)
- QualityAgent: Clinical guideline adherence (Phase 2, Week 10)
- OrdersAgent: Lab/imaging order validation (Phase 2, Week 10)
"""

from phoenix_guardian.agents.base_agent import AgentResult, BaseAgent
from phoenix_guardian.agents.coding_agent import (
    CodingAgent,
    CodingResult,
    CPTCode,
    EncounterType,
    ICD10Code,
)
from phoenix_guardian.agents.prior_auth_agent import (
    PriorAuthAgent,
    InsuranceInfo,
    PreAuthForm,
    PreAuthResult,
    Urgency,
    AuthType,
    ApprovalLikelihood,
)
from phoenix_guardian.agents.quality_agent import (
    QualityAgent,
    QualityFlag,
    QualityResult,
    PatientInfo,
    LabResult,
    Severity,
    GuidelineSource,
    QualityCategory,
)
from phoenix_guardian.agents.orders_agent import (
    OrdersAgent,
    Order,
    RecentOrder,
    PatientContext,
    ValidatedOrder,
    SuggestedOrder,
    CostOptimization,
    OrdersResult,
    OrderType,
    Urgency as OrderUrgency,
    OrderStatus,
    Priority,
)
from phoenix_guardian.agents.navigator_agent import (
    NavigatorAgent,
    PatientNotFoundError,
    create_mock_patient_database,
)
from phoenix_guardian.agents.safety_agent import (
    SafetyAgent,
    SecurityException,
    ThreatDetection,
    ThreatLevel,
    ThreatType,
)
from phoenix_guardian.agents.scribe_agent import ScribeAgent
from phoenix_guardian.agents.sentinel_q_agent import (
    SentinelQAgent,
    SecurityAction,
    SentinelDecision,
    ThreatIntelligence,
)
from phoenix_guardian.agents.sentinelq_integration import (
    SentinelQDeceptionBridge,
)

__all__ = [
    # Base
    "AgentResult",
    "BaseAgent",
    # Scribe
    "ScribeAgent",
    # Navigator
    "NavigatorAgent",
    "PatientNotFoundError",
    "create_mock_patient_database",
    # Safety
    "SafetyAgent",
    "SecurityException",
    "ThreatDetection",
    "ThreatLevel",
    "ThreatType",
    # Sentinel-Q
    "SentinelQAgent",
    "SecurityAction",
    "SentinelDecision",
    "ThreatIntelligence",
    # SentinelQ Deception Bridge
    "SentinelQDeceptionBridge",
    # Coding (Week 10)
    "CodingAgent",
    "CodingResult",
    "CPTCode",
    "EncounterType",
    "ICD10Code",
    # Prior Auth (Week 10)
    "PriorAuthAgent",
    "InsuranceInfo",
    "PreAuthForm",
    "PreAuthResult",
    "Urgency",
    "AuthType",
    "ApprovalLikelihood",
    # Quality (Week 10)
    "QualityAgent",
    "QualityFlag",
    "QualityResult",
    "PatientInfo",
    "LabResult",
    "Severity",
    "GuidelineSource",
    "QualityCategory",
    # Orders (Week 10)
    "OrdersAgent",
    "Order",
    "RecentOrder",
    "PatientContext",
    "ValidatedOrder",
    "SuggestedOrder",
    "CostOptimization",
    "OrdersResult",
    "OrderType",
    "OrderUrgency",
    "OrderStatus",
    "Priority",
]
