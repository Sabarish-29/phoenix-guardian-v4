"""
Tests for Regulatory Compliance (20 tests).

Tests:
1. Service record management
2. Title VI report generation
3. Language access plan
4. Compliance metrics
5. LEP statistics
6. Recommendations
"""

import pytest
from datetime import datetime, timedelta

from phoenix_guardian.localization.regulatory_compliance import (
    RegulatoryCompliance,
    LanguageServiceRecord,
    TitleVIReport,
    LanguageAccessPlan,
    InterpreterType,
    DocumentType,
)
from phoenix_guardian.localization.locale_manager import SupportedLocale


class TestServiceRecordManagement:
    """Tests for service record management."""
    
    def test_record_language_service(self):
        """Test recording language service."""
        compliance = RegulatoryCompliance()
        
        record = compliance.record_language_service(
            patient_id="patient1",
            encounter_id="encounter1",
            patient_language=SupportedLocale.ES_MX,
            interpreter_type=InterpreterType.AI_TRANSLATION,
            documents_translated=[DocumentType.DISCHARGE_INSTRUCTIONS],
            patient_notified=True,
            translation_quality_score=0.95
        )
        
        assert isinstance(record, LanguageServiceRecord)
        assert record.patient_id == "patient1"
        assert record.patient_language == SupportedLocale.ES_MX
        assert record.patient_notified_of_services is True
    
    def test_record_service_declined(self):
        """Test recording when patient declines services."""
        compliance = RegulatoryCompliance()
        
        record = compliance.record_service_declined(
            patient_id="patient2",
            encounter_id="encounter2",
            patient_language=SupportedLocale.ZH_CN
        )
        
        assert record.patient_declined_services is True
        assert record.patient_notified_of_services is True
    
    def test_service_record_to_dict(self):
        """Test service record serialization."""
        record = LanguageServiceRecord(
            patient_id="patient1",
            encounter_id="encounter1",
            date=datetime.now().isoformat(),
            patient_language=SupportedLocale.ES_MX,
            interpreter_type=InterpreterType.AI_TRANSLATION,
            documents_translated=[DocumentType.DISCHARGE_INSTRUCTIONS]
        )
        
        d = record.to_dict()
        
        assert d["patient_id"] == "patient1"
        assert d["patient_language"] == "es-MX"
        assert d["interpreter_type"] == "ai_translation"


class TestTitleVIReportGeneration:
    """Tests for Title VI report generation."""
    
    def test_generate_report(self):
        """Test generating Title VI report."""
        compliance = RegulatoryCompliance()
        
        # Add some records
        now = datetime.now()
        for i in range(5):
            compliance.record_language_service(
                patient_id=f"patient{i}",
                encounter_id=f"encounter{i}",
                patient_language=SupportedLocale.ES_MX,
                interpreter_type=InterpreterType.AI_TRANSLATION,
                documents_translated=[DocumentType.DISCHARGE_INSTRUCTIONS],
                translation_quality_score=0.9
            )
        
        report = compliance.generate_title_vi_report(
            tenant_id="hospital1",
            hospital_name="Test Hospital",
            start_date=(now - timedelta(days=1)).isoformat(),
            end_date=(now + timedelta(days=1)).isoformat()
        )
        
        assert isinstance(report, TitleVIReport)
        assert report.total_encounters == 5
        assert report.hospital_name == "Test Hospital"
    
    def test_report_encounters_by_language(self):
        """Test report tracks encounters by language."""
        compliance = RegulatoryCompliance()
        
        now = datetime.now()
        
        # Add Spanish encounters
        for i in range(3):
            compliance.record_language_service(
                patient_id=f"es_patient{i}",
                encounter_id=f"es_encounter{i}",
                patient_language=SupportedLocale.ES_MX,
                interpreter_type=InterpreterType.AI_TRANSLATION,
                documents_translated=[]
            )
        
        # Add Mandarin encounters
        for i in range(2):
            compliance.record_language_service(
                patient_id=f"zh_patient{i}",
                encounter_id=f"zh_encounter{i}",
                patient_language=SupportedLocale.ZH_CN,
                interpreter_type=InterpreterType.AI_TRANSLATION,
                documents_translated=[]
            )
        
        report = compliance.generate_title_vi_report(
            tenant_id="hospital1",
            hospital_name="Test Hospital",
            start_date=(now - timedelta(days=1)).isoformat(),
            end_date=(now + timedelta(days=1)).isoformat()
        )
        
        assert report.encounters_by_language[SupportedLocale.ES_MX] == 3
        assert report.encounters_by_language[SupportedLocale.ZH_CN] == 2
    
    def test_report_compliance_rate(self):
        """Test compliance rate calculation."""
        compliance = RegulatoryCompliance()
        
        now = datetime.now()
        
        # All LEP patients served
        for i in range(5):
            compliance.record_language_service(
                patient_id=f"patient{i}",
                encounter_id=f"encounter{i}",
                patient_language=SupportedLocale.ES_MX,
                interpreter_type=InterpreterType.AI_TRANSLATION,
                documents_translated=[],
                patient_notified=True
            )
        
        report = compliance.generate_title_vi_report(
            tenant_id="hospital1",
            hospital_name="Test Hospital",
            start_date=(now - timedelta(days=1)).isoformat(),
            end_date=(now + timedelta(days=1)).isoformat()
        )
        
        # 100% compliance
        assert report.compliance_rate == 1.0
        assert report.is_compliant is True
    
    def test_report_to_dict(self):
        """Test report serialization."""
        compliance = RegulatoryCompliance()
        
        now = datetime.now()
        compliance.record_language_service(
            patient_id="patient1",
            encounter_id="encounter1",
            patient_language=SupportedLocale.ES_MX,
            interpreter_type=InterpreterType.AI_TRANSLATION,
            documents_translated=[]
        )
        
        report = compliance.generate_title_vi_report(
            tenant_id="hospital1",
            hospital_name="Test Hospital",
            start_date=(now - timedelta(days=1)).isoformat(),
            end_date=(now + timedelta(days=1)).isoformat()
        )
        
        d = report.to_dict()
        
        assert "report_period" in d
        assert "hospital" in d
        assert "summary" in d
        assert "compliance" in d


class TestLanguageAccessPlan:
    """Tests for language access plan."""
    
    def test_create_language_access_plan(self):
        """Test creating language access plan."""
        compliance = RegulatoryCompliance()
        
        plan = compliance.create_language_access_plan(
            hospital_name="Test Hospital",
            tenant_id="hospital1",
            supported_languages=[
                SupportedLocale.EN_US,
                SupportedLocale.ES_MX,
                SupportedLocale.ZH_CN
            ]
        )
        
        assert isinstance(plan, LanguageAccessPlan)
        assert plan.hospital_name == "Test Hospital"
        assert len(plan.primary_languages) == 3
        assert plan.interpretation_available_24_7 is True
    
    def test_vital_documents_specified(self):
        """Test vital documents are specified in plan."""
        compliance = RegulatoryCompliance()
        
        plan = compliance.create_language_access_plan(
            hospital_name="Test Hospital",
            tenant_id="hospital1",
            supported_languages=[SupportedLocale.ES_MX]
        )
        
        assert DocumentType.DISCHARGE_INSTRUCTIONS in plan.vital_documents_translated
        assert DocumentType.CONSENT_FORM in plan.vital_documents_translated
        assert DocumentType.PATIENT_RIGHTS in plan.vital_documents_translated
    
    def test_get_language_access_plan(self):
        """Test retrieving stored language access plan."""
        compliance = RegulatoryCompliance()
        
        compliance.create_language_access_plan(
            hospital_name="Test Hospital",
            tenant_id="hospital1",
            supported_languages=[SupportedLocale.ES_MX]
        )
        
        retrieved = compliance.get_language_access_plan("hospital1")
        
        assert retrieved is not None
        assert retrieved.hospital_name == "Test Hospital"
    
    def test_plan_to_dict(self):
        """Test plan serialization."""
        plan = LanguageAccessPlan(
            hospital_name="Test Hospital",
            tenant_id="hospital1",
            effective_date=datetime.now().isoformat(),
            primary_languages=[SupportedLocale.ES_MX],
            interpretation_available_24_7=True,
            vital_documents_translated=[DocumentType.DISCHARGE_INSTRUCTIONS],
            translator_qualifications="AI Translation",
            quality_monitoring_process="Monthly audits",
            complaint_procedure="Patient relations",
            staff_trained_on_language_services=True,
            training_frequency="Quarterly"
        )
        
        d = plan.to_dict()
        
        assert d["hospital_name"] == "Test Hospital"
        assert "es-MX" in d["primary_languages"]


class TestComplianceMetrics:
    """Tests for compliance metrics."""
    
    def test_quality_score_tracking(self):
        """Test quality score tracking."""
        compliance = RegulatoryCompliance()
        
        now = datetime.now()
        
        # Add records with varying quality
        for i, score in enumerate([0.95, 0.88, 0.92]):
            compliance.record_language_service(
                patient_id=f"patient{i}",
                encounter_id=f"encounter{i}",
                patient_language=SupportedLocale.ES_MX,
                interpreter_type=InterpreterType.AI_TRANSLATION,
                documents_translated=[],
                translation_quality_score=score
            )
        
        report = compliance.generate_title_vi_report(
            tenant_id="hospital1",
            hospital_name="Test Hospital",
            start_date=(now - timedelta(days=1)).isoformat(),
            end_date=(now + timedelta(days=1)).isoformat()
        )
        
        # Average should be (0.95 + 0.88 + 0.92) / 3 ≈ 0.92
        assert 0.91 <= report.quality_scores_average <= 0.93
    
    def test_documents_translated_count(self):
        """Test document translation counting."""
        compliance = RegulatoryCompliance()
        
        now = datetime.now()
        
        compliance.record_language_service(
            patient_id="patient1",
            encounter_id="encounter1",
            patient_language=SupportedLocale.ES_MX,
            interpreter_type=InterpreterType.AI_TRANSLATION,
            documents_translated=[
                DocumentType.DISCHARGE_INSTRUCTIONS,
                DocumentType.MEDICATION_GUIDE,
                DocumentType.CONSENT_FORM
            ]
        )
        
        report = compliance.generate_title_vi_report(
            tenant_id="hospital1",
            hospital_name="Test Hospital",
            start_date=(now - timedelta(days=1)).isoformat(),
            end_date=(now + timedelta(days=1)).isoformat()
        )
        
        assert report.documents_translated == 3


class TestLEPStatistics:
    """Tests for LEP statistics."""
    
    def test_get_lep_statistics(self):
        """Test getting LEP patient statistics."""
        compliance = RegulatoryCompliance()
        
        now = datetime.now()
        
        # Add LEP encounters
        compliance.record_language_service(
            patient_id="patient1",
            encounter_id="encounter1",
            patient_language=SupportedLocale.ES_MX,
            interpreter_type=InterpreterType.AI_TRANSLATION,
            documents_translated=[]
        )
        
        compliance.record_language_service(
            patient_id="patient2",
            encounter_id="encounter2",
            patient_language=SupportedLocale.ZH_CN,
            interpreter_type=InterpreterType.VIDEO_INTERPRETER,
            documents_translated=[]
        )
        
        stats = compliance.get_lep_statistics(
            start_date=(now - timedelta(days=1)).isoformat(),
            end_date=(now + timedelta(days=1)).isoformat()
        )
        
        assert stats["total_lep_encounters"] == 2
        assert "es-MX" in stats["by_language"]
        assert "zh-CN" in stats["by_language"]


class TestRecommendations:
    """Tests for compliance recommendations."""
    
    def test_recommendations_for_low_compliance(self):
        """Test recommendations generated for low compliance."""
        compliance = RegulatoryCompliance()
        
        now = datetime.now()
        
        # Add LEP encounters without full service
        compliance.record_language_service(
            patient_id="patient1",
            encounter_id="encounter1",
            patient_language=SupportedLocale.ES_MX,
            interpreter_type=InterpreterType.AI_TRANSLATION,
            documents_translated=[],
            patient_notified=False  # Not notified
        )
        
        report = compliance.generate_title_vi_report(
            tenant_id="hospital1",
            hospital_name="Test Hospital",
            start_date=(now - timedelta(days=1)).isoformat(),
            end_date=(now + timedelta(days=1)).isoformat()
        )
        
        # Should have recommendations
        assert len(report.recommendations) > 0
    
    def test_compliance_issues_tracked(self):
        """Test compliance issues are tracked."""
        compliance = RegulatoryCompliance()
        
        now = datetime.now()
        
        # Create low-quality scenario
        for i in range(5):
            compliance.record_language_service(
                patient_id=f"patient{i}",
                encounter_id=f"encounter{i}",
                patient_language=SupportedLocale.ES_MX,
                interpreter_type=InterpreterType.AI_TRANSLATION,
                documents_translated=[],
                translation_quality_score=0.5  # Low quality
            )
        
        report = compliance.generate_title_vi_report(
            tenant_id="hospital1",
            hospital_name="Test Hospital",
            start_date=(now - timedelta(days=1)).isoformat(),
            end_date=(now + timedelta(days=1)).isoformat()
        )
        
        # Should flag quality issues
        assert report.is_compliant is False
        assert len(report.compliance_issues) > 0


class TestServiceRecordQueries:
    """Tests for querying service records."""
    
    def test_get_records_by_patient(self):
        """Test filtering records by patient."""
        compliance = RegulatoryCompliance()
        
        compliance.record_language_service(
            patient_id="patient1",
            encounter_id="encounter1",
            patient_language=SupportedLocale.ES_MX,
            interpreter_type=InterpreterType.AI_TRANSLATION,
            documents_translated=[]
        )
        
        compliance.record_language_service(
            patient_id="patient2",
            encounter_id="encounter2",
            patient_language=SupportedLocale.ZH_CN,
            interpreter_type=InterpreterType.AI_TRANSLATION,
            documents_translated=[]
        )
        
        records = compliance.get_service_records(patient_id="patient1")
        
        assert len(records) == 1
        assert records[0].patient_id == "patient1"
    
    def test_get_records_by_language(self):
        """Test filtering records by language."""
        compliance = RegulatoryCompliance()
        
        compliance.record_language_service(
            patient_id="patient1",
            encounter_id="encounter1",
            patient_language=SupportedLocale.ES_MX,
            interpreter_type=InterpreterType.AI_TRANSLATION,
            documents_translated=[]
        )
        
        compliance.record_language_service(
            patient_id="patient2",
            encounter_id="encounter2",
            patient_language=SupportedLocale.ZH_CN,
            interpreter_type=InterpreterType.AI_TRANSLATION,
            documents_translated=[]
        )
        
        records = compliance.get_service_records(language=SupportedLocale.ES_MX)
        
        assert len(records) == 1
        assert records[0].patient_language == SupportedLocale.ES_MX
