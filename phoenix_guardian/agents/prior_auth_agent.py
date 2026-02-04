"""
Insurance Pre-Authorization Agent

The PriorAuthAgent determines if procedures/medications require
insurance pre-authorization and generates pre-auth request forms.

Supported Features:
- Pre-auth determination by carrier and procedure
- Form generation with clinical rationale
- Urgency-based timeline adjustment
- Approval likelihood estimation
- Alternative procedure suggestions
"""

import re
import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import structlog

from phoenix_guardian.agents.base_agent import BaseAgent

logger = structlog.get_logger(__name__)


class Urgency(Enum):
    """Urgency levels for prior authorization."""
    EMERGENCY = "emergency"
    URGENT = "urgent"
    ROUTINE = "routine"


class AuthType(Enum):
    """Types of authorization."""
    PRIOR_AUTHORIZATION = "prior_authorization"
    PREDETERMINATION = "predetermination"
    REFERRAL = "referral"
    NONE = "none"


class ApprovalLikelihood(Enum):
    """Likelihood of approval."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNCERTAIN = "uncertain"


@dataclass
class InsuranceInfo:
    """Insurance carrier information."""
    carrier: str
    plan_type: str
    member_id: str
    group_number: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


@dataclass
class PreAuthForm:
    """Pre-authorization request form."""
    form_type: str
    fields: Dict[str, Any]
    required_attachments: List[str]
    submission_method: str
    carrier_contact: Dict[str, str]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


@dataclass
class PreAuthResult:
    """Result of prior authorization check."""
    requires_auth: bool
    auth_type: str
    estimated_timeline: str
    bypass_conditions: List[str]
    required_documents: List[str]
    pre_auth_form: Optional[PreAuthForm]
    approval_likelihood: str
    alternative_procedures: List[Dict[str, Any]]
    carrier_specific_notes: str
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = {
            "requires_auth": self.requires_auth,
            "auth_type": self.auth_type,
            "estimated_timeline": self.estimated_timeline,
            "bypass_conditions": self.bypass_conditions,
            "required_documents": self.required_documents,
            "pre_auth_form": self.pre_auth_form.to_dict() if self.pre_auth_form else None,
            "approval_likelihood": self.approval_likelihood,
            "alternative_procedures": self.alternative_procedures,
            "carrier_specific_notes": self.carrier_specific_notes,
        }
        return result


class PriorAuthAgent(BaseAgent):
    """
    Insurance pre-authorization agent.
    
    Determines if procedures/medications require prior authorization,
    generates request forms, and estimates approval likelihood.
    """
    
    # Insurance carrier rules
    CARRIER_RULES: Dict[str, Dict[str, Any]] = {
        "blue cross blue shield": {
            "aliases": ["bcbs", "blue cross", "bluecross"],
            "requires_auth_procedures": [
                "70553",  # MRI Brain
                "74177",  # CT Abdomen/Pelvis with contrast
                "74176",  # CT Abdomen/Pelvis without contrast
                "93458",  # Cardiac catheterization
                "29881",  # Knee arthroscopy
                "95810",  # Sleep study
                "81200", "81201", "81202", "81203", "81204", "81205",  # Genetic testing
                "27447",  # Total knee replacement
                "27130",  # Total hip replacement
            ],
            "no_auth_procedures": [
                "71045", "71046", "71047", "71048",  # Chest X-rays
                "85025",  # CBC
                "80053",  # CMP
                "80048",  # BMP
                "93000",  # EKG
                "99211", "99212", "99213", "99214", "99215",  # Office visits
            ],
            "timeline_routine": "3-5 business days",
            "timeline_urgent": "24-48 hours",
            "contact": {
                "phone": "1-800-676-BLUE",
                "fax": "1-888-555-1234",
                "portal_url": "https://provider.bcbs.com/prior-auth",
                "hours": "M-F 8am-8pm ET, 24/7 for urgent",
            },
        },
        "unitedhealthcare": {
            "aliases": ["uhc", "united", "united healthcare", "unitedhealth"],
            "requires_auth_procedures": [
                "70553",  # MRI Brain
                "74177",  # CT Abdomen/Pelvis
                "70552",  # MRI Brain without contrast
                "72148",  # MRI Lumbar spine
                "93458",  # Cardiac cath
                "29881",  # Knee arthroscopy
                "95810",  # Sleep study
                "27447",  # Total knee replacement
                "27130",  # Total hip replacement
                "43239",  # Upper GI endoscopy
            ],
            "no_auth_procedures": [
                "71045", "71046",  # Chest X-rays
                "85025",  # CBC
                "80053",  # CMP
                "93000",  # EKG
                "76700",  # Ultrasound abdomen
                "99211", "99212", "99213", "99214", "99215",  # Office visits
                "G0105", "G0121",  # Screening colonoscopy (preventive)
            ],
            "timeline_routine": "2-4 business days",
            "timeline_urgent": "24 hours",
            "contact": {
                "phone": "1-877-842-3210",
                "fax": "1-888-912-4567",
                "portal_url": "https://www.uhcprovider.com/prior-auth",
                "hours": "24/7",
            },
        },
        "medicare": {
            "aliases": ["medicare original", "cms"],
            "requires_auth_procedures": [
                "K0800", "K0801", "K0802", "K0803", "K0804",  # Power wheelchairs
                "K0805", "K0806", "K0807", "K0808", "K0809",  # Power wheelchairs
                "E0601",  # CPAP
                "E0260", "E0261",  # Hospital beds
                "A0426",  # Non-emergency ambulance transport
            ],
            "no_auth_procedures": [
                "70553",  # MRI (covered without auth)
                "74177",  # CT
                "93458",  # Cardiac cath
                "85025",  # CBC
                "80053",  # CMP
                "93000",  # EKG
                "99211", "99212", "99213", "99214", "99215",  # Office visits
                "G0105", "G0121",  # Screening colonoscopy
            ],
            "timeline_routine": "10 business days",
            "timeline_urgent": "72 hours",
            "contact": {
                "phone": "1-800-MEDICARE",
                "fax": "1-888-555-6789",
                "portal_url": "https://www.cms.gov/prior-auth",
                "hours": "24/7",
            },
        },
        "medicare advantage": {
            "aliases": ["ma plan", "medicare part c"],
            "requires_auth_procedures": [
                "70553",  # MRI Brain
                "74177",  # CT Abdomen/Pelvis
                "93458",  # Cardiac cath
                "29881",  # Knee arthroscopy
                "27447",  # Total knee replacement
                "27130",  # Total hip replacement
            ],
            "no_auth_procedures": [
                "85025",  # CBC
                "80053",  # CMP
                "93000",  # EKG
                "99211", "99212", "99213", "99214", "99215",  # Office visits
            ],
            "timeline_routine": "3-7 business days",
            "timeline_urgent": "24-72 hours",
            "contact": {
                "phone": "Varies by plan",
                "fax": "Varies by plan",
                "portal_url": "Check member card",
                "hours": "Varies by plan",
            },
        },
        "medicaid": {
            "aliases": ["state medicaid", "medical assistance"],
            "requires_auth_procedures": [
                "70553",  # MRI Brain
                "74177",  # CT
                "29881",  # Knee arthroscopy
                "A0426",  # Non-emergency transport
                "E0601",  # CPAP
            ],
            "no_auth_procedures": [
                "85025",  # CBC
                "80053",  # CMP
                "93000",  # EKG
                "99211", "99212", "99213", "99214", "99215",  # Office visits
            ],
            "timeline_routine": "5-10 business days",
            "timeline_urgent": "24-48 hours",
            "contact": {
                "phone": "State-specific",
                "fax": "State-specific",
                "portal_url": "State-specific portal",
                "hours": "M-F 8am-5pm",
            },
        },
    }
    
    # Procedure categories for classification
    PROCEDURE_CATEGORIES: Dict[str, Dict[str, Any]] = {
        # Imaging - often requires auth
        "70553": {"name": "MRI Brain with contrast", "category": "imaging", "cost": "high"},
        "70552": {"name": "MRI Brain without contrast", "category": "imaging", "cost": "high"},
        "72148": {"name": "MRI Lumbar spine", "category": "imaging", "cost": "high"},
        "74177": {"name": "CT Abdomen/Pelvis with contrast", "category": "imaging", "cost": "high"},
        "74176": {"name": "CT Abdomen/Pelvis without contrast", "category": "imaging", "cost": "medium"},
        "74150": {"name": "CT Abdomen without contrast", "category": "imaging", "cost": "medium"},
        
        # X-rays - typically no auth
        "71045": {"name": "Chest X-ray single view", "category": "imaging", "cost": "low"},
        "71046": {"name": "Chest X-ray 2 views", "category": "imaging", "cost": "low"},
        
        # Cardiac procedures
        "93458": {"name": "Cardiac catheterization", "category": "procedure", "cost": "high"},
        "93000": {"name": "Electrocardiogram (EKG)", "category": "diagnostic", "cost": "low"},
        
        # Orthopedic
        "29881": {"name": "Knee arthroscopy with meniscectomy", "category": "surgery", "cost": "high"},
        "27447": {"name": "Total knee arthroplasty", "category": "surgery", "cost": "high"},
        "27130": {"name": "Total hip arthroplasty", "category": "surgery", "cost": "high"},
        
        # Labs - no auth
        "85025": {"name": "Complete blood count (CBC)", "category": "lab", "cost": "low"},
        "80053": {"name": "Comprehensive metabolic panel (CMP)", "category": "lab", "cost": "low"},
        "80048": {"name": "Basic metabolic panel (BMP)", "category": "lab", "cost": "low"},
        
        # Office visits - no auth
        "99213": {"name": "Office visit, established, low complexity", "category": "evaluation", "cost": "low"},
        "99214": {"name": "Office visit, established, moderate", "category": "evaluation", "cost": "low"},
        "99215": {"name": "Office visit, established, high", "category": "evaluation", "cost": "medium"},
        
        # Sleep study
        "95810": {"name": "Polysomnography", "category": "diagnostic", "cost": "medium"},
        
        # DME - Medicare requires auth
        "K0800": {"name": "Power wheelchair group 1", "category": "dme", "cost": "high"},
        "E0601": {"name": "CPAP device", "category": "dme", "cost": "medium"},
        
        # Ultrasound
        "76700": {"name": "Ultrasound abdomen complete", "category": "imaging", "cost": "low"},
    }
    
    # Diagnosis-procedure pairings for approval estimation
    EVIDENCE_BASED_PAIRINGS: Dict[str, List[str]] = {
        "93458": ["I21.09", "I21.11", "I21.21", "I25.10", "I20.0"],  # Cardiac cath - cardiac diagnoses
        "70553": ["G43.909", "R51.9", "G40.909", "C71.9"],  # MRI Brain - headache, seizure, tumor
        "29881": ["M23.20", "M23.21", "S83.20"],  # Knee scope - meniscus tear
        "95810": ["G47.33", "R06.83"],  # Sleep study - apnea, snoring
    }
    
    # Alternative procedures by original procedure
    ALTERNATIVES: Dict[str, List[Dict[str, Any]]] = {
        "74177": [  # CT Abdomen with contrast
            {
                "procedure": "CT Abdomen without contrast",
                "cpt_code": "74150",
                "rationale": "Non-contrast CT may be appropriate if contrast allergy or renal impairment",
                "requires_auth": False,
            },
            {
                "procedure": "Ultrasound Abdomen",
                "cpt_code": "76700",
                "rationale": "Less expensive alternative for initial evaluation",
                "requires_auth": False,
            },
        ],
        "70553": [  # MRI Brain with contrast
            {
                "procedure": "MRI Brain without contrast",
                "cpt_code": "70552",
                "rationale": "Non-contrast MRI may be sufficient for initial evaluation",
                "requires_auth": True,
            },
            {
                "procedure": "CT Head without contrast",
                "cpt_code": "70450",
                "rationale": "CT is faster and may be appropriate for acute symptoms",
                "requires_auth": False,
            },
        ],
    }
    
    def __init__(self, **kwargs: Any) -> None:
        """Initialize PriorAuthAgent."""
        super().__init__(name="PriorAuth", **kwargs)
        logger.info("PriorAuthAgent initialized")
    
    async def _run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Check prior authorization requirements and generate forms.
        
        Args:
            context: Must contain:
                - 'procedure_code' (str): CPT code
                - 'insurance' (dict): Carrier, plan_type, member_id
                - 'urgency' (str, optional): "routine", "urgent", "emergency"
                - 'diagnosis_codes' (list, optional): ICD-10 codes
                - 'clinical_rationale' (str, optional): Medical necessity text
        
        Returns:
            Dict with PreAuthResult data and reasoning
        """
        start_time = time.perf_counter()
        
        # Extract and validate inputs
        procedure_code = context.get("procedure_code")
        if not procedure_code:
            raise ValueError("Procedure code is required for prior authorization check")
        
        insurance_data = context.get("insurance", {})
        if not insurance_data or not insurance_data.get("carrier"):
            raise ValueError("Insurance carrier information is required")
        
        # Parse insurance info
        insurance = InsuranceInfo(
            carrier=insurance_data.get("carrier", ""),
            plan_type=insurance_data.get("plan_type", ""),
            member_id=insurance_data.get("member_id", ""),
            group_number=insurance_data.get("group_number"),
        )
        
        # Parse urgency
        urgency_str = context.get("urgency", "routine").lower()
        try:
            urgency = Urgency(urgency_str)
        except ValueError:
            urgency = Urgency.ROUTINE
        
        # Get optional fields
        diagnosis_codes = context.get("diagnosis_codes", [])
        procedure_name = context.get("procedure_name", "")
        clinical_rationale = context.get("clinical_rationale", "")
        patient_age = context.get("patient_age")
        
        # Normalize carrier name
        carrier_key = self._normalize_carrier(insurance.carrier)
        
        # Check if procedure requires prior auth
        requires_auth, carrier_rules = self._check_requires_auth(
            carrier_key, procedure_code
        )
        
        # Determine urgency impact
        urgency_result = self._determine_urgency_impact(
            urgency, procedure_code, diagnosis_codes
        )
        
        # Override requires_auth for emergencies
        if urgency == Urgency.EMERGENCY:
            requires_auth = False
        
        # Determine auth type
        auth_type = self._determine_auth_type(requires_auth, carrier_key, procedure_code)
        
        # Calculate timeline
        timeline = self._determine_timeline(
            carrier_rules, urgency, urgency_result
        )
        
        # Get required documents
        required_docs = self._get_required_documents(
            procedure_code, diagnosis_codes, carrier_key
        )
        
        # Get bypass conditions
        bypass_conditions = self._get_bypass_conditions(urgency, procedure_code)
        
        # Estimate approval likelihood
        approval_likelihood = self._estimate_approval_likelihood(
            procedure_code, diagnosis_codes, clinical_rationale
        )
        
        # Get alternative procedures if low approval likelihood
        alternatives = []
        if approval_likelihood in [ApprovalLikelihood.LOW, ApprovalLikelihood.UNCERTAIN]:
            alternatives = self._suggest_alternatives(procedure_code)
        
        # Generate pre-auth form if auth required
        pre_auth_form = None
        if requires_auth:
            pre_auth_form = self._generate_form(
                procedure_code=procedure_code,
                procedure_name=procedure_name or self._get_procedure_name(procedure_code),
                diagnosis_codes=diagnosis_codes,
                insurance=insurance,
                clinical_rationale=clinical_rationale,
                urgency=urgency,
                carrier_rules=carrier_rules,
            )
        
        # Build carrier-specific notes
        carrier_notes = self._build_carrier_notes(
            carrier_key, procedure_code, requires_auth, approval_likelihood
        )
        
        # Build result
        result = PreAuthResult(
            requires_auth=requires_auth,
            auth_type=auth_type.value,
            estimated_timeline=timeline,
            bypass_conditions=bypass_conditions,
            required_documents=required_docs,
            pre_auth_form=pre_auth_form,
            approval_likelihood=approval_likelihood.value,
            alternative_procedures=alternatives,
            carrier_specific_notes=carrier_notes,
        )
        
        # Build reasoning
        reasoning = self._build_reasoning(
            requires_auth, carrier_key, procedure_code,
            urgency, approval_likelihood, diagnosis_codes
        )
        
        processing_time = (time.perf_counter() - start_time) * 1000
        
        logger.info(
            "Prior auth check complete",
            procedure_code=procedure_code,
            carrier=insurance.carrier,
            requires_auth=requires_auth,
            approval_likelihood=approval_likelihood.value,
            processing_time_ms=f"{processing_time:.2f}",
        )
        
        return {
            "data": result.to_dict(),
            "reasoning": reasoning,
        }
    
    def _normalize_carrier(self, carrier: str) -> str:
        """Normalize carrier name to match our rules."""
        carrier_lower = carrier.lower().strip()
        
        for key, rules in self.CARRIER_RULES.items():
            if carrier_lower == key:
                return key
            if carrier_lower in rules.get("aliases", []):
                return key
        
        # Unknown carrier
        return "unknown"
    
    def _check_requires_auth(
        self,
        carrier_key: str,
        procedure_code: str,
    ) -> Tuple[bool, Dict[str, Any]]:
        """Check if procedure requires prior auth for carrier."""
        if carrier_key == "unknown":
            # Default to requiring auth for unknown carriers
            return True, {}
        
        rules = self.CARRIER_RULES.get(carrier_key, {})
        
        # Check if explicitly no auth
        no_auth_procedures = rules.get("no_auth_procedures", [])
        if procedure_code in no_auth_procedures:
            return False, rules
        
        # Check if explicitly requires auth
        requires_auth_procedures = rules.get("requires_auth_procedures", [])
        if procedure_code in requires_auth_procedures:
            return True, rules
        
        # Default: Check procedure category
        proc_info = self.PROCEDURE_CATEGORIES.get(procedure_code, {})
        cost = proc_info.get("cost", "unknown")
        
        # High-cost procedures typically require auth
        if cost == "high":
            return True, rules
        
        return False, rules
    
    def _determine_urgency_impact(
        self,
        urgency: Urgency,
        procedure_code: str,
        diagnosis_codes: List[str],
    ) -> Dict[str, Any]:
        """Determine impact of urgency on authorization."""
        if urgency == Urgency.EMERGENCY:
            return {
                "bypass": True,
                "bypass_reason": "Emergency services bypass prior authorization per federal law (EMTALA)",
                "timeline": "Retrospective review within 72 hours",
                "notes": "Proceed with procedure. Submit documentation within 72 hours for retrospective review.",
            }
        
        # Check for urgent conditions
        urgent_diagnosis_prefixes = ["I21", "I63", "A41", "J96"]  # STEMI, stroke, sepsis, respiratory failure
        
        if urgency == Urgency.URGENT:
            is_truly_urgent = any(
                any(code.startswith(prefix) for prefix in urgent_diagnosis_prefixes)
                for code in diagnosis_codes
            )
            if is_truly_urgent:
                return {
                    "bypass": False,
                    "expedited": True,
                    "timeline": "24-48 hours (expedited review)",
                    "notes": "Request expedited peer-to-peer review. Consider proceeding if life-threatening.",
                }
        
        return {
            "bypass": False,
            "expedited": False,
            "timeline": "Standard processing",
            "notes": "Standard prior authorization process",
        }
    
    def _determine_auth_type(
        self,
        requires_auth: bool,
        carrier_key: str,
        procedure_code: str,
    ) -> AuthType:
        """Determine the type of authorization required."""
        if not requires_auth:
            return AuthType.NONE
        
        # DME often requires predetermination
        proc_info = self.PROCEDURE_CATEGORIES.get(procedure_code, {})
        if proc_info.get("category") == "dme":
            return AuthType.PREDETERMINATION
        
        # Specialist visits might need referral
        if carrier_key in ["medicaid"] and proc_info.get("category") == "evaluation":
            return AuthType.REFERRAL
        
        return AuthType.PRIOR_AUTHORIZATION
    
    def _determine_timeline(
        self,
        carrier_rules: Dict[str, Any],
        urgency: Urgency,
        urgency_result: Dict[str, Any],
    ) -> str:
        """Calculate expected approval timeline."""
        if urgency == Urgency.EMERGENCY:
            return "Retrospective review within 72 hours"
        
        if urgency_result.get("expedited"):
            return urgency_result.get("timeline", "24-48 hours")
        
        if urgency == Urgency.URGENT:
            return carrier_rules.get("timeline_urgent", "24-48 hours")
        
        return carrier_rules.get("timeline_routine", "3-5 business days")
    
    def _get_required_documents(
        self,
        procedure_code: str,
        diagnosis_codes: List[str],
        carrier_key: str,
    ) -> List[str]:
        """Get list of required documents for authorization."""
        docs = ["Physician clinical notes documenting medical necessity"]
        
        proc_info = self.PROCEDURE_CATEGORIES.get(procedure_code, {})
        category = proc_info.get("category", "")
        
        if category == "imaging":
            docs.extend([
                "Previous imaging results (if available)",
                "History of conservative treatment",
            ])
        
        if category == "surgery":
            docs.extend([
                "Operative report (if revision)",
                "Physical therapy notes (if applicable)",
                "Conservative treatment history",
            ])
        
        # Cardiac-specific
        if procedure_code in ["93458"]:
            docs.extend([
                "EKG results",
                "Cardiac enzyme levels (troponin)",
                "Stress test results (if applicable)",
            ])
        
        # DME-specific
        if category == "dme":
            docs.extend([
                "Certificate of Medical Necessity (CMN)",
                "Face-to-face evaluation notes",
            ])
        
        # Add diagnosis-specific docs
        for code in diagnosis_codes:
            if code.startswith("I21"):  # MI
                if "Cardiac enzyme levels (troponin)" not in docs:
                    docs.append("Cardiac enzyme levels (troponin)")
                if "EKG results" not in docs:
                    docs.append("EKG results")
        
        return docs
    
    def _get_bypass_conditions(
        self,
        urgency: Urgency,
        procedure_code: str,
    ) -> List[str]:
        """Get conditions that bypass prior authorization."""
        conditions = []
        
        if urgency == Urgency.EMERGENCY:
            conditions.append(
                "Emergency services bypass prior authorization per federal law (EMTALA)"
            )
        
        proc_info = self.PROCEDURE_CATEGORIES.get(procedure_code, {})
        
        if procedure_code in ["93458"]:  # Cardiac cath
            conditions.append(
                "Emergency STEMI cases may proceed with retrospective review"
            )
        
        if proc_info.get("category") == "imaging":
            conditions.append(
                "Inpatient imaging during admission typically doesn't require separate auth"
            )
        
        return conditions
    
    def _estimate_approval_likelihood(
        self,
        procedure_code: str,
        diagnosis_codes: List[str],
        clinical_rationale: str,
    ) -> ApprovalLikelihood:
        """Estimate likelihood of approval based on medical necessity."""
        rationale_lower = clinical_rationale.lower()
        
        # High likelihood indicators
        high_indicators = [
            "guideline" in rationale_lower,
            "aha" in rationale_lower or "acc" in rationale_lower,  # Cardiology guidelines
            "evidence-based" in rationale_lower,
            "emergency" in rationale_lower,
            "life-threatening" in rationale_lower,
            "acute" in rationale_lower,
        ]
        
        # Check diagnosis-procedure pairing
        expected_diagnoses = self.EVIDENCE_BASED_PAIRINGS.get(procedure_code, [])
        has_matching_diagnosis = any(
            any(code.startswith(expected[:3]) for expected in expected_diagnoses)
            for code in diagnosis_codes
        )
        if has_matching_diagnosis:
            high_indicators.append(True)
        
        if sum(high_indicators) >= 2:
            return ApprovalLikelihood.HIGH
        
        # Low likelihood indicators - check BEFORE medium
        # These indicate likely denial regardless of supporting diagnoses
        low_indicators = [
            "screening" in rationale_lower and "average risk" in rationale_lower,
            "experimental" in rationale_lower,
            "investigational" in rationale_lower,
            "cosmetic" in rationale_lower,
        ]
        
        if any(low_indicators):
            return ApprovalLikelihood.LOW
        
        # Medium likelihood indicators
        medium_indicators = [
            "symptomatic" in rationale_lower,
            "failed conservative" in rationale_lower,
            "refractory" in rationale_lower,
            "persistent" in rationale_lower,
            len(diagnosis_codes) > 0,  # Has supporting diagnoses
        ]
        
        if any(medium_indicators):
            return ApprovalLikelihood.MEDIUM
        
        return ApprovalLikelihood.UNCERTAIN
    
    def _suggest_alternatives(
        self,
        procedure_code: str,
    ) -> List[Dict[str, Any]]:
        """Suggest alternative procedures if denial likely."""
        return self.ALTERNATIVES.get(procedure_code, [])
    
    def _get_procedure_name(self, procedure_code: str) -> str:
        """Get procedure name from code."""
        proc_info = self.PROCEDURE_CATEGORIES.get(procedure_code, {})
        return proc_info.get("name", f"Procedure {procedure_code}")
    
    def _generate_form(
        self,
        procedure_code: str,
        procedure_name: str,
        diagnosis_codes: List[str],
        insurance: InsuranceInfo,
        clinical_rationale: str,
        urgency: Urgency,
        carrier_rules: Dict[str, Any],
    ) -> PreAuthForm:
        """Generate pre-authorization request form."""
        # Build form fields
        fields = {
            "patient_name": "[FROM PATIENT CONTEXT]",
            "member_id": insurance.member_id,
            "group_number": insurance.group_number or "[N/A]",
            "diagnosis_codes": ", ".join(diagnosis_codes) if diagnosis_codes else "[REQUIRED]",
            "diagnosis_descriptions": "[FROM ICD-10 LOOKUP]",
            "procedure_code": procedure_code,
            "procedure_description": procedure_name,
            "clinical_rationale": clinical_rationale or "[REQUIRED - Document medical necessity]",
            "physician_name": "[REQUIRED]",
            "physician_npi": "[REQUIRED]",
            "facility_name": "[REQUIRED]",
            "requested_date": "[REQUIRED]",
            "urgency_level": urgency.value,
        }
        
        # Determine required attachments
        proc_info = self.PROCEDURE_CATEGORIES.get(procedure_code, {})
        attachments = ["Clinical notes"]
        
        if proc_info.get("category") == "imaging":
            attachments.extend(["Previous imaging (if applicable)", "Conservative treatment records"])
        
        if procedure_code in ["93458"]:  # Cardiac
            attachments.extend(["EKG report", "Lab results (troponin)"])
        
        if proc_info.get("category") == "dme":
            attachments.extend(["Certificate of Medical Necessity", "Face-to-face notes"])
        
        # Determine submission method
        submission_method = "portal" if carrier_rules.get("contact", {}).get("portal_url") else "fax"
        
        return PreAuthForm(
            form_type="prior_authorization",
            fields=fields,
            required_attachments=attachments,
            submission_method=submission_method,
            carrier_contact=carrier_rules.get("contact", {
                "phone": "Contact carrier directly",
                "fax": "Contact carrier directly",
                "portal_url": "Check member card",
                "hours": "Business hours",
            }),
        )
    
    def _build_carrier_notes(
        self,
        carrier_key: str,
        procedure_code: str,
        requires_auth: bool,
        approval_likelihood: ApprovalLikelihood,
    ) -> str:
        """Build carrier-specific notes and recommendations."""
        notes = []
        
        if carrier_key == "unknown":
            notes.append("Unknown carrier. Contact insurance directly to verify prior auth requirements.")
            return " ".join(notes)
        
        carrier_name = carrier_key.title()
        proc_name = self._get_procedure_name(procedure_code)
        
        if requires_auth:
            notes.append(f"{carrier_name} typically requires prior authorization for {proc_name}.")
            
            if approval_likelihood == ApprovalLikelihood.HIGH:
                notes.append("High approval likelihood given clear medical necessity.")
            elif approval_likelihood == ApprovalLikelihood.LOW:
                notes.append("Consider peer-to-peer review if initial denial received.")
            
            if carrier_key in ["blue cross blue shield", "unitedhealthcare"]:
                notes.append("Consider peer-to-peer discussion if denied.")
        else:
            notes.append(f"{carrier_name} does not require prior authorization for {proc_name}.")
        
        return " ".join(notes)
    
    def _build_reasoning(
        self,
        requires_auth: bool,
        carrier_key: str,
        procedure_code: str,
        urgency: Urgency,
        approval_likelihood: ApprovalLikelihood,
        diagnosis_codes: List[str],
    ) -> str:
        """Build human-readable reasoning."""
        parts = []
        
        proc_name = self._get_procedure_name(procedure_code)
        carrier_name = carrier_key.title() if carrier_key != "unknown" else "this carrier"
        
        if urgency == Urgency.EMERGENCY:
            parts.append(
                f"Emergency case - {proc_name} can proceed without prior authorization "
                f"per EMTALA requirements. Submit documentation for retrospective review."
            )
        elif requires_auth:
            parts.append(
                f"{proc_name} (CPT {procedure_code}) requires prior authorization "
                f"for {carrier_name}."
            )
            
            if urgency == Urgency.URGENT:
                parts.append("Urgent request qualifies for expedited review.")
            
            parts.append(f"Approval likelihood: {approval_likelihood.value}.")
            
            if diagnosis_codes:
                parts.append(f"Supporting diagnoses: {', '.join(diagnosis_codes)}.")
        else:
            parts.append(
                f"{proc_name} (CPT {procedure_code}) does not require prior authorization "
                f"for {carrier_name}."
            )
        
        return " ".join(parts)
