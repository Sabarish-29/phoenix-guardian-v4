"""
Federated Learning module for Phoenix Guardian.

Privacy-preserving threat intelligence sharing across hospitals.
This module implements differential privacy mechanisms to enable
collaborative threat detection without exposing sensitive hospital data.

Key Components:
    - DifferentialPrivacyEngine: Core DP mechanisms (Laplace, Gaussian)
    - ThreatSignatureGenerator: Create anonymized attack signatures
    - SecureAggregator: Merge signatures from multiple hospitals
    - ModelDistributor: Distribute updated models to hospitals

Privacy Guarantees:
    - ε (epsilon) = 0.5 (strong privacy)
    - δ (delta) = 1e-5 (extremely low failure probability)
    - k-anonymity: Each signature from ≥2 hospitals
"""

from phoenix_guardian.federated.differential_privacy import (
    DifferentialPrivacyEngine,
    PrivacyBudget,
    PrivacyMetadata,
    PrivacyAccountant,
)
from phoenix_guardian.federated.threat_signature import (
    ThreatSignature,
    ThreatSignatureGenerator,
)
from phoenix_guardian.federated.secure_aggregator import (
    SecureAggregator,
    AggregatedSignature,
)
from phoenix_guardian.federated.model_distributor import (
    ModelDistributor,
    ModelVersion,
)
from phoenix_guardian.federated.privacy_validator import (
    PrivacyValidator,
)
from phoenix_guardian.federated.attack_pattern_extractor import (
    AttackPatternExtractor,
)
from phoenix_guardian.federated.contribution_pipeline import (
    ContributionPipeline,
)
from phoenix_guardian.federated.global_model_builder import (
    GlobalModelBuilder,
)
from phoenix_guardian.federated.privacy_auditor import (
    PrivacyAuditor,
)

__all__ = [
    # Core Privacy
    "DifferentialPrivacyEngine",
    "PrivacyBudget",
    "PrivacyMetadata",
    "PrivacyAccountant",
    # Threat Signatures
    "ThreatSignature",
    "ThreatSignatureGenerator",
    # Aggregation
    "SecureAggregator",
    "AggregatedSignature",
    # Distribution
    "ModelDistributor",
    "ModelVersion",
    # Validation
    "PrivacyValidator",
    "PrivacyAuditor",
    # Extraction
    "AttackPatternExtractor",
    # Pipeline
    "ContributionPipeline",
    "GlobalModelBuilder",
]

__version__ = "1.0.0"
