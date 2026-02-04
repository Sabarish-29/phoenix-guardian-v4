"""
Tests for Translation Memory (17 tests).

Tests:
1. Initialization
2. Term lookup
3. Code-based lookup (SNOMED, ICD-10, RxNorm)
4. Term management
5. Physician feedback
6. Inconsistency detection
7. Export/Import
"""

import pytest

from phoenix_guardian.localization.translation_memory import (
    TranslationMemory,
    TermEntry,
    GlossaryType,
)
from phoenix_guardian.localization.locale_manager import SupportedLocale


class TestTranslationMemoryInitialization:
    """Tests for TranslationMemory initialization."""
    
    def test_initialization(self):
        """Test memory initializes properly."""
        memory = TranslationMemory()
        
        assert memory is not None
        assert len(memory.glossary) > 0
    
    def test_preloaded_glossary(self):
        """Test glossary is preloaded with medical terms."""
        memory = TranslationMemory()
        
        # Check some expected terms
        assert "chest pain" in memory.glossary
        assert "diabetes" in memory.glossary
        assert "aspirin" in memory.glossary


class TestTermLookup:
    """Tests for term lookup."""
    
    def test_lookup_exact_match(self):
        """Test exact term lookup."""
        memory = TranslationMemory()
        
        entry = memory.lookup("chest pain", SupportedLocale.ES_MX)
        
        assert entry is not None
        assert entry.source_term == "chest pain"
        assert entry.get_translation(SupportedLocale.ES_MX) == "dolor torácico"
    
    def test_lookup_case_insensitive(self):
        """Test lookup is case insensitive."""
        memory = TranslationMemory()
        
        entry = memory.lookup("CHEST PAIN", SupportedLocale.ES_MX)
        
        assert entry is not None
        assert entry.source_term == "chest pain"
    
    def test_lookup_by_type(self):
        """Test lookup filtered by glossary type."""
        memory = TranslationMemory()
        
        # Aspirin is a medication
        entry = memory.lookup(
            "aspirin",
            SupportedLocale.ES_MX,
            glossary_type=GlossaryType.MEDICATION
        )
        
        assert entry is not None
        assert entry.glossary_type == GlossaryType.MEDICATION
    
    def test_lookup_wrong_type_returns_none(self):
        """Test lookup with wrong type returns None."""
        memory = TranslationMemory()
        
        # Aspirin is not a diagnosis
        entry = memory.lookup(
            "aspirin",
            SupportedLocale.ES_MX,
            glossary_type=GlossaryType.DIAGNOSIS
        )
        
        assert entry is None
    
    def test_lookup_nonexistent_term(self):
        """Test lookup of nonexistent term."""
        memory = TranslationMemory()
        
        entry = memory.lookup("nonexistent_term_xyz", SupportedLocale.ES_MX)
        
        assert entry is None


class TestCodeBasedLookup:
    """Tests for code-based lookup."""
    
    def test_lookup_by_snomed(self):
        """Test lookup by SNOMED code."""
        memory = TranslationMemory()
        
        entry = memory.lookup_by_snomed("29857009", SupportedLocale.ES_MX)
        
        assert entry is not None
        assert entry.source_term == "chest pain"
    
    def test_lookup_by_icd10(self):
        """Test lookup by ICD-10 code."""
        memory = TranslationMemory()
        
        entry = memory.lookup_by_icd10("E11", SupportedLocale.ES_MX)
        
        assert entry is not None
        assert entry.source_term == "diabetes"
    
    def test_lookup_by_rxnorm(self):
        """Test lookup by RxNorm code."""
        memory = TranslationMemory()
        
        entry = memory.lookup_by_rxnorm("1191", SupportedLocale.ES_MX)
        
        assert entry is not None
        assert entry.source_term == "aspirin"


class TestTermManagement:
    """Tests for term management."""
    
    def test_add_term(self):
        """Test adding new term."""
        memory = TranslationMemory()
        
        entry = memory.add_term(
            source_term="new condition",
            translations={SupportedLocale.ES_MX: "nueva condición"},
            glossary_type=GlossaryType.DIAGNOSIS,
            verified=True
        )
        
        assert entry is not None
        assert "new condition" in memory.glossary
        
        # Can look it up
        found = memory.lookup("new condition", SupportedLocale.ES_MX)
        assert found is not None
        assert found.verified is True
    
    def test_record_usage(self):
        """Test usage tracking."""
        memory = TranslationMemory()
        
        initial_count = memory.glossary["chest pain"].usage_count
        
        # Lookup records usage
        memory.lookup("chest pain", SupportedLocale.ES_MX)
        
        assert memory.glossary["chest pain"].usage_count == initial_count + 1


class TestPhysicianFeedback:
    """Tests for physician feedback integration."""
    
    def test_update_from_feedback_existing(self):
        """Test updating existing term from feedback."""
        memory = TranslationMemory()
        
        # Update translation
        memory.update_from_feedback(
            source_term="chest pain",
            locale=SupportedLocale.ES_MX,
            physician_translation="dolor de pecho"
        )
        
        entry = memory.glossary["chest pain"]
        
        # New translation is primary
        assert entry.get_translation(SupportedLocale.ES_MX) == "dolor de pecho"
        
        # Old translation is in alternatives
        assert "dolor torácico" in entry.get_alternatives(SupportedLocale.ES_MX)
        
        # Now verified
        assert entry.verified is True
    
    def test_update_from_feedback_new_term(self):
        """Test creating new term from feedback."""
        memory = TranslationMemory()
        
        memory.update_from_feedback(
            source_term="brand new term",
            locale=SupportedLocale.ES_MX,
            physician_translation="término nuevo"
        )
        
        assert "brand new term" in memory.glossary
        entry = memory.glossary["brand new term"]
        assert entry.verified is True


class TestInconsistencyDetection:
    """Tests for inconsistency detection."""
    
    def test_get_inconsistencies(self):
        """Test finding terms with multiple translations."""
        memory = TranslationMemory()
        
        # Create inconsistency
        memory.update_from_feedback(
            "chest pain",
            SupportedLocale.ES_MX,
            "dolor de pecho"
        )
        
        inconsistencies = memory.get_inconsistencies(SupportedLocale.ES_MX)
        
        assert len(inconsistencies) > 0
        
        chest_pain = next(
            (i for i in inconsistencies if i["term"] == "chest pain"),
            None
        )
        assert chest_pain is not None
        assert "dolor torácico" in chest_pain["alternatives"]


class TestExportImport:
    """Tests for export/import functionality."""
    
    def test_export_glossary(self):
        """Test exporting glossary."""
        memory = TranslationMemory()
        
        exported = memory.export_glossary(SupportedLocale.ES_MX)
        
        assert isinstance(exported, dict)
        assert "chest pain" in exported
        assert exported["chest pain"] == "dolor torácico"
    
    def test_export_by_type(self):
        """Test exporting glossary filtered by type."""
        memory = TranslationMemory()
        
        exported = memory.export_glossary(
            SupportedLocale.ES_MX,
            glossary_type=GlossaryType.MEDICATION
        )
        
        assert "aspirin" in exported
        assert "chest pain" not in exported  # symptom, not medication
    
    def test_get_statistics(self):
        """Test getting memory statistics."""
        memory = TranslationMemory()
        
        stats = memory.get_statistics()
        
        assert "total_terms" in stats
        assert "by_type" in stats
        assert "verified_count" in stats
        assert stats["total_terms"] > 0
