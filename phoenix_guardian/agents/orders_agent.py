"""
OrdersAgent - Lab and imaging order validation agent.

Validates medical orders, detects duplicates, checks contraindications,
and suggests additional tests based on clinical protocols.
"""

from enum import Enum
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime, date, timedelta
import re

from .base_agent import BaseAgent


class OrderType(Enum):
    """Type of medical order."""
    LAB = "lab"
    IMAGING = "imaging"
    PROCEDURE = "procedure"


class Urgency(Enum):
    """Urgency level for orders."""
    STAT = "stat"  # Immediate (within 1 hour)
    URGENT = "urgent"  # Within 4 hours
    ROUTINE = "routine"  # Within 24 hours
    SCHEDULED = "scheduled"  # Scheduled appointment


class OrderStatus(Enum):
    """Validation status of order."""
    APPROVED = "approved"
    DUPLICATE = "duplicate"
    CONTRAINDICATED = "contraindicated"
    QUESTIONABLE = "questionable"  # May not be appropriate
    MODIFIED = "modified"  # Suggest modification


class Priority(Enum):
    """Priority level for suggested orders."""
    CRITICAL = "critical"  # Life-threatening if not ordered
    HIGH = "high"  # Important for diagnosis/management
    MEDIUM = "medium"  # Helpful but not essential
    LOW = "low"  # Nice to have


@dataclass
class Order:
    """Medical order (lab or imaging)."""
    test: str  # "CBC", "MRI Brain", etc.
    order_type: OrderType
    urgency: Urgency = Urgency.ROUTINE
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "test": self.test,
            "order_type": self.order_type.value,
            "urgency": self.urgency.value
        }


@dataclass
class RecentOrder:
    """Previously completed order."""
    test: str
    date: date
    result: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "test": self.test,
            "date": self.date.isoformat() if self.date else None,
            "result": self.result
        }


@dataclass
class PatientContext:
    """Patient clinical context for order validation."""
    age: int
    sex: str
    creatinine: Optional[float] = None  # mg/dL
    egfr: Optional[float] = None  # mL/min/1.73m²
    allergies: List[str] = field(default_factory=list)
    pregnancy_status: Optional[str] = None  # "pregnant", "not_pregnant", "unknown"
    weight_kg: Optional[float] = None
    conditions: List[str] = field(default_factory=list)  # Active diagnoses
    has_pacemaker: bool = False
    has_icd: bool = False
    on_metformin: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "age": self.age,
            "sex": self.sex,
            "creatinine": self.creatinine,
            "egfr": self.egfr,
            "allergies": self.allergies,
            "pregnancy_status": self.pregnancy_status,
            "weight_kg": self.weight_kg,
            "conditions": self.conditions,
            "has_pacemaker": self.has_pacemaker,
            "has_icd": self.has_icd,
            "on_metformin": self.on_metformin
        }


@dataclass
class ValidatedOrder:
    """Validation result for a single order."""
    test: str
    status: OrderStatus
    issue: Optional[str] = None
    recommendation: Optional[str] = None
    contraindications: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "test": self.test,
            "status": self.status.value,
            "issue": self.issue,
            "recommendation": self.recommendation,
            "contraindications": self.contraindications
        }


@dataclass
class SuggestedOrder:
    """Suggested additional order."""
    test: str
    rationale: str
    urgency: Urgency
    priority: Priority
    order_type: OrderType
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "test": self.test,
            "rationale": self.rationale,
            "urgency": self.urgency.value,
            "priority": self.priority.value,
            "order_type": self.order_type.value
        }


@dataclass
class CostOptimization:
    """Cost optimization recommendation."""
    current_cost: float
    optimized_cost: float
    savings: float
    suggestion: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "current_cost": self.current_cost,
            "optimized_cost": self.optimized_cost,
            "savings": self.savings,
            "suggestion": self.suggestion
        }


@dataclass
class OrdersResult:
    """Result of order validation."""
    validated_orders: List[ValidatedOrder]
    suggested_additions: List[SuggestedOrder]
    panel_recommendations: List[str]
    contraindications: List[str]
    cost_optimization: Optional[CostOptimization]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "validated_orders": [o.to_dict() for o in self.validated_orders],
            "suggested_additions": [s.to_dict() for s in self.suggested_additions],
            "panel_recommendations": self.panel_recommendations,
            "contraindications": self.contraindications,
            "cost_optimization": self.cost_optimization.to_dict() if self.cost_optimization else None
        }


class OrdersAgent(BaseAgent):
    """Lab and imaging order validation agent."""
    
    # Test validity periods in days (stable patient)
    # Format: {test_name: (stable_days, acute_days)}
    TEST_VALIDITY_PERIODS: Dict[str, Tuple[int, int]] = {
        # Labs
        "cbc": (7, 1),
        "cbc with differential": (7, 1),
        "bmp": (3, 1),
        "cmp": (3, 1),
        "liver enzymes": (14, 3),
        "hepatic function panel": (14, 3),
        "lipid panel": (90, 90),
        "hba1c": (90, 90),
        "tsh": (180, 180),
        "pt/inr": (7, 1),
        "ptt": (7, 1),
        "troponin": (0, 0),  # Serial - never reuse
        "d-dimer": (1, 1),
        "blood cultures": (0, 0),  # Never reuse
        "lactate": (1, 1),
        "procalcitonin": (1, 1),
        "urinalysis": (7, 1),
        "glucose": (1, 1),
        "bun": (3, 1),
        "creatinine": (3, 1),
        "potassium": (3, 1),
        "sodium": (3, 1),
        "magnesium": (7, 1),
        "phosphorus": (7, 1),
        "bnp": (3, 1),
        "nt-probnp": (3, 1),
        "blood gas": (0, 0),  # Never reuse
        "abg": (0, 0),
        "vbg": (0, 0),
        "beta-hydroxybutyrate": (1, 1),
        "urine ketones": (1, 1),
        # Imaging
        "chest x-ray": (7, 1),
        "cxr": (7, 1),
        "ct abdomen": (30, 7),
        "ct pelvis": (30, 7),
        "ct abdomen/pelvis": (30, 7),
        "ct head": (30, 1),
        "ct chest": (30, 7),
        "mri": (30, 30),
        "mri brain": (30, 7),
        "ultrasound": (30, 7),
        "renal ultrasound": (30, 7),
        "echocardiogram": (30, 30),
        "carotid ultrasound": (90, 30),
        "ekg": (7, 1),
    }
    
    # Test costs in USD
    TEST_COSTS: Dict[str, float] = {
        "cbc": 35.0,
        "cbc with differential": 45.0,
        "bmp": 45.0,
        "cmp": 50.0,
        "liver enzymes": 40.0,
        "hepatic function panel": 55.0,
        "lipid panel": 50.0,
        "hba1c": 35.0,
        "tsh": 40.0,
        "pt/inr": 25.0,
        "ptt": 25.0,
        "troponin": 45.0,
        "d-dimer": 50.0,
        "blood cultures": 60.0,
        "lactate": 35.0,
        "procalcitonin": 75.0,
        "urinalysis": 15.0,
        "glucose": 10.0,
        "bnp": 55.0,
        "nt-probnp": 65.0,
        "blood gas": 45.0,
        "abg": 45.0,
        "vbg": 40.0,
        "beta-hydroxybutyrate": 40.0,
        "chest x-ray": 75.0,
        "cxr": 75.0,
        "ct head": 350.0,
        "ct abdomen": 500.0,
        "ct chest": 450.0,
        "ct abdomen/pelvis": 600.0,
        "mri brain": 800.0,
        "mri": 700.0,
        "ultrasound": 200.0,
        "renal ultrasound": 200.0,
        "echocardiogram": 350.0,
        "carotid ultrasound": 250.0,
        "ekg": 50.0,
    }
    
    # Panel equivalents: individual tests -> panel recommendation
    PANEL_RECOMMENDATIONS: Dict[str, Dict[str, Any]] = {
        "bmp": {
            "recommend": "cmp",
            "cost_diff": 5.0,
            "additional_values": ["ALT", "AST", "Alkaline phosphatase", "Bilirubin", "Albumin", "Protein"],
            "message": "Order CMP instead of BMP for comprehensive metabolic assessment (only $5 more, provides 6 additional values)"
        },
        "cbc": {
            "recommend": "cbc with differential",
            "cost_diff": 10.0,
            "condition": "infection",  # Only recommend if infection suspected
            "additional_values": ["neutrophils", "lymphocytes", "monocytes", "eosinophils", "basophils"],
            "message": "Order CBC with differential if infection suspected ($10 more, critical for diagnosis)"
        },
    }
    
    # Diagnosis protocols - ICD-10 prefix -> required/recommended tests
    DIAGNOSIS_PROTOCOLS: Dict[str, Dict[str, Any]] = {
        # Sepsis (A41.x)
        "sepsis": {
            "icd10_prefixes": ["A41", "A40", "R65.2"],
            "keywords": ["sepsis", "septic", "bacteremia"],
            "required": [
                {"test": "Blood cultures x2", "rationale": "Required before antibiotic administration in sepsis. Two sets from different sites recommended.", "urgency": Urgency.STAT, "priority": Priority.CRITICAL, "order_type": OrderType.LAB},
                {"test": "Lactate", "rationale": "Sepsis workup incomplete without lactate level. Elevated lactate (>2 mmol/L) indicates tissue hypoperfusion and guides resuscitation (Surviving Sepsis Campaign guidelines).", "urgency": Urgency.STAT, "priority": Priority.CRITICAL, "order_type": OrderType.LAB},
                {"test": "CBC with differential", "rationale": "Essential for sepsis workup - WBC count, left shift, bandemia.", "urgency": Urgency.STAT, "priority": Priority.CRITICAL, "order_type": OrderType.LAB},
                {"test": "CMP", "rationale": "Essential for sepsis - electrolytes, creatinine, liver enzymes.", "urgency": Urgency.STAT, "priority": Priority.CRITICAL, "order_type": OrderType.LAB},
            ],
            "recommended": [
                {"test": "Procalcitonin", "rationale": "Helps differentiate bacterial vs. viral infection and guide antibiotic therapy.", "urgency": Urgency.STAT, "priority": Priority.HIGH, "order_type": OrderType.LAB},
                {"test": "Urinalysis with reflex culture", "rationale": "Identify urinary source of sepsis (especially common in elderly females).", "urgency": Urgency.STAT, "priority": Priority.HIGH, "order_type": OrderType.LAB},
                {"test": "Chest X-ray", "rationale": "Identify pulmonary source of sepsis (pneumonia).", "urgency": Urgency.STAT, "priority": Priority.HIGH, "order_type": OrderType.IMAGING},
            ]
        },
        # Chest Pain / ACS (I20.x, I21.x)
        "chest_pain": {
            "icd10_prefixes": ["I20", "I21", "I22", "I24", "I25", "R07.9"],
            "keywords": ["chest pain", "acs", "acute coronary", "stemi", "nstemi", "angina", "mi", "myocardial infarction"],
            "required": [
                {"test": "Troponin", "rationale": "Serial troponins essential for ACS diagnosis (at presentation, 3 hours, 6 hours).", "urgency": Urgency.STAT, "priority": Priority.CRITICAL, "order_type": OrderType.LAB},
                {"test": "EKG", "rationale": "Immediate EKG for STEMI identification - door-to-EKG <10 minutes.", "urgency": Urgency.STAT, "priority": Priority.CRITICAL, "order_type": OrderType.PROCEDURE},
                {"test": "CMP", "rationale": "Electrolytes and creatinine essential for cardiac workup.", "urgency": Urgency.STAT, "priority": Priority.CRITICAL, "order_type": OrderType.LAB},
            ],
            "recommended": [
                {"test": "CBC", "rationale": "Rule out anemia as cause of chest pain/angina.", "urgency": Urgency.STAT, "priority": Priority.HIGH, "order_type": OrderType.LAB},
                {"test": "Chest X-ray", "rationale": "Rule out pneumonia, aortic dissection, other causes.", "urgency": Urgency.STAT, "priority": Priority.HIGH, "order_type": OrderType.IMAGING},
                {"test": "BNP", "rationale": "Assess for heart failure if dyspnea present.", "urgency": Urgency.STAT, "priority": Priority.MEDIUM, "order_type": OrderType.LAB},
                {"test": "D-dimer", "rationale": "If PE suspected based on Wells score.", "urgency": Urgency.STAT, "priority": Priority.MEDIUM, "order_type": OrderType.LAB},
            ]
        },
        # Diabetic Ketoacidosis (E10.1, E11.1)
        "dka": {
            "icd10_prefixes": ["E10.1", "E11.1", "E13.1"],
            "keywords": ["dka", "diabetic ketoacidosis", "ketoacidosis"],
            "required": [
                {"test": "Glucose", "rationale": "Serum glucose essential for DKA diagnosis and monitoring.", "urgency": Urgency.STAT, "priority": Priority.CRITICAL, "order_type": OrderType.LAB},
                {"test": "BMP", "rationale": "Anion gap calculation, potassium monitoring critical in DKA.", "urgency": Urgency.STAT, "priority": Priority.CRITICAL, "order_type": OrderType.LAB},
                {"test": "Blood gas", "rationale": "Venous or arterial blood gas for pH and bicarbonate.", "urgency": Urgency.STAT, "priority": Priority.CRITICAL, "order_type": OrderType.LAB},
                {"test": "Beta-hydroxybutyrate", "rationale": "Ketone measurement - more accurate than urine ketones.", "urgency": Urgency.STAT, "priority": Priority.CRITICAL, "order_type": OrderType.LAB},
            ],
            "recommended": [
                {"test": "CBC", "rationale": "Rule out infection as DKA precipitant.", "urgency": Urgency.STAT, "priority": Priority.HIGH, "order_type": OrderType.LAB},
                {"test": "Phosphorus", "rationale": "Monitor during DKA treatment - shifts with insulin.", "urgency": Urgency.STAT, "priority": Priority.HIGH, "order_type": OrderType.LAB},
                {"test": "Magnesium", "rationale": "Often depleted in DKA.", "urgency": Urgency.STAT, "priority": Priority.HIGH, "order_type": OrderType.LAB},
                {"test": "Urinalysis", "rationale": "Rule out UTI as DKA precipitant.", "urgency": Urgency.STAT, "priority": Priority.HIGH, "order_type": OrderType.LAB},
                {"test": "HbA1c", "rationale": "Assess chronic glycemic control.", "urgency": Urgency.ROUTINE, "priority": Priority.MEDIUM, "order_type": OrderType.LAB},
            ]
        },
        # Stroke (I63.x)
        "stroke": {
            "icd10_prefixes": ["I63", "I64", "G45"],
            "keywords": ["stroke", "cva", "cerebrovascular", "tia", "transient ischemic"],
            "required": [
                {"test": "CT head without contrast", "rationale": "Rule out hemorrhage before tPA - door-to-CT <25 minutes.", "urgency": Urgency.STAT, "priority": Priority.CRITICAL, "order_type": OrderType.IMAGING},
                {"test": "Glucose", "rationale": "Fingerstick glucose - hypoglycemia can mimic stroke.", "urgency": Urgency.STAT, "priority": Priority.CRITICAL, "order_type": OrderType.LAB},
                {"test": "PT/INR", "rationale": "Required if considering tPA - must be <1.7.", "urgency": Urgency.STAT, "priority": Priority.CRITICAL, "order_type": OrderType.LAB},
                {"test": "PTT", "rationale": "Coagulation status for thrombolytic eligibility.", "urgency": Urgency.STAT, "priority": Priority.CRITICAL, "order_type": OrderType.LAB},
            ],
            "recommended": [
                {"test": "CBC", "rationale": "Platelet count needed for tPA eligibility (>100k).", "urgency": Urgency.STAT, "priority": Priority.HIGH, "order_type": OrderType.LAB},
                {"test": "CMP", "rationale": "Electrolytes and renal function.", "urgency": Urgency.STAT, "priority": Priority.HIGH, "order_type": OrderType.LAB},
                {"test": "Troponin", "rationale": "Cardiac workup - stroke can cause cardiac injury.", "urgency": Urgency.STAT, "priority": Priority.HIGH, "order_type": OrderType.LAB},
                {"test": "EKG", "rationale": "Identify atrial fibrillation as stroke etiology.", "urgency": Urgency.STAT, "priority": Priority.HIGH, "order_type": OrderType.PROCEDURE},
                {"test": "Lipid panel", "rationale": "Cardiovascular risk assessment.", "urgency": Urgency.ROUTINE, "priority": Priority.MEDIUM, "order_type": OrderType.LAB},
            ]
        },
        # Acute Kidney Injury (N17.x)
        "aki": {
            "icd10_prefixes": ["N17"],
            "keywords": ["aki", "acute kidney injury", "acute renal failure", "arf"],
            "required": [
                {"test": "BMP", "rationale": "Creatinine, potassium, bicarbonate essential for AKI assessment.", "urgency": Urgency.STAT, "priority": Priority.CRITICAL, "order_type": OrderType.LAB},
                {"test": "Urinalysis", "rationale": "Assess for intrinsic renal disease, casts, proteinuria.", "urgency": Urgency.STAT, "priority": Priority.CRITICAL, "order_type": OrderType.LAB},
                {"test": "Urine sodium", "rationale": "Calculate FENa to differentiate prerenal vs intrinsic.", "urgency": Urgency.STAT, "priority": Priority.HIGH, "order_type": OrderType.LAB},
            ],
            "recommended": [
                {"test": "CBC", "rationale": "Rule out HUS, TTP (microangiopathic hemolytic anemia).", "urgency": Urgency.STAT, "priority": Priority.HIGH, "order_type": OrderType.LAB},
                {"test": "Renal ultrasound", "rationale": "Rule out obstruction (hydronephrosis).", "urgency": Urgency.URGENT, "priority": Priority.HIGH, "order_type": OrderType.IMAGING},
            ]
        },
        # Pneumonia (J18.x)
        "pneumonia": {
            "icd10_prefixes": ["J18", "J13", "J14", "J15", "J16", "J17"],
            "keywords": ["pneumonia", "cap", "community acquired pneumonia", "hap"],
            "required": [
                {"test": "Chest X-ray", "rationale": "PA and lateral chest X-ray for pneumonia diagnosis.", "urgency": Urgency.STAT, "priority": Priority.CRITICAL, "order_type": OrderType.IMAGING},
                {"test": "CBC with differential", "rationale": "WBC count and differential for infection assessment.", "urgency": Urgency.STAT, "priority": Priority.HIGH, "order_type": OrderType.LAB},
            ],
            "recommended": [
                {"test": "BMP", "rationale": "Assess renal function, electrolytes if hypoxic or septic.", "urgency": Urgency.STAT, "priority": Priority.HIGH, "order_type": OrderType.LAB},
                {"test": "Blood cultures", "rationale": "If severe pneumonia or bacteremia suspected.", "urgency": Urgency.STAT, "priority": Priority.HIGH, "order_type": OrderType.LAB},
                {"test": "Procalcitonin", "rationale": "Guide antibiotic therapy duration.", "urgency": Urgency.STAT, "priority": Priority.MEDIUM, "order_type": OrderType.LAB},
                {"test": "Sputum culture", "rationale": "If productive cough, identify pathogen.", "urgency": Urgency.ROUTINE, "priority": Priority.MEDIUM, "order_type": OrderType.LAB},
            ]
        },
    }
    
    # Imaging contraindications
    CONTRAINDICATION_RULES: Dict[str, Dict[str, Any]] = {
        "ct_contrast": {
            "tests": ["ct with contrast", "ct abdomen", "ct chest", "ct abdomen/pelvis", "cta"],
            "absolute": [
                {"condition": "contrast_allergy", "message": "Patient has contrast dye allergy - avoid CT with IV contrast unless emergent and pre-medicated with steroids/antihistamines"},
                {"condition": "egfr_below_30", "message": "Patient has eGFR <30 - high risk of contrast-induced nephropathy. Use non-contrast imaging if possible."},
            ],
            "relative": [
                {"condition": "egfr_30_45", "message": "Patient has eGFR 30-45 - use caution with iodinated contrast, ensure adequate hydration"},
                {"condition": "metformin_low_egfr", "message": "Patient on metformin with eGFR <60 - hold metformin 48 hours after contrast"},
            ]
        },
        "mri": {
            "tests": ["mri", "mri brain", "mri spine", "mri abdomen"],
            "absolute": [
                {"condition": "pacemaker", "message": "Patient has pacemaker - MRI contraindicated unless MRI-compatible device confirmed"},
                {"condition": "icd", "message": "Patient has ICD - MRI contraindicated unless MRI-compatible device confirmed"},
            ],
            "relative": [
                {"condition": "pregnancy_first_trimester", "message": "Patient is pregnant - avoid gadolinium in first trimester"},
            ]
        },
        "gadolinium": {
            "tests": ["mri with contrast", "mri brain with contrast", "mra"],
            "absolute": [
                {"condition": "egfr_below_30", "message": "Patient has eGFR <30 - risk of nephrogenic systemic fibrosis (NSF) with gadolinium"},
                {"condition": "gadolinium_allergy", "message": "Patient has gadolinium allergy - avoid gadolinium-based contrast"},
            ],
            "relative": []
        },
        "pregnancy_radiation": {
            "tests": ["ct", "ct abdomen", "ct pelvis", "ct abdomen/pelvis", "x-ray abdomen", "x-ray pelvis"],
            "absolute": [
                {"condition": "pregnant", "message": "Patient is pregnant - avoid radiation exposure to abdomen/pelvis. Consider ultrasound or MRI without gadolinium."},
            ],
            "relative": []
        }
    }
    
    def __init__(self):
        """Initialize OrdersAgent."""
        super().__init__(name="Orders")
    
    async def _run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate lab and imaging orders.
        
        Args:
            context: Dictionary containing:
                - orders: List of orders to validate
                - diagnosis: Clinical diagnosis (optional)
                - recent_orders: List of recent orders (optional)
                - patient_context: Patient information (optional)
        
        Returns:
            OrdersResult with validation results, suggestions, and optimizations.
        """
        # Parse input
        orders_data = context.get("orders", [])
        diagnosis = context.get("diagnosis", "")
        recent_orders_data = context.get("recent_orders", [])
        patient_data = context.get("patient_context", {})
        
        # Validate input
        if not orders_data:
            raise ValueError("At least one order is required")
        
        # Parse orders
        orders = self._parse_orders(orders_data)
        recent_orders = self._parse_recent_orders(recent_orders_data)
        patient = self._parse_patient_context(patient_data)
        
        # Determine if acute illness
        is_acute = self._is_acute_illness(diagnosis, context)
        
        # Validate each order
        validated_orders = []
        all_contraindications = []
        
        for order in orders:
            validated = self._validate_order(order, recent_orders, patient, is_acute)
            validated_orders.append(validated)
            all_contraindications.extend(validated.contraindications)
        
        # Check for additional contraindications based on patient context
        patient_contraindications = self._check_patient_contraindications(orders, patient)
        all_contraindications.extend(patient_contraindications)
        
        # Remove duplicates from contraindications
        all_contraindications = list(set(all_contraindications))
        
        # Suggest additional tests based on diagnosis protocol
        suggested_additions = self._suggest_protocol_tests(diagnosis, orders)
        
        # Recommend panels
        panel_recommendations = self._recommend_panels(orders, diagnosis)
        
        # Calculate cost optimization
        cost_optimization = self._calculate_cost_optimization(orders, panel_recommendations)
        
        # Build result
        result = OrdersResult(
            validated_orders=validated_orders,
            suggested_additions=suggested_additions,
            panel_recommendations=panel_recommendations,
            contraindications=all_contraindications,
            cost_optimization=cost_optimization
        )
        
        # Generate reasoning
        reasoning = self._generate_reasoning(diagnosis, validated_orders, suggested_additions)
        
        return {
            "data": result.to_dict(),
            "reasoning": reasoning
        }
    
    def _parse_orders(self, orders_data: List[Dict[str, Any]]) -> List[Order]:
        """Parse order data into Order objects."""
        orders = []
        for o in orders_data:
            try:
                order_type = OrderType(o.get("order_type", "lab"))
            except ValueError:
                order_type = OrderType.LAB
            
            try:
                urgency = Urgency(o.get("urgency", "routine"))
            except ValueError:
                urgency = Urgency.ROUTINE
            
            orders.append(Order(
                test=o.get("test", ""),
                order_type=order_type,
                urgency=urgency
            ))
        return orders
    
    def _parse_recent_orders(self, recent_data: List[Dict[str, Any]]) -> List[RecentOrder]:
        """Parse recent order data into RecentOrder objects."""
        recent = []
        for r in recent_data:
            try:
                date_str = r.get("date", "")
                if isinstance(date_str, str):
                    order_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                elif isinstance(date_str, date):
                    order_date = date_str
                else:
                    continue
                
                recent.append(RecentOrder(
                    test=r.get("test", ""),
                    date=order_date,
                    result=r.get("result")
                ))
            except (ValueError, TypeError):
                continue
        return recent
    
    def _parse_patient_context(self, patient_data: Dict[str, Any]) -> Optional[PatientContext]:
        """Parse patient context data."""
        if not patient_data:
            return None
        
        return PatientContext(
            age=patient_data.get("age", 0),
            sex=patient_data.get("sex", "unknown"),
            creatinine=patient_data.get("creatinine"),
            egfr=patient_data.get("egfr"),
            allergies=patient_data.get("allergies", []),
            pregnancy_status=patient_data.get("pregnancy_status"),
            weight_kg=patient_data.get("weight_kg"),
            conditions=patient_data.get("conditions", []),
            has_pacemaker=patient_data.get("has_pacemaker", False),
            has_icd=patient_data.get("has_icd", False),
            on_metformin=patient_data.get("on_metformin", False)
        )
    
    def _is_acute_illness(self, diagnosis: str, context: Dict[str, Any]) -> bool:
        """Determine if this is an acute illness requiring shorter validity periods."""
        acute_keywords = [
            "sepsis", "septic", "acute", "emergency", "stat",
            "chest pain", "stroke", "dka", "mi", "stemi", "nstemi",
            "pneumonia", "aki", "trauma", "hemorrhage", "shock"
        ]
        
        diagnosis_lower = diagnosis.lower()
        for keyword in acute_keywords:
            if keyword in diagnosis_lower:
                return True
        
        # Check if any STAT orders
        orders = context.get("orders", [])
        for order in orders:
            if isinstance(order, dict) and order.get("urgency") == "stat":
                return True
        
        return False
    
    def _validate_order(self, order: Order, recent_orders: List[RecentOrder],
                       patient: Optional[PatientContext], is_acute: bool) -> ValidatedOrder:
        """Validate a single order."""
        test_lower = order.test.lower()
        
        # Check for duplicates
        is_duplicate, duplicate_info = self._check_duplicate(test_lower, recent_orders, is_acute)
        
        if is_duplicate:
            return ValidatedOrder(
                test=order.test,
                status=OrderStatus.DUPLICATE,
                issue=duplicate_info,
                recommendation="Review previous result. If clinical status changed, reordering acceptable. Otherwise, use recent result.",
                contraindications=[]
            )
        
        # Check contraindications
        contraindications = self._check_contraindications(order, patient)
        
        if contraindications:
            # Check if any are absolute contraindications
            absolute_terms = ["avoid", "contraindicated", "high risk"]
            has_absolute = any(
                any(term in ci.lower() for term in absolute_terms)
                for ci in contraindications
            )
            
            if has_absolute:
                return ValidatedOrder(
                    test=order.test,
                    status=OrderStatus.CONTRAINDICATED,
                    issue="Contraindication(s) identified",
                    recommendation="Review contraindications before proceeding. Consider alternative imaging.",
                    contraindications=contraindications
                )
        
        # Check if test is recognized
        if not self._is_known_test(test_lower):
            return ValidatedOrder(
                test=order.test,
                status=OrderStatus.QUESTIONABLE,
                issue="Test name not recognized in database",
                recommendation="Verify test name is correct.",
                contraindications=contraindications
            )
        
        # Generate recommendations for approved orders
        recommendation = self._get_order_recommendation(order, patient)
        
        return ValidatedOrder(
            test=order.test,
            status=OrderStatus.APPROVED,
            issue=None,
            recommendation=recommendation,
            contraindications=contraindications
        )
    
    def _check_duplicate(self, test: str, recent_orders: List[RecentOrder],
                        is_acute: bool) -> Tuple[bool, Optional[str]]:
        """Check if test is a duplicate of a recent order."""
        test_lower = test.lower()
        
        # Normalize test names for comparison
        test_aliases = {
            "cbc with diff": "cbc with differential",
            "complete blood count": "cbc",
            "basic metabolic panel": "bmp",
            "comprehensive metabolic panel": "cmp",
            "chest xray": "chest x-ray",
        }
        
        normalized_test = test_aliases.get(test_lower, test_lower)
        
        # Tests that should never be considered duplicates
        never_duplicate = ["troponin", "blood cultures", "blood gas", "abg", "vbg"]
        if normalized_test in never_duplicate:
            return False, None
        
        # Get validity period
        validity = self._get_validity_period(normalized_test, is_acute)
        if validity == 0:
            return False, None
        
        today = date.today()
        
        for recent in recent_orders:
            recent_test_lower = recent.test.lower()
            recent_normalized = test_aliases.get(recent_test_lower, recent_test_lower)
            
            # Check for exact match or related tests
            if self._tests_overlap(normalized_test, recent_normalized):
                days_ago = (today - recent.date).days
                
                if days_ago < validity:
                    result_info = f" with result: {recent.result}" if recent.result else ""
                    return True, f"{recent.test} ordered {days_ago} day(s) ago{result_info}. Recent result available."
        
        return False, None
    
    def _tests_overlap(self, test1: str, test2: str) -> bool:
        """Check if two tests overlap (e.g., BMP vs CMP)."""
        if test1 == test2:
            return True
        
        # CMP contains BMP
        if (test1 == "bmp" and test2 == "cmp") or (test1 == "cmp" and test2 == "bmp"):
            return True
        
        # CBC variations
        if test1.startswith("cbc") and test2.startswith("cbc"):
            return True
        
        return False
    
    def _get_validity_period(self, test: str, is_acute: bool) -> int:
        """Get validity period in days for a test."""
        test_lower = test.lower()
        
        if test_lower in self.TEST_VALIDITY_PERIODS:
            stable_days, acute_days = self.TEST_VALIDITY_PERIODS[test_lower]
            return acute_days if is_acute else stable_days
        
        # Default validity periods
        if "ct" in test_lower or "mri" in test_lower:
            return 7 if is_acute else 30
        
        return 3 if is_acute else 7  # Default for unknown labs
    
    def _check_contraindications(self, order: Order, patient: Optional[PatientContext]) -> List[str]:
        """Check for contraindications to a test."""
        if not patient:
            return []
        
        contraindications = []
        test_lower = order.test.lower()
        
        # Check each contraindication rule
        for rule_name, rule in self.CONTRAINDICATION_RULES.items():
            # Check if this order matches the rule's tests
            matches_rule = any(t in test_lower for t in rule["tests"])
            
            if matches_rule:
                # Check absolute contraindications
                for ci in rule.get("absolute", []):
                    if self._check_condition(ci["condition"], patient):
                        contraindications.append(ci["message"])
                
                # Check relative contraindications
                for ci in rule.get("relative", []):
                    if self._check_condition(ci["condition"], patient):
                        contraindications.append(ci["message"])
        
        return contraindications
    
    def _check_condition(self, condition: str, patient: PatientContext) -> bool:
        """Check if a patient meets a specific condition."""
        if condition == "contrast_allergy":
            allergies_lower = [a.lower() for a in patient.allergies]
            return any(
                term in allergy
                for allergy in allergies_lower
                for term in ["contrast", "iodine", "iodinated"]
            )
        
        elif condition == "gadolinium_allergy":
            allergies_lower = [a.lower() for a in patient.allergies]
            return any("gadolinium" in a for a in allergies_lower)
        
        elif condition == "egfr_below_30":
            return patient.egfr is not None and patient.egfr < 30
        
        elif condition == "egfr_30_45":
            return patient.egfr is not None and 30 <= patient.egfr < 45
        
        elif condition == "metformin_low_egfr":
            return patient.on_metformin and patient.egfr is not None and patient.egfr < 60
        
        elif condition == "pacemaker":
            return patient.has_pacemaker
        
        elif condition == "icd":
            return patient.has_icd
        
        elif condition == "pregnant":
            return patient.pregnancy_status == "pregnant"
        
        elif condition == "pregnancy_first_trimester":
            # Simplified - just check if pregnant
            return patient.pregnancy_status == "pregnant"
        
        return False
    
    def _check_patient_contraindications(self, orders: List[Order],
                                         patient: Optional[PatientContext]) -> List[str]:
        """Check for general patient-level contraindications."""
        if not patient:
            return []
        
        contraindications = []
        
        # Check for contrast-related orders in patient with renal impairment
        contrast_orders = [o for o in orders if self._is_contrast_order(o.test)]
        
        if contrast_orders and patient.egfr:
            if patient.egfr < 30:
                contraindications.append(
                    f"Patient has eGFR {int(patient.egfr)} (CKD Stage 4/5) - "
                    "use caution with iodinated contrast (risk of contrast-induced nephropathy)"
                )
            elif 30 <= patient.egfr < 45:
                contraindications.append(
                    f"Patient has eGFR {int(patient.egfr)} (CKD Stage 3b) - "
                    "ensure adequate hydration before and after contrast"
                )
        
        # Check contrast allergy
        if contrast_orders:
            allergies_lower = [a.lower() for a in patient.allergies]
            if any("contrast" in a or "dye" in a or "iodine" in a for a in allergies_lower):
                contraindications.append(
                    "Patient has contrast dye allergy - avoid CT with IV contrast unless "
                    "emergent and pre-medicated with steroids/antihistamines"
                )
        
        return contraindications
    
    def _is_contrast_order(self, test: str) -> bool:
        """Check if order involves contrast."""
        test_lower = test.lower()
        contrast_terms = ["contrast", "cta", "ct abdomen", "ct chest", "ct pelvis"]
        return any(term in test_lower for term in contrast_terms)
    
    def _is_known_test(self, test: str) -> bool:
        """Check if test is in known database."""
        test_lower = test.lower()
        
        known_tests = set(self.TEST_VALIDITY_PERIODS.keys()) | set(self.TEST_COSTS.keys())
        
        # Also check partial matches
        for known in known_tests:
            if known in test_lower or test_lower in known:
                return True
        
        # Common variations
        known_variations = [
            "ct", "mri", "x-ray", "xray", "ultrasound", "echo", "ekg",
            "culture", "panel", "screen", "level"
        ]
        
        return any(v in test_lower for v in known_variations)
    
    def _get_order_recommendation(self, order: Order, patient: Optional[PatientContext]) -> Optional[str]:
        """Get recommendation for an approved order."""
        test_lower = order.test.lower()
        
        # BMP -> CMP recommendation
        if test_lower == "bmp":
            return "Consider ordering CMP instead for complete metabolic assessment (minimal cost difference)."
        
        # CBC -> CBC with diff if infection
        if test_lower == "cbc":
            return "Consider CBC with differential if infection is suspected."
        
        return None
    
    def _suggest_protocol_tests(self, diagnosis: str, current_orders: List[Order]) -> List[SuggestedOrder]:
        """Suggest additional tests based on diagnosis protocol."""
        if not diagnosis:
            return []
        
        suggestions = []
        diagnosis_lower = diagnosis.lower()
        
        # Find matching protocol
        matched_protocol = None
        for protocol_name, protocol in self.DIAGNOSIS_PROTOCOLS.items():
            # Check ICD-10 prefixes
            for prefix in protocol.get("icd10_prefixes", []):
                if prefix in diagnosis.upper():
                    matched_protocol = protocol
                    break
            
            if matched_protocol:
                break
            
            # Check keywords
            for keyword in protocol.get("keywords", []):
                if keyword in diagnosis_lower:
                    matched_protocol = protocol
                    break
            
            if matched_protocol:
                break
        
        if not matched_protocol:
            return []
        
        # Get current test names (normalized)
        current_tests = {self._normalize_test_name(o.test) for o in current_orders}
        
        # Add required tests not already ordered
        for test_info in matched_protocol.get("required", []):
            test_normalized = self._normalize_test_name(test_info["test"])
            if not self._test_already_ordered(test_normalized, current_tests):
                suggestions.append(SuggestedOrder(
                    test=test_info["test"],
                    rationale=test_info["rationale"],
                    urgency=test_info["urgency"],
                    priority=test_info["priority"],
                    order_type=test_info["order_type"]
                ))
        
        # Add recommended tests not already ordered
        for test_info in matched_protocol.get("recommended", []):
            test_normalized = self._normalize_test_name(test_info["test"])
            if not self._test_already_ordered(test_normalized, current_tests):
                suggestions.append(SuggestedOrder(
                    test=test_info["test"],
                    rationale=test_info["rationale"],
                    urgency=test_info["urgency"],
                    priority=test_info["priority"],
                    order_type=test_info["order_type"]
                ))
        
        # Sort by priority
        priority_order = {Priority.CRITICAL: 0, Priority.HIGH: 1, Priority.MEDIUM: 2, Priority.LOW: 3}
        suggestions.sort(key=lambda x: priority_order.get(x.priority, 4))
        
        return suggestions
    
    def _normalize_test_name(self, test: str) -> str:
        """Normalize test name for comparison."""
        test_lower = test.lower()
        
        # Remove common suffixes
        test_lower = test_lower.replace(" x2", "").replace(" with reflex culture", "")
        test_lower = test_lower.replace(" without contrast", "").replace(" with contrast", "")
        
        # Common aliases
        aliases = {
            "chest x-ray": "cxr",
            "chest xray": "cxr",
            "complete blood count": "cbc",
            "basic metabolic panel": "bmp",
            "comprehensive metabolic panel": "cmp",
            "blood gas": "abg",
        }
        
        return aliases.get(test_lower, test_lower)
    
    def _test_already_ordered(self, test: str, current_tests: set) -> bool:
        """Check if a test (or equivalent) is already ordered."""
        if test in current_tests:
            return True
        
        # Check equivalents
        equivalents = {
            "cmp": ["bmp", "cmp"],
            "bmp": ["bmp", "cmp"],
            "cbc": ["cbc", "cbc with differential"],
            "cbc with differential": ["cbc", "cbc with differential"],
            "cxr": ["chest x-ray", "cxr", "chest xray"],
            "abg": ["blood gas", "abg", "vbg"],
        }
        
        test_equivalents = equivalents.get(test, [test])
        return any(eq in current_tests for eq in test_equivalents)
    
    def _recommend_panels(self, orders: List[Order], diagnosis: str) -> List[str]:
        """Recommend test panels vs individual tests."""
        recommendations = []
        order_tests = [o.test.lower() for o in orders]
        diagnosis_lower = diagnosis.lower() if diagnosis else ""
        
        # Check for BMP -> CMP recommendation
        if "bmp" in order_tests and "cmp" not in order_tests:
            rec = self.PANEL_RECOMMENDATIONS["bmp"]
            recommendations.append(rec["message"])
        
        # Check for CBC -> CBC with diff recommendation
        if "cbc" in order_tests and "cbc with differential" not in order_tests:
            rec = self.PANEL_RECOMMENDATIONS["cbc"]
            # Only recommend if infection might be present
            infection_keywords = ["infection", "sepsis", "pneumonia", "fever", "leukocytosis"]
            if any(kw in diagnosis_lower for kw in infection_keywords):
                recommendations.append(rec["message"])
        
        return recommendations
    
    def _calculate_cost_optimization(self, orders: List[Order],
                                     panel_recommendations: List[str]) -> Optional[CostOptimization]:
        """Calculate potential cost savings."""
        # Calculate current cost
        current_cost = 0.0
        for order in orders:
            test_lower = order.test.lower()
            cost = self.TEST_COSTS.get(test_lower, 50.0)  # Default cost
            current_cost += cost
        
        # Calculate optimized cost based on recommendations
        optimized_cost = current_cost
        suggestion = ""
        
        # Check if BMP can be upgraded to CMP
        order_tests = [o.test.lower() for o in orders]
        if "bmp" in order_tests and "cmp" not in order_tests:
            # BMP ($45) -> CMP ($50) = +$5 but better value
            bmp_cost = self.TEST_COSTS.get("bmp", 45.0)
            cmp_cost = self.TEST_COSTS.get("cmp", 50.0)
            cost_diff = cmp_cost - bmp_cost
            
            optimized_cost = current_cost - bmp_cost + cmp_cost
            suggestion = f"Order CMP (${cmp_cost:.0f}) instead of BMP (${bmp_cost:.0f}) for comprehensive assessment (only ${cost_diff:.0f} more, provides 6 additional values)"
        
        if not suggestion:
            return None
        
        savings = current_cost - optimized_cost
        
        return CostOptimization(
            current_cost=current_cost,
            optimized_cost=optimized_cost,
            savings=savings,
            suggestion=suggestion
        )
    
    def _generate_reasoning(self, diagnosis: str, validated_orders: List[ValidatedOrder],
                           suggested_additions: List[SuggestedOrder]) -> str:
        """Generate reasoning summary."""
        parts = []
        
        # Summarize validation results
        approved = sum(1 for o in validated_orders if o.status == OrderStatus.APPROVED)
        duplicates = sum(1 for o in validated_orders if o.status == OrderStatus.DUPLICATE)
        contraindicated = sum(1 for o in validated_orders if o.status == OrderStatus.CONTRAINDICATED)
        
        if validated_orders:
            parts.append(f"Validated {len(validated_orders)} order(s): {approved} approved")
            if duplicates:
                parts.append(f"{duplicates} duplicate(s)")
            if contraindicated:
                parts.append(f"{contraindicated} contraindicated")
        
        # Summarize suggestions
        if suggested_additions:
            critical = [s for s in suggested_additions if s.priority == Priority.CRITICAL]
            if critical:
                critical_tests = ", ".join(s.test for s in critical)
                parts.append(f"Critical missing tests: {critical_tests}")
        
        # Protocol-based reasoning
        if diagnosis:
            for protocol_name, protocol in self.DIAGNOSIS_PROTOCOLS.items():
                keywords = protocol.get("keywords", [])
                if any(kw in diagnosis.lower() for kw in keywords):
                    parts.append(f"{protocol_name.replace('_', ' ').title()} workup identified")
                    break
        
        return ". ".join(parts) + "." if parts else "Order validation complete."
