"""
Regulatory Compliance - Title VI Language Access Requirements.

Title VI of the Civil Rights Act of 1964 requires federally-funded
healthcare facilities to provide language access services.

REQUIREMENTS:
1. Identify patient's preferred language
2. Provide qualified interpreters (or equivalent technology)
3. Translate vital documents
4. Notify patients of language services
5. Document all language services provided

PHOENIX GUARDIAN COMPLIANCE:
✓ Language detection (automatic)
✓ Professional-quality medical translation
✓ Discharge instructions in patient's language
✓ Audit trail of all translations
✓ Title VI compliance reports
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta
from enum import Enum
import logging

from phoenix_guardian.localization.locale_manager import SupportedLocale

logger = logging.getLogger(__name__)


class InterpreterType(Enum):
    """Types of interpretation services."""
    AI_TRANSLATION = "ai_translation"
    LIVE_INTERPRETER = "live_interpreter"
    VIDEO_INTERPRETER = "video_interpreter"
    PHONE_INTERPRETER = "phone_interpreter"
    BILINGUAL_STAFF = "bilingual_staff"


class DocumentType(Enum):
    """Types of translated documents."""
    DISCHARGE_INSTRUCTIONS = "discharge_instructions"
    CONSENT_FORM = "consent_form"
    MEDICATION_GUIDE = "medication_guide"
    PATIENT_RIGHTS = "patient_rights"
    HIPAA_NOTICE = "hipaa_notice"
    BILLING_STATEMENT = "billing_statement"
    APPOINTMENT_REMINDER = "appointment_reminder"


@dataclass
class LanguageServiceRecord:
    """
    Record of language services provided to a patient.
    
    Required for Title VI compliance documentation.
    """
    patient_id: str
    encounter_id: str
    date: str
    
    # Language services provided
    patient_language: SupportedLocale
    interpreter_type: InterpreterType
    documents_translated: List[DocumentType]
    
    # Quality metrics
    translation_quality_score: Optional[float] = None
    physician_review_completed: bool = False
    
    # Title VI specific
    patient_notified_of_services: bool = False
    patient_declined_services: bool = False
    
    # Duration tracking
    interpretation_duration_minutes: Optional[int] = None
    
    # Notes
    notes: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "patient_id": self.patient_id,
            "encounter_id": self.encounter_id,
            "date": self.date,
            "patient_language": self.patient_language.value,
            "interpreter_type": self.interpreter_type.value,
            "documents_translated": [d.value for d in self.documents_translated],
            "translation_quality_score": self.translation_quality_score,
            "physician_review_completed": self.physician_review_completed,
            "patient_notified_of_services": self.patient_notified_of_services,
            "patient_declined_services": self.patient_declined_services,
            "interpretation_duration_minutes": self.interpretation_duration_minutes
        }


@dataclass
class TitleVIReport:
    """
    Title VI compliance report for a time period.
    """
    report_period_start: str
    report_period_end: str
    hospital_name: str
    tenant_id: str
    
    # Aggregate statistics
    total_encounters: int
    encounters_by_language: Dict[SupportedLocale, int]
    
    # Language service metrics
    interpretation_services_provided: int
    documents_translated: int
    patient_notifications_completed: int
    
    # Compliance metrics
    compliance_rate: float         # % of LEP patients receiving services
    quality_scores_average: float
    
    # Detailed records
    service_records: List[LanguageServiceRecord] = field(default_factory=list)
    
    # Recommendations
    recommendations: List[str] = field(default_factory=list)
    
    # Compliance status
    is_compliant: bool = True
    compliance_issues: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for export."""
        return {
            "report_period": {
                "start": self.report_period_start,
                "end": self.report_period_end
            },
            "hospital": {
                "name": self.hospital_name,
                "tenant_id": self.tenant_id
            },
            "summary": {
                "total_encounters": self.total_encounters,
                "encounters_by_language": {
                    k.value: v for k, v in self.encounters_by_language.items()
                },
                "interpretation_services_provided": self.interpretation_services_provided,
                "documents_translated": self.documents_translated,
                "patient_notifications_completed": self.patient_notifications_completed
            },
            "compliance": {
                "compliance_rate": self.compliance_rate,
                "quality_scores_average": self.quality_scores_average,
                "is_compliant": self.is_compliant,
                "issues": self.compliance_issues
            },
            "recommendations": self.recommendations
        }


@dataclass
class LanguageAccessPlan:
    """
    Hospital's language access plan (Title VI requirement).
    """
    hospital_name: str
    tenant_id: str
    effective_date: str
    
    # Supported languages
    primary_languages: List[SupportedLocale]
    
    # Service commitments
    interpretation_available_24_7: bool
    vital_documents_translated: List[DocumentType]
    
    # Quality assurance
    translator_qualifications: str
    quality_monitoring_process: str
    complaint_procedure: str
    
    # Staff training
    staff_trained_on_language_services: bool
    training_frequency: str
    
    # Review schedule
    last_review_date: Optional[str] = None
    next_review_date: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "hospital_name": self.hospital_name,
            "tenant_id": self.tenant_id,
            "effective_date": self.effective_date,
            "primary_languages": [l.value for l in self.primary_languages],
            "interpretation_available_24_7": self.interpretation_available_24_7,
            "vital_documents_translated": [d.value for d in self.vital_documents_translated],
            "translator_qualifications": self.translator_qualifications,
            "quality_monitoring_process": self.quality_monitoring_process,
            "complaint_procedure": self.complaint_procedure,
            "staff_trained_on_language_services": self.staff_trained_on_language_services,
            "training_frequency": self.training_frequency,
            "last_review_date": self.last_review_date,
            "next_review_date": self.next_review_date
        }


class RegulatoryCompliance:
    """
    Manages Title VI compliance for language services.
    """
    
    # Compliance thresholds
    COMPLIANCE_RATE_TARGET = 0.95      # 95% of LEP patients must receive services
    QUALITY_SCORE_TARGET = 0.85        # 85% minimum quality score
    NOTIFICATION_RATE_TARGET = 0.98    # 98% of patients must be notified
    
    def __init__(self):
        self.service_records: List[LanguageServiceRecord] = []
        self.language_access_plans: Dict[str, LanguageAccessPlan] = {}
    
    def record_language_service(
        self,
        patient_id: str,
        encounter_id: str,
        patient_language: SupportedLocale,
        interpreter_type: InterpreterType,
        documents_translated: List[DocumentType],
        patient_notified: bool = True,
        translation_quality_score: Optional[float] = None,
        physician_review_completed: bool = False,
        interpretation_duration_minutes: Optional[int] = None,
        notes: Optional[str] = None
    ) -> LanguageServiceRecord:
        """
        Record language services provided.
        
        This creates audit trail for Title VI compliance.
        """
        record = LanguageServiceRecord(
            patient_id=patient_id,
            encounter_id=encounter_id,
            date=datetime.now().isoformat(),
            patient_language=patient_language,
            interpreter_type=interpreter_type,
            documents_translated=documents_translated,
            patient_notified_of_services=patient_notified,
            translation_quality_score=translation_quality_score,
            physician_review_completed=physician_review_completed,
            interpretation_duration_minutes=interpretation_duration_minutes,
            notes=notes
        )
        
        self.service_records.append(record)
        
        logger.info(
            f"Recorded language service: {patient_language.value} for "
            f"encounter {encounter_id}"
        )
        
        return record
    
    def record_service_declined(
        self,
        patient_id: str,
        encounter_id: str,
        patient_language: SupportedLocale
    ) -> LanguageServiceRecord:
        """
        Record when patient declines language services.
        
        Important for compliance - shows services were offered.
        """
        record = LanguageServiceRecord(
            patient_id=patient_id,
            encounter_id=encounter_id,
            date=datetime.now().isoformat(),
            patient_language=patient_language,
            interpreter_type=InterpreterType.AI_TRANSLATION,  # Offered
            documents_translated=[],
            patient_notified_of_services=True,
            patient_declined_services=True
        )
        
        self.service_records.append(record)
        
        logger.info(
            f"Patient {patient_id} declined language services for "
            f"encounter {encounter_id}"
        )
        
        return record
    
    def generate_title_vi_report(
        self,
        tenant_id: str,
        hospital_name: str,
        start_date: str,
        end_date: str
    ) -> TitleVIReport:
        """
        Generate Title VI compliance report.
        
        This report demonstrates compliance with federal language
        access requirements.
        """
        # Filter records by date range
        start_dt = datetime.fromisoformat(start_date)
        end_dt = datetime.fromisoformat(end_date)
        
        period_records = [
            r for r in self.service_records
            if start_dt <= datetime.fromisoformat(r.date) <= end_dt
        ]
        
        # Calculate statistics
        total = len(period_records)
        
        # Count by language
        by_language: Dict[SupportedLocale, int] = {}
        for record in period_records:
            lang = record.patient_language
            by_language[lang] = by_language.get(lang, 0) + 1
        
        # Count services (exclude declined)
        active_records = [r for r in period_records if not r.patient_declined_services]
        interpretation_count = len(active_records)
        docs_translated = sum(len(r.documents_translated) for r in active_records)
        notifications = sum(1 for r in period_records if r.patient_notified_of_services)
        
        # Quality metrics
        quality_scores = [
            r.translation_quality_score for r in active_records
            if r.translation_quality_score is not None
        ]
        avg_quality = (sum(quality_scores) / len(quality_scores)) if quality_scores else 0.0
        
        # Compliance rate (% of LEP patients receiving services)
        lep_count = total - by_language.get(SupportedLocale.EN_US, 0)
        lep_served = sum(
            1 for r in period_records
            if r.patient_language != SupportedLocale.EN_US and 
            (not r.patient_declined_services or r.patient_notified_of_services)
        )
        compliance_rate = (lep_served / lep_count) if lep_count > 0 else 1.0
        
        # Check compliance status
        is_compliant = True
        compliance_issues = []
        
        if compliance_rate < self.COMPLIANCE_RATE_TARGET:
            is_compliant = False
            compliance_issues.append(
                f"Compliance rate {compliance_rate*100:.1f}% below target {self.COMPLIANCE_RATE_TARGET*100:.0f}%"
            )
        
        if avg_quality < self.QUALITY_SCORE_TARGET and quality_scores:
            is_compliant = False
            compliance_issues.append(
                f"Quality score {avg_quality:.2f} below target {self.QUALITY_SCORE_TARGET}"
            )
        
        notification_rate = notifications / total if total > 0 else 1.0
        if notification_rate < self.NOTIFICATION_RATE_TARGET:
            is_compliant = False
            compliance_issues.append(
                f"Notification rate {notification_rate*100:.1f}% below target {self.NOTIFICATION_RATE_TARGET*100:.0f}%"
            )
        
        # Generate recommendations
        recommendations = self._generate_recommendations(
            period_records,
            compliance_rate,
            avg_quality,
            by_language
        )
        
        return TitleVIReport(
            report_period_start=start_date,
            report_period_end=end_date,
            hospital_name=hospital_name,
            tenant_id=tenant_id,
            total_encounters=total,
            encounters_by_language=by_language,
            interpretation_services_provided=interpretation_count,
            documents_translated=docs_translated,
            patient_notifications_completed=notifications,
            compliance_rate=round(compliance_rate, 3),
            quality_scores_average=round(avg_quality, 2),
            service_records=period_records,
            recommendations=recommendations,
            is_compliant=is_compliant,
            compliance_issues=compliance_issues
        )
    
    def create_language_access_plan(
        self,
        hospital_name: str,
        tenant_id: str,
        supported_languages: List[SupportedLocale]
    ) -> LanguageAccessPlan:
        """
        Create hospital's language access plan.
        
        Title VI requires hospitals to have a written plan.
        """
        plan = LanguageAccessPlan(
            hospital_name=hospital_name,
            tenant_id=tenant_id,
            effective_date=datetime.now().isoformat(),
            primary_languages=supported_languages,
            interpretation_available_24_7=True,  # Phoenix Guardian is always available
            vital_documents_translated=[
                DocumentType.DISCHARGE_INSTRUCTIONS,
                DocumentType.MEDICATION_GUIDE,
                DocumentType.PATIENT_RIGHTS,
                DocumentType.CONSENT_FORM,
                DocumentType.HIPAA_NOTICE
            ],
            translator_qualifications=(
                "Phoenix Guardian uses medical-grade AI translation with "
                "SNOMED CT and ICD-10 terminology standardization. "
                "Translations reviewed by licensed physicians."
            ),
            quality_monitoring_process=(
                "All translations scored for medical accuracy. "
                "Physician feedback integrated into translation memory. "
                "Monthly quality audits conducted."
            ),
            complaint_procedure=(
                "Patients may file language service complaints with "
                "hospital patient relations department. "
                "Complaints reviewed within 48 hours."
            ),
            staff_trained_on_language_services=True,
            training_frequency="Quarterly",
            last_review_date=datetime.now().isoformat(),
            next_review_date=(datetime.now() + timedelta(days=365)).isoformat()
        )
        
        # Store plan
        self.language_access_plans[tenant_id] = plan
        
        logger.info(f"Created language access plan for {hospital_name}")
        
        return plan
    
    def get_language_access_plan(
        self,
        tenant_id: str
    ) -> Optional[LanguageAccessPlan]:
        """Get language access plan for a hospital."""
        return self.language_access_plans.get(tenant_id)
    
    def get_service_records(
        self,
        patient_id: Optional[str] = None,
        encounter_id: Optional[str] = None,
        language: Optional[SupportedLocale] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> List[LanguageServiceRecord]:
        """
        Query service records with filters.
        """
        records = self.service_records
        
        if patient_id:
            records = [r for r in records if r.patient_id == patient_id]
        
        if encounter_id:
            records = [r for r in records if r.encounter_id == encounter_id]
        
        if language:
            records = [r for r in records if r.patient_language == language]
        
        if start_date:
            start_dt = datetime.fromisoformat(start_date)
            records = [
                r for r in records
                if datetime.fromisoformat(r.date) >= start_dt
            ]
        
        if end_date:
            end_dt = datetime.fromisoformat(end_date)
            records = [
                r for r in records
                if datetime.fromisoformat(r.date) <= end_dt
            ]
        
        return records
    
    def get_lep_statistics(
        self,
        start_date: str,
        end_date: str
    ) -> Dict[str, Any]:
        """
        Get Limited English Proficiency (LEP) patient statistics.
        """
        records = self.get_service_records(start_date=start_date, end_date=end_date)
        
        lep_records = [
            r for r in records
            if r.patient_language != SupportedLocale.EN_US
        ]
        
        by_language = {}
        by_interpreter_type = {}
        
        for record in lep_records:
            lang = record.patient_language.value
            by_language[lang] = by_language.get(lang, 0) + 1
            
            itype = record.interpreter_type.value
            by_interpreter_type[itype] = by_interpreter_type.get(itype, 0) + 1
        
        return {
            "total_lep_encounters": len(lep_records),
            "by_language": by_language,
            "by_interpreter_type": by_interpreter_type,
            "declined_services": sum(
                1 for r in lep_records if r.patient_declined_services
            ),
            "physician_reviewed": sum(
                1 for r in lep_records if r.physician_review_completed
            )
        }
    
    def _generate_recommendations(
        self,
        records: List[LanguageServiceRecord],
        compliance_rate: float,
        avg_quality: float,
        by_language: Dict[SupportedLocale, int]
    ) -> List[str]:
        """
        Generate recommendations for improving language services.
        """
        recommendations = []
        
        if compliance_rate < self.COMPLIANCE_RATE_TARGET:
            recommendations.append(
                f"Compliance rate is {compliance_rate*100:.1f}%. "
                f"Target is {self.COMPLIANCE_RATE_TARGET*100:.0f}%+. "
                f"Ensure all LEP patients are offered language services."
            )
        
        if avg_quality < self.QUALITY_SCORE_TARGET and avg_quality > 0:
            recommendations.append(
                f"Average translation quality is {avg_quality:.2f}. "
                f"Target is {self.QUALITY_SCORE_TARGET}+. "
                f"Review translation memory for commonly mistranslated terms."
            )
        
        # Check for languages that need more support
        for lang, count in by_language.items():
            if count >= 10 and lang != SupportedLocale.EN_US:
                recommendations.append(
                    f"{count} encounters in {lang.language_name}. "
                    f"Consider recruiting bilingual staff for this language."
                )
        
        # Check physician review rate
        reviewed = sum(1 for r in records if r.physician_review_completed)
        review_rate = reviewed / len(records) if records else 0
        if review_rate < 0.5:
            recommendations.append(
                f"Only {review_rate*100:.0f}% of translations reviewed by physicians. "
                f"Increase physician review to improve accuracy."
            )
        
        if not recommendations:
            recommendations.append(
                "Language services are meeting all compliance targets. "
                "Continue current practices."
            )
        
        return recommendations
