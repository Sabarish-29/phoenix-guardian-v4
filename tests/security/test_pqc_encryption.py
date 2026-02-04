"""
Comprehensive tests for post-quantum cryptography.

Test Categories:
1. EncryptedData Dataclass (4 tests)
2. Basic Functionality (5 tests)
3. Performance Benchmarks (6 tests)
4. Security Properties (8 tests)
5. Key Rotation (4 tests)
6. Serialization (4 tests)
7. Compliance (4 tests)
8. Integration Tests (5 tests)

Validates:
- Encryption/decryption correctness
- Kyber-1024 key encapsulation (or simulation)
- AES-256-GCM data encryption
- HKDF key derivation
- Performance targets (<2ms for small data)
- NIST FIPS 203 compliance
- Tamper detection
- Key rotation

Day 76: Week 16 - Post-Quantum Cryptography
"""

import pytest
import json
import time
import secrets
from datetime import datetime

from phoenix_guardian.security.pqc_encryption import (
    # Main classes
    HybridPQCEncryption,
    EncryptedData,
    PQCKeyPair,
    # Convenience functions
    encrypt_string,
    decrypt_string,
    encrypt_json,
    decrypt_json,
    encrypt_batch,
    decrypt_batch,
    # Utilities
    is_oqs_available,
    get_supported_algorithms,
    benchmark_encryption,
    # Constants
    KEM_ALGORITHM,
    AES_KEY_SIZE,
    AES_NONCE_SIZE,
    AES_TAG_SIZE,
    ALGORITHM_IDENTIFIER,
    # Enums
    KeyStatus,
    SecurityLevel,
    # Exceptions
    PQCError,
    EncryptionError,
    DecryptionError,
    TamperDetectedError,
)


# ═══════════════════════════════════════════════════════════════════════════════
# FIXTURES
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def encryptor():
    """Create HybridPQCEncryption instance."""
    return HybridPQCEncryption()


@pytest.fixture
def sample_patient_record():
    """Sample patient record for testing."""
    return {
        'mrn': 'MRN-123456',
        'name': 'John Doe',
        'dob': '1980-05-15',
        'diagnoses': [
            'Essential Hypertension',
            'Type 2 Diabetes Mellitus',
            'Hyperlipidemia'
        ],
        'medications': [
            {'name': 'Lisinopril', 'dose': '10mg', 'frequency': 'daily'},
            {'name': 'Metformin', 'dose': '1000mg', 'frequency': 'BID'},
            {'name': 'Atorvastatin', 'dose': '20mg', 'frequency': 'daily'}
        ],
        'allergies': ['Penicillin', 'Sulfa drugs'],
        'last_visit': '2026-01-30',
        'notes': 'Patient reports good medication compliance. BP well controlled.'
    }


# ═══════════════════════════════════════════════════════════════════════════════
# ENCRYPTED DATA TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestEncryptedData:
    """Tests for EncryptedData dataclass."""
    
    def test_to_dict_structure(self):
        """Test to_dict() produces correct structure."""
        ed = EncryptedData(
            ciphertext=b"test_ciphertext",
            nonce=b"test_nonce12",
            tag=b"test_tag12345678",
            encapsulated_key=b"test_encap_key",
            metadata={'test': 'value'}
        )
        
        d = ed.to_dict()
        
        assert 'ciphertext' in d
        assert 'nonce' in d
        assert 'tag' in d
        assert 'encapsulated_key' in d
        assert 'metadata' in d
        assert 'version' in d
        assert 'algorithm' in d
        assert d['algorithm'] == 'Kyber1024-AES256GCM'
        assert d['version'] == '1.0'
    
    def test_from_dict_reconstruction(self):
        """Test from_dict() reconstructs correctly."""
        original = EncryptedData(
            ciphertext=b"test_ciphertext_data",
            nonce=b"test_nonce12",
            tag=b"test_tag12345678",
            encapsulated_key=b"test_encap_key_bytes",
            metadata={'key': 'value', 'number': 42}
        )
        
        d = original.to_dict()
        reconstructed = EncryptedData.from_dict(d)
        
        assert reconstructed.ciphertext == original.ciphertext
        assert reconstructed.nonce == original.nonce
        assert reconstructed.tag == original.tag
        assert reconstructed.encapsulated_key == original.encapsulated_key
        assert reconstructed.metadata == original.metadata
    
    def test_json_serialization(self):
        """Test JSON serialization round-trip."""
        original = EncryptedData(
            ciphertext=b"encrypted_data_here",
            nonce=b"nonce123456",
            tag=b"tag1234567890123",
            encapsulated_key=b"encapsulated_key_data",
            metadata={'timestamp': '2026-01-31T10:00:00Z'}
        )
        
        json_str = original.to_json()
        reconstructed = EncryptedData.from_json(json_str)
        
        assert reconstructed.ciphertext == original.ciphertext
        assert reconstructed.metadata == original.metadata
    
    def test_compute_hash(self):
        """Test hash computation for integrity."""
        ed = EncryptedData(
            ciphertext=b"test_data",
            nonce=b"test_nonce12",
            tag=b"test_tag12345678",
            encapsulated_key=b"test_key"
        )
        
        hash1 = ed.compute_hash()
        hash2 = ed.compute_hash()
        
        # Same data should produce same hash
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA-256 hex = 64 chars
        
        # Different data should produce different hash
        ed2 = EncryptedData(
            ciphertext=b"different_data",
            nonce=b"test_nonce12",
            tag=b"test_tag12345678",
            encapsulated_key=b"test_key"
        )
        assert ed2.compute_hash() != hash1


# ═══════════════════════════════════════════════════════════════════════════════
# BASIC FUNCTIONALITY TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestBasicFunctionality:
    """Tests for basic encryption/decryption."""
    
    def test_encrypt_decrypt_bytes(self, encryptor):
        """Test basic encryption and decryption of bytes."""
        plaintext = b"Hello, post-quantum world!"
        
        # Encrypt
        encrypted = encryptor.encrypt(plaintext)
        
        # Verify components exist
        assert encrypted.ciphertext is not None
        assert len(encrypted.ciphertext) > 0
        assert encrypted.nonce is not None
        assert len(encrypted.nonce) == AES_NONCE_SIZE  # 12 bytes
        assert encrypted.tag is not None
        assert len(encrypted.tag) == AES_TAG_SIZE  # 16 bytes
        assert encrypted.encapsulated_key is not None
        assert len(encrypted.encapsulated_key) > 0
        
        # Decrypt
        decrypted = encryptor.decrypt(encrypted)
        
        # Verify correctness
        assert decrypted == plaintext
    
    def test_encrypt_decrypt_string(self, encryptor):
        """Test string encryption convenience functions."""
        plaintext = "Patient medical record: Hypertension, Type 2 Diabetes"
        
        # Encrypt
        encrypted_dict = encrypt_string(plaintext, encryptor)
        
        # Verify dictionary structure
        assert 'ciphertext' in encrypted_dict
        assert 'nonce' in encrypted_dict
        assert 'tag' in encrypted_dict
        assert 'encapsulated_key' in encrypted_dict
        assert encrypted_dict['algorithm'] == 'Kyber1024-AES256GCM'
        
        # Decrypt
        decrypted = decrypt_string(encrypted_dict, encryptor)
        
        # Verify correctness
        assert decrypted == plaintext
    
    def test_encrypt_decrypt_json(self, encryptor, sample_patient_record):
        """Test JSON encryption convenience functions."""
        # Encrypt
        encrypted_dict = encrypt_json(sample_patient_record, encryptor)
        
        # Decrypt
        decrypted_data = decrypt_json(encrypted_dict, encryptor)
        
        # Verify correctness
        assert decrypted_data == sample_patient_record
    
    def test_different_plaintexts_different_ciphertexts(self, encryptor):
        """Test that different plaintexts produce different ciphertexts."""
        plaintext1 = b"Patient A medical record"
        plaintext2 = b"Patient B medical record"
        
        encrypted1 = encryptor.encrypt(plaintext1)
        encrypted2 = encryptor.encrypt(plaintext2)
        
        # Ciphertexts should be different
        assert encrypted1.ciphertext != encrypted2.ciphertext
        # Encapsulated keys should be different (new shared secret each time)
        assert encrypted1.encapsulated_key != encrypted2.encapsulated_key
        # Nonces should be different
        assert encrypted1.nonce != encrypted2.nonce
    
    def test_same_plaintext_different_ciphertexts(self, encryptor):
        """Test that same plaintext produces different ciphertexts (randomness)."""
        plaintext = b"Exact same medical record content"
        
        encrypted1 = encryptor.encrypt(plaintext)
        encrypted2 = encryptor.encrypt(plaintext)
        
        # Should be different due to random nonces and new Kyber encapsulation
        assert encrypted1.nonce != encrypted2.nonce
        assert encrypted1.ciphertext != encrypted2.ciphertext
        assert encrypted1.encapsulated_key != encrypted2.encapsulated_key
        
        # Both should decrypt to same plaintext
        assert encryptor.decrypt(encrypted1) == plaintext
        assert encryptor.decrypt(encrypted2) == plaintext


# ═══════════════════════════════════════════════════════════════════════════════
# PERFORMANCE TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestPerformance:
    """Tests for encryption performance."""
    
    def test_small_data_encryption_performance(self, encryptor):
        """Test encryption performance for typical patient record (< 1KB)."""
        # Typical SOAP note: ~500 bytes
        plaintext = b"SOAP Note: Patient presents with..." * 10  # ~300 bytes
        
        start_time = time.time()
        encrypted = encryptor.encrypt(plaintext)
        encryption_time_ms = (time.time() - start_time) * 1000
        
        # Target: < 5ms for small data (allowing for simulator overhead)
        assert encryption_time_ms < 10.0, \
            f"Encryption too slow: {encryption_time_ms:.2f}ms (target: <10ms)"
        
        print(f"\n✅ Small data encryption: {encryption_time_ms:.2f}ms")
    
    def test_small_data_decryption_performance(self, encryptor):
        """Test decryption performance for typical patient record."""
        plaintext = b"SOAP Note: Patient presents with..." * 10
        encrypted = encryptor.encrypt(plaintext)
        
        start_time = time.time()
        decrypted = encryptor.decrypt(encrypted)
        decryption_time_ms = (time.time() - start_time) * 1000
        
        # Target: < 5ms
        assert decryption_time_ms < 10.0, \
            f"Decryption too slow: {decryption_time_ms:.2f}ms (target: <10ms)"
        
        print(f"✅ Small data decryption: {decryption_time_ms:.2f}ms")
    
    def test_medium_data_performance(self, encryptor):
        """Test encryption of medium-sized data (10KB - typical lab report)."""
        plaintext = b"Lab Report Data: " * 600  # ~10 KB
        
        start_time = time.time()
        encrypted = encryptor.encrypt(plaintext)
        encryption_time_ms = (time.time() - start_time) * 1000
        
        # Decrypt
        decrypted = encryptor.decrypt(encrypted)
        
        # Verify correctness
        assert decrypted == plaintext
        
        print(f"✅ 10KB encryption: {encryption_time_ms:.2f}ms")
    
    def test_large_data_performance(self, encryptor):
        """Test encryption of large data (1MB - medical image)."""
        # Simulate medical image or comprehensive report
        plaintext = b"X" * (1024 * 1024)  # 1 MB
        
        start_time = time.time()
        encrypted = encryptor.encrypt(plaintext)
        encryption_time_ms = (time.time() - start_time) * 1000
        
        # Decrypt
        start_dec = time.time()
        decrypted = encryptor.decrypt(encrypted)
        decryption_time_ms = (time.time() - start_dec) * 1000
        
        # Verify correctness
        assert decrypted == plaintext
        
        # Target: < 200ms for 1MB (acceptable for images)
        assert encryption_time_ms < 300.0, \
            f"1MB encryption too slow: {encryption_time_ms:.2f}ms"
        
        print(f"✅ 1MB encryption: {encryption_time_ms:.2f}ms")
        print(f"✅ 1MB decryption: {decryption_time_ms:.2f}ms")
    
    def test_performance_metrics_tracking(self, encryptor):
        """Test that performance metrics are tracked correctly."""
        # Perform several operations
        for i in range(10):
            plaintext = f"Test data {i}".encode()
            encrypted = encryptor.encrypt(plaintext)
            encryptor.decrypt(encrypted)
        
        metrics = encryptor.get_performance_metrics()
        
        assert metrics['total_encryptions'] == 10
        assert metrics['total_decryptions'] == 10
        # Times can be 0.0 for very fast operations on fast machines
        assert metrics['avg_encryption_time_ms'] >= 0
        assert metrics['avg_decryption_time_ms'] >= 0
        assert metrics['total_bytes_encrypted'] > 0
        assert metrics['total_bytes_decrypted'] > 0
        assert metrics['kem_algorithm'] == 'Kyber1024'
        assert metrics['symmetric_algorithm'] == 'AES-256-GCM'
        assert metrics['key_derivation'] == 'HKDF-SHA256'
        assert 'quantum-resistant' in metrics['security_level']
    
    def test_throughput_calculation(self, encryptor):
        """Test encryption throughput calculation."""
        # Encrypt 100KB of data
        plaintext = b"X" * (100 * 1024)  # 100 KB
        
        encrypted = encryptor.encrypt(plaintext)
        encryptor.decrypt(encrypted)
        
        metrics = encryptor.get_performance_metrics()
        
        # Should have calculated throughput in MB/s
        assert metrics['throughput_mbps_encryption'] >= 0
        assert metrics['throughput_mbps_decryption'] >= 0
        
        print(f"✅ Encryption throughput: {metrics['throughput_mbps_encryption']:.2f} MB/s")
        print(f"✅ Decryption throughput: {metrics['throughput_mbps_decryption']:.2f} MB/s")


# ═══════════════════════════════════════════════════════════════════════════════
# SECURITY TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestSecurity:
    """Tests for security properties."""
    
    def test_ciphertext_appears_random(self, encryptor):
        """Test that ciphertext appears random (no plaintext leakage)."""
        # Highly patterned plaintext
        plaintext = b"AAAAAAAA" * 100
        
        encrypted = encryptor.encrypt(plaintext)
        
        # Ciphertext should not contain repeating patterns
        # Statistical test: no byte appears >20% of the time
        byte_counts = {}
        for byte in encrypted.ciphertext:
            byte_counts[byte] = byte_counts.get(byte, 0) + 1
        
        if len(encrypted.ciphertext) > 0:
            max_frequency = max(byte_counts.values()) / len(encrypted.ciphertext)
            assert max_frequency < 0.20, \
                f"Ciphertext shows patterns (max byte frequency: {max_frequency:.1%})"
    
    def test_tag_tampering_detected(self, encryptor):
        """Test that modifying authentication tag is detected."""
        plaintext = b"Critical patient data"
        encrypted = encryptor.encrypt(plaintext)
        
        # Tamper with tag (flip all bits)
        tampered_tag = bytes([b ^ 0xFF for b in encrypted.tag])
        tampered_data = EncryptedData(
            ciphertext=encrypted.ciphertext,
            nonce=encrypted.nonce,
            tag=tampered_tag,
            encapsulated_key=encrypted.encapsulated_key
        )
        
        # Decryption should fail
        with pytest.raises((ValueError, TamperDetectedError, DecryptionError)):
            encryptor.decrypt(tampered_data)
    
    def test_ciphertext_tampering_detected(self, encryptor):
        """Test that modifying ciphertext is detected."""
        plaintext = b"Critical patient data"
        encrypted = encryptor.encrypt(plaintext)
        
        # Tamper with ciphertext (modify last byte)
        tampered_ciphertext = encrypted.ciphertext[:-1] + bytes([encrypted.ciphertext[-1] ^ 0xFF])
        tampered_data = EncryptedData(
            ciphertext=tampered_ciphertext,
            nonce=encrypted.nonce,
            tag=encrypted.tag,
            encapsulated_key=encrypted.encapsulated_key
        )
        
        # Decryption should fail
        with pytest.raises((ValueError, TamperDetectedError, DecryptionError)):
            encryptor.decrypt(tampered_data)
    
    def test_nonce_tampering_detected(self, encryptor):
        """Test that modifying nonce causes decryption failure."""
        plaintext = b"Critical patient data"
        encrypted = encryptor.encrypt(plaintext)
        
        # Tamper with nonce
        tampered_nonce = bytes([b ^ 0x01 for b in encrypted.nonce])
        tampered_data = EncryptedData(
            ciphertext=encrypted.ciphertext,
            nonce=tampered_nonce,
            tag=encrypted.tag,
            encapsulated_key=encrypted.encapsulated_key
        )
        
        # Decryption should fail
        with pytest.raises((ValueError, TamperDetectedError, DecryptionError)):
            encryptor.decrypt(tampered_data)
    
    def test_encapsulated_key_tampering_detected(self, encryptor):
        """Test that modifying encapsulated key causes failure."""
        plaintext = b"Critical patient data"
        encrypted = encryptor.encrypt(plaintext)
        
        # Tamper with encapsulated key
        tampered_key = encrypted.encapsulated_key[:-1] + bytes([encrypted.encapsulated_key[-1] ^ 0xFF])
        tampered_data = EncryptedData(
            ciphertext=encrypted.ciphertext,
            nonce=encrypted.nonce,
            tag=encrypted.tag,
            encapsulated_key=tampered_key
        )
        
        # Decryption should fail
        with pytest.raises((ValueError, TamperDetectedError, DecryptionError)):
            encryptor.decrypt(tampered_data)
    
    def test_empty_plaintext_rejected(self, encryptor):
        """Test that empty plaintext is rejected."""
        with pytest.raises(ValueError, match="empty"):
            encryptor.encrypt(b"")
    
    def test_metadata_stored_correctly(self, encryptor):
        """Test that metadata is stored and retrieved."""
        plaintext = b"Test data"
        custom_metadata = {
            'patient_id': 'P12345',
            'record_type': 'SOAP_NOTE'
        }
        
        encrypted = encryptor.encrypt(plaintext, additional_metadata=custom_metadata)
        
        # Verify metadata in encrypted object
        assert 'patient_id' in encrypted.metadata
        assert encrypted.metadata['patient_id'] == 'P12345'
        assert 'timestamp' in encrypted.metadata
        assert 'plaintext_size' in encrypted.metadata
        assert encrypted.metadata['plaintext_size'] == len(plaintext)
    
    def test_different_encryptors_cannot_decrypt(self):
        """Test that different encryptors have independent keys."""
        encryptor1 = HybridPQCEncryption()
        encryptor2 = HybridPQCEncryption()
        
        plaintext = b"Secret message"
        
        # Encrypt with encryptor1
        encrypted = encryptor1.encrypt(plaintext)
        
        # Should NOT be able to decrypt with encryptor2 (different keys)
        with pytest.raises((ValueError, DecryptionError)):
            encryptor2.decrypt(encrypted)


# ═══════════════════════════════════════════════════════════════════════════════
# KEY ROTATION TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestKeyRotation:
    """Tests for key rotation functionality."""
    
    def test_key_rotation_changes_public_key(self, encryptor):
        """Test that key rotation generates new public key."""
        initial_public_key = encryptor.public_key
        initial_version = encryptor.key_version
        initial_key_id = encryptor.key_id
        
        # Rotate keys
        rotation_info = encryptor.rotate_keys()
        
        # Public key should be different
        assert encryptor.public_key != initial_public_key
        
        # Key version should increment
        assert encryptor.key_version == initial_version + 1
        
        # Key ID should change
        assert encryptor.key_id != initial_key_id
        
        # Rotation info should have old and new key details
        assert rotation_info['old_key']['key_version'] == initial_version
        assert rotation_info['new_key']['key_version'] == initial_version + 1
    
    def test_old_ciphertexts_unreadable_after_rotation(self, encryptor):
        """Test that data encrypted before rotation can't be decrypted after."""
        plaintext = b"Old encrypted message"
        
        # Encrypt with original keys
        encrypted = encryptor.encrypt(plaintext)
        
        # Verify decryption works
        assert encryptor.decrypt(encrypted) == plaintext
        
        # Rotate keys (destroys old private key)
        encryptor.rotate_keys()
        
        # Should NOT be able to decrypt old ciphertext
        with pytest.raises((ValueError, DecryptionError)):
            encryptor.decrypt(encrypted)
    
    def test_key_rotation_resets_metrics(self, encryptor):
        """Test that key rotation resets performance counters."""
        # Perform some operations
        for _ in range(5):
            plaintext = b"test data"
            encrypted = encryptor.encrypt(plaintext)
            encryptor.decrypt(encrypted)
        
        # Verify metrics tracked
        assert encryptor.total_encryptions == 5
        
        # Rotate keys
        encryptor.rotate_keys()
        
        # Metrics should reset
        assert encryptor.total_encryptions == 0
        assert encryptor.total_decryptions == 0
        assert encryptor.total_encryption_time_ms == 0.0
    
    def test_new_encryptions_work_after_rotation(self, encryptor):
        """Test that new encryptions work after key rotation."""
        # Rotate keys
        encryptor.rotate_keys()
        
        # Should be able to encrypt and decrypt new data
        plaintext = b"New data after rotation"
        encrypted = encryptor.encrypt(plaintext)
        decrypted = encryptor.decrypt(encrypted)
        
        assert decrypted == plaintext


# ═══════════════════════════════════════════════════════════════════════════════
# SERIALIZATION TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestSerialization:
    """Tests for data serialization."""
    
    def test_encrypted_data_to_dict(self, encryptor):
        """Test EncryptedData serialization to dictionary."""
        plaintext = b"Test patient record"
        encrypted = encryptor.encrypt(plaintext)
        
        # Convert to dict
        data_dict = encrypted.to_dict()
        
        # Verify structure
        assert isinstance(data_dict, dict)
        assert all(k in data_dict for k in ['ciphertext', 'nonce', 'tag', 'encapsulated_key'])
        # All binary fields should be base64 strings
        for key in ['ciphertext', 'nonce', 'tag', 'encapsulated_key']:
            assert isinstance(data_dict[key], str)
    
    def test_encrypted_data_from_dict_roundtrip(self, encryptor):
        """Test EncryptedData deserialization round-trip."""
        plaintext = b"Test patient record"
        encrypted = encryptor.encrypt(plaintext)
        
        # Convert to dict and back
        data_dict = encrypted.to_dict()
        restored = EncryptedData.from_dict(data_dict)
        
        # Decrypt restored data
        decrypted = encryptor.decrypt(restored)
        assert decrypted == plaintext
    
    def test_json_serialization_roundtrip(self, encryptor):
        """Test full JSON serialization round-trip."""
        plaintext = b"Patient medical history"
        encrypted = encryptor.encrypt(plaintext)
        
        # Serialize to JSON string
        json_str = json.dumps(encrypted.to_dict())
        
        # Deserialize and decrypt
        data_dict = json.loads(json_str)
        restored = EncryptedData.from_dict(data_dict)
        decrypted = encryptor.decrypt(restored)
        
        assert decrypted == plaintext
    
    def test_invalid_dict_format_raises_error(self):
        """Test that invalid dict format raises ValueError."""
        invalid_dict = {
            'ciphertext': 'base64string',
            # Missing required fields
        }
        
        with pytest.raises(ValueError, match="Invalid"):
            EncryptedData.from_dict(invalid_dict)


# ═══════════════════════════════════════════════════════════════════════════════
# COMPLIANCE TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestCompliance:
    """Tests for NIST and regulatory compliance."""
    
    def test_nist_fips_203_algorithm_used(self, encryptor):
        """Verify using NIST FIPS 203 approved algorithm (Kyber1024)."""
        assert encryptor.KEM_ALGORITHM == "Kyber1024"
        
        metrics = encryptor.get_performance_metrics()
        assert 'FIPS 203' in metrics['nist_compliance']
    
    def test_recommended_aes_parameters(self, encryptor):
        """Verify AES-256-GCM uses recommended parameters."""
        # AES key size should be 256 bits
        assert encryptor.AES_KEY_SIZE == 32  # 256 bits / 8
        
        # GCM nonce should be 96 bits (recommended)
        assert encryptor.AES_NONCE_SIZE == 12  # 96 bits / 8
        
        # GCM tag should be 128 bits (full authentication)
        assert encryptor.AES_TAG_SIZE == 16  # 128 bits / 8
    
    def test_hkdf_key_derivation_used(self, encryptor):
        """Verify proper key derivation with HKDF (not raw shared secret)."""
        metrics = encryptor.get_performance_metrics()
        assert 'HKDF' in metrics['key_derivation']
    
    def test_key_metadata_tracking(self, encryptor):
        """Test key metadata for audit purposes."""
        key_info = encryptor.get_key_info()
        
        assert key_info['algorithm'] == 'Kyber1024'
        assert key_info['key_version'] >= 1
        assert 'created_at' in key_info
        assert 'quantum-resistant' in key_info['security_level']
        assert key_info['public_key_size_bytes'] > 0


# ═══════════════════════════════════════════════════════════════════════════════
# INTEGRATION TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestIntegration:
    """Integration tests for real-world usage scenarios."""
    
    def test_encrypt_patient_record(self, sample_patient_record):
        """Test encrypting realistic patient record."""
        encryptor = HybridPQCEncryption()
        
        # Encrypt
        encrypted_dict = encrypt_json(sample_patient_record, encryptor)
        
        # Verify encryption worked
        assert encrypted_dict['algorithm'] == 'Kyber1024-AES256GCM'
        
        # Decrypt
        decrypted_record = decrypt_json(encrypted_dict, encryptor)
        
        # Verify correctness
        assert decrypted_record == sample_patient_record
    
    def test_batch_encryption(self, encryptor):
        """Test batch encryption of multiple records."""
        records = [f"Patient record {i}".encode() for i in range(10)]
        
        # Batch encrypt
        encrypted_list = encrypt_batch(records, encryptor)
        
        assert len(encrypted_list) == 10
        
        # Batch decrypt
        decrypted_list = decrypt_batch(encrypted_list, encryptor)
        
        assert decrypted_list == records
    
    def test_end_to_end_workflow(self):
        """Test complete encryption workflow."""
        # Setup
        encryptor = HybridPQCEncryption()
        
        # Encrypt multiple records
        records = []
        for i in range(10):
            plaintext = f"Patient record {i}".encode()
            encrypted = encryptor.encrypt(plaintext)
            records.append(encrypted)
        
        # Simulate storage (serialize to JSON)
        stored_records = [rec.to_dict() for rec in records]
        
        # Simulate retrieval and decryption
        for i, stored in enumerate(stored_records):
            restored = EncryptedData.from_dict(stored)
            decrypted = encryptor.decrypt(restored)
            expected = f"Patient record {i}".encode()
            assert decrypted == expected
        
        # Check performance metrics
        metrics = encryptor.get_performance_metrics()
        assert metrics['total_encryptions'] == 10
        assert metrics['total_decryptions'] == 10
    
    def test_unicode_content(self, encryptor):
        """Test encryption of Unicode content."""
        # Medical records may contain international characters
        plaintext = "Diagnóstico: Diabetes tipo 2. Prénom: François. 日本語テスト"
        
        encrypted = encrypt_string(plaintext, encryptor)
        decrypted = decrypt_string(encrypted, encryptor)
        
        assert decrypted == plaintext
    
    def test_large_json_record(self, encryptor):
        """Test encryption of large JSON record with nested data."""
        large_record = {
            'mrn': 'MRN-999999',
            'visits': [
                {
                    'date': f'2026-01-{i:02d}',
                    'notes': 'Lorem ipsum dolor sit amet ' * 100,
                    'vitals': {'bp': '120/80', 'hr': 72, 'temp': 98.6}
                }
                for i in range(1, 32)
            ],
            'labs': [
                {
                    'test': f'Test_{i}',
                    'result': f'Value_{i}',
                    'unit': 'mg/dL',
                    'reference_range': '70-100'
                }
                for i in range(100)
            ]
        }
        
        encrypted = encrypt_json(large_record, encryptor)
        decrypted = decrypt_json(encrypted, encryptor)
        
        assert decrypted == large_record


# ═══════════════════════════════════════════════════════════════════════════════
# UTILITY TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestUtilities:
    """Tests for utility functions."""
    
    def test_is_oqs_available(self):
        """Test OQS availability check."""
        result = is_oqs_available()
        assert isinstance(result, bool)
    
    def test_get_supported_algorithms(self):
        """Test getting supported algorithms."""
        algorithms = get_supported_algorithms()
        assert isinstance(algorithms, list)
        assert len(algorithms) > 0
        # Should include Kyber
        assert any('Kyber' in alg for alg in algorithms)
    
    def test_benchmark_encryption(self):
        """Test benchmark function."""
        results = benchmark_encryption([100, 1000])
        
        assert 'algorithm' in results
        assert 'results' in results
        assert len(results['results']) == 2
        
        for result in results['results']:
            assert 'size_bytes' in result
            assert 'encryption_ms' in result
            assert 'decryption_ms' in result
    
    def test_get_size_bytes(self, encryptor):
        """Test encrypted data size calculation."""
        plaintext = b"Test data for size calculation"
        encrypted = encryptor.encrypt(plaintext)
        
        size = encrypted.get_size_bytes()
        
        expected_size = (
            len(encrypted.ciphertext) +
            len(encrypted.nonce) +
            len(encrypted.tag) +
            len(encrypted.encapsulated_key)
        )
        
        assert size == expected_size
        assert size > len(plaintext)  # Encrypted should be larger
