"""
Tests for Evidence Validator.

Tests evidence validation for integrity, completeness, and correctness.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock

from phoenix_guardian.compliance.evidence_validator import (
    EvidenceValidator,
    ValidationResult,
    ValidationIssue,
    ValidationSeverity,
)
from phoenix_guardian.compliance.evidence_types import (
    Evidence,
    EvidenceType,
    EvidenceSource,
    TSCCriterion,
)


class TestValidationIssue:
    """Tests for ValidationIssue dataclass."""
    
    def test_issue_creation(self):
        """Test creating a validation issue."""
        issue = ValidationIssue(
            evidence_id="test_001",
            severity=ValidationSeverity.ERROR,
            category="integrity",
            message="Hash mismatch",
            remediation="Re-collect evidence",
        )
        
        assert issue.evidence_id == "test_001"
        assert issue.severity == ValidationSeverity.ERROR


class TestValidationResult:
    """Tests for ValidationResult dataclass."""
    
    def test_is_valid_with_no_errors(self):
        """Test is_valid with no errors."""
        result = ValidationResult(
            validation_id="val_001",
            validated_at=datetime.now().isoformat(),
            total_evidence=10,
            valid_count=10,
            invalid_count=0,
            issues=[],
        )
        
        assert result.is_valid is True
    
    def test_is_valid_with_errors(self):
        """Test is_valid with errors."""
        result = ValidationResult(
            validation_id="val_001",
            validated_at=datetime.now().isoformat(),
            total_evidence=10,
            valid_count=9,
            invalid_count=1,
            issues=[ValidationIssue(
                evidence_id="test",
                severity=ValidationSeverity.ERROR,
                category="test",
                message="Error",
            )],
        )
        
        assert result.is_valid is False
    
    def test_error_count(self):
        """Test error count calculation."""
        result = ValidationResult(
            validation_id="val_001",
            validated_at=datetime.now().isoformat(),
            total_evidence=10,
            valid_count=8,
            invalid_count=2,
            issues=[
                ValidationIssue("1", ValidationSeverity.ERROR, "test", "Error"),
                ValidationIssue("2", ValidationSeverity.ERROR, "test", "Error"),
                ValidationIssue("3", ValidationSeverity.WARNING, "test", "Warning"),
            ],
        )
        
        assert result.error_count == 2
        assert result.warning_count == 1
    
    def test_to_dict(self):
        """Test conversion to dictionary."""
        result = ValidationResult(
            validation_id="val_001",
            validated_at="2026-01-01T00:00:00",
            total_evidence=10,
            valid_count=10,
            invalid_count=0,
        )
        
        data = result.to_dict()
        
        assert data["validation_id"] == "val_001"
        assert data["is_valid"] is True


class TestEvidenceValidator:
    """Tests for EvidenceValidator."""
    
    @pytest.fixture
    def validator(self):
        """Create a validator instance."""
        return EvidenceValidator()
    
    @pytest.fixture
    def valid_evidence(self):
        """Create valid evidence."""
        evidence = Evidence(
            evidence_id="test_001",
            evidence_type=EvidenceType.ACCESS_LOG,
            evidence_source=EvidenceSource.APPLICATION_LOG,
            tsc_criteria=[TSCCriterion.CC6_LOGICAL_ACCESS],
            control_description="Test control for access logging and monitoring",
            collected_at=datetime.now().isoformat(),
            event_timestamp=(datetime.now() - timedelta(hours=1)).isoformat(),
            data_hash="",
            data={"test": "data"},
        )
        evidence.data_hash = evidence.compute_hash()
        return evidence
    
    def test_validate_empty_list(self, validator):
        """Test validating empty list."""
        result = validator.validate([])
        
        assert result.total_evidence == 0
        assert result.is_valid is True
    
    def test_validate_valid_evidence(self, validator, valid_evidence):
        """Test validating valid evidence."""
        result = validator.validate([valid_evidence])
        
        assert result.valid_count == 1
        assert result.error_count == 0
    
    def test_validate_tampered_hash(self, validator, valid_evidence):
        """Test validating evidence with tampered hash."""
        valid_evidence.data_hash = "tampered_hash"
        
        result = validator.validate([valid_evidence])
        
        assert result.error_count > 0
        integrity_errors = [
            i for i in result.issues
            if i.category == "integrity"
        ]
        assert len(integrity_errors) > 0
    
    def test_validate_missing_hash(self, validator, valid_evidence):
        """Test validating evidence without hash."""
        valid_evidence.data_hash = ""
        
        result = validator.validate([valid_evidence])
        
        assert result.error_count > 0
    
    def test_validate_missing_collected_at(self, validator, valid_evidence):
        """Test validating evidence without collected_at."""
        valid_evidence.collected_at = ""
        
        result = validator.validate([valid_evidence])
        
        assert result.error_count > 0
    
    def test_validate_missing_event_timestamp(self, validator, valid_evidence):
        """Test validating evidence without event_timestamp."""
        valid_evidence.event_timestamp = ""
        
        result = validator.validate([valid_evidence])
        
        assert result.error_count > 0
    
    def test_validate_future_collection_timestamp(self, validator, valid_evidence):
        """Test validating evidence with future timestamp."""
        valid_evidence.collected_at = (datetime.now() + timedelta(days=1)).isoformat()
        
        result = validator.validate([valid_evidence])
        
        assert result.error_count > 0
    
    def test_validate_missing_tsc_criteria(self, validator, valid_evidence):
        """Test validating evidence without TSC mapping."""
        valid_evidence.tsc_criteria = []
        
        result = validator.validate([valid_evidence])
        
        assert result.error_count > 0
    
    def test_validate_short_control_description(self, validator, valid_evidence):
        """Test validating evidence with short description."""
        valid_evidence.control_description = "Short"
        
        result = validator.validate([valid_evidence])
        
        # Should be warning, not error
        warnings = [
            i for i in result.issues
            if i.severity == ValidationSeverity.WARNING
        ]
        assert len(warnings) > 0
    
    def test_strict_mode(self, validator, valid_evidence):
        """Test strict mode upgrades warnings to errors."""
        valid_evidence.control_description = "Short"
        
        result = validator.validate([valid_evidence], strict=True)
        
        # In strict mode, warnings become errors
        assert result.error_count > 0
    
    def test_validate_for_audit_period(self, validator, valid_evidence):
        """Test validation for audit period."""
        result = validator.validate_for_audit_period(
            [valid_evidence],
            audit_start="2026-01-01T00:00:00",
            audit_end="2026-01-31T23:59:59"
        )
        
        assert isinstance(result, ValidationResult)
    
    def test_validation_history_tracked(self, validator, valid_evidence):
        """Test validation history is tracked."""
        validator.validate([valid_evidence])
        
        assert len(validator.validation_history) == 1
    
    def test_get_validation_summary(self, validator, valid_evidence):
        """Test validation summary."""
        validator.validate([valid_evidence])
        
        summary = validator.get_validation_summary()
        
        assert "total_validations" in summary
        assert summary["total_validations"] == 1
    
    def test_old_evidence_warning(self, validator):
        """Test warning for old evidence."""
        old_evidence = Evidence(
            evidence_id="old_001",
            evidence_type=EvidenceType.ACCESS_LOG,
            evidence_source=EvidenceSource.APPLICATION_LOG,
            tsc_criteria=[TSCCriterion.CC6_LOGICAL_ACCESS],
            control_description="Test control for access logging and monitoring",
            collected_at=datetime.now().isoformat(),
            event_timestamp=(datetime.now() - timedelta(days=400)).isoformat(),
            data_hash="",
            data={},
        )
        old_evidence.data_hash = old_evidence.compute_hash()
        
        result = validator.validate([old_evidence])
        
        age_warnings = [
            i for i in result.issues
            if "days old" in i.message
        ]
        assert len(age_warnings) > 0
