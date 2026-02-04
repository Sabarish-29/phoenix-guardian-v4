"""
Tests for Audit Package Generator.

Tests generation of audit packages for SOC 2 Type II.
"""

import pytest
from datetime import datetime
from unittest.mock import MagicMock
import json

from phoenix_guardian.compliance.audit_package_generator import (
    AuditPackageGenerator,
    AuditPackage,
)
from phoenix_guardian.compliance.evidence_types import (
    Evidence,
    EvidenceType,
    EvidenceSource,
    TSCCriterion,
)


class TestAuditPackage:
    """Tests for AuditPackage dataclass."""
    
    def test_package_creation(self):
        """Test creating an audit package."""
        package = AuditPackage(
            package_id="pkg_001",
            generated_at=datetime.now().isoformat(),
            audit_period_start="2025-07-01",
            audit_period_end="2025-12-31",
        )
        
        assert package.package_id == "pkg_001"
        assert package.total_evidence == 0
    
    def test_to_dict(self):
        """Test conversion to dictionary."""
        package = AuditPackage(
            package_id="pkg_001",
            generated_at="2026-01-01T00:00:00",
            audit_period_start="2025-07-01",
            audit_period_end="2025-12-31",
            total_evidence=100,
        )
        
        data = package.to_dict()
        
        assert data["package_id"] == "pkg_001"
        assert data["total_evidence"] == 100


class TestAuditPackageGenerator:
    """Tests for AuditPackageGenerator."""
    
    @pytest.fixture
    def generator(self):
        """Create a generator instance."""
        return AuditPackageGenerator()
    
    @pytest.fixture
    def sample_evidence(self):
        """Create sample evidence."""
        evidence_list = []
        for i in range(5):
            e = Evidence(
                evidence_id=f"test_{i:03d}",
                evidence_type=EvidenceType.ACCESS_LOG,
                evidence_source=EvidenceSource.APPLICATION_LOG,
                tsc_criteria=[TSCCriterion.CC6_LOGICAL_ACCESS],
                control_description="Test control description for access",
                collected_at=datetime.now().isoformat(),
                event_timestamp="2025-07-15T12:00:00",
                data_hash="",
                data={"test": i},
            )
            e.data_hash = e.compute_hash()
            evidence_list.append(e)
        return evidence_list
    
    def test_tsc_descriptions_defined(self, generator):
        """Test TSC descriptions are defined."""
        assert TSCCriterion.CC6_LOGICAL_ACCESS in generator.TSC_DESCRIPTIONS
        assert "Logical Access" in generator.TSC_DESCRIPTIONS[TSCCriterion.CC6_LOGICAL_ACCESS]
    
    def test_generate_package(self, generator, sample_evidence):
        """Test generating a package."""
        package = generator.generate(
            sample_evidence,
            audit_period_start="2025-07-01",
            audit_period_end="2025-12-31"
        )
        
        assert isinstance(package, AuditPackage)
        assert package.total_evidence == 5
    
    def test_generate_package_id(self, generator, sample_evidence):
        """Test package ID is generated."""
        package = generator.generate(
            sample_evidence,
            "2025-07-01",
            "2025-12-31"
        )
        
        assert package.package_id.startswith("audit_pkg_")
    
    def test_evidence_organized_by_tsc(self, generator, sample_evidence):
        """Test evidence is organized by TSC."""
        package = generator.generate(
            sample_evidence,
            "2025-07-01",
            "2025-12-31"
        )
        
        assert "CC6" in package.evidence_by_tsc
        assert len(package.evidence_by_tsc["CC6"]) == 5
    
    def test_tsc_coverage_tracked(self, generator, sample_evidence):
        """Test TSC coverage is tracked."""
        package = generator.generate(
            sample_evidence,
            "2025-07-01",
            "2025-12-31"
        )
        
        assert package.tsc_coverage["CC6"] == 5
    
    def test_manifest_hash_computed(self, generator, sample_evidence):
        """Test manifest hash is computed."""
        package = generator.generate(
            sample_evidence,
            "2025-07-01",
            "2025-12-31"
        )
        
        assert package.manifest_hash is not None
        assert len(package.manifest_hash) == 64  # SHA-256
    
    def test_validation_included(self, generator, sample_evidence):
        """Test validation result is included."""
        package = generator.generate(
            sample_evidence,
            "2025-07-01",
            "2025-12-31",
            validate=True
        )
        
        assert package.validation_result is not None
    
    def test_generate_index(self, generator, sample_evidence):
        """Test generating package index."""
        package = generator.generate(
            sample_evidence,
            "2025-07-01",
            "2025-12-31"
        )
        
        index = generator.generate_index(package)
        
        assert "package_id" in index
        assert "summary" in index
        assert "sections" in index
    
    def test_index_has_sections_per_tsc(self, generator, sample_evidence):
        """Test index has section per TSC."""
        package = generator.generate(
            sample_evidence,
            "2025-07-01",
            "2025-12-31"
        )
        
        index = generator.generate_index(package)
        
        assert len(index["sections"]) == len(TSCCriterion)
    
    def test_generate_summary_report(self, generator, sample_evidence):
        """Test generating summary report."""
        package = generator.generate(
            sample_evidence,
            "2025-07-01",
            "2025-12-31"
        )
        
        report = generator.generate_summary_report(package)
        
        assert "report_type" in report
        assert "evidence_summary" in report
        assert "validation_summary" in report
    
    def test_recommendations_generated(self, generator, sample_evidence):
        """Test recommendations are generated."""
        package = generator.generate(
            sample_evidence,
            "2025-07-01",
            "2025-12-31"
        )
        
        report = generator.generate_summary_report(package)
        
        assert "recommendations" in report
        assert isinstance(report["recommendations"], list)
    
    def test_generated_packages_tracked(self, generator, sample_evidence):
        """Test generated packages are tracked."""
        generator.generate(
            sample_evidence,
            "2025-07-01",
            "2025-12-31"
        )
        
        assert len(generator.generated_packages) == 1
    
    def test_empty_evidence_package(self, generator):
        """Test generating package with no evidence."""
        package = generator.generate(
            [],
            "2025-07-01",
            "2025-12-31"
        )
        
        assert package.total_evidence == 0
    
    def test_skip_validation(self, generator, sample_evidence):
        """Test skipping validation."""
        package = generator.generate(
            sample_evidence,
            "2025-07-01",
            "2025-12-31",
            validate=False
        )
        
        assert package.validation_result is None
