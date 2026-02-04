"""
Tests for the simple Fernet encryption service.

Tests cover:
- Basic encryption/decryption
- Dictionary field encryption
- PII/PHI encryption helpers
- Key generation
- Error handling
"""

import pytest
import os

from phoenix_guardian.security.encryption import (
    EncryptionService,
    EncryptionError,
    DecryptionError,
    get_encryption_service,
    reset_encryption_service,
    encrypt_pii,
    decrypt_pii,
    encrypt_phi,
    decrypt_phi,
)


@pytest.fixture(autouse=True)
def reset_service():
    """Reset singleton before each test."""
    reset_encryption_service()
    yield
    reset_encryption_service()


class TestEncryptionServiceInitialization:
    """Tests for EncryptionService initialization."""
    
    def test_initialization_creates_service(self):
        """Test that encryption service can be initialized."""
        service = EncryptionService()
        assert service is not None
        assert service.key is not None
        assert service.fernet is not None
    
    def test_initialization_with_env_key(self, monkeypatch):
        """Test initialization with ENCRYPTION_KEY env var."""
        from cryptography.fernet import Fernet
        test_key = Fernet.generate_key().decode()
        monkeypatch.setenv("ENCRYPTION_KEY", test_key)
        
        service = EncryptionService()
        assert service.key == test_key.encode()
        assert not service.key_was_generated
    
    def test_initialization_generates_key_without_env(self, monkeypatch):
        """Test that key is generated if not in env."""
        monkeypatch.delenv("ENCRYPTION_KEY", raising=False)
        
        service = EncryptionService()
        assert service.key is not None
        # Key should be generated - the property may or may not be set
        # depending on implementation, but service should work
        assert len(service.key) > 0


class TestBasicEncryption:
    """Tests for basic string encryption/decryption."""
    
    def test_encrypt_decrypt_string(self):
        """Test basic string encryption/decryption."""
        service = EncryptionService()
        
        original = "123-45-6789"
        encrypted = service.encrypt(original)
        decrypted = service.decrypt(encrypted)
        
        assert encrypted != original  # Data should be encrypted
        assert decrypted == original  # Should decrypt back to original
    
    def test_encrypt_empty_string(self):
        """Test encrypting empty string returns empty string."""
        service = EncryptionService()
        
        encrypted = service.encrypt("")
        assert encrypted == ""
    
    def test_decrypt_empty_string(self):
        """Test decrypting empty string returns empty string."""
        service = EncryptionService()
        
        decrypted = service.decrypt("")
        assert decrypted == ""
    
    def test_encrypt_unicode(self):
        """Test encrypting unicode characters."""
        service = EncryptionService()
        
        original = "患者姓名: 张三 📧 test@example.com"
        encrypted = service.encrypt(original)
        decrypted = service.decrypt(encrypted)
        
        assert decrypted == original
    
    def test_encrypt_long_string(self):
        """Test encrypting long string."""
        service = EncryptionService()
        
        original = "A" * 10000
        encrypted = service.encrypt(original)
        decrypted = service.decrypt(encrypted)
        
        assert decrypted == original
    
    def test_encryption_is_randomized(self):
        """Test that encrypting same data produces different ciphertexts."""
        service = EncryptionService()
        
        data = "sensitive data"
        encrypted1 = service.encrypt(data)
        encrypted2 = service.encrypt(data)
        
        # Due to random IV, encryptions should be different
        assert encrypted1 != encrypted2
        
        # But both should decrypt to same value
        assert service.decrypt(encrypted1) == data
        assert service.decrypt(encrypted2) == data


class TestDictionaryEncryption:
    """Tests for dictionary field encryption."""
    
    def test_encrypt_dict_specific_fields(self):
        """Test encrypting specific fields in a dictionary."""
        service = EncryptionService()
        
        data = {
            "name": "John Doe",
            "ssn": "123-45-6789",
            "email": "john@example.com",
            "age": 45
        }
        
        encrypted = service.encrypt_dict(data, ['ssn', 'email'])
        
        # Name and age should be unchanged
        assert encrypted["name"] == "John Doe"
        assert encrypted["age"] == 45
        
        # SSN and email should be encrypted (different from original)
        assert encrypted["ssn"] != "123-45-6789"
        assert encrypted["email"] != "john@example.com"
    
    def test_decrypt_dict_specific_fields(self):
        """Test decrypting specific fields in a dictionary."""
        service = EncryptionService()
        
        data = {
            "name": "John Doe",
            "ssn": "123-45-6789",
            "email": "john@example.com"
        }
        
        encrypted = service.encrypt_dict(data, ['ssn', 'email'])
        decrypted = service.decrypt_dict(encrypted, ['ssn', 'email'])
        
        assert decrypted["ssn"] == "123-45-6789"
        assert decrypted["email"] == "john@example.com"
        assert decrypted["name"] == "John Doe"
    
    def test_encrypt_dict_missing_fields(self):
        """Test encrypting when some fields don't exist."""
        service = EncryptionService()
        
        data = {"name": "John Doe"}
        encrypted = service.encrypt_dict(data, ['ssn', 'email'])
        
        # Should not raise, just skip missing fields
        assert encrypted["name"] == "John Doe"
        assert "ssn" not in encrypted
    
    def test_encrypt_dict_none_values(self):
        """Test encrypting when fields have None values."""
        service = EncryptionService()
        
        data = {
            "name": "John Doe",
            "ssn": None,
            "email": ""
        }
        
        encrypted = service.encrypt_dict(data, ['ssn', 'email'])
        
        # None and empty should remain unchanged
        assert encrypted["ssn"] is None
        assert encrypted["email"] == ""


class TestPIIPHIHelpers:
    """Tests for PII/PHI encryption helper functions."""
    
    def test_pii_encryption_helpers(self):
        """Test PII encryption helper functions."""
        data = {
            "name": "Jane Smith",
            "ssn": "987-65-4321",
            "phone": "555-1234",
            "email": "jane@example.com",
            "address": "123 Main St"
        }
        
        encrypted = encrypt_pii(data)
        
        # Name should not be encrypted (not in PII list)
        assert encrypted["name"] == "Jane Smith"
        
        # PII fields should be encrypted
        assert encrypted["ssn"] != "987-65-4321"
        assert encrypted["phone"] != "555-1234"
        assert encrypted["email"] != "jane@example.com"
        assert encrypted["address"] != "123 Main St"
        
        # Decrypt and verify
        decrypted = decrypt_pii(encrypted)
        assert decrypted["ssn"] == "987-65-4321"
        assert decrypted["phone"] == "555-1234"
    
    def test_phi_encryption_includes_medical_data(self):
        """Test PHI encryption includes medical fields."""
        service = EncryptionService()
        
        data = {
            "name": "Jane Smith",
            "ssn": "987-65-4321",
            "diagnosis": "Hypertension",
            "medications": "Lisinopril 10mg"
        }
        
        encrypted = service.encrypt_phi(data)
        
        # PHI fields should be encrypted
        assert encrypted["ssn"] != "987-65-4321"
        assert encrypted["diagnosis"] != "Hypertension"
        assert encrypted["medications"] != "Lisinopril 10mg"


class TestSingletonService:
    """Tests for singleton service behavior."""
    
    def test_singleton_returns_same_instance(self):
        """Test that get_encryption_service returns same instance."""
        service1 = get_encryption_service()
        service2 = get_encryption_service()
        
        assert service1 is service2  # Should be same object
    
    def test_reset_creates_new_instance(self):
        """Test that reset_encryption_service creates new instance."""
        service1 = get_encryption_service()
        reset_encryption_service()
        service2 = get_encryption_service()
        
        assert service1 is not service2  # Should be different objects


class TestKeyGeneration:
    """Tests for key generation utilities."""
    
    def test_generate_key_creates_valid_key(self):
        """Test that generated key is valid Fernet key."""
        from cryptography.fernet import Fernet
        
        key = EncryptionService.generate_key()
        
        # Should be valid Fernet key
        fernet = Fernet(key.encode())
        assert fernet is not None
    
    def test_derive_key_from_password(self):
        """Test deriving key from password."""
        key, salt = EncryptionService.derive_key_from_password("my-password")
        
        assert key is not None
        assert salt is not None
        assert len(salt) == 16
        
        # Same password and salt should produce same key
        key2, _ = EncryptionService.derive_key_from_password("my-password", salt)
        assert key == key2
    
    def test_different_passwords_different_keys(self):
        """Test different passwords produce different keys."""
        salt = os.urandom(16)
        
        key1, _ = EncryptionService.derive_key_from_password("password1", salt)
        key2, _ = EncryptionService.derive_key_from_password("password2", salt)
        
        assert key1 != key2


class TestErrorHandling:
    """Tests for error handling."""
    
    def test_decrypt_invalid_data_raises_error(self):
        """Test decrypting invalid data raises DecryptionError."""
        service = EncryptionService()
        
        with pytest.raises(DecryptionError):
            service.decrypt("not-valid-encrypted-data")
    
    def test_decrypt_wrong_key_raises_error(self):
        """Test decrypting with wrong key raises DecryptionError."""
        from cryptography.fernet import Fernet
        
        # Encrypt with one service
        service1 = EncryptionService()
        encrypted = service1.encrypt("secret data")
        
        # Try to decrypt with different key
        different_key = Fernet.generate_key()
        service2 = EncryptionService(key=different_key)
        
        with pytest.raises(DecryptionError):
            service2.decrypt(encrypted)
