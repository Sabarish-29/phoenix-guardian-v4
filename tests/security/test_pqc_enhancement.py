"""
Tests for Sprint 3: Post-Quantum Cryptography Enhancement.

Tests cover:
- PHI field-level encryption/decryption
- PQC key rotation
- PHI middleware configuration
- PQC TLS configuration
- PQC API endpoints
"""

import json
import os
from datetime import datetime
from typing import Any, Dict
from unittest.mock import MagicMock, patch

import pytest


class TestPHIEncryptionService:
    """Test PHI field-level encryption service."""

    def test_phi_service_importable(self):
        """PHI encryption service should be importable."""
        from phoenix_guardian.security.phi_encryption import PHIEncryptionService
        assert PHIEncryptionService is not None

    def test_phi_service_init(self):
        """PHI encryption service should initialize with defaults."""
        from phoenix_guardian.security.phi_encryption import PHIEncryptionService
        service = PHIEncryptionService()
        assert service._operations_count == 0
        assert service._fields_encrypted == 0
        assert service._fields_decrypted == 0

    def test_phi_service_additional_fields(self):
        """PHI service should accept additional custom fields."""
        from phoenix_guardian.security.phi_encryption import PHIEncryptionService
        service = PHIEncryptionService(
            additional_phi_fields={"custom_field_1", "custom_field_2"}
        )
        assert "custom_field_1" in service._phi_fields
        assert "custom_field_2" in service._phi_fields
        # Standard fields should also be present
        assert "patient_name" in service._phi_fields
        assert "ssn" in service._phi_fields

    def test_encrypt_phi_fields(self):
        """Should encrypt known PHI fields and leave others unchanged."""
        from phoenix_guardian.security.phi_encryption import PHIEncryptionService
        service = PHIEncryptionService(audit_log=False)

        data = {
            "patient_name": "John Doe",
            "ssn": "123-45-6789",
            "visit_type": "outpatient",  # Not PHI
            "notes": "General visit",    # Not PHI
        }

        encrypted = service.encrypt_phi_fields(data, context="test")

        # PHI fields should be encrypted
        assert isinstance(encrypted["patient_name"], dict)
        assert encrypted["patient_name"]["__pqc_encrypted__"] is True
        assert isinstance(encrypted["ssn"], dict)
        assert encrypted["ssn"]["__pqc_encrypted__"] is True

        # Non-PHI fields should be unchanged
        assert encrypted["visit_type"] == "outpatient"
        assert encrypted["notes"] == "General visit"

    def test_decrypt_phi_fields(self):
        """Should decrypt PQC-encrypted PHI fields back to original values."""
        from phoenix_guardian.security.phi_encryption import PHIEncryptionService
        service = PHIEncryptionService(audit_log=False)

        original = {
            "patient_name": "Jane Smith",
            "mrn": "MRN-12345",
            "visit_type": "inpatient",
        }

        encrypted = service.encrypt_phi_fields(original, context="test")
        decrypted = service.decrypt_phi_fields(encrypted, context="test")

        assert decrypted["patient_name"] == "Jane Smith"
        assert decrypted["mrn"] == "MRN-12345"
        assert decrypted["visit_type"] == "inpatient"

    def test_encrypt_nested_phi(self):
        """Should encrypt PHI fields in nested dictionaries."""
        from phoenix_guardian.security.phi_encryption import PHIEncryptionService
        service = PHIEncryptionService(audit_log=False)

        data = {
            "encounter": {
                "patient_name": "Bob Jones",
                "diagnosis": "Hypertension",
                "severity": "moderate",  # Not PHI
            },
            "provider": "Dr. Smith",  # Not a PHI key
        }

        encrypted = service.encrypt_phi_fields(data)

        # Nested PHI should be encrypted
        assert encrypted["encounter"]["patient_name"]["__pqc_encrypted__"] is True
        assert encrypted["encounter"]["diagnosis"]["__pqc_encrypted__"] is True
        # Non-PHI nested should be unchanged
        assert encrypted["encounter"]["severity"] == "moderate"
        assert encrypted["provider"] == "Dr. Smith"

    def test_encrypt_list_values(self):
        """Should encrypt PHI fields that contain lists."""
        from phoenix_guardian.security.phi_encryption import PHIEncryptionService
        service = PHIEncryptionService(audit_log=False)

        data = {
            "medications": ["aspirin", "metformin"],
            "severity": "low",
        }

        encrypted = service.encrypt_phi_fields(data)
        assert encrypted["medications"]["__pqc_encrypted__"] is True

        decrypted = service.decrypt_phi_fields(encrypted)
        assert decrypted["medications"] == ["aspirin", "metformin"]

    def test_encrypt_null_values_skipped(self):
        """Should skip None values for PHI fields."""
        from phoenix_guardian.security.phi_encryption import PHIEncryptionService
        service = PHIEncryptionService(audit_log=False)

        data = {
            "patient_name": None,
            "visit_type": "outpatient",
        }

        encrypted = service.encrypt_phi_fields(data)
        assert encrypted["patient_name"] is None
        assert encrypted["visit_type"] == "outpatient"

    def test_metrics_tracking(self):
        """Should track encryption/decryption metrics."""
        from phoenix_guardian.security.phi_encryption import PHIEncryptionService
        service = PHIEncryptionService(audit_log=False)

        data = {"patient_name": "Test", "ssn": "111-22-3333"}
        encrypted = service.encrypt_phi_fields(data)
        service.decrypt_phi_fields(encrypted)

        metrics = service.get_metrics()
        assert metrics["total_operations"] == 2
        assert metrics["fields_encrypted"] >= 2
        assert metrics["fields_decrypted"] >= 2
        assert metrics["total_time_ms"] >= 0

    def test_key_rotation(self):
        """Should support key rotation."""
        from phoenix_guardian.security.phi_encryption import PHIEncryptionService
        service = PHIEncryptionService(audit_log=False)

        result = service.rotate_keys()
        assert "new_key" in result or "old_key" in result


class TestPHIFieldDefinitions:
    """Test PHI field identification."""

    def test_phi_fields_contain_hipaa_identifiers(self):
        """PHI field set should include HIPAA-defined identifiers."""
        from phoenix_guardian.security.phi_encryption import PHI_FIELDS

        hipaa_fields = [
            "patient_name", "date_of_birth", "ssn", "mrn",
            "phone", "email", "address", "health_plan_id",
        ]
        for field in hipaa_fields:
            assert field in PHI_FIELDS, f"HIPAA field '{field}' missing from PHI_FIELDS"

    def test_phi_container_fields(self):
        """Container fields should be defined for recursive search."""
        from phoenix_guardian.security.phi_encryption import PHI_CONTAINER_FIELDS

        assert "patient" in PHI_CONTAINER_FIELDS
        assert "encounter" in PHI_CONTAINER_FIELDS
        assert "demographics" in PHI_CONTAINER_FIELDS


class TestPQCTLSConfig:
    """Test PQC TLS configuration."""

    def test_tls_config_init(self):
        """TLS config should initialize with defaults."""
        from phoenix_guardian.security.phi_encryption import PQCTLSConfig
        config = PQCTLSConfig()
        assert config.cert_file is None or isinstance(config.cert_file, str)

    def test_tls_info(self):
        """TLS info should return useful diagnostic data."""
        from phoenix_guardian.security.phi_encryption import PQCTLSConfig
        config = PQCTLSConfig()
        info = config.get_tls_info()

        assert "openssl_version" in info
        assert "tls_version" in info
        assert info["tls_version"] == "TLS 1.3"
        assert "pq_available" in info

    def test_create_ssl_context(self):
        """Should create a valid SSL context."""
        import ssl
        from phoenix_guardian.security.phi_encryption import PQCTLSConfig
        config = PQCTLSConfig()
        try:
            ctx = config.create_ssl_context()
            assert isinstance(ctx, ssl.SSLContext)
        except ssl.SSLError:
            pytest.skip("SSL cipher configuration not supported on this platform")


class TestPHIMiddleware:
    """Test PHI encryption middleware."""

    def test_middleware_disabled_by_default(self):
        """Middleware should be disabled when env var is not set."""
        from phoenix_guardian.security.phi_encryption import PHIEncryptionMiddleware

        mock_app = MagicMock()
        middleware = PHIEncryptionMiddleware(mock_app)
        assert middleware._enabled is False
        assert middleware._service is None

    @patch.dict("os.environ", {"PHI_ENCRYPTION_ENABLED": "true"})
    def test_middleware_enabled(self):
        """Middleware should enable when env var is set."""
        from phoenix_guardian.security.phi_encryption import PHIEncryptionMiddleware

        mock_app = MagicMock()
        middleware = PHIEncryptionMiddleware(mock_app)
        assert middleware._enabled is True
        assert middleware._service is not None


class TestGlobalSingleton:
    """Test global PHI encryption service singleton."""

    def test_get_phi_service_singleton(self):
        """Should return consistent singleton instance."""
        from phoenix_guardian.security import phi_encryption

        # Reset singleton
        phi_encryption._global_phi_service = None

        service1 = phi_encryption.get_phi_encryption_service()
        service2 = phi_encryption.get_phi_encryption_service()
        assert service1 is service2


class TestPQCAPIRoutes:
    """Test PQC API route models."""

    def test_encrypt_request_model(self):
        """EncryptRequest model should validate."""
        from phoenix_guardian.api.routes.pqc import EncryptRequest

        req = EncryptRequest(plaintext="test string")
        assert req.plaintext == "test string"
        assert req.context == "api"

    def test_phi_encrypt_request_model(self):
        """PHIEncryptRequest model should validate."""
        from phoenix_guardian.api.routes.pqc import PHIEncryptRequest

        req = PHIEncryptRequest(
            data={"patient_name": "John", "ssn": "123-45-6789"},
            context="unit-test",
        )
        assert req.data["patient_name"] == "John"
        assert req.context == "unit-test"

    def test_health_response_model(self):
        """PQCHealthResponse model should validate."""
        from phoenix_guardian.api.routes.pqc import PQCHealthResponse

        resp = PQCHealthResponse(
            status="healthy",
            algorithm="Kyber1024",
            oqs_available=False,
            key_id="abc123",
            key_version=1,
            total_encryptions=0,
            total_decryptions=0,
            using_simulator=True,
            tls_info={"openssl_version": "3.0.0"},
        )
        assert resp.status == "healthy"
        assert resp.using_simulator is True
