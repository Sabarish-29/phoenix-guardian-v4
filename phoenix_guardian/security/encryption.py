"""
Simple encryption service for PII/PHI data.

Provides Fernet symmetric encryption for sensitive fields like:
- Social Security Numbers
- Phone numbers
- Email addresses
- Physical addresses
- Date of birth

This is a simplified encryption service for common use cases.
For post-quantum secure encryption, use pqc_encryption module.

HIPAA Compliance:
- 45 CFR §164.312(a)(2)(iv): Encryption and decryption
- NIST SP 800-111: Storage encryption guidelines
"""

import os
import base64
import logging
from typing import Dict, List, Any, Optional

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

logger = logging.getLogger(__name__)


class EncryptionError(Exception):
    """Error during encryption operation."""
    pass


class DecryptionError(Exception):
    """Error during decryption operation."""
    pass


class EncryptionService:
    """
    Handles encryption/decryption of sensitive PII/PHI data.
    
    Uses Fernet symmetric encryption (AES-128-CBC with HMAC).
    Key is derived from environment variable or auto-generated.
    
    Usage:
        service = EncryptionService()
        encrypted = service.encrypt("123-45-6789")
        decrypted = service.decrypt(encrypted)
    
    For PII fields:
        encrypted_data = service.encrypt_dict(patient_data, ['ssn', 'phone'])
        decrypted_data = service.decrypt_dict(encrypted_data, ['ssn', 'phone'])
    """
    
    # PII fields that should be encrypted
    PII_FIELDS = ['ssn', 'phone', 'email', 'address', 'date_of_birth']
    
    # PHI fields that should be encrypted (extends PII)
    PHI_FIELDS = PII_FIELDS + [
        'diagnosis', 'medications', 'allergies', 'lab_results',
        'insurance_id', 'medical_record_number'
    ]
    
    def __init__(self, key: Optional[bytes] = None):
        """
        Initialize encryption service with key.
        
        Args:
            key: Optional encryption key (32 bytes base64-encoded).
                 If not provided, uses ENCRYPTION_KEY env var or generates new key.
        """
        self.key = key or self._get_or_create_key()
        self.fernet = Fernet(self.key)
        self._key_generated = False
    
    def _get_or_create_key(self) -> bytes:
        """
        Get encryption key from environment or generate new one.
        
        Returns:
            Encryption key as bytes (base64-encoded)
            
        Note:
            If generating new key, prints warning to add to .env
        """
        key_env = os.getenv("ENCRYPTION_KEY")
        
        if key_env:
            try:
                # Validate it's a proper Fernet key
                Fernet(key_env.encode())
                return key_env.encode()
            except Exception as e:
                logger.warning(f"Invalid ENCRYPTION_KEY format: {e}, generating new key")
        
        # Generate new key
        key = Fernet.generate_key()
        self._key_generated = True
        
        logger.warning("⚠️  Generated new encryption key")
        logger.warning(f"    Add to .env file: ENCRYPTION_KEY={key.decode()}")
        logger.warning("    ⚠️  SAVE THIS KEY SECURELY - Lost key = lost data!")
        
        return key
    
    @property
    def key_was_generated(self) -> bool:
        """Check if key was auto-generated (not from env)."""
        return self._key_generated
    
    def encrypt(self, data: str) -> str:
        """
        Encrypt string data.
        
        Args:
            data: Plain text string to encrypt
            
        Returns:
            Encrypted string (base64 encoded)
            
        Raises:
            EncryptionError: If encryption fails
        """
        if not data:
            return ""
        
        try:
            encrypted = self.fernet.encrypt(data.encode('utf-8'))
            return encrypted.decode('utf-8')
        except Exception as e:
            raise EncryptionError(f"Encryption failed: {e}") from e
    
    def decrypt(self, encrypted_data: str) -> str:
        """
        Decrypt string data.
        
        Args:
            encrypted_data: Encrypted string to decrypt
            
        Returns:
            Decrypted plain text string
            
        Raises:
            DecryptionError: If decryption fails (invalid key or data)
        """
        if not encrypted_data:
            return ""
        
        try:
            decrypted = self.fernet.decrypt(encrypted_data.encode('utf-8'))
            return decrypted.decode('utf-8')
        except InvalidToken:
            raise DecryptionError("Decryption failed: Invalid token or key")
        except Exception as e:
            raise DecryptionError(f"Decryption failed: {e}") from e
    
    def encrypt_dict(
        self, 
        data: Dict[str, Any], 
        fields: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Encrypt specific fields in a dictionary.
        
        Args:
            data: Dictionary containing data
            fields: List of field names to encrypt (default: PII_FIELDS)
            
        Returns:
            Dictionary with specified fields encrypted
        """
        if fields is None:
            fields = self.PII_FIELDS
        
        encrypted = data.copy()
        
        for field in fields:
            if field in encrypted and encrypted[field]:
                try:
                    encrypted[field] = self.encrypt(str(encrypted[field]))
                except EncryptionError:
                    logger.error(f"Failed to encrypt field: {field}")
                    raise
        
        return encrypted
    
    def decrypt_dict(
        self, 
        data: Dict[str, Any], 
        fields: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Decrypt specific fields in a dictionary.
        
        Args:
            data: Dictionary with encrypted fields
            fields: List of field names to decrypt (default: PII_FIELDS)
            
        Returns:
            Dictionary with specified fields decrypted
        """
        if fields is None:
            fields = self.PII_FIELDS
        
        decrypted = data.copy()
        
        for field in fields:
            if field in decrypted and decrypted[field]:
                try:
                    decrypted[field] = self.decrypt(decrypted[field])
                except DecryptionError:
                    logger.error(f"Failed to decrypt field: {field}")
                    raise
        
        return decrypted
    
    def encrypt_pii(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Encrypt PII fields in patient data.
        
        Args:
            data: Patient data dictionary
            
        Returns:
            Dictionary with PII fields encrypted
        """
        return self.encrypt_dict(data, self.PII_FIELDS)
    
    def decrypt_pii(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Decrypt PII fields in patient data.
        
        Args:
            data: Patient data with encrypted PII
            
        Returns:
            Dictionary with PII fields decrypted
        """
        return self.decrypt_dict(data, self.PII_FIELDS)
    
    def encrypt_phi(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Encrypt PHI fields in patient data.
        
        Args:
            data: Patient data dictionary
            
        Returns:
            Dictionary with PHI fields encrypted
        """
        return self.encrypt_dict(data, self.PHI_FIELDS)
    
    def decrypt_phi(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Decrypt PHI fields in patient data.
        
        Args:
            data: Patient data with encrypted PHI
            
        Returns:
            Dictionary with PHI fields decrypted
        """
        return self.decrypt_dict(data, self.PHI_FIELDS)
    
    @staticmethod
    def generate_key() -> str:
        """
        Generate a new encryption key.
        
        Returns:
            Base64-encoded Fernet key as string
        """
        return Fernet.generate_key().decode('utf-8')
    
    @staticmethod
    def derive_key_from_password(
        password: str, 
        salt: Optional[bytes] = None
    ) -> tuple[bytes, bytes]:
        """
        Derive encryption key from password using PBKDF2.
        
        Args:
            password: Password to derive key from
            salt: Optional salt (16 bytes). Generated if not provided.
            
        Returns:
            Tuple of (key, salt) - both as bytes
        """
        if salt is None:
            salt = os.urandom(16)
        
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=480000,
        )
        
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        return key, salt


# Singleton instance
_encryption_service: Optional[EncryptionService] = None


def get_encryption_service() -> EncryptionService:
    """
    Get singleton encryption service instance.
    
    Returns:
        EncryptionService instance
    """
    global _encryption_service
    if _encryption_service is None:
        _encryption_service = EncryptionService()
    return _encryption_service


def reset_encryption_service() -> None:
    """
    Reset singleton encryption service.
    
    Useful for testing with different keys.
    """
    global _encryption_service
    _encryption_service = None


# Convenience functions
def encrypt_pii(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Encrypt PII fields in patient data.
    
    Args:
        data: Patient data dictionary
        
    Returns:
        Dictionary with PII fields encrypted
    """
    service = get_encryption_service()
    return service.encrypt_pii(data)


def decrypt_pii(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Decrypt PII fields in patient data.
    
    Args:
        data: Patient data with encrypted PII
        
    Returns:
        Dictionary with PII fields decrypted
    """
    service = get_encryption_service()
    return service.decrypt_pii(data)


def encrypt_phi(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Encrypt PHI fields in patient data.
    
    Args:
        data: Patient data dictionary
        
    Returns:
        Dictionary with PHI fields encrypted
    """
    service = get_encryption_service()
    return service.encrypt_phi(data)


def decrypt_phi(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Decrypt PHI fields in patient data.
    
    Args:
        data: Patient data with encrypted PHI
        
    Returns:
        Dictionary with PHI fields decrypted
    """
    service = get_encryption_service()
    return service.decrypt_phi(data)
