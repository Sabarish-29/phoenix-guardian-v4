"""
Phoenix Guardian - CDS Engine Tests
Sprint 65-66: CDS Expansion

Comprehensive tests for Clinical Decision Support Engine.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

# Import CDS components
import sys
sys.path.insert(0, "d:/phoenix guardian v4")

from cds.cds_engine import (
    CDSHookType,
    CardIndicator,
    CardSource,
    CDSCard,
    CDSRequest,
    CDSResponse,
    CDSRule,
    CDSEngine,
    DrugInteractionRule,
    LabCriticalValueRule,
    SOAPQualityRule,
    AlertFatigueManager,
)


class TestCDSCard:
    """Test CDS Card creation and FHIR conversion."""
    
    def test_card_creation_defaults(self):
        """Test card creation with defaults."""
        card = CDSCard(
            summary="Test summary",
            detail="Test detail",
        )
        
        assert card.summary == "Test summary"
        assert card.detail == "Test detail"
        assert card.indicator == CardIndicator.INFO
        assert card.source_label == "Phoenix Guardian"
        assert card.uuid is not None
        assert len(card.uuid) == 36  # UUID format
    
    def test_card_with_all_fields(self):
        """Test card with all fields populated."""
        card = CDSCard(
            uuid="test-uuid-123",
            summary="Critical alert",
            detail="This is a critical alert",
            indicator=CardIndicator.CRITICAL,
            source_label="Drug Database",
            source_url="https://example.com",
            source_type=CardSource.DRUG_DATABASE,
            suggestions=[{"label": "Take action", "uuid": "sug-1"}],
            links=[{"label": "Learn more", "url": "/learn"}],
            override_reasons=["Patient tolerating", "Will monitor"],
            rule_id="test-001",
            evidence_grade="A",
        )
        
        assert card.indicator == CardIndicator.CRITICAL
        assert len(card.suggestions) == 1
        assert len(card.links) == 1
        assert len(card.override_reasons) == 2
    
    def test_card_to_fhir_format(self):
        """Test conversion to FHIR CDS Hooks format."""
        card = CDSCard(
            uuid="fhir-uuid",
            summary="Drug interaction",
            detail="Detailed information",
            indicator=CardIndicator.WARNING,
            source_label="Phoenix Guardian",
            source_url="https://phoenix.health",
            override_reasons=["Clinical override"],
        )
        
        fhir = card.to_fhir()
        
        assert fhir["uuid"] == "fhir-uuid"
        assert fhir["summary"] == "Drug interaction"
        assert fhir["indicator"] == "warning"
        assert fhir["source"]["label"] == "Phoenix Guardian"
        assert fhir["source"]["url"] == "https://phoenix.health"
        assert len(fhir["overrideReasons"]) == 1
        assert fhir["overrideReasons"][0]["code"] == "Clinical override"
    
    def test_card_to_fhir_minimal(self):
        """Test minimal card FHIR conversion."""
        card = CDSCard(summary="Info", detail="Details")
        fhir = card.to_fhir()
        
        assert "uuid" in fhir
        assert "summary" in fhir
        assert "indicator" in fhir
        assert "source" in fhir
        # Optional fields should not be present if empty
        assert "suggestions" not in fhir or fhir.get("suggestions") == []


class TestCDSRequest:
    """Test CDS Request parsing and context extraction."""
    
    def test_request_creation(self):
        """Test basic request creation."""
        request = CDSRequest(
            hook=CDSHookType.PATIENT_VIEW,
            context={"patientId": "patient-123"},
        )
        
        assert request.hook == CDSHookType.PATIENT_VIEW
        assert request.patient_id == "patient-123"
        assert request.hook_instance is not None
    
    def test_patient_id_from_context(self):
        """Test patient ID extraction from context."""
        request = CDSRequest(
            hook=CDSHookType.ORDER_SELECT,
            context={"patientId": "ctx-patient"},
        )
        
        assert request.patient_id == "ctx-patient"
    
    def test_patient_id_from_prefetch(self):
        """Test patient ID extraction from prefetch."""
        request = CDSRequest(
            hook=CDSHookType.ORDER_SELECT,
            prefetch={"patient": {"id": "prefetch-patient", "resourceType": "Patient"}},
        )
        
        assert request.patient_id == "prefetch-patient"
    
    def test_encounter_id_extraction(self):
        """Test encounter ID extraction."""
        request = CDSRequest(
            hook=CDSHookType.ENCOUNTER_START,
            context={"patientId": "p1", "encounterId": "enc-456"},
        )
        
        assert request.encounter_id == "enc-456"
    
    def test_request_with_fhir_authorization(self):
        """Test request with FHIR authorization."""
        request = CDSRequest(
            hook=CDSHookType.MEDICATION_PRESCRIBE,
            fhir_server="https://fhir.hospital.com",
            fhir_authorization={
                "access_token": "token123",
                "token_type": "Bearer",
            },
        )
        
        assert request.fhir_server == "https://fhir.hospital.com"
        assert request.fhir_authorization["access_token"] == "token123"


class TestCDSResponse:
    """Test CDS Response creation and conversion."""
    
    def test_response_creation(self):
        """Test basic response creation."""
        response = CDSResponse(
            cards=[CDSCard(summary="Test", detail="Details")],
            latency_ms=50.5,
            rules_evaluated=3,
        )
        
        assert len(response.cards) == 1
        assert response.latency_ms == 50.5
        assert response.rules_evaluated == 3
    
    def test_response_to_fhir(self):
        """Test FHIR conversion."""
        response = CDSResponse(
            cards=[
                CDSCard(summary="Card 1", detail="Detail 1"),
                CDSCard(summary="Card 2", detail="Detail 2"),
            ],
            system_actions=[{"type": "update", "resource": {}}],
        )
        
        fhir = response.to_fhir()
        
        assert len(fhir["cards"]) == 2
        assert len(fhir["systemActions"]) == 1


class TestDrugInteractionRule:
    """Test drug-drug interaction detection."""
    
    @pytest.fixture
    def rule(self):
        return DrugInteractionRule()
    
    def test_rule_metadata(self, rule):
        """Test rule metadata."""
        assert rule.rule_id == "drug-interaction-001"
        assert rule.priority == 10
        assert rule.evidence_grade == "A"
        assert CDSHookType.MEDICATION_PRESCRIBE in rule.hooks
    
    def test_prefetch_templates(self, rule):
        """Test prefetch template generation."""
        templates = rule.prefetch_templates()
        
        assert "patient" in templates
        assert "medications" in templates
        assert "{{context.patientId}}" in templates["medications"]
    
    @pytest.mark.asyncio
    async def test_warfarin_aspirin_interaction(self, rule):
        """Test detection of warfarin-aspirin interaction."""
        request = CDSRequest(
            hook=CDSHookType.MEDICATION_PRESCRIBE,
            context={
                "patientId": "p1",
                "draftOrders": {"medication": "aspirin 81mg"},
            },
            prefetch={
                "medications": {
                    "resourceType": "Bundle",
                    "entry": [{
                        "resource": {
                            "resourceType": "MedicationRequest",
                            "medicationCodeableConcept": {
                                "coding": [{"display": "Warfarin 5mg"}]
                            }
                        }
                    }]
                }
            },
        )
        
        cards = await rule.evaluate(request)
        
        assert len(cards) == 1
        assert cards[0].indicator == CardIndicator.CRITICAL
        assert "bleeding" in cards[0].detail.lower()
    
    @pytest.mark.asyncio
    async def test_no_interaction(self, rule):
        """Test no false positive when no interaction."""
        request = CDSRequest(
            hook=CDSHookType.MEDICATION_PRESCRIBE,
            context={
                "patientId": "p1",
                "draftOrders": {"medication": "acetaminophen 500mg"},
            },
            prefetch={
                "medications": {
                    "resourceType": "Bundle",
                    "entry": [{
                        "resource": {
                            "resourceType": "MedicationRequest",
                            "medicationCodeableConcept": {
                                "coding": [{"display": "Lisinopril 10mg"}]
                            }
                        }
                    }]
                }
            },
        )
        
        cards = await rule.evaluate(request)
        
        assert len(cards) == 0
    
    @pytest.mark.asyncio
    async def test_empty_medication(self, rule):
        """Test handling of empty medication."""
        request = CDSRequest(
            hook=CDSHookType.MEDICATION_PRESCRIBE,
            context={"patientId": "p1", "draftOrders": {}},
            prefetch={},
        )
        
        cards = await rule.evaluate(request)
        
        assert len(cards) == 0


class TestLabCriticalValueRule:
    """Test critical lab value detection."""
    
    @pytest.fixture
    def rule(self):
        return LabCriticalValueRule()
    
    def test_rule_metadata(self, rule):
        """Test rule metadata."""
        assert rule.rule_id == "lab-critical-001"
        assert rule.priority == 5  # Higher priority than drug interactions
        assert CDSHookType.PATIENT_VIEW in rule.hooks
    
    @pytest.mark.asyncio
    async def test_critical_potassium_high(self, rule):
        """Test detection of critically high potassium."""
        request = CDSRequest(
            hook=CDSHookType.PATIENT_VIEW,
            context={"patientId": "p1"},
            prefetch={
                "labs": {
                    "resourceType": "Bundle",
                    "entry": [{
                        "resource": {
                            "resourceType": "Observation",
                            "code": {"coding": [{"display": "Potassium"}]},
                            "valueQuantity": {"value": 7.0, "unit": "mEq/L"},
                        }
                    }]
                }
            },
        )
        
        cards = await rule.evaluate(request)
        
        assert len(cards) == 1
        assert cards[0].indicator == CardIndicator.CRITICAL
        assert "potassium" in cards[0].summary.lower()
        assert "critically high" in cards[0].summary.lower()
    
    @pytest.mark.asyncio
    async def test_critical_glucose_low(self, rule):
        """Test detection of critically low glucose."""
        request = CDSRequest(
            hook=CDSHookType.PATIENT_VIEW,
            context={"patientId": "p1"},
            prefetch={
                "labs": {
                    "resourceType": "Bundle",
                    "entry": [{
                        "resource": {
                            "resourceType": "Observation",
                            "code": {"coding": [{"display": "Glucose"}]},
                            "valueQuantity": {"value": 35, "unit": "mg/dL"},
                        }
                    }]
                }
            },
        )
        
        cards = await rule.evaluate(request)
        
        assert len(cards) == 1
        assert "glucose" in cards[0].summary.lower()
        assert "critically low" in cards[0].summary.lower()
    
    @pytest.mark.asyncio
    async def test_normal_values_no_alert(self, rule):
        """Test no alert for normal values."""
        request = CDSRequest(
            hook=CDSHookType.PATIENT_VIEW,
            context={"patientId": "p1"},
            prefetch={
                "labs": {
                    "resourceType": "Bundle",
                    "entry": [{
                        "resource": {
                            "resourceType": "Observation",
                            "code": {"coding": [{"display": "Potassium"}]},
                            "valueQuantity": {"value": 4.0, "unit": "mEq/L"},
                        }
                    }]
                }
            },
        )
        
        cards = await rule.evaluate(request)
        
        assert len(cards) == 0
    
    @pytest.mark.asyncio
    async def test_multiple_critical_labs(self, rule):
        """Test multiple critical lab values."""
        request = CDSRequest(
            hook=CDSHookType.PATIENT_VIEW,
            context={"patientId": "p1"},
            prefetch={
                "labs": {
                    "resourceType": "Bundle",
                    "entry": [
                        {
                            "resource": {
                                "resourceType": "Observation",
                                "code": {"coding": [{"display": "Potassium"}]},
                                "valueQuantity": {"value": 7.5},
                            }
                        },
                        {
                            "resource": {
                                "resourceType": "Observation",
                                "code": {"coding": [{"display": "Sodium"}]},
                                "valueQuantity": {"value": 115},
                            }
                        },
                    ]
                }
            },
        )
        
        cards = await rule.evaluate(request)
        
        assert len(cards) == 2


class TestSOAPQualityRule:
    """Test SOAP note quality checks."""
    
    @pytest.fixture
    def rule(self):
        return SOAPQualityRule()
    
    def test_rule_metadata(self, rule):
        """Test rule metadata."""
        assert rule.rule_id == "soap-quality-001"
        assert CDSHookType.SOAP_NOTE_DRAFT in rule.hooks
        assert CDSHookType.SOAP_NOTE_SIGN in rule.hooks
    
    @pytest.mark.asyncio
    async def test_incomplete_subjective(self, rule):
        """Test detection of incomplete subjective section."""
        request = CDSRequest(
            hook=CDSHookType.SOAP_NOTE_DRAFT,
            context={
                "patientId": "p1",
                "soapNote": {
                    "subjective": "Headache",  # Too short
                    "objective": "V" * 150,
                    "assessment": "A" * 100,
                    "plan": "P" * 150,
                    "icd10_codes": ["R51"],
                },
            },
        )
        
        cards = await rule.evaluate(request)
        
        # Should have warning about subjective being short
        assert any("subjective" in c.summary.lower() for c in cards)
    
    @pytest.mark.asyncio
    async def test_missing_icd10_codes(self, rule):
        """Test detection of missing ICD-10 codes."""
        request = CDSRequest(
            hook=CDSHookType.SOAP_NOTE_SIGN,
            context={
                "patientId": "p1",
                "soapNote": {
                    "subjective": "S" * 100,
                    "objective": "O" * 150,
                    "assessment": "A" * 100,
                    "plan": "P" * 150,
                    # Missing icd10_codes
                },
            },
        )
        
        cards = await rule.evaluate(request)
        
        assert any("diagnosis code" in c.summary.lower() for c in cards)
    
    @pytest.mark.asyncio
    async def test_complete_soap_note(self, rule):
        """Test no warnings for complete SOAP note."""
        request = CDSRequest(
            hook=CDSHookType.SOAP_NOTE_SIGN,
            context={
                "patientId": "p1",
                "soapNote": {
                    "subjective": "Patient presents with 3-day history of persistent headache. " * 5,
                    "objective": "Vital signs stable. Neurological exam normal. " * 10,
                    "assessment": "Tension headache. No red flags for secondary causes. " * 5,
                    "plan": "Ibuprofen 400mg TID. Follow up in 2 weeks if no improvement. " * 5,
                    "icd10_codes": ["G44.209"],
                },
            },
        )
        
        cards = await rule.evaluate(request)
        
        # Should have no quality warnings
        assert len(cards) == 0


class TestAlertFatigueManager:
    """Test alert fatigue management."""
    
    @pytest.fixture
    def manager(self):
        return AlertFatigueManager(redis_client=None)
    
    @pytest.mark.asyncio
    async def test_never_suppress_critical(self, manager):
        """Test that critical alerts are never suppressed."""
        card = CDSCard(
            summary="Critical",
            detail="Critical alert",
            indicator=CardIndicator.CRITICAL,
            rule_id="test-rule",
        )
        
        result = await manager.should_suppress(card, "user-1", "patient-1")
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_info_can_be_suppressed_by_cooldown(self, manager):
        """Test that info alerts can be suppressed by cooldown."""
        card = CDSCard(
            summary="Info",
            detail="Info alert",
            indicator=CardIndicator.INFO,
            rule_id="test-rule",
        )
        
        # Mock the last shown time to be recent
        manager._local_cache["cds:shown:test-rule:user-1:patient-1"] = {
            "last_shown": datetime.utcnow() - timedelta(hours=1)
        }
        
        with patch.object(manager, "_get_last_shown", return_value=datetime.utcnow() - timedelta(hours=1)):
            result = await manager.should_suppress(card, "user-1", "patient-1")
            assert result is True
    
    @pytest.mark.asyncio
    async def test_record_interaction(self, manager):
        """Test recording user interaction."""
        # Should not raise
        await manager.record_interaction(
            card_uuid="card-123",
            user_id="user-1",
            action="dismissed",
            override_reason="Not clinically relevant",
        )
    
    @pytest.mark.asyncio
    async def test_fatigue_report_structure(self, manager):
        """Test fatigue report structure."""
        report = await manager.get_fatigue_report("user-1")
        
        assert "user_id" in report
        assert "total_alerts" in report
        assert "accepted" in report
        assert "dismissed" in report
        assert "override_rate" in report


class TestCDSEngine:
    """Test main CDS Engine."""
    
    @pytest.fixture
    def engine(self):
        return CDSEngine()
    
    def test_default_rules_registered(self, engine):
        """Test default rules are registered."""
        assert len(engine.rules) >= 3
        
        rule_ids = [r.rule_id for r in engine.rules]
        assert "drug-interaction-001" in rule_ids
        assert "lab-critical-001" in rule_ids
        assert "soap-quality-001" in rule_ids
    
    def test_service_discovery(self, engine):
        """Test CDS Hooks service discovery."""
        services = engine.get_service_definition()
        
        assert "services" in services
        assert len(services["services"]) > 0
        
        # Check service structure
        service = services["services"][0]
        assert "id" in service
        assert "hook" in service
        assert "title" in service
        assert "prefetch" in service
    
    @pytest.mark.asyncio
    async def test_evaluate_patient_view(self, engine):
        """Test evaluation of patient-view hook."""
        request = CDSRequest(
            hook=CDSHookType.PATIENT_VIEW,
            context={"patientId": "p1"},
            prefetch={
                "labs": {
                    "resourceType": "Bundle",
                    "entry": [{
                        "resource": {
                            "resourceType": "Observation",
                            "code": {"coding": [{"display": "Potassium"}]},
                            "valueQuantity": {"value": 7.5},
                        }
                    }]
                }
            },
        )
        
        response = await engine.evaluate(request)
        
        assert isinstance(response, CDSResponse)
        assert response.rules_evaluated > 0
        assert response.latency_ms >= 0
        # Should have critical potassium alert
        assert len(response.cards) >= 1
    
    @pytest.mark.asyncio
    async def test_cards_sorted_by_severity(self, engine):
        """Test that cards are sorted by severity."""
        request = CDSRequest(
            hook=CDSHookType.SOAP_NOTE_DRAFT,
            context={
                "patientId": "p1",
                "soapNote": {
                    "subjective": "Short",
                    "objective": "Short",
                    "assessment": "Short",
                    "plan": "Short",
                },
            },
            prefetch={
                "labs": {
                    "resourceType": "Bundle",
                    "entry": [{
                        "resource": {
                            "resourceType": "Observation",
                            "code": {"coding": [{"display": "Potassium"}]},
                            "valueQuantity": {"value": 7.5},
                        }
                    }]
                }
            },
        )
        
        response = await engine.evaluate(request)
        
        if len(response.cards) >= 2:
            # Critical should come before warnings
            first_critical_idx = next(
                (i for i, c in enumerate(response.cards) if c.indicator == CardIndicator.CRITICAL),
                len(response.cards)
            )
            first_warning_idx = next(
                (i for i, c in enumerate(response.cards) if c.indicator == CardIndicator.WARNING),
                len(response.cards)
            )
            first_info_idx = next(
                (i for i, c in enumerate(response.cards) if c.indicator == CardIndicator.INFO),
                len(response.cards)
            )
            
            assert first_critical_idx <= first_warning_idx <= first_info_idx
    
    def test_enable_disable_rule(self, engine):
        """Test enabling and disabling rules."""
        rule_id = "drug-interaction-001"
        
        # Disable
        result = engine.disable_rule(rule_id)
        assert result is True
        
        rule = engine.get_rule_by_id(rule_id)
        assert rule.enabled is False
        
        # Enable
        result = engine.enable_rule(rule_id)
        assert result is True
        assert rule.enabled is True
    
    def test_get_rule_by_id(self, engine):
        """Test getting rule by ID."""
        rule = engine.get_rule_by_id("drug-interaction-001")
        assert rule is not None
        assert rule.rule_id == "drug-interaction-001"
        
        # Non-existent
        rule = engine.get_rule_by_id("nonexistent-rule")
        assert rule is None
    
    @pytest.mark.asyncio
    async def test_record_feedback(self, engine):
        """Test recording feedback."""
        # Should not raise
        await engine.record_feedback(
            card_uuid="card-123",
            user_id="user-1",
            action="accepted",
        )
    
    def test_register_custom_rule(self, engine):
        """Test registering a custom rule."""
        
        class CustomRule(CDSRule):
            rule_id = "custom-001"
            name = "Custom Rule"
            description = "Test custom rule"
            version = "1.0.0"
            hooks = [CDSHookType.PATIENT_VIEW]
            
            async def evaluate(self, request: CDSRequest) -> list[CDSCard]:
                return []
            
            def prefetch_templates(self) -> dict[str, str]:
                return {}
        
        initial_count = len(engine.rules)
        engine.register_rule(CustomRule())
        
        assert len(engine.rules) == initial_count + 1
        assert engine.get_rule_by_id("custom-001") is not None


class TestCDSHookTypes:
    """Test CDS Hook type enumeration."""
    
    def test_standard_hooks(self):
        """Test standard CDS Hooks are defined."""
        assert CDSHookType.PATIENT_VIEW.value == "patient-view"
        assert CDSHookType.ORDER_SELECT.value == "order-select"
        assert CDSHookType.MEDICATION_PRESCRIBE.value == "medication-prescribe"
    
    def test_phoenix_custom_hooks(self):
        """Test Phoenix Guardian custom hooks."""
        assert CDSHookType.SOAP_NOTE_DRAFT.value == "soap-note-draft"
        assert CDSHookType.SOAP_NOTE_SIGN.value == "soap-note-sign"
        assert CDSHookType.DIAGNOSIS_SUGGEST.value == "diagnosis-suggest"


class TestCardIndicators:
    """Test card indicator enumeration."""
    
    def test_indicator_values(self):
        """Test indicator values match FHIR spec."""
        assert CardIndicator.INFO.value == "info"
        assert CardIndicator.WARNING.value == "warning"
        assert CardIndicator.CRITICAL.value == "critical"


class TestIntegration:
    """Integration tests for CDS engine."""
    
    @pytest.mark.asyncio
    async def test_full_workflow(self):
        """Test complete CDS workflow."""
        engine = CDSEngine()
        
        # 1. Service discovery
        services = engine.get_service_definition()
        assert len(services["services"]) > 0
        
        # 2. Evaluate hook
        request = CDSRequest(
            hook=CDSHookType.MEDICATION_PRESCRIBE,
            context={
                "patientId": "patient-123",
                "draftOrders": {"medication": "Aspirin 81mg"},
            },
            prefetch={
                "medications": {
                    "resourceType": "Bundle",
                    "entry": [{
                        "resource": {
                            "resourceType": "MedicationRequest",
                            "medicationCodeableConcept": {
                                "coding": [{"display": "Warfarin 5mg"}]
                            }
                        }
                    }]
                }
            },
            user_id="provider-1",
            hospital_id="hospital-001",
        )
        
        response = await engine.evaluate(request)
        
        # 3. Get FHIR response
        fhir_response = response.to_fhir()
        assert "cards" in fhir_response
        
        # 4. Record feedback if cards present
        if response.cards:
            await engine.record_feedback(
                card_uuid=response.cards[0].uuid,
                user_id="provider-1",
                action="accepted",
            )
    
    @pytest.mark.asyncio
    async def test_multiple_rules_evaluated(self):
        """Test multiple rules evaluated for single hook."""
        engine = CDSEngine()
        
        # Create request that triggers multiple rules
        request = CDSRequest(
            hook=CDSHookType.SOAP_NOTE_DRAFT,
            context={
                "patientId": "patient-123",
                "soapNote": {
                    "subjective": "Short",  # Will trigger quality rule
                },
            },
            prefetch={
                "labs": {
                    "resourceType": "Bundle",
                    "entry": [{
                        "resource": {
                            "resourceType": "Observation",
                            "code": {"coding": [{"display": "Potassium"}]},
                            "valueQuantity": {"value": 7.5},  # Will trigger lab rule
                        }
                    }]
                }
            },
        )
        
        response = await engine.evaluate(request)
        
        # Should have cards from multiple rules
        assert len(response.cards) >= 2
        assert response.rules_evaluated >= 2
