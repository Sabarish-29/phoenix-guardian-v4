# ADR-008: HashiCorp Vault for Secrets Management

## Status
Accepted

## Date
Day 145 (Phase 3)

## Context

Phoenix Guardian handles sensitive data requiring robust secrets management:
1. Database credentials
2. API keys for external services (EHR systems, AI models)
3. Encryption keys for patient data
4. TLS certificates
5. JWT signing keys

Requirements:
- Dynamic secrets with automatic rotation
- Audit logging of all secret access
- Fine-grained access control
- Encryption as a service
- HIPAA and SOC 2 compliance

## Decision

We will use HashiCorp Vault as our centralized secrets management solution.

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                       Vault Cluster                              │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │                    Vault HA (3 nodes)                      │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │ │
│  │  │   Active     │  │   Standby    │  │   Standby    │     │ │
│  │  │   (leader)   │  │   (follower) │  │   (follower) │     │ │
│  │  └──────────────┘  └──────────────┘  └──────────────┘     │ │
│  │          │                                                  │ │
│  │          ▼                                                  │ │
│  │  ┌────────────────────────────────────────────────────┐   │ │
│  │  │              Integrated Storage (Raft)              │   │ │
│  │  └────────────────────────────────────────────────────┘   │ │
│  └────────────────────────────────────────────────────────────┘ │
│                            │                                     │
│                            │                                     │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │                    Secrets Engines                          │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │ │
│  │  │     KV      │  │  Database   │  │    PKI      │         │ │
│  │  │  (static)   │  │  (dynamic)  │  │   (certs)   │         │ │
│  │  └─────────────┘  └─────────────┘  └─────────────┘         │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │ │
│  │  │   Transit   │  │  AWS/GCP    │  │  Kubernetes │         │ │
│  │  │ (encryption)│  │  (cloud)    │  │   (auth)    │         │ │
│  │  └─────────────┘  └─────────────┘  └─────────────┘         │ │
│  └────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                               │
                               │ Access
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Application Pods                              │
│  ┌─────────────────────┐  ┌─────────────────────┐               │
│  │    API Gateway      │  │  Encounter Service  │               │
│  │  ┌───────────────┐  │  │  ┌───────────────┐  │               │
│  │  │ Vault Sidecar │  │  │  │ Vault Sidecar │  │               │
│  │  │   (injector)  │  │  │  │   (injector)  │  │               │
│  │  └───────────────┘  │  │  └───────────────┘  │               │
│  └─────────────────────┘  └─────────────────────┘               │
└─────────────────────────────────────────────────────────────────┘
```

### Secrets Engine Configuration

```hcl
# Enable KV secrets engine for static secrets
resource "vault_mount" "kv" {
  path        = "phoenix-guardian"
  type        = "kv-v2"
  description = "Phoenix Guardian application secrets"
  options = {
    version = "2"
  }
}

# Enable database secrets engine for dynamic credentials
resource "vault_mount" "database" {
  path        = "database"
  type        = "database"
  description = "Dynamic database credentials"
}

resource "vault_database_secret_backend_connection" "postgres" {
  backend       = vault_mount.database.path
  name          = "phoenix-guardian-db"
  allowed_roles = ["app-role", "readonly-role"]

  postgresql {
    connection_url = "postgresql://{{username}}:{{password}}@postgres.phoenix-guardian.svc:5432/phoenix_guardian"
  }

  root_rotation_statements = [
    "ALTER USER \"{{username}}\" WITH PASSWORD '{{password}}';"
  ]
}

resource "vault_database_secret_backend_role" "app_role" {
  backend             = vault_mount.database.path
  name                = "app-role"
  db_name             = vault_database_secret_backend_connection.postgres.name
  creation_statements = [
    "CREATE ROLE \"{{name}}\" WITH LOGIN PASSWORD '{{password}}' VALID UNTIL '{{expiration}}';",
    "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO \"{{name}}\";"
  ]
  default_ttl = 3600   # 1 hour
  max_ttl     = 86400  # 24 hours
}

# Enable transit engine for encryption
resource "vault_mount" "transit" {
  path        = "transit"
  type        = "transit"
  description = "Encryption as a service"
}

resource "vault_transit_secret_backend_key" "patient_data" {
  backend          = vault_mount.transit.path
  name             = "patient-data"
  type             = "aes256-gcm96"
  deletion_allowed = false
  exportable       = false
  
  auto_rotate_period = "2592000"  # 30 days
}
```

### Kubernetes Authentication

```yaml
# Vault Auth Config
apiVersion: v1
kind: ConfigMap
metadata:
  name: vault-agent-config
data:
  agent-config.hcl: |
    auto_auth {
      method "kubernetes" {
        mount_path = "auth/kubernetes"
        config = {
          role = "phoenix-guardian-app"
        }
      }
      sink "file" {
        config = {
          path = "/vault/token"
        }
      }
    }
    
    template {
      source      = "/vault/templates/secrets.ctmpl"
      destination = "/vault/secrets/config.json"
    }
```

### Policy Configuration

```hcl
# Application policy
path "phoenix-guardian/data/api/*" {
  capabilities = ["read"]
}

path "database/creds/app-role" {
  capabilities = ["read"]
}

path "transit/encrypt/patient-data" {
  capabilities = ["update"]
}

path "transit/decrypt/patient-data" {
  capabilities = ["update"]
}

# Deny access to admin paths
path "sys/*" {
  capabilities = ["deny"]
}

path "auth/*" {
  capabilities = ["deny"]
}
```

### Application Integration

```python
import hvac
from functools import lru_cache

class VaultClient:
    """Vault client for secrets management."""
    
    def __init__(self, vault_addr: str, role: str):
        self.client = hvac.Client(url=vault_addr)
        self._authenticate_kubernetes(role)
        
    def _authenticate_kubernetes(self, role: str):
        """Authenticate using Kubernetes service account."""
        with open('/var/run/secrets/kubernetes.io/serviceaccount/token') as f:
            jwt = f.read()
            
        self.client.auth.kubernetes.login(
            role=role,
            jwt=jwt,
            mount_point='kubernetes'
        )
        
    @lru_cache(maxsize=100)
    def get_secret(self, path: str) -> dict:
        """Get secret from KV store."""
        response = self.client.secrets.kv.v2.read_secret_version(
            path=path,
            mount_point='phoenix-guardian'
        )
        return response['data']['data']
    
    def get_database_credentials(self) -> tuple:
        """Get dynamic database credentials."""
        response = self.client.secrets.database.generate_credentials(
            name='app-role',
            mount_point='database'
        )
        return response['data']['username'], response['data']['password']
    
    def encrypt_patient_data(self, plaintext: bytes) -> str:
        """Encrypt patient data using transit engine."""
        import base64
        encoded = base64.b64encode(plaintext).decode()
        
        response = self.client.secrets.transit.encrypt_data(
            name='patient-data',
            plaintext=encoded,
            mount_point='transit'
        )
        return response['data']['ciphertext']
    
    def decrypt_patient_data(self, ciphertext: str) -> bytes:
        """Decrypt patient data using transit engine."""
        import base64
        
        response = self.client.secrets.transit.decrypt_data(
            name='patient-data',
            ciphertext=ciphertext,
            mount_point='transit'
        )
        return base64.b64decode(response['data']['plaintext'])
```

## Consequences

### Positive

1. **Dynamic secrets** - Database credentials rotate automatically
2. **Audit logging** - All access logged for compliance
3. **Encryption as a service** - Centralized key management
4. **Fine-grained policies** - Least privilege access
5. **Kubernetes native** - Seamless pod authentication
6. **High availability** - Raft-based HA cluster

### Negative

1. **Operational complexity** - Vault cluster management
2. **Learning curve** - Team needs Vault expertise
3. **Dependency** - Applications depend on Vault availability
4. **Unsealing** - Auto-unseal requires cloud KMS
5. **Cost** - Enterprise features require license

### Risks

1. **Vault outage** - Mitigated by HA deployment and local caching
2. **Seal event** - Mitigated by auto-unseal with cloud KMS
3. **Credential leak** - Mitigated by short TTLs and audit logging

## Alternatives Considered

### Kubernetes Secrets

**Pros:**
- Built-in
- Simple
- No additional infrastructure

**Cons:**
- No rotation
- No audit logging
- Base64 encoding (not encryption)
- No dynamic secrets

**Rejected because:** Insufficient security and compliance features.

### AWS Secrets Manager / GCP Secret Manager

**Pros:**
- Managed service
- Rotation support
- Cloud-native

**Cons:**
- Vendor lock-in
- Per-secret pricing
- Less flexible policies

**Rejected because:** Multi-cloud strategy requires portable solution.

### CyberArk Conjur

**Pros:**
- Enterprise features
- Strong security
- PAM integration

**Cons:**
- Complex
- Expensive
- Less Kubernetes-native

**Rejected because:** Vault provides similar features with better Kubernetes integration.

### External Secrets Operator

**Pros:**
- Kubernetes-native
- Multi-provider support
- Good for existing secret stores

**Cons:**
- No dynamic secrets
- No encryption service
- Still needs backend

**Rejected because:** Need full secrets management, not just sync.

## Validation

1. **Dynamic credential testing** - Credentials rotate correctly
2. **Audit log verification** - All access logged
3. **Encryption testing** - Transit engine encrypt/decrypt works
4. **HA failover testing** - Standby promotion works
5. **Policy testing** - Access denied for unauthorized paths

## References

- Vault Documentation: https://developer.hashicorp.com/vault/docs
- Vault Kubernetes Guide: https://developer.hashicorp.com/vault/tutorials/kubernetes
- HIPAA Secrets Management: Internal compliance document
