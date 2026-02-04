"""
Phoenix Guardian Integrations Module.

This module provides integration capabilities including:
- Electronic Health Record (EHR) systems through FHIR R4
- SMTP email alerts
- Slack webhook notifications
- GeoIP geolocation

Main Components:
- FHIRClient: Unified FHIR R4 client for EHR systems
- EpicConnector: Epic-specific connector with OAuth 2.0 JWT authentication
- CernerConnector: Cerner-specific connector with OAuth 2.0 client credentials
- SMTPEmailClient: Production email client with retry logic
- SlackClient: Slack webhook integration
- GeoIPClient: IP geolocation using MaxMind

Usage:
    from phoenix_guardian.integrations import FHIRClient, FHIRConfig

    config = FHIRConfig(
        base_url="https://fhir.epic.com/api/FHIR/R4/",
        client_id="your-client-id",
        access_token="your-token"
    )

    client = FHIRClient(config)
    patient = client.get_patient("12345")

Epic Usage:
    from phoenix_guardian.integrations import EpicConnector, EpicConfig

    config = EpicConfig(client_id="test", use_sandbox=True)
    with EpicConnector(config) as epic:
        patient = epic.get_patient(epic.get_sandbox_test_patients()[0])

Cerner Usage:
    from phoenix_guardian.integrations import CernerConnector, create_cerner_sandbox_connector

    with create_cerner_sandbox_connector() as cerner:
        patient = cerner.get_patient("12724066")  # Smart, Nancy
"""

from .fhir_client import (
    # Main Client
    FHIRClient,

    # Configuration
    FHIRConfig,

    # Patient Resources
    FHIRPatient,
    FHIRObservation,
    FHIRCondition,
    FHIRMedicationRequest,
    FHIRDocumentReference,
    FHIRDiagnosticReport,
    FHIRBundle,

    # Enums
    FHIRResourceType,
    ObservationStatus,
    ObservationCategory,
    ConditionClinicalStatus,
    ConditionVerificationStatus,
    MedicationRequestStatus,
    DocumentReferenceStatus,

    # Constants
    LOINCCodes,

    # Exceptions
    FHIRError,
    FHIRAuthenticationError,
    FHIRNotFoundError,
    FHIRValidationError,
    FHIRPermissionError,
    FHIRServerError,
    FHIRConnectionError,
)

from .epic_connector import (
    # Epic Connector
    EpicConnector,
    EpicConfig,
    EpicTokenResponse,
    EpicEnvironment,

    # Epic Constants
    EPIC_SANDBOX_TEST_PATIENTS,
    EPIC_SANDBOX_BASE_URL,
    EPIC_SANDBOX_TOKEN_URL,
    EPIC_IDENTIFIER_SYSTEMS,
    EPIC_SCOPES,

    # Epic Exceptions
    EpicError,
    EpicAuthenticationError,
    EpicConnectionError,
    EpicConfigurationError,

    # Factory Functions
    create_epic_sandbox_connector,
    create_epic_production_connector,
)

from .cerner_connector import (
    # Cerner Connector
    CernerConnector,
    CernerConfig,
    CernerTokenResponse,
    CernerEnvironment,

    # Cerner Constants
    CERNER_SANDBOX_TENANT_ID,
    CERNER_SANDBOX_BASE_URL,
    CERNER_SANDBOX_TEST_PATIENTS,
    CERNER_IDENTIFIER_SYSTEMS,
    CERNER_DEFAULT_SCOPES,
    CERNER_WRITE_SCOPES,

    # Cerner Exceptions
    CernerError,
    CernerAuthenticationError,
    CernerConnectionError,
    CernerConfigurationError,
    CernerResourceNotFoundError,

    # Factory Functions
    create_cerner_sandbox_connector,
    create_cerner_production_connector,
)

from .base_connector import (
    # Base Classes
    BaseOAuthConnector,
    BaseConnectorConfig,
    TokenResponse,

    # Exceptions
    ConnectorError,
    AuthenticationError,
    ConfigurationError,
    ResourceNotFoundError,

    # Decorators
    handle_fhir_errors,
    retry_on_failure,
    require_connection,

    # Utilities
    parse_oauth_error_response,
)


__all__ = [
    # FHIR Client
    "FHIRClient",
    "FHIRConfig",

    # FHIR Resources
    "FHIRPatient",
    "FHIRObservation",
    "FHIRCondition",
    "FHIRMedicationRequest",
    "FHIRDocumentReference",
    "FHIRDiagnosticReport",
    "FHIRBundle",

    # FHIR Enums
    "FHIRResourceType",
    "ObservationStatus",
    "ObservationCategory",
    "ConditionClinicalStatus",
    "ConditionVerificationStatus",
    "MedicationRequestStatus",
    "DocumentReferenceStatus",

    # FHIR Constants
    "LOINCCodes",

    # FHIR Exceptions
    "FHIRError",
    "FHIRAuthenticationError",
    "FHIRNotFoundError",
    "FHIRValidationError",
    "FHIRPermissionError",
    "FHIRServerError",
    "FHIRConnectionError",

    # Epic Connector
    "EpicConnector",
    "EpicConfig",
    "EpicTokenResponse",
    "EpicEnvironment",

    # Epic Constants
    "EPIC_SANDBOX_TEST_PATIENTS",
    "EPIC_SANDBOX_BASE_URL",
    "EPIC_SANDBOX_TOKEN_URL",
    "EPIC_IDENTIFIER_SYSTEMS",
    "EPIC_SCOPES",

    # Epic Exceptions
    "EpicError",
    "EpicAuthenticationError",
    "EpicConnectionError",
    "EpicConfigurationError",

    # Epic Factory Functions
    "create_epic_sandbox_connector",
    "create_epic_production_connector",

    # Cerner Connector
    "CernerConnector",
    "CernerConfig",
    "CernerTokenResponse",
    "CernerEnvironment",

    # Cerner Constants
    "CERNER_SANDBOX_TENANT_ID",
    "CERNER_SANDBOX_BASE_URL",
    "CERNER_SANDBOX_TEST_PATIENTS",
    "CERNER_IDENTIFIER_SYSTEMS",
    "CERNER_DEFAULT_SCOPES",
    "CERNER_WRITE_SCOPES",

    # Cerner Exceptions
    "CernerError",
    "CernerAuthenticationError",
    "CernerConnectionError",
    "CernerConfigurationError",
    "CernerResourceNotFoundError",

    # Cerner Factory Functions
    "create_cerner_sandbox_connector",
    "create_cerner_production_connector",

    # Base Connector
    "BaseOAuthConnector",
    "BaseConnectorConfig",
    "TokenResponse",

    # Base Exceptions
    "ConnectorError",
    "AuthenticationError",
    "ConfigurationError",
    "ResourceNotFoundError",

    # Decorators
    "handle_fhir_errors",
    "retry_on_failure",
    "require_connection",

    # Utilities
    "parse_oauth_error_response",
    
    # SMTP Email Client
    "SMTPEmailClient",
    "EmailMessage",
    "EmailResult",
    
    # Slack Client
    "SlackClient",
    "SlackMessage",
    "SlackResult",
    
    # GeoIP Client
    "GeoIPClient",
    "GeoLocation",
]

# Import new integration clients
try:
    from .smtp_client import SMTPEmailClient, EmailMessage, EmailResult
except ImportError:
    pass

try:
    from .slack_client import SlackClient, SlackMessage, SlackResult
except ImportError:
    pass

try:
    from .geoip_client import GeoIPClient, GeoLocation
except ImportError:
    pass
