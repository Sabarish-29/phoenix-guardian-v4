"""
API Routes for Post-Quantum Cryptography management.

Provides endpoints for:
- Encryption/decryption operations
- Key management and rotation
- PQC benchmarks and health
- PHI field encryption status
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from phoenix_guardian.api.auth import get_current_user

router = APIRouter(prefix="/pqc", tags=["post-quantum-cryptography"])


# ═══════════════════════════════════════════════════════════════════════════════
# Request/Response Models
# ═══════════════════════════════════════════════════════════════════════════════


class EncryptRequest(BaseModel):
    """Request model for string encryption."""
    plaintext: str = Field(..., description="String to encrypt")
    context: str = Field(default="api", description="Encryption context for audit")


class EncryptResponse(BaseModel):
    """Response model for encryption result."""
    algorithm: str
    key_id: str
    key_version: int
    ciphertext_b64: str
    encrypted_at: str


class DecryptRequest(BaseModel):
    """Request model for string decryption."""
    ciphertext_b64: str = Field(..., description="Base64-encoded ciphertext envelope")


class DecryptResponse(BaseModel):
    """Response model for decryption result."""
    plaintext: str
    decrypted_at: str


class PHIEncryptRequest(BaseModel):
    """Request model for PHI field encryption."""
    data: Dict[str, Any] = Field(..., description="Dictionary with potential PHI fields")
    context: str = Field(default="api", description="Context for audit logging")


class KeyRotationResponse(BaseModel):
    """Response model for key rotation result."""
    old_key_id: str
    new_key_id: str
    old_version: int
    new_version: int
    rotated_at: str


class BenchmarkResponse(BaseModel):
    """Response model for PQC benchmark results."""
    algorithm: str
    using_simulator: bool
    results: List[Dict[str, Any]]


class PQCHealthResponse(BaseModel):
    """Response model for PQC system health."""
    status: str
    algorithm: str
    oqs_available: bool
    key_id: str
    key_version: int
    total_encryptions: int
    total_decryptions: int
    using_simulator: bool
    tls_info: Dict[str, Any]


# ═══════════════════════════════════════════════════════════════════════════════
# Endpoints
# ═══════════════════════════════════════════════════════════════════════════════


@router.post("/encrypt", response_model=EncryptResponse)
async def encrypt_data(
    request: EncryptRequest,
    current_user=Depends(get_current_user),
):
    """
    Encrypt a string using Kyber-1024 + AES-256-GCM hybrid encryption.

    Uses NIST FIPS 203 compliant post-quantum cryptography.
    """
    try:
        from phoenix_guardian.security.pqc_encryption import (
            encrypt_string, HybridPQCEncryption,
        )
        import json
        from datetime import datetime, timezone

        encryptor = HybridPQCEncryption()
        encrypted = encrypt_string(request.plaintext, encryptor)

        return EncryptResponse(
            algorithm=encrypted.get("algorithm", "Kyber1024-AES256GCM"),
            key_id=encrypted.get("metadata", {}).get("key_id", "unknown"),
            key_version=encrypted.get("metadata", {}).get("key_version", 1),
            ciphertext_b64=encrypted.get("ciphertext", ""),
            encrypted_at=datetime.now(timezone.utc).isoformat(),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Encryption failed: {str(e)}")


@router.post("/encrypt-phi")
async def encrypt_phi_fields(
    request: PHIEncryptRequest,
    current_user=Depends(get_current_user),
):
    """
    Encrypt PHI fields in a data dictionary.

    Automatically identifies and encrypts HIPAA-defined PHI fields
    (names, DOB, SSN, MRN, etc.) using post-quantum cryptography.
    Non-PHI fields are left unencrypted.
    """
    try:
        from phoenix_guardian.security.phi_encryption import get_phi_encryption_service

        service = get_phi_encryption_service()
        encrypted_data = service.encrypt_phi_fields(request.data, context=request.context)
        return {"encrypted_data": encrypted_data, "metrics": service.get_metrics()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PHI encryption failed: {str(e)}")


@router.post("/decrypt-phi")
async def decrypt_phi_fields(
    request: PHIEncryptRequest,
    current_user=Depends(get_current_user),
):
    """
    Decrypt PQC-encrypted PHI fields in a data dictionary.

    Automatically detects and decrypts fields marked with the
    '__pqc_encrypted__' envelope marker.
    """
    try:
        from phoenix_guardian.security.phi_encryption import get_phi_encryption_service

        service = get_phi_encryption_service()
        decrypted_data = service.decrypt_phi_fields(request.data, context=request.context)
        return {"decrypted_data": decrypted_data, "metrics": service.get_metrics()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PHI decryption failed: {str(e)}")


@router.post("/rotate-keys", response_model=KeyRotationResponse)
async def rotate_encryption_keys(
    current_user=Depends(get_current_user),
):
    """
    Rotate post-quantum encryption keys.

    Generates a new Kyber-1024 key pair. Previously encrypted data
    can still be decrypted with the old key (stored in key history).

    **Note:** Key rotation should be performed monthly or after
    a suspected security incident.
    """
    try:
        from phoenix_guardian.security.phi_encryption import get_phi_encryption_service
        from datetime import datetime, timezone

        service = get_phi_encryption_service()
        result = service.rotate_keys()

        return KeyRotationResponse(
            old_key_id=result.get("old_key_id", "unknown"),
            new_key_id=result.get("new_key_id", "unknown"),
            old_version=result.get("old_version", 0),
            new_version=result.get("new_version", 1),
            rotated_at=datetime.now(timezone.utc).isoformat(),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Key rotation failed: {str(e)}")


@router.get("/benchmark", response_model=BenchmarkResponse)
async def run_benchmark(
    current_user=Depends(get_current_user),
):
    """
    Run PQC encryption benchmarks.

    Tests encryption/decryption performance across multiple data sizes
    (100B, 1KB, 10KB, 100KB, 1MB) and reports throughput.

    Typical results:
    - 100B:  ~1-2ms encrypt, ~1-2ms decrypt
    - 1KB:   ~1-2ms encrypt, ~1-2ms decrypt
    - 1MB:   ~50-100ms encrypt, ~50-100ms decrypt
    """
    try:
        from phoenix_guardian.security.pqc_encryption import benchmark_encryption

        results = benchmark_encryption()
        return BenchmarkResponse(
            algorithm=results["algorithm"],
            using_simulator=results["using_simulator"],
            results=results["results"],
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Benchmark failed: {str(e)}")


@router.get("/health", response_model=PQCHealthResponse)
async def pqc_health(
    current_user=Depends(get_current_user),
):
    """
    Get post-quantum cryptography system health status.

    Returns information about:
    - Algorithm in use
    - OQS library availability
    - Key status and version
    - Total operations count
    - TLS PQ support status
    """
    try:
        from phoenix_guardian.security.pqc_encryption import (
            is_oqs_available,
            HybridPQCEncryption,
            KEM_ALGORITHM,
        )
        from phoenix_guardian.security.phi_encryption import PQCTLSConfig

        pqc = HybridPQCEncryption()
        tls_config = PQCTLSConfig()

        return PQCHealthResponse(
            status="healthy",
            algorithm=KEM_ALGORITHM,
            oqs_available=is_oqs_available(),
            key_id=pqc.key_id,
            key_version=pqc.key_version,
            total_encryptions=pqc.total_encryptions,
            total_decryptions=pqc.total_decryptions,
            using_simulator=pqc._using_simulator,
            tls_info=tls_config.get_tls_info(),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)}")


@router.get("/algorithms")
async def list_algorithms(
    current_user=Depends(get_current_user),
):
    """
    List supported post-quantum KEM algorithms.
    
    Returns available algorithms from the OQS library or
    simulator mode list.
    """
    try:
        from phoenix_guardian.security.pqc_encryption import get_supported_algorithms

        algorithms = get_supported_algorithms()
        return {
            "algorithms": algorithms,
            "default": "Kyber1024",
            "compliance": "NIST FIPS 203",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed: {str(e)}")
