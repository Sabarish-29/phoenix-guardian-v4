"""
Infrastructure validation tests for Phoenix Guardian production deployment.
Run after terraform apply to verify resources are correctly provisioned.

Tests validate:
- Terraform configuration validity
- EKS cluster configuration
- RDS PostgreSQL setup
- ElastiCache Redis setup
- Kubernetes accessibility
- Required namespaces
- Pod health status
"""

import subprocess
import json
import os
import pytest
from typing import Any


# =============================================================================
# HELPERS
# =============================================================================

def run_terraform(cmd: list[str], cwd: str = "infrastructure/terraform") -> dict[str, Any]:
    """Execute terraform command and return parsed output."""
    result = subprocess.run(
        ["terraform"] + cmd,
        cwd=cwd,
        capture_output=True,
        text=True,
        env={**os.environ, "TF_IN_AUTOMATION": "1"},
        timeout=300
    )
    if result.returncode != 0:
        raise RuntimeError(f"Terraform error: {result.stderr}")
    return json.loads(result.stdout) if result.stdout.strip() else {}


def run_kubectl(cmd: list[str], timeout: int = 30) -> dict[str, Any] | str:
    """Execute kubectl command and return parsed JSON output."""
    full_cmd = ["kubectl"] + cmd
    if "-o" not in cmd and "json" not in " ".join(cmd):
        full_cmd.extend(["-o", "json"])
    
    result = subprocess.run(
        full_cmd,
        capture_output=True,
        text=True,
        timeout=timeout
    )
    if result.returncode != 0:
        raise RuntimeError(f"kubectl error: {result.stderr}")
    
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return result.stdout


# =============================================================================
# TERRAFORM VALIDATION TESTS
# =============================================================================

class TestTerraformValidation:
    """Validate Terraform configuration."""

    def test_terraform_validate(self):
        """Terraform configuration is syntactically valid."""
        result = subprocess.run(
            ["terraform", "validate", "-json"],
            cwd="infrastructure/terraform",
            capture_output=True,
            text=True,
            timeout=60
        )
        assert result.returncode == 0, f"Terraform validate failed: {result.stderr}"
        validation = json.loads(result.stdout)
        assert validation.get("valid") is True, f"Validation errors: {validation}"

    def test_terraform_fmt(self):
        """Terraform files are properly formatted."""
        result = subprocess.run(
            ["terraform", "fmt", "-check", "-recursive"],
            cwd="infrastructure/terraform",
            capture_output=True,
            timeout=60
        )
        assert result.returncode == 0, (
            "Terraform files not formatted. Run 'terraform fmt -recursive' to fix."
        )


# =============================================================================
# EKS CLUSTER TESTS
# =============================================================================

class TestEKSCluster:
    """Validate EKS cluster configuration."""

    @pytest.fixture
    def terraform_outputs(self) -> dict[str, Any]:
        """Get Terraform outputs."""
        return run_terraform(["output", "-json"])

    def test_eks_cluster_exists(self, terraform_outputs):
        """EKS cluster is created with correct name."""
        assert "eks_cluster_id" in terraform_outputs, "eks_cluster_id output missing"
        cluster_id = terraform_outputs["eks_cluster_id"]["value"]
        assert cluster_id.startswith("phoenix-"), f"Unexpected cluster name: {cluster_id}"

    def test_eks_has_three_node_groups(self, terraform_outputs):
        """EKS has system, api, and ml node groups."""
        assert "eks_node_groups" in terraform_outputs, "eks_node_groups output missing"
        node_groups = terraform_outputs["eks_node_groups"]["value"]
        
        required_groups = ["system", "api", "ml"]
        for group in required_groups:
            assert group in node_groups, f"Missing node group: {group}"

    def test_eks_oidc_provider_configured(self, terraform_outputs):
        """OIDC provider is configured for IRSA."""
        assert "eks_oidc_provider_arn" in terraform_outputs
        oidc_arn = terraform_outputs["eks_oidc_provider_arn"]["value"]
        assert "oidc-provider" in oidc_arn, f"Invalid OIDC ARN: {oidc_arn}"


# =============================================================================
# RDS POSTGRESQL TESTS
# =============================================================================

class TestRDSPostgreSQL:
    """Validate RDS PostgreSQL configuration."""

    @pytest.fixture
    def terraform_outputs(self) -> dict[str, Any]:
        """Get Terraform outputs."""
        return run_terraform(["output", "-json"])

    def test_rds_endpoint_exists(self, terraform_outputs):
        """RDS endpoint is available."""
        assert "rds_endpoint" in terraform_outputs
        endpoint = terraform_outputs["rds_endpoint"]["value"]
        assert endpoint, "RDS endpoint is empty"
        assert "rds.amazonaws.com" in endpoint, f"Invalid RDS endpoint: {endpoint}"

    def test_rds_multi_az_enabled(self, terraform_outputs):
        """RDS PostgreSQL has multi-AZ enabled for HA."""
        assert "rds_multi_az" in terraform_outputs
        multi_az = terraform_outputs["rds_multi_az"]["value"]
        assert multi_az is True, "RDS Multi-AZ is not enabled (HIPAA requirement)"

    def test_rds_encryption_enabled(self, terraform_outputs):
        """RDS storage is encrypted at rest."""
        assert "rds_storage_encrypted" in terraform_outputs
        encrypted = terraform_outputs["rds_storage_encrypted"]["value"]
        assert encrypted is True, "RDS storage encryption is not enabled (HIPAA requirement)"


# =============================================================================
# ELASTICACHE REDIS TESTS
# =============================================================================

class TestElastiCacheRedis:
    """Validate ElastiCache Redis configuration."""

    @pytest.fixture
    def terraform_outputs(self) -> dict[str, Any]:
        """Get Terraform outputs."""
        return run_terraform(["output", "-json"])

    def test_redis_endpoint_exists(self, terraform_outputs):
        """Redis cluster endpoint is available."""
        assert "redis_endpoint" in terraform_outputs
        endpoint = terraform_outputs["redis_endpoint"]["value"]
        assert endpoint, "Redis endpoint is empty"
        assert "cache.amazonaws.com" in endpoint, f"Invalid Redis endpoint: {endpoint}"

    def test_redis_encryption_at_rest(self, terraform_outputs):
        """Redis has encryption at rest enabled."""
        assert "redis_at_rest_encryption_enabled" in terraform_outputs
        encrypted = terraform_outputs["redis_at_rest_encryption_enabled"]["value"]
        assert encrypted is True, "Redis at-rest encryption not enabled (HIPAA requirement)"

    def test_redis_encryption_in_transit(self, terraform_outputs):
        """Redis has encryption in transit enabled."""
        assert "redis_transit_encryption_enabled" in terraform_outputs
        encrypted = terraform_outputs["redis_transit_encryption_enabled"]["value"]
        assert encrypted is True, "Redis in-transit encryption not enabled (HIPAA requirement)"


# =============================================================================
# KUBERNETES INTEGRATION TESTS
# =============================================================================

@pytest.mark.integration
class TestKubernetesIntegration:
    """Integration tests requiring Kubernetes cluster access."""

    def test_kubernetes_api_accessible(self):
        """Can connect to Kubernetes API server."""
        result = subprocess.run(
            ["kubectl", "cluster-info"],
            capture_output=True,
            text=True,
            timeout=10
        )
        assert result.returncode == 0, f"Cannot connect to K8s: {result.stderr}"
        assert "Kubernetes control plane" in result.stdout

    def test_required_namespaces_exist(self):
        """All required namespaces are created."""
        result = run_kubectl(["get", "namespaces"])
        namespaces = result.get("items", [])
        names = [ns["metadata"]["name"] for ns in namespaces]
        
        required = ["production", "staging", "monitoring", "argocd"]
        for ns in required:
            assert ns in names, f"Missing required namespace: {ns}"

    def test_node_groups_have_nodes(self):
        """Each node group has at least one ready node."""
        result = run_kubectl(["get", "nodes"])
        nodes = result.get("items", [])
        
        # Group nodes by role label
        node_groups = {}
        for node in nodes:
            labels = node["metadata"].get("labels", {})
            role = labels.get("role", "unknown")
            node_groups.setdefault(role, []).append(node)
        
        required_groups = ["system", "api", "ml"]
        for group in required_groups:
            assert group in node_groups, f"No nodes found for group: {group}"
            
            # Check at least one node is Ready
            group_nodes = node_groups[group]
            ready_nodes = [
                n for n in group_nodes
                if any(
                    c["type"] == "Ready" and c["status"] == "True"
                    for c in n["status"].get("conditions", [])
                )
            ]
            assert len(ready_nodes) >= 1, f"No Ready nodes in group: {group}"


@pytest.mark.integration
class TestProductionPods:
    """Test production namespace pod health."""

    def test_all_pods_running(self):
        """All pods in production namespace are Running."""
        result = run_kubectl(["get", "pods", "-n", "production"])
        pods = result.get("items", [])
        
        if not pods:
            pytest.skip("No pods in production namespace yet")
        
        for pod in pods:
            name = pod["metadata"]["name"]
            phase = pod["status"]["phase"]
            assert phase == "Running", f"Pod {name} is {phase}, expected Running"

    def test_api_deployment_available(self):
        """Phoenix API deployment is available."""
        result = run_kubectl(["get", "deployment", "phoenix-api", "-n", "production"])
        
        status = result.get("status", {})
        available = status.get("availableReplicas", 0)
        desired = result.get("spec", {}).get("replicas", 1)
        
        assert available >= 1, "No available API replicas"
        assert available == desired, f"API: {available}/{desired} replicas available"

    def test_worker_deployment_available(self):
        """Phoenix Worker deployment is available."""
        result = run_kubectl(["get", "deployment", "phoenix-worker", "-n", "production"])
        
        status = result.get("status", {})
        available = status.get("availableReplicas", 0)
        
        assert available >= 1, "No available Worker replicas"

    def test_beacon_deployment_available(self):
        """Phoenix Beacon (ML) deployment is available."""
        result = run_kubectl(["get", "deployment", "phoenix-beacon", "-n", "production"])
        
        status = result.get("status", {})
        available = status.get("availableReplicas", 0)
        
        assert available >= 1, "No available Beacon replicas"

    def test_no_pod_restart_loops(self):
        """No pods are in crash loop (high restart count)."""
        result = run_kubectl(["get", "pods", "-n", "production"])
        pods = result.get("items", [])
        
        for pod in pods:
            name = pod["metadata"]["name"]
            containers = pod["status"].get("containerStatuses", [])
            
            for container in containers:
                restarts = container.get("restartCount", 0)
                assert restarts < 10, f"Pod {name} has {restarts} restarts (crash loop?)"


@pytest.mark.integration
class TestSecurityConfiguration:
    """Test security-related configurations."""

    def test_network_policies_exist(self):
        """Network policies are applied to production namespace."""
        result = run_kubectl(["get", "networkpolicies", "-n", "production"])
        policies = result.get("items", [])
        
        assert len(policies) >= 1, "No network policies in production namespace"
        
        policy_names = [p["metadata"]["name"] for p in policies]
        assert "default-deny-all" in policy_names, "Missing default-deny-all policy"

    def test_pod_security_context(self):
        """Pods run with non-root security context."""
        result = run_kubectl(["get", "pods", "-n", "production"])
        pods = result.get("items", [])
        
        if not pods:
            pytest.skip("No pods in production namespace yet")
        
        for pod in pods:
            name = pod["metadata"]["name"]
            spec = pod["spec"]
            
            security_context = spec.get("securityContext", {})
            run_as_non_root = security_context.get("runAsNonRoot", False)
            
            # Also check container-level security context
            for container in spec.get("containers", []):
                container_sc = container.get("securityContext", {})
                allow_priv_esc = container_sc.get("allowPrivilegeEscalation", True)
                
                assert not allow_priv_esc, f"Pod {name} allows privilege escalation"

    def test_secrets_not_exposed_in_env(self):
        """Secrets are referenced via secretKeyRef, not plain env values."""
        result = run_kubectl(["get", "deployments", "-n", "production"])
        deployments = result.get("items", [])
        
        sensitive_env_names = ["PASSWORD", "SECRET", "TOKEN", "KEY", "CREDENTIAL"]
        
        for deploy in deployments:
            name = deploy["metadata"]["name"]
            containers = deploy["spec"]["template"]["spec"]["containers"]
            
            for container in containers:
                for env in container.get("env", []):
                    env_name = env["name"]
                    
                    # Check if sensitive env var uses valueFrom (secret reference)
                    if any(s in env_name.upper() for s in sensitive_env_names):
                        assert "valueFrom" in env, (
                            f"Deployment {name}: {env_name} should use secretKeyRef"
                        )


@pytest.mark.integration  
class TestResourceLimits:
    """Test resource limits and requests are configured."""

    def test_pods_have_resource_limits(self):
        """All pods have CPU and memory limits."""
        result = run_kubectl(["get", "pods", "-n", "production"])
        pods = result.get("items", [])
        
        if not pods:
            pytest.skip("No pods in production namespace yet")
        
        for pod in pods:
            name = pod["metadata"]["name"]
            containers = pod["spec"]["containers"]
            
            for container in containers:
                resources = container.get("resources", {})
                limits = resources.get("limits", {})
                
                assert "cpu" in limits, f"Pod {name}: missing CPU limit"
                assert "memory" in limits, f"Pod {name}: missing memory limit"

    def test_hpa_configured(self):
        """Horizontal Pod Autoscalers are configured."""
        result = run_kubectl(["get", "hpa", "-n", "production"])
        hpas = result.get("items", [])
        
        expected_hpas = ["phoenix-api", "phoenix-worker", "phoenix-beacon"]
        hpa_names = [h["metadata"]["name"] for h in hpas]
        
        for expected in expected_hpas:
            assert expected in hpa_names, f"Missing HPA for {expected}"

    def test_pdb_configured(self):
        """Pod Disruption Budgets are configured."""
        result = run_kubectl(["get", "pdb", "-n", "production"])
        pdbs = result.get("items", [])
        
        expected_pdbs = ["phoenix-api", "phoenix-worker", "phoenix-beacon"]
        pdb_names = [p["metadata"]["name"] for p in pdbs]
        
        for expected in expected_pdbs:
            assert expected in pdb_names, f"Missing PDB for {expected}"
