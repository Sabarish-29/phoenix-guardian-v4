"""
Phoenix Guardian - Clinical Decision Support Engine
Sprint 65-66: CDS Expansion

FHIR CDS Hooks implementation for clinical decision support
integrated with SOAP note generation.
"""

import asyncio
import hashlib
import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


class CDSHookType(Enum):
    """Standard CDS Hooks triggers."""
    
    PATIENT_VIEW = "patient-view"
    ORDER_SELECT = "order-select"
    ORDER_SIGN = "order-sign"
    MEDICATION_PRESCRIBE = "medication-prescribe"
    ENCOUNTER_START = "encounter-start"
    ENCOUNTER_DISCHARGE = "encounter-discharge"
    APPOINTMENT_BOOK = "appointment-book"
    
    # Phoenix Guardian custom hooks
    SOAP_NOTE_DRAFT = "soap-note-draft"
    SOAP_NOTE_SIGN = "soap-note-sign"
    DIAGNOSIS_SUGGEST = "diagnosis-suggest"


class CardIndicator(Enum):
    """CDS Card urgency indicators."""
    
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class CardSource(Enum):
    """Card source types for transparency."""
    
    CLINICAL_GUIDELINE = "clinical_guideline"
    DRUG_DATABASE = "drug_database"
    LAB_REFERENCE = "lab_reference"
    AI_INFERENCE = "ai_inference"
    LOCAL_PROTOCOL = "local_protocol"


@dataclass
class CDSCard:
    """CDS Hooks Card response."""
    
    uuid: str = field(default_factory=lambda: str(uuid4()))
    summary: str = ""
    detail: str = ""
    indicator: CardIndicator = CardIndicator.INFO
    source_label: str = "Phoenix Guardian"
    source_url: Optional[str] = None
    source_icon: Optional[str] = None
    source_type: CardSource = CardSource.AI_INFERENCE
    
    # Suggestions (actions user can take)
    suggestions: list[dict[str, Any]] = field(default_factory=list)
    
    # Links for more information
    links: list[dict[str, str]] = field(default_factory=list)
    
    # Override reasons if user dismisses
    override_reasons: list[str] = field(default_factory=list)
    
    # Selection behavior for suggestions
    selection_behavior: str = "at-most-one"
    
    # Metadata
    created_at: datetime = field(default_factory=datetime.utcnow)
    rule_id: Optional[str] = None
    evidence_grade: Optional[str] = None  # A, B, C, D for evidence quality
    
    def to_fhir(self) -> dict[str, Any]:
        """Convert to FHIR CDS Hooks card format."""
        card = {
            "uuid": self.uuid,
            "summary": self.summary,
            "detail": self.detail,
            "indicator": self.indicator.value,
            "source": {
                "label": self.source_label,
            },
            "selectionBehavior": self.selection_behavior,
        }
        
        if self.source_url:
            card["source"]["url"] = self.source_url
        if self.source_icon:
            card["source"]["icon"] = self.source_icon
        
        if self.suggestions:
            card["suggestions"] = self.suggestions
        if self.links:
            card["links"] = self.links
        if self.override_reasons:
            card["overrideReasons"] = [
                {"code": r, "display": r} for r in self.override_reasons
            ]
        
        return card


@dataclass
class CDSRequest:
    """CDS Hooks request context."""
    
    hook: CDSHookType
    hook_instance: str = field(default_factory=lambda: str(uuid4()))
    
    # FHIR server info
    fhir_server: Optional[str] = None
    fhir_authorization: Optional[dict[str, str]] = None
    
    # Context data (varies by hook)
    context: dict[str, Any] = field(default_factory=dict)
    
    # Prefetch data (pre-fetched FHIR resources)
    prefetch: dict[str, Any] = field(default_factory=dict)
    
    # Hospital/tenant context
    hospital_id: str = ""
    user_id: str = ""
    
    # Request metadata
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    @property
    def patient_id(self) -> Optional[str]:
        """Extract patient ID from context."""
        if "patientId" in self.context:
            return self.context["patientId"]
        if "patient" in self.prefetch:
            return self.prefetch["patient"].get("id")
        return None
    
    @property
    def encounter_id(self) -> Optional[str]:
        """Extract encounter ID from context."""
        return self.context.get("encounterId")


@dataclass
class CDSResponse:
    """CDS Hooks response."""
    
    cards: list[CDSCard] = field(default_factory=list)
    system_actions: list[dict[str, Any]] = field(default_factory=list)
    
    # Metadata
    hook_instance: str = ""
    latency_ms: float = 0.0
    rules_evaluated: int = 0
    
    def to_fhir(self) -> dict[str, Any]:
        """Convert to FHIR CDS Hooks response format."""
        return {
            "cards": [card.to_fhir() for card in self.cards],
            "systemActions": self.system_actions,
        }


class CDSRule(ABC):
    """Abstract base class for CDS rules."""
    
    rule_id: str
    name: str
    description: str
    version: str
    enabled: bool = True
    
    # Which hooks trigger this rule
    hooks: list[CDSHookType]
    
    # Priority (lower = higher priority, evaluated first)
    priority: int = 100
    
    # Evidence grade
    evidence_grade: str = "C"
    
    @abstractmethod
    async def evaluate(self, request: CDSRequest) -> list[CDSCard]:
        """Evaluate the rule and return cards."""
        pass
    
    @abstractmethod
    def prefetch_templates(self) -> dict[str, str]:
        """Return FHIR query templates for prefetch."""
        pass


class DrugInteractionRule(CDSRule):
    """Check for drug-drug interactions."""
    
    rule_id = "drug-interaction-001"
    name = "Drug-Drug Interaction Check"
    description = "Alerts for potential drug interactions"
    version = "1.0.0"
    hooks = [CDSHookType.MEDICATION_PRESCRIBE, CDSHookType.ORDER_SELECT]
    priority = 10
    evidence_grade = "A"
    
    # Known critical interactions (simplified for demo)
    CRITICAL_INTERACTIONS = {
        ("warfarin", "aspirin"): {
            "severity": CardIndicator.CRITICAL,
            "summary": "Warfarin + Aspirin: Increased bleeding risk",
            "detail": "Concurrent use of warfarin and aspirin significantly "
                     "increases the risk of major bleeding events. Consider "
                     "alternative antiplatelet therapy or adjust warfarin dosing.",
        },
        ("metformin", "contrast"): {
            "severity": CardIndicator.WARNING,
            "summary": "Metformin: Hold before contrast procedures",
            "detail": "Metformin should be held 48 hours before and after "
                     "iodinated contrast administration to reduce risk of "
                     "contrast-induced nephropathy and lactic acidosis.",
        },
        ("ssri", "maoi"): {
            "severity": CardIndicator.CRITICAL,
            "summary": "SSRI + MAOI: Serotonin syndrome risk",
            "detail": "Concurrent use of SSRIs and MAOIs can cause potentially "
                     "fatal serotonin syndrome. A 2-week washout period is required.",
        },
    }
    
    def prefetch_templates(self) -> dict[str, str]:
        return {
            "patient": "Patient/{{context.patientId}}",
            "medications": "MedicationRequest?patient={{context.patientId}}&status=active",
        }
    
    async def evaluate(self, request: CDSRequest) -> list[CDSCard]:
        cards = []
        
        # Get current medications from prefetch
        current_meds = self._extract_medications(request.prefetch.get("medications", {}))
        
        # Get new medication from context
        new_med = request.context.get("draftOrders", {}).get("medication", "").lower()
        
        if not new_med:
            return cards
        
        # Check for interactions
        for (drug1, drug2), interaction_info in self.CRITICAL_INTERACTIONS.items():
            if new_med in drug1 or drug1 in new_med:
                for current in current_meds:
                    if drug2 in current or current in drug2:
                        cards.append(CDSCard(
                            summary=interaction_info["summary"],
                            detail=interaction_info["detail"],
                            indicator=interaction_info["severity"],
                            source_type=CardSource.DRUG_DATABASE,
                            source_label="Phoenix Guardian Drug Interaction Database",
                            rule_id=self.rule_id,
                            evidence_grade=self.evidence_grade,
                            override_reasons=[
                                "Patient tolerating combination",
                                "Benefits outweigh risks",
                                "Will monitor closely",
                            ],
                            suggestions=[
                                {
                                    "label": "Review current medications",
                                    "uuid": str(uuid4()),
                                    "actions": [{
                                        "type": "update",
                                        "description": "Flag for pharmacy review",
                                    }]
                                }
                            ],
                        ))
        
        return cards
    
    def _extract_medications(self, med_bundle: dict) -> list[str]:
        """Extract medication names from FHIR MedicationRequest bundle."""
        meds = []
        entries = med_bundle.get("entry", [])
        for entry in entries:
            resource = entry.get("resource", {})
            if resource.get("resourceType") == "MedicationRequest":
                med_ref = resource.get("medicationCodeableConcept", {})
                coding = med_ref.get("coding", [{}])[0]
                display = coding.get("display", "").lower()
                if display:
                    meds.append(display)
        return meds


class LabCriticalValueRule(CDSRule):
    """Alert for critical lab values."""
    
    rule_id = "lab-critical-001"
    name = "Critical Lab Value Alert"
    description = "Alerts for critical lab values requiring immediate attention"
    version = "1.0.0"
    hooks = [CDSHookType.PATIENT_VIEW, CDSHookType.SOAP_NOTE_DRAFT]
    priority = 5
    evidence_grade = "A"
    
    # Critical lab ranges
    CRITICAL_VALUES = {
        "potassium": {"low": 2.5, "high": 6.5, "unit": "mEq/L"},
        "sodium": {"low": 120, "high": 160, "unit": "mEq/L"},
        "glucose": {"low": 40, "high": 500, "unit": "mg/dL"},
        "hemoglobin": {"low": 7.0, "high": 20.0, "unit": "g/dL"},
        "platelets": {"low": 20, "high": 1000, "unit": "K/uL"},
        "inr": {"low": None, "high": 5.0, "unit": "ratio"},
        "creatinine": {"low": None, "high": 10.0, "unit": "mg/dL"},
        "troponin": {"low": None, "high": 0.04, "unit": "ng/mL"},
    }
    
    def prefetch_templates(self) -> dict[str, str]:
        return {
            "patient": "Patient/{{context.patientId}}",
            "labs": "Observation?patient={{context.patientId}}&category=laboratory&_sort=-date&_count=50",
        }
    
    async def evaluate(self, request: CDSRequest) -> list[CDSCard]:
        cards = []
        
        labs = request.prefetch.get("labs", {})
        entries = labs.get("entry", [])
        
        for entry in entries:
            resource = entry.get("resource", {})
            if resource.get("resourceType") != "Observation":
                continue
            
            # Get lab name and value
            coding = resource.get("code", {}).get("coding", [{}])[0]
            lab_name = coding.get("display", "").lower()
            
            value_quantity = resource.get("valueQuantity", {})
            value = value_quantity.get("value")
            
            if value is None:
                continue
            
            # Check against critical ranges
            for lab_type, ranges in self.CRITICAL_VALUES.items():
                if lab_type in lab_name:
                    if ranges["low"] and value < ranges["low"]:
                        cards.append(self._create_critical_card(
                            lab_name, value, ranges["unit"], "critically low", ranges["low"]
                        ))
                    elif ranges["high"] and value > ranges["high"]:
                        cards.append(self._create_critical_card(
                            lab_name, value, ranges["unit"], "critically high", ranges["high"]
                        ))
                    break
        
        return cards
    
    def _create_critical_card(
        self, 
        lab_name: str, 
        value: float, 
        unit: str,
        status: str,
        threshold: float
    ) -> CDSCard:
        return CDSCard(
            summary=f"CRITICAL: {lab_name.title()} is {status}",
            detail=f"Current value: {value} {unit} (threshold: {threshold} {unit}). "
                   f"Immediate clinical attention may be required.",
            indicator=CardIndicator.CRITICAL,
            source_type=CardSource.LAB_REFERENCE,
            source_label="Phoenix Guardian Lab Monitoring",
            rule_id=self.rule_id,
            evidence_grade=self.evidence_grade,
            links=[{
                "label": "View full lab results",
                "url": "/labs/patient/{{patientId}}",
                "type": "smart"
            }],
        )


class SOAPQualityRule(CDSRule):
    """Quality checks for SOAP note generation."""
    
    rule_id = "soap-quality-001"
    name = "SOAP Note Quality Check"
    description = "Ensures SOAP notes meet documentation standards"
    version = "1.0.0"
    hooks = [CDSHookType.SOAP_NOTE_DRAFT, CDSHookType.SOAP_NOTE_SIGN]
    priority = 50
    evidence_grade = "B"
    
    # Minimum section lengths (characters)
    MIN_LENGTHS = {
        "subjective": 50,
        "objective": 100,
        "assessment": 50,
        "plan": 100,
    }
    
    def prefetch_templates(self) -> dict[str, str]:
        return {
            "patient": "Patient/{{context.patientId}}",
        }
    
    async def evaluate(self, request: CDSRequest) -> list[CDSCard]:
        cards = []
        
        soap_note = request.context.get("soapNote", {})
        
        for section, min_length in self.MIN_LENGTHS.items():
            content = soap_note.get(section, "")
            if len(content) < min_length:
                cards.append(CDSCard(
                    summary=f"SOAP {section.title()} section may be incomplete",
                    detail=f"The {section} section contains only {len(content)} "
                           f"characters. Consider expanding for complete documentation.",
                    indicator=CardIndicator.WARNING,
                    source_type=CardSource.LOCAL_PROTOCOL,
                    source_label="Phoenix Guardian Documentation Standards",
                    rule_id=self.rule_id,
                    suggestions=[{
                        "label": f"Expand {section} section",
                        "uuid": str(uuid4()),
                    }],
                ))
        
        # Check for diagnosis code
        if not soap_note.get("icd10_codes"):
            cards.append(CDSCard(
                summary="No diagnosis codes assigned",
                detail="SOAP note is missing ICD-10 diagnosis codes. "
                       "Please assign appropriate diagnosis codes before signing.",
                indicator=CardIndicator.WARNING,
                source_type=CardSource.LOCAL_PROTOCOL,
                rule_id=self.rule_id,
            ))
        
        return cards


class AlertFatigueManager:
    """
    Manages alert fatigue by tracking user interactions and adjusting thresholds.
    
    Key strategies:
    1. Track dismissal rates per rule
    2. Suppress low-value repeated alerts
    3. Aggregate similar alerts
    4. Personalize based on user specialty
    """
    
    def __init__(self, redis_client=None):
        self.redis = redis_client
        self._local_cache: dict[str, dict] = {}
        
        # Default suppression thresholds
        self.dismissal_threshold = 0.7  # Suppress if 70%+ dismissed
        self.min_samples = 10  # Minimum samples before suppression
        self.cooldown_hours = 4  # Hours before repeating alert
    
    async def should_suppress(
        self,
        card: CDSCard,
        user_id: str,
        patient_id: str,
    ) -> bool:
        """Determine if alert should be suppressed."""
        
        # Never suppress critical alerts
        if card.indicator == CardIndicator.CRITICAL:
            return False
        
        # Check cooldown for same patient/rule combination
        key = self._cache_key(card.rule_id, user_id, patient_id)
        
        last_shown = await self._get_last_shown(key)
        if last_shown:
            elapsed = datetime.utcnow() - last_shown
            if elapsed < timedelta(hours=self.cooldown_hours):
                logger.debug(f"Suppressing {card.rule_id}: cooldown active")
                return True
        
        # Check user's dismissal rate for this rule
        stats = await self._get_rule_stats(card.rule_id, user_id)
        if stats["total"] >= self.min_samples:
            dismissal_rate = stats["dismissed"] / stats["total"]
            if dismissal_rate > self.dismissal_threshold:
                logger.info(
                    f"Suppressing {card.rule_id} for user {user_id}: "
                    f"{dismissal_rate:.1%} dismissal rate"
                )
                return True
        
        return False
    
    async def record_interaction(
        self,
        card_uuid: str,
        user_id: str,
        action: str,  # "accepted", "dismissed", "override"
        override_reason: Optional[str] = None,
    ) -> None:
        """Record user interaction with alert."""
        interaction = {
            "card_uuid": card_uuid,
            "user_id": user_id,
            "action": action,
            "override_reason": override_reason,
            "timestamp": datetime.utcnow().isoformat(),
        }
        
        # Store for analytics
        if self.redis:
            key = f"cds:interaction:{card_uuid}"
            await self.redis.set(key, json.dumps(interaction), ex=86400 * 30)
        
        logger.info(f"CDS interaction: {action} on {card_uuid}")
    
    async def get_fatigue_report(self, user_id: str) -> dict[str, Any]:
        """Generate alert fatigue report for user."""
        # In production, aggregate from Redis/database
        return {
            "user_id": user_id,
            "report_date": datetime.utcnow().isoformat(),
            "total_alerts": 0,
            "accepted": 0,
            "dismissed": 0,
            "override_rate": 0.0,
            "top_dismissed_rules": [],
            "recommendations": [],
        }
    
    def _cache_key(self, rule_id: str, user_id: str, patient_id: str) -> str:
        return f"cds:shown:{rule_id}:{user_id}:{patient_id}"
    
    async def _get_last_shown(self, key: str) -> Optional[datetime]:
        if self.redis:
            val = await self.redis.get(key)
            if val:
                return datetime.fromisoformat(val.decode())
        return self._local_cache.get(key, {}).get("last_shown")
    
    async def _get_rule_stats(self, rule_id: str, user_id: str) -> dict:
        # Simplified - in production, aggregate from database
        return {"total": 0, "dismissed": 0, "accepted": 0}


class CDSEngine:
    """
    Main Clinical Decision Support Engine.
    
    Integrates with FHIR CDS Hooks specification for EHR interoperability.
    """
    
    def __init__(self, config: Optional[dict] = None):
        self.config = config or {}
        self.rules: list[CDSRule] = []
        self.fatigue_manager = AlertFatigueManager()
        
        # Rule registry by hook type
        self._hook_rules: dict[CDSHookType, list[CDSRule]] = {}
        
        # Initialize default rules
        self._register_default_rules()
    
    def _register_default_rules(self) -> None:
        """Register default CDS rules."""
        self.register_rule(DrugInteractionRule())
        self.register_rule(LabCriticalValueRule())
        self.register_rule(SOAPQualityRule())
    
    def register_rule(self, rule: CDSRule) -> None:
        """Register a CDS rule."""
        self.rules.append(rule)
        
        for hook in rule.hooks:
            if hook not in self._hook_rules:
                self._hook_rules[hook] = []
            self._hook_rules[hook].append(rule)
        
        # Sort by priority
        for hook in rule.hooks:
            self._hook_rules[hook].sort(key=lambda r: r.priority)
        
        logger.info(f"Registered CDS rule: {rule.rule_id}")
    
    def get_service_definition(self) -> dict[str, Any]:
        """
        Return CDS Hooks service discovery document.
        Endpoint: GET /cds-services
        """
        services = []
        
        for hook_type in CDSHookType:
            if hook_type in self._hook_rules:
                # Aggregate prefetch templates
                prefetch = {}
                for rule in self._hook_rules[hook_type]:
                    prefetch.update(rule.prefetch_templates())
                
                services.append({
                    "id": f"phoenix-{hook_type.value}",
                    "hook": hook_type.value,
                    "title": f"Phoenix Guardian - {hook_type.value.replace('-', ' ').title()}",
                    "description": f"Clinical decision support for {hook_type.value}",
                    "prefetch": prefetch,
                })
        
        return {
            "services": services,
        }
    
    async def evaluate(self, request: CDSRequest) -> CDSResponse:
        """
        Evaluate all applicable rules for a CDS request.
        Endpoint: POST /cds-services/{service-id}
        """
        start_time = datetime.utcnow()
        cards: list[CDSCard] = []
        rules_evaluated = 0
        
        # Get rules for this hook
        applicable_rules = self._hook_rules.get(request.hook, [])
        
        for rule in applicable_rules:
            if not rule.enabled:
                continue
            
            try:
                rules_evaluated += 1
                rule_cards = await rule.evaluate(request)
                
                # Apply alert fatigue filtering
                for card in rule_cards:
                    if request.user_id and request.patient_id:
                        if await self.fatigue_manager.should_suppress(
                            card, request.user_id, request.patient_id
                        ):
                            continue
                    cards.append(card)
                    
            except Exception as e:
                logger.error(f"Error evaluating rule {rule.rule_id}: {e}")
        
        # Sort cards by indicator severity
        severity_order = {
            CardIndicator.CRITICAL: 0,
            CardIndicator.WARNING: 1,
            CardIndicator.INFO: 2,
        }
        cards.sort(key=lambda c: severity_order.get(c.indicator, 99))
        
        latency = (datetime.utcnow() - start_time).total_seconds() * 1000
        
        return CDSResponse(
            cards=cards,
            hook_instance=request.hook_instance,
            latency_ms=latency,
            rules_evaluated=rules_evaluated,
        )
    
    async def record_feedback(
        self,
        card_uuid: str,
        user_id: str,
        action: str,
        override_reason: Optional[str] = None,
    ) -> None:
        """
        Record user feedback on CDS card.
        Endpoint: POST /cds-services/{service-id}/feedback
        """
        await self.fatigue_manager.record_interaction(
            card_uuid, user_id, action, override_reason
        )
    
    def get_rule_by_id(self, rule_id: str) -> Optional[CDSRule]:
        """Get rule by ID."""
        for rule in self.rules:
            if rule.rule_id == rule_id:
                return rule
        return None
    
    def enable_rule(self, rule_id: str) -> bool:
        """Enable a CDS rule."""
        rule = self.get_rule_by_id(rule_id)
        if rule:
            rule.enabled = True
            return True
        return False
    
    def disable_rule(self, rule_id: str) -> bool:
        """Disable a CDS rule."""
        rule = self.get_rule_by_id(rule_id)
        if rule:
            rule.enabled = False
            return True
        return False


# FastAPI integration
def create_cds_router():
    """Create FastAPI router for CDS Hooks endpoints."""
    from fastapi import APIRouter, Request, HTTPException
    
    router = APIRouter(prefix="/cds-services", tags=["CDS Hooks"])
    engine = CDSEngine()
    
    @router.get("/")
    async def discovery():
        """CDS Hooks service discovery."""
        return engine.get_service_definition()
    
    @router.post("/{service_id}")
    async def evaluate_hook(service_id: str, request: Request):
        """Evaluate CDS hook."""
        body = await request.json()
        
        # Parse hook type
        hook_name = service_id.replace("phoenix-", "")
        try:
            hook_type = CDSHookType(hook_name)
        except ValueError:
            raise HTTPException(404, f"Unknown service: {service_id}")
        
        # Build CDS request
        cds_request = CDSRequest(
            hook=hook_type,
            hook_instance=body.get("hookInstance", str(uuid4())),
            fhir_server=body.get("fhirServer"),
            fhir_authorization=body.get("fhirAuthorization"),
            context=body.get("context", {}),
            prefetch=body.get("prefetch", {}),
            hospital_id=request.headers.get("X-Hospital-ID", ""),
            user_id=request.headers.get("X-User-ID", ""),
        )
        
        response = await engine.evaluate(cds_request)
        return response.to_fhir()
    
    @router.post("/{service_id}/feedback")
    async def feedback(service_id: str, request: Request):
        """Record user feedback on CDS cards."""
        body = await request.json()
        
        await engine.record_feedback(
            card_uuid=body.get("card"),
            user_id=request.headers.get("X-User-ID", ""),
            action=body.get("outcome"),
            override_reason=body.get("overrideReason"),
        )
        
        return {"status": "recorded"}
    
    return router
