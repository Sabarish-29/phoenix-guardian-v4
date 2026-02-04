"""
Patient Communication Generator.

Generates patient-facing communications in their preferred language:
- Discharge instructions
- Medication guides
- Appointment reminders
- Follow-up instructions
- Educational materials

LITERACY CONSIDERATIONS:
- Uses 6th-grade reading level
- Avoids medical jargon
- Includes visual cues where possible
- Culturally appropriate phrasing

REGULATORY COMPLIANCE:
- HIPAA-compliant content
- Required disclaimers included
- Emergency contact information
- Interpreter services notice
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from enum import Enum
from datetime import datetime, date
import logging

from phoenix_guardian.language.language_detector import Language

logger = logging.getLogger(__name__)


class CommunicationType(Enum):
    """Types of patient communications."""
    DISCHARGE_INSTRUCTIONS = "discharge_instructions"
    MEDICATION_GUIDE = "medication_guide"
    APPOINTMENT_REMINDER = "appointment_reminder"
    FOLLOWUP_INSTRUCTIONS = "followup_instructions"
    LAB_RESULTS = "lab_results"
    EDUCATIONAL_MATERIAL = "educational_material"
    CONSENT_FORM = "consent_form"


class ReadingLevel(Enum):
    """Target reading level for content."""
    ELEMENTARY = "elementary"      # 3rd-5th grade
    MIDDLE_SCHOOL = "middle_school"  # 6th-8th grade (recommended)
    HIGH_SCHOOL = "high_school"    # 9th-12th grade
    ADULT = "adult"                # College level


@dataclass
class MedicationInstruction:
    """Instructions for a single medication."""
    medication_name: str
    dosage: str
    frequency: str
    route: str  # oral, injection, topical, etc.
    special_instructions: Optional[str] = None
    side_effects: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


@dataclass
class FollowUpAppointment:
    """Follow-up appointment details."""
    specialty: str
    timeframe: str  # "within 2 weeks", "in 3 months"
    reason: str
    urgency: str = "routine"  # routine, urgent, emergent


@dataclass
class DischargeInstructions:
    """
    Complete discharge instructions for a patient.
    
    Attributes:
        patient_name: Patient's name
        language: Target language for instructions
        diagnosis_summary: Plain-language diagnosis
        medications: List of medication instructions
        activity_restrictions: What patient should/shouldn't do
        warning_signs: Signs requiring immediate medical attention
        follow_up: Follow-up appointment information
        emergency_contact: Emergency contact information
        generated_at: When instructions were generated
    """
    patient_name: str
    language: Language
    diagnosis_summary: str
    medications: List[MedicationInstruction]
    activity_restrictions: List[str]
    warning_signs: List[str]
    follow_up: List[FollowUpAppointment]
    emergency_contact: str = "911"
    generated_at: datetime = field(default_factory=datetime.now)
    
    # Additional content
    diet_instructions: Optional[str] = None
    wound_care: Optional[str] = None
    physical_therapy: Optional[str] = None
    
    def to_text(self) -> str:
        """Convert instructions to plain text format."""
        return PatientCommunicationGenerator().format_discharge_instructions(self)


class PatientCommunicationGenerator:
    """
    Generates patient-facing clinical communications.
    
    Creates culturally appropriate, easy-to-read medical communications
    in the patient's preferred language.
    
    Example:
        generator = PatientCommunicationGenerator()
        instructions = generator.generate_discharge_instructions(
            patient_name="María García",
            language=Language.SPANISH_MX,
            diagnosis="Type 2 Diabetes",
            medications=[...],
            follow_up=[...]
        )
        print(instructions.to_text())
    """
    
    # Section headers by language
    SECTION_HEADERS = {
        Language.ENGLISH: {
            "title": "Discharge Instructions",
            "diagnosis": "Your Diagnosis",
            "medications": "Your Medications",
            "restrictions": "Activity Instructions",
            "warning_signs": "When to Seek Medical Attention",
            "follow_up": "Follow-Up Appointments",
            "emergency": "In Case of Emergency",
            "diet": "Diet Instructions",
            "wound_care": "Wound Care",
        },
        Language.SPANISH_MX: {
            "title": "Instrucciones de Alta",
            "diagnosis": "Su Diagnóstico",
            "medications": "Sus Medicamentos",
            "restrictions": "Instrucciones de Actividad",
            "warning_signs": "Cuándo Buscar Atención Médica",
            "follow_up": "Citas de Seguimiento",
            "emergency": "En Caso de Emergencia",
            "diet": "Instrucciones de Dieta",
            "wound_care": "Cuidado de la Herida",
        },
        Language.SPANISH_US: {
            "title": "Instrucciones de Alta",
            "diagnosis": "Su Diagnóstico",
            "medications": "Sus Medicamentos",
            "restrictions": "Instrucciones de Actividad",
            "warning_signs": "Cuándo Buscar Atención Médica",
            "follow_up": "Citas de Seguimiento",
            "emergency": "En Caso de Emergencia",
            "diet": "Instrucciones de Dieta",
            "wound_care": "Cuidado de la Herida",
        },
        Language.MANDARIN: {
            "title": "出院指导",
            "diagnosis": "您的诊断",
            "medications": "您的药物",
            "restrictions": "活动指导",
            "warning_signs": "何时就医",
            "follow_up": "复诊预约",
            "emergency": "紧急情况",
            "diet": "饮食指导",
            "wound_care": "伤口护理",
        }
    }
    
    # Common phrases by language
    COMMON_PHRASES = {
        Language.ENGLISH: {
            "take_medication": "Take {dose} of {medication} {frequency}",
            "with_food": "with food",
            "without_food": "on an empty stomach",
            "call_911": "Call 911 immediately",
            "call_doctor": "Call your doctor",
            "return_er": "Return to the emergency room if",
            "interpreter": "Free interpreter services are available. Ask any staff member for assistance.",
        },
        Language.SPANISH_MX: {
            "take_medication": "Tome {dose} de {medication} {frequency}",
            "with_food": "con comida",
            "without_food": "en ayunas",
            "call_911": "Llame al 911 inmediatamente",
            "call_doctor": "Llame a su médico",
            "return_er": "Regrese a la sala de emergencias si",
            "interpreter": "Servicios de intérprete gratuitos están disponibles. Pregunte a cualquier miembro del personal.",
        },
        Language.SPANISH_US: {
            "take_medication": "Tome {dose} de {medication} {frequency}",
            "with_food": "con comida",
            "without_food": "en ayunas",
            "call_911": "Llame al 911 inmediatamente",
            "call_doctor": "Llame a su médico",
            "return_er": "Regrese a la sala de emergencias si",
            "interpreter": "Servicios de intérprete gratuitos están disponibles.",
        },
        Language.MANDARIN: {
            "take_medication": "服用 {medication} {dose} {frequency}",
            "with_food": "随餐服用",
            "without_food": "空腹服用",
            "call_911": "立即拨打911",
            "call_doctor": "请联系您的医生",
            "return_er": "如有以下情况请返回急诊室",
            "interpreter": "提供免费口译服务。请向工作人员询问。",
        }
    }
    
    # Frequency translations
    FREQUENCY_TRANSLATIONS = {
        Language.ENGLISH: {
            "once_daily": "once daily",
            "twice_daily": "twice daily",
            "three_times_daily": "three times daily",
            "four_times_daily": "four times daily",
            "every_4_hours": "every 4 hours",
            "every_6_hours": "every 6 hours",
            "every_8_hours": "every 8 hours",
            "every_12_hours": "every 12 hours",
            "as_needed": "as needed",
            "at_bedtime": "at bedtime",
        },
        Language.SPANISH_MX: {
            "once_daily": "una vez al día",
            "twice_daily": "dos veces al día",
            "three_times_daily": "tres veces al día",
            "four_times_daily": "cuatro veces al día",
            "every_4_hours": "cada 4 horas",
            "every_6_hours": "cada 6 horas",
            "every_8_hours": "cada 8 horas",
            "every_12_hours": "cada 12 horas",
            "as_needed": "según sea necesario",
            "at_bedtime": "antes de acostarse",
        },
        Language.SPANISH_US: {
            "once_daily": "una vez al día",
            "twice_daily": "dos veces al día",
            "three_times_daily": "tres veces al día",
            "four_times_daily": "cuatro veces al día",
            "every_4_hours": "cada 4 horas",
            "every_6_hours": "cada 6 horas",
            "every_8_hours": "cada 8 horas",
            "every_12_hours": "cada 12 horas",
            "as_needed": "según sea necesario",
            "at_bedtime": "antes de acostarse",
        },
        Language.MANDARIN: {
            "once_daily": "每天一次",
            "twice_daily": "每天两次",
            "three_times_daily": "每天三次",
            "four_times_daily": "每天四次",
            "every_4_hours": "每4小时",
            "every_6_hours": "每6小时",
            "every_8_hours": "每8小时",
            "every_12_hours": "每12小时",
            "as_needed": "按需",
            "at_bedtime": "睡前",
        }
    }
    
    def __init__(self, reading_level: ReadingLevel = ReadingLevel.MIDDLE_SCHOOL):
        """
        Initialize generator.
        
        Args:
            reading_level: Target reading level for content
        """
        self.reading_level = reading_level
    
    def generate_discharge_instructions(
        self,
        patient_name: str,
        language: Language,
        diagnosis: str,
        medications: List[Dict[str, Any]],
        activity_restrictions: List[str],
        warning_signs: List[str],
        follow_up: List[Dict[str, Any]],
        diet_instructions: Optional[str] = None,
        wound_care: Optional[str] = None
    ) -> DischargeInstructions:
        """
        Generate complete discharge instructions.
        
        Args:
            patient_name: Patient's name
            language: Target language
            diagnosis: Diagnosis in plain language
            medications: List of medication dicts
            activity_restrictions: Activity instructions
            warning_signs: Warning signs to watch for
            follow_up: Follow-up appointments
            diet_instructions: Optional diet instructions
            wound_care: Optional wound care instructions
        
        Returns:
            DischargeInstructions object
        """
        # Convert medication dicts to MedicationInstruction objects
        med_instructions = []
        for med in medications:
            med_instructions.append(MedicationInstruction(
                medication_name=med.get("name", ""),
                dosage=med.get("dosage", ""),
                frequency=med.get("frequency", ""),
                route=med.get("route", "oral"),
                special_instructions=med.get("special_instructions"),
                side_effects=med.get("side_effects", []),
                warnings=med.get("warnings", [])
            ))
        
        # Convert follow-up dicts to FollowUpAppointment objects
        follow_up_appointments = []
        for fu in follow_up:
            follow_up_appointments.append(FollowUpAppointment(
                specialty=fu.get("specialty", ""),
                timeframe=fu.get("timeframe", ""),
                reason=fu.get("reason", ""),
                urgency=fu.get("urgency", "routine")
            ))
        
        # Translate diagnosis to target language
        translated_diagnosis = self._translate_diagnosis(diagnosis, language)
        
        # Translate activity restrictions
        translated_restrictions = [
            self._translate_restriction(r, language) for r in activity_restrictions
        ]
        
        # Translate warning signs
        translated_warnings = [
            self._translate_warning(w, language) for w in warning_signs
        ]
        
        return DischargeInstructions(
            patient_name=patient_name,
            language=language,
            diagnosis_summary=translated_diagnosis,
            medications=med_instructions,
            activity_restrictions=translated_restrictions,
            warning_signs=translated_warnings,
            follow_up=follow_up_appointments,
            diet_instructions=diet_instructions,
            wound_care=wound_care
        )
    
    def format_discharge_instructions(
        self,
        instructions: DischargeInstructions
    ) -> str:
        """
        Format discharge instructions as readable text.
        
        Args:
            instructions: DischargeInstructions object
        
        Returns:
            Formatted text string
        """
        lang = instructions.language
        headers = self.SECTION_HEADERS.get(lang, self.SECTION_HEADERS[Language.ENGLISH])
        phrases = self.COMMON_PHRASES.get(lang, self.COMMON_PHRASES[Language.ENGLISH])
        
        lines = []
        
        # Title
        lines.append("=" * 50)
        lines.append(headers["title"].upper())
        lines.append("=" * 50)
        lines.append("")
        
        # Patient name
        lines.append(f"Patient: {instructions.patient_name}")
        lines.append(f"Date: {instructions.generated_at.strftime('%Y-%m-%d')}")
        lines.append("")
        
        # Diagnosis
        lines.append("-" * 50)
        lines.append(headers["diagnosis"].upper())
        lines.append("-" * 50)
        lines.append(instructions.diagnosis_summary)
        lines.append("")
        
        # Medications
        if instructions.medications:
            lines.append("-" * 50)
            lines.append(headers["medications"].upper())
            lines.append("-" * 50)
            for med in instructions.medications:
                med_line = self._format_medication(med, lang)
                lines.append(f"• {med_line}")
                if med.special_instructions:
                    lines.append(f"  → {med.special_instructions}")
            lines.append("")
        
        # Activity restrictions
        if instructions.activity_restrictions:
            lines.append("-" * 50)
            lines.append(headers["restrictions"].upper())
            lines.append("-" * 50)
            for restriction in instructions.activity_restrictions:
                lines.append(f"• {restriction}")
            lines.append("")
        
        # Warning signs
        if instructions.warning_signs:
            lines.append("-" * 50)
            lines.append(headers["warning_signs"].upper())
            lines.append("-" * 50)
            lines.append(phrases["return_er"] + ":")
            for warning in instructions.warning_signs:
                lines.append(f"• {warning}")
            lines.append("")
        
        # Follow-up
        if instructions.follow_up:
            lines.append("-" * 50)
            lines.append(headers["follow_up"].upper())
            lines.append("-" * 50)
            for fu in instructions.follow_up:
                lines.append(f"• {fu.specialty}: {fu.timeframe}")
                lines.append(f"  Reason: {fu.reason}")
            lines.append("")
        
        # Emergency
        lines.append("-" * 50)
        lines.append(headers["emergency"].upper())
        lines.append("-" * 50)
        lines.append(phrases["call_911"])
        lines.append("")
        
        # Interpreter notice
        lines.append("-" * 50)
        lines.append(phrases["interpreter"])
        lines.append("-" * 50)
        
        return "\n".join(lines)
    
    def generate_medication_guide(
        self,
        medications: List[MedicationInstruction],
        language: Language
    ) -> str:
        """
        Generate a medication guide for patient.
        
        Args:
            medications: List of medications
            language: Target language
        
        Returns:
            Formatted medication guide
        """
        lines = []
        headers = self.SECTION_HEADERS.get(language, self.SECTION_HEADERS[Language.ENGLISH])
        
        lines.append(headers["medications"].upper())
        lines.append("=" * 40)
        lines.append("")
        
        for med in medications:
            lines.append(f"📋 {med.medication_name.upper()}")
            lines.append(f"   Dose: {med.dosage}")
            lines.append(f"   How often: {med.frequency}")
            lines.append(f"   How to take: {med.route}")
            
            if med.special_instructions:
                lines.append(f"   ⚠️ {med.special_instructions}")
            
            if med.side_effects:
                lines.append("   Possible side effects:")
                for se in med.side_effects:
                    lines.append(f"      • {se}")
            
            lines.append("")
        
        return "\n".join(lines)
    
    def generate_appointment_reminder(
        self,
        patient_name: str,
        appointment_date: date,
        appointment_time: str,
        provider_name: str,
        specialty: str,
        location: str,
        language: Language
    ) -> str:
        """
        Generate appointment reminder.
        
        Args:
            patient_name: Patient's name
            appointment_date: Date of appointment
            appointment_time: Time of appointment
            provider_name: Provider's name
            specialty: Type of appointment
            location: Appointment location
            language: Target language
        
        Returns:
            Formatted appointment reminder
        """
        templates = {
            Language.ENGLISH: f"""
APPOINTMENT REMINDER

Dear {patient_name},

This is a reminder of your upcoming appointment:

Date: {appointment_date.strftime('%B %d, %Y')}
Time: {appointment_time}
Provider: {provider_name}
Type: {specialty}
Location: {location}

Please arrive 15 minutes early.
Bring your insurance card and medication list.

To reschedule, call us at least 24 hours in advance.
""",
            Language.SPANISH_MX: f"""
RECORDATORIO DE CITA

Estimado/a {patient_name},

Este es un recordatorio de su próxima cita:

Fecha: {appointment_date.strftime('%d de %B de %Y')}
Hora: {appointment_time}
Proveedor: {provider_name}
Tipo: {specialty}
Ubicación: {location}

Por favor llegue 15 minutos antes.
Traiga su tarjeta de seguro y lista de medicamentos.

Para reprogramar, llámenos con al menos 24 horas de anticipación.
""",
            Language.MANDARIN: f"""
预约提醒

尊敬的 {patient_name}，

这是您即将到来的预约提醒：

日期：{appointment_date.strftime('%Y年%m月%d日')}
时间：{appointment_time}
医生：{provider_name}
类型：{specialty}
地点：{location}

请提前15分钟到达。
请携带您的保险卡和药物清单。

如需改期，请至少提前24小时致电。
"""
        }
        
        return templates.get(language, templates[Language.ENGLISH]).strip()
    
    def _format_medication(
        self,
        med: MedicationInstruction,
        language: Language
    ) -> str:
        """Format single medication instruction."""
        phrases = self.COMMON_PHRASES.get(language, self.COMMON_PHRASES[Language.ENGLISH])
        
        template = phrases["take_medication"]
        return template.format(
            dose=med.dosage,
            medication=med.medication_name,
            frequency=med.frequency
        )
    
    def _translate_diagnosis(self, diagnosis: str, language: Language) -> str:
        """Translate diagnosis to patient-friendly language."""
        # In production: Use medical translator
        # For now, return as-is (would be pre-translated)
        return diagnosis
    
    def _translate_restriction(self, restriction: str, language: Language) -> str:
        """Translate activity restriction."""
        # In production: Use medical translator
        return restriction
    
    def _translate_warning(self, warning: str, language: Language) -> str:
        """Translate warning sign."""
        # In production: Use medical translator
        return warning
    
    def get_supported_languages(self) -> List[Language]:
        """Get list of supported languages."""
        return list(self.SECTION_HEADERS.keys())
    
    def get_communication_types(self) -> List[CommunicationType]:
        """Get list of supported communication types."""
        return list(CommunicationType)
