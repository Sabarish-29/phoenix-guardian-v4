"""
Tests for Patient Communication Generator (14 tests).

Tests:
1. Initialization
2. Discharge instructions generation
3. Medication guide generation
4. Appointment reminder generation
5. Language-specific formatting
6. Communication types
"""

import pytest
from datetime import date, datetime

from phoenix_guardian.language.patient_communication_generator import (
    PatientCommunicationGenerator,
    DischargeInstructions,
    MedicationInstruction,
    FollowUpAppointment,
    CommunicationType,
    ReadingLevel,
)
from phoenix_guardian.language.language_detector import Language


class TestGeneratorInitialization:
    """Tests for generator initialization."""
    
    def test_initialization_default(self):
        """Test default initialization."""
        generator = PatientCommunicationGenerator()
        
        assert generator is not None
        assert generator.reading_level == ReadingLevel.MIDDLE_SCHOOL
    
    def test_initialization_custom_level(self):
        """Test initialization with custom reading level."""
        generator = PatientCommunicationGenerator(
            reading_level=ReadingLevel.ELEMENTARY
        )
        
        assert generator.reading_level == ReadingLevel.ELEMENTARY
    
    def test_supported_languages(self):
        """Test getting supported languages."""
        generator = PatientCommunicationGenerator()
        
        languages = generator.get_supported_languages()
        
        assert Language.ENGLISH in languages
        assert Language.SPANISH_MX in languages
        assert Language.MANDARIN in languages
    
    def test_communication_types(self):
        """Test getting communication types."""
        generator = PatientCommunicationGenerator()
        
        types = generator.get_communication_types()
        
        assert CommunicationType.DISCHARGE_INSTRUCTIONS in types
        assert CommunicationType.MEDICATION_GUIDE in types
        assert CommunicationType.APPOINTMENT_REMINDER in types


class TestDischargeInstructionsGeneration:
    """Tests for discharge instructions generation."""
    
    def test_generate_discharge_instructions_english(self):
        """Test generating English discharge instructions."""
        generator = PatientCommunicationGenerator()
        
        instructions = generator.generate_discharge_instructions(
            patient_name="John Smith",
            language=Language.ENGLISH,
            diagnosis="Type 2 Diabetes",
            medications=[
                {"name": "Metformin", "dosage": "500mg", "frequency": "twice daily", "route": "oral"}
            ],
            activity_restrictions=["Avoid strenuous exercise for 24 hours"],
            warning_signs=["High fever", "Severe chest pain"],
            follow_up=[
                {"specialty": "Primary Care", "timeframe": "within 2 weeks", "reason": "Follow-up"}
            ]
        )
        
        assert isinstance(instructions, DischargeInstructions)
        assert instructions.patient_name == "John Smith"
        assert instructions.language == Language.ENGLISH
    
    def test_generate_discharge_instructions_spanish(self):
        """Test generating Spanish discharge instructions."""
        generator = PatientCommunicationGenerator()
        
        instructions = generator.generate_discharge_instructions(
            patient_name="María García",
            language=Language.SPANISH_MX,
            diagnosis="Diabetes Tipo 2",
            medications=[],
            activity_restrictions=[],
            warning_signs=["Fiebre alta"],
            follow_up=[]
        )
        
        assert instructions.language == Language.SPANISH_MX
    
    def test_discharge_instructions_to_text(self):
        """Test converting instructions to text."""
        generator = PatientCommunicationGenerator()
        
        instructions = generator.generate_discharge_instructions(
            patient_name="John Smith",
            language=Language.ENGLISH,
            diagnosis="Diabetes",
            medications=[],
            activity_restrictions=[],
            warning_signs=[],
            follow_up=[]
        )
        
        text = instructions.to_text()
        
        assert "John Smith" in text
        assert "Discharge Instructions" in text.upper() or "DISCHARGE" in text.upper()


class TestMedicationGuideGeneration:
    """Tests for medication guide generation."""
    
    def test_generate_medication_guide(self):
        """Test generating medication guide."""
        generator = PatientCommunicationGenerator()
        
        medications = [
            MedicationInstruction(
                medication_name="Metformin",
                dosage="500mg",
                frequency="twice daily",
                route="oral",
                special_instructions="Take with food",
                side_effects=["Nausea", "Diarrhea"]
            )
        ]
        
        guide = generator.generate_medication_guide(
            medications,
            Language.ENGLISH
        )
        
        assert "Metformin" in guide.upper()
        assert "500mg" in guide
    
    def test_medication_guide_spanish(self):
        """Test generating Spanish medication guide."""
        generator = PatientCommunicationGenerator()
        
        medications = [
            MedicationInstruction(
                medication_name="Aspirina",
                dosage="325mg",
                frequency="una vez al día",
                route="oral"
            )
        ]
        
        guide = generator.generate_medication_guide(
            medications,
            Language.SPANISH_MX
        )
        
        assert "Aspirina" in guide.upper()


class TestAppointmentReminderGeneration:
    """Tests for appointment reminder generation."""
    
    def test_generate_appointment_reminder_english(self):
        """Test generating English appointment reminder."""
        generator = PatientCommunicationGenerator()
        
        reminder = generator.generate_appointment_reminder(
            patient_name="John Smith",
            appointment_date=date(2026, 2, 15),
            appointment_time="10:00 AM",
            provider_name="Dr. Johnson",
            specialty="Primary Care",
            location="123 Medical Center",
            language=Language.ENGLISH
        )
        
        assert "John Smith" in reminder
        assert "Dr. Johnson" in reminder
        assert "February" in reminder or "2026" in reminder
    
    def test_generate_appointment_reminder_spanish(self):
        """Test generating Spanish appointment reminder."""
        generator = PatientCommunicationGenerator()
        
        reminder = generator.generate_appointment_reminder(
            patient_name="María García",
            appointment_date=date(2026, 2, 15),
            appointment_time="10:00 AM",
            provider_name="Dr. López",
            specialty="Medicina Familiar",
            location="Centro Médico",
            language=Language.SPANISH_MX
        )
        
        assert "María García" in reminder
        assert "RECORDATORIO" in reminder.upper() or "CITA" in reminder.upper()
    
    def test_generate_appointment_reminder_mandarin(self):
        """Test generating Mandarin appointment reminder."""
        generator = PatientCommunicationGenerator()
        
        reminder = generator.generate_appointment_reminder(
            patient_name="李明",
            appointment_date=date(2026, 2, 15),
            appointment_time="10:00 AM",
            provider_name="张医生",
            specialty="内科",
            location="医疗中心",
            language=Language.MANDARIN
        )
        
        assert "李明" in reminder
        assert "预约" in reminder or "提醒" in reminder


class TestLanguageSpecificFormatting:
    """Tests for language-specific formatting."""
    
    def test_section_headers_per_language(self):
        """Test section headers are defined per language."""
        generator = PatientCommunicationGenerator()
        
        assert Language.ENGLISH in generator.SECTION_HEADERS
        assert Language.SPANISH_MX in generator.SECTION_HEADERS
        assert Language.MANDARIN in generator.SECTION_HEADERS
    
    def test_common_phrases_per_language(self):
        """Test common phrases are defined per language."""
        generator = PatientCommunicationGenerator()
        
        assert Language.ENGLISH in generator.COMMON_PHRASES
        assert Language.SPANISH_MX in generator.COMMON_PHRASES
        assert Language.MANDARIN in generator.COMMON_PHRASES
    
    def test_frequency_translations(self):
        """Test frequency translations are defined."""
        generator = PatientCommunicationGenerator()
        
        english_freq = generator.FREQUENCY_TRANSLATIONS[Language.ENGLISH]
        spanish_freq = generator.FREQUENCY_TRANSLATIONS[Language.SPANISH_MX]
        
        assert "twice_daily" in english_freq
        assert "twice_daily" in spanish_freq
        assert english_freq["twice_daily"] == "twice daily"
        assert spanish_freq["twice_daily"] == "dos veces al día"
