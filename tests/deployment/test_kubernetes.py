"""
Phoenix Guardian - Kubernetes Manifest Tests
Tests for validating Kubernetes manifests and configuration.
Version: 1.0.0

These tests validate:
- YAML syntax and structure
- Kubernetes resource configuration
- Security requirements
- Resource limits and requests
- High availability configuration
"""

import os
import re
import subprocess
import pytest
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

# ==============================================================================
# Test Configuration
# ==============================================================================

PROJECT_ROOT = Path(__file__).parent.parent.parent
K8S_DIR = PROJECT_ROOT / "k8s"

MANIFEST_FILES = {
    "namespaces": K8S_DIR / "namespaces.yaml",
    "app": K8S_DIR / "app-deployment.yaml",
    "worker": K8S_DIR / "worker-deployment.yaml",
    "beacon": K8S_DIR / "beacon-deployment.yaml",
    "postgres": K8S_DIR / "postgres-statefulset.yaml",
    "redis": K8S_DIR / "redis-deployment.yaml",
    "ingress": K8S_DIR / "ingress.yaml",
    "secrets": K8S_DIR / "secrets.yaml",
    "hpa": K8S_DIR / "hpa.yaml",
}


# ==============================================================================
# Helper Functions
# ==============================================================================

def load_yaml_documents(filepath: Path) -> List[Dict[str, Any]]:
    """Load all YAML documents from a file."""
    if not filepath.exists():
        return []
    
    content = filepath.read_text(encoding="utf-8")
    documents = list(yaml.safe_load_all(content))
    return [doc for doc in documents if doc is not None]


def get_resources_by_kind(documents: List[Dict], kind: str) -> List[Dict]:
    """Filter resources by kind."""
    return [doc for doc in documents if doc.get("kind") == kind]


def kubectl_available() -> bool:
    """Check if kubectl is available AND can connect to a cluster."""
    try:
        # Check kubectl client is available
        client_result = subprocess.run(
            ["kubectl", "version", "--client"],
            capture_output=True,
            timeout=10,
        )
        if client_result.returncode != 0:
            return False
        
        # Check kubectl can connect to a cluster (cluster-info is fast)
        cluster_result = subprocess.run(
            ["kubectl", "cluster-info"],
            capture_output=True,
            timeout=5,
        )
        return cluster_result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def run_kubectl_dry_run(filepath: Path) -> subprocess.CompletedProcess:
    """Run kubectl apply --dry-run on a manifest."""
    try:
        result = subprocess.run(
            ["kubectl", "apply", "--dry-run=client", "--validate=false", "-f", str(filepath)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result
    except subprocess.TimeoutExpired:
        pytest.skip("kubectl command timed out")
    except FileNotFoundError:
        pytest.skip("kubectl not installed")


# ==============================================================================
# Test: Manifest Existence
# ==============================================================================

class TestManifestExistence:
    """Tests for Kubernetes manifest file existence."""

    def test_namespaces_manifest_exists(self):
        """Verify namespaces.yaml exists."""
        assert MANIFEST_FILES["namespaces"].exists(), "namespaces.yaml should exist"

    def test_app_deployment_exists(self):
        """Verify app-deployment.yaml exists."""
        assert MANIFEST_FILES["app"].exists(), "app-deployment.yaml should exist"

    def test_worker_deployment_exists(self):
        """Verify worker-deployment.yaml exists."""
        assert MANIFEST_FILES["worker"].exists(), "worker-deployment.yaml should exist"

    def test_beacon_deployment_exists(self):
        """Verify beacon-deployment.yaml exists."""
        assert MANIFEST_FILES["beacon"].exists(), "beacon-deployment.yaml should exist"

    def test_postgres_statefulset_exists(self):
        """Verify postgres-statefulset.yaml exists."""
        assert MANIFEST_FILES["postgres"].exists(), "postgres-statefulset.yaml should exist"

    def test_redis_deployment_exists(self):
        """Verify redis-deployment.yaml exists."""
        assert MANIFEST_FILES["redis"].exists(), "redis-deployment.yaml should exist"

    def test_ingress_manifest_exists(self):
        """Verify ingress.yaml exists."""
        assert MANIFEST_FILES["ingress"].exists(), "ingress.yaml should exist"

    def test_secrets_manifest_exists(self):
        """Verify secrets.yaml exists."""
        assert MANIFEST_FILES["secrets"].exists(), "secrets.yaml should exist"

    def test_hpa_manifest_exists(self):
        """Verify hpa.yaml exists."""
        assert MANIFEST_FILES["hpa"].exists(), "hpa.yaml should exist"


# ==============================================================================
# Test: YAML Validity
# ==============================================================================

class TestYamlValidity:
    """Tests for YAML syntax validity."""

    @pytest.mark.parametrize("manifest_name", list(MANIFEST_FILES.keys()))
    def test_manifest_is_valid_yaml(self, manifest_name: str):
        """Verify manifest is valid YAML."""
        filepath = MANIFEST_FILES[manifest_name]
        if not filepath.exists():
            pytest.skip(f"{manifest_name} manifest not found")
        
        content = filepath.read_text(encoding="utf-8")
        try:
            documents = list(yaml.safe_load_all(content))
            assert len(documents) > 0, f"{manifest_name} should have at least one document"
        except yaml.YAMLError as e:
            pytest.fail(f"{manifest_name} is not valid YAML: {e}")

    @pytest.mark.parametrize("manifest_name", list(MANIFEST_FILES.keys()))
    def test_manifest_has_api_version(self, manifest_name: str):
        """Verify manifest resources have apiVersion."""
        filepath = MANIFEST_FILES[manifest_name]
        if not filepath.exists():
            pytest.skip(f"{manifest_name} manifest not found")
        
        documents = load_yaml_documents(filepath)
        for doc in documents:
            assert "apiVersion" in doc, f"{manifest_name} resources should have apiVersion"

    @pytest.mark.parametrize("manifest_name", list(MANIFEST_FILES.keys()))
    def test_manifest_has_kind(self, manifest_name: str):
        """Verify manifest resources have kind."""
        filepath = MANIFEST_FILES[manifest_name]
        if not filepath.exists():
            pytest.skip(f"{manifest_name} manifest not found")
        
        documents = load_yaml_documents(filepath)
        for doc in documents:
            assert "kind" in doc, f"{manifest_name} resources should have kind"


# ==============================================================================
# Test: Deployment Configuration
# ==============================================================================

class TestDeploymentConfiguration:
    """Tests for Deployment resource configuration."""

    def test_app_deployment_has_correct_replicas(self):
        """Verify app deployment has at least 3 replicas."""
        documents = load_yaml_documents(MANIFEST_FILES["app"])
        deployments = get_resources_by_kind(documents, "Deployment")
        
        assert len(deployments) > 0, "Should have Deployment resource"
        
        for deployment in deployments:
            replicas = deployment.get("spec", {}).get("replicas", 0)
            assert replicas >= 3, f"App should have at least 3 replicas, got {replicas}"

    def test_worker_deployment_has_correct_replicas(self):
        """Verify worker deployment has at least 2 replicas."""
        documents = load_yaml_documents(MANIFEST_FILES["worker"])
        deployments = get_resources_by_kind(documents, "Deployment")
        
        assert len(deployments) > 0, "Should have Deployment resource"
        
        for deployment in deployments:
            replicas = deployment.get("spec", {}).get("replicas", 0)
            assert replicas >= 2, f"Worker should have at least 2 replicas, got {replicas}"

    def test_beacon_deployment_has_correct_replicas(self):
        """Verify beacon deployment has at least 5 replicas."""
        documents = load_yaml_documents(MANIFEST_FILES["beacon"])
        deployments = get_resources_by_kind(documents, "Deployment")
        
        assert len(deployments) > 0, "Should have Deployment resource"
        
        for deployment in deployments:
            replicas = deployment.get("spec", {}).get("replicas", 0)
            assert replicas >= 5, f"Beacon should have at least 5 replicas, got {replicas}"

    @pytest.mark.parametrize("manifest_name", ["app", "worker", "beacon"])
    def test_deployment_has_rolling_update_strategy(self, manifest_name: str):
        """Verify deployment uses RollingUpdate strategy."""
        filepath = MANIFEST_FILES[manifest_name]
        documents = load_yaml_documents(filepath)
        deployments = get_resources_by_kind(documents, "Deployment")
        
        for deployment in deployments:
            strategy = deployment.get("spec", {}).get("strategy", {})
            strategy_type = strategy.get("type", "RollingUpdate")
            assert strategy_type == "RollingUpdate", \
                f"{manifest_name} should use RollingUpdate strategy"


# ==============================================================================
# Test: Security Configuration
# ==============================================================================

class TestSecurityConfiguration:
    """Tests for Kubernetes security configuration."""

    @pytest.mark.parametrize("manifest_name", ["app", "worker", "beacon"])
    def test_deployment_runs_as_non_root(self, manifest_name: str):
        """Verify deployment runs as non-root user."""
        filepath = MANIFEST_FILES[manifest_name]
        documents = load_yaml_documents(filepath)
        deployments = get_resources_by_kind(documents, "Deployment")
        
        for deployment in deployments:
            pod_spec = deployment.get("spec", {}).get("template", {}).get("spec", {})
            security_context = pod_spec.get("securityContext", {})
            
            assert security_context.get("runAsNonRoot", False) is True, \
                f"{manifest_name} should run as non-root"

    @pytest.mark.parametrize("manifest_name", ["app", "worker", "beacon"])
    def test_deployment_has_service_account(self, manifest_name: str):
        """Verify deployment has service account configured."""
        filepath = MANIFEST_FILES[manifest_name]
        documents = load_yaml_documents(filepath)
        deployments = get_resources_by_kind(documents, "Deployment")
        
        for deployment in deployments:
            pod_spec = deployment.get("spec", {}).get("template", {}).get("spec", {})
            service_account = pod_spec.get("serviceAccountName")
            
            assert service_account is not None, \
                f"{manifest_name} should have serviceAccountName"

    def test_namespace_has_network_policy(self):
        """Verify namespace has NetworkPolicy defined."""
        documents = load_yaml_documents(MANIFEST_FILES["namespaces"])
        network_policies = get_resources_by_kind(documents, "NetworkPolicy")
        
        assert len(network_policies) > 0, "Should have NetworkPolicy resource"

    def test_secrets_uses_sealed_secrets(self):
        """Verify secrets use SealedSecret for encryption."""
        documents = load_yaml_documents(MANIFEST_FILES["secrets"])
        sealed_secrets = get_resources_by_kind(documents, "SealedSecret")
        
        assert len(sealed_secrets) > 0, "Should use SealedSecret resources"


# ==============================================================================
# Test: Resource Limits
# ==============================================================================

class TestResourceLimits:
    """Tests for resource requests and limits."""

    @pytest.mark.parametrize("manifest_name", ["app", "worker", "beacon"])
    def test_deployment_has_resource_requests(self, manifest_name: str):
        """Verify deployment has resource requests."""
        filepath = MANIFEST_FILES[manifest_name]
        documents = load_yaml_documents(filepath)
        deployments = get_resources_by_kind(documents, "Deployment")
        
        for deployment in deployments:
            containers = deployment.get("spec", {}).get("template", {}).get("spec", {}).get("containers", [])
            
            for container in containers:
                resources = container.get("resources", {})
                requests = resources.get("requests", {})
                
                assert "cpu" in requests, f"{manifest_name} container should have CPU request"
                assert "memory" in requests, f"{manifest_name} container should have memory request"

    @pytest.mark.parametrize("manifest_name", ["app", "worker", "beacon"])
    def test_deployment_has_resource_limits(self, manifest_name: str):
        """Verify deployment has resource limits."""
        filepath = MANIFEST_FILES[manifest_name]
        documents = load_yaml_documents(filepath)
        deployments = get_resources_by_kind(documents, "Deployment")
        
        for deployment in deployments:
            containers = deployment.get("spec", {}).get("template", {}).get("spec", {}).get("containers", [])
            
            for container in containers:
                resources = container.get("resources", {})
                limits = resources.get("limits", {})
                
                assert "cpu" in limits, f"{manifest_name} container should have CPU limit"
                assert "memory" in limits, f"{manifest_name} container should have memory limit"


# ==============================================================================
# Test: Health Probes
# ==============================================================================

class TestHealthProbes:
    """Tests for liveness and readiness probes."""

    @pytest.mark.parametrize("manifest_name", ["app", "beacon"])
    def test_deployment_has_readiness_probe(self, manifest_name: str):
        """Verify deployment has readiness probe."""
        filepath = MANIFEST_FILES[manifest_name]
        documents = load_yaml_documents(filepath)
        deployments = get_resources_by_kind(documents, "Deployment")
        
        for deployment in deployments:
            containers = deployment.get("spec", {}).get("template", {}).get("spec", {}).get("containers", [])
            
            for container in containers:
                assert "readinessProbe" in container, \
                    f"{manifest_name} container should have readinessProbe"

    @pytest.mark.parametrize("manifest_name", ["app", "beacon"])
    def test_deployment_has_liveness_probe(self, manifest_name: str):
        """Verify deployment has liveness probe."""
        filepath = MANIFEST_FILES[manifest_name]
        documents = load_yaml_documents(filepath)
        deployments = get_resources_by_kind(documents, "Deployment")
        
        for deployment in deployments:
            containers = deployment.get("spec", {}).get("template", {}).get("spec", {}).get("containers", [])
            
            for container in containers:
                assert "livenessProbe" in container, \
                    f"{manifest_name} container should have livenessProbe"


# ==============================================================================
# Test: StatefulSet Configuration
# ==============================================================================

class TestStatefulSetConfiguration:
    """Tests for StatefulSet configuration (PostgreSQL)."""

    def test_postgres_uses_statefulset(self):
        """Verify PostgreSQL uses StatefulSet, not Deployment."""
        documents = load_yaml_documents(MANIFEST_FILES["postgres"])
        statefulsets = get_resources_by_kind(documents, "StatefulSet")
        deployments = get_resources_by_kind(documents, "Deployment")
        
        assert len(statefulsets) > 0, "PostgreSQL should use StatefulSet"
        # Deployments for Postgres should not exist (except for related services)
        postgres_deployments = [d for d in deployments if "postgres" in d.get("metadata", {}).get("name", "").lower()]
        assert len(postgres_deployments) == 0, "PostgreSQL should not use Deployment"

    def test_postgres_has_volume_claim_templates(self):
        """Verify PostgreSQL StatefulSet has volumeClaimTemplates."""
        documents = load_yaml_documents(MANIFEST_FILES["postgres"])
        statefulsets = get_resources_by_kind(documents, "StatefulSet")
        
        for statefulset in statefulsets:
            vct = statefulset.get("spec", {}).get("volumeClaimTemplates", [])
            assert len(vct) > 0, "PostgreSQL should have volumeClaimTemplates"

    def test_postgres_has_headless_service(self):
        """Verify PostgreSQL has headless service for stable network identity."""
        documents = load_yaml_documents(MANIFEST_FILES["postgres"])
        services = get_resources_by_kind(documents, "Service")
        
        headless_services = [
            s for s in services 
            if s.get("spec", {}).get("clusterIP") == "None"
        ]
        
        assert len(headless_services) > 0, "PostgreSQL should have headless service"

    def test_postgres_has_multiple_replicas(self):
        """Verify PostgreSQL has multiple replicas for HA."""
        documents = load_yaml_documents(MANIFEST_FILES["postgres"])
        statefulsets = get_resources_by_kind(documents, "StatefulSet")
        
        for statefulset in statefulsets:
            replicas = statefulset.get("spec", {}).get("replicas", 0)
            assert replicas >= 3, f"PostgreSQL should have 3+ replicas for HA, got {replicas}"


# ==============================================================================
# Test: HPA Configuration
# ==============================================================================

class TestHPAConfiguration:
    """Tests for Horizontal Pod Autoscaler configuration."""

    def test_hpa_exists_for_app(self):
        """Verify HPA exists for app deployment."""
        documents = load_yaml_documents(MANIFEST_FILES["hpa"])
        hpas = get_resources_by_kind(documents, "HorizontalPodAutoscaler")
        
        app_hpas = [h for h in hpas if "app" in h.get("metadata", {}).get("name", "").lower()]
        assert len(app_hpas) > 0, "Should have HPA for app"

    def test_hpa_has_min_replicas(self):
        """Verify HPA has minReplicas set."""
        documents = load_yaml_documents(MANIFEST_FILES["hpa"])
        hpas = get_resources_by_kind(documents, "HorizontalPodAutoscaler")
        
        for hpa in hpas:
            min_replicas = hpa.get("spec", {}).get("minReplicas", 0)
            assert min_replicas >= 2, "HPA should have minReplicas >= 2"

    def test_hpa_has_max_replicas(self):
        """Verify HPA has maxReplicas set."""
        documents = load_yaml_documents(MANIFEST_FILES["hpa"])
        hpas = get_resources_by_kind(documents, "HorizontalPodAutoscaler")
        
        for hpa in hpas:
            max_replicas = hpa.get("spec", {}).get("maxReplicas", 0)
            assert max_replicas >= 5, "HPA should have maxReplicas >= 5"


# ==============================================================================
# Test: Ingress Configuration
# ==============================================================================

class TestIngressConfiguration:
    """Tests for Ingress configuration."""

    def test_ingress_has_tls(self):
        """Verify Ingress has TLS configuration."""
        documents = load_yaml_documents(MANIFEST_FILES["ingress"])
        ingresses = get_resources_by_kind(documents, "Ingress")
        
        for ingress in ingresses:
            tls = ingress.get("spec", {}).get("tls", [])
            assert len(tls) > 0, "Ingress should have TLS configuration"

    def test_ingress_has_hosts(self):
        """Verify Ingress has host rules."""
        documents = load_yaml_documents(MANIFEST_FILES["ingress"])
        ingresses = get_resources_by_kind(documents, "Ingress")
        
        for ingress in ingresses:
            rules = ingress.get("spec", {}).get("rules", [])
            assert len(rules) > 0, "Ingress should have host rules"

    def test_ingress_has_security_annotations(self):
        """Verify Ingress has security-related annotations."""
        documents = load_yaml_documents(MANIFEST_FILES["ingress"])
        ingresses = get_resources_by_kind(documents, "Ingress")
        
        for ingress in ingresses:
            annotations = ingress.get("metadata", {}).get("annotations", {})
            
            # Check for SSL redirect annotation
            ssl_redirect_keys = [k for k in annotations.keys() if "ssl-redirect" in k.lower()]
            assert len(ssl_redirect_keys) > 0, "Ingress should have SSL redirect annotation"


# ==============================================================================
# Test: Labels and Selectors
# ==============================================================================

class TestLabelsAndSelectors:
    """Tests for Kubernetes labels and selectors."""

    @pytest.mark.parametrize("manifest_name", ["app", "worker", "beacon"])
    def test_deployment_has_standard_labels(self, manifest_name: str):
        """Verify deployment has standard Kubernetes labels."""
        filepath = MANIFEST_FILES[manifest_name]
        documents = load_yaml_documents(filepath)
        deployments = get_resources_by_kind(documents, "Deployment")
        
        for deployment in deployments:
            labels = deployment.get("metadata", {}).get("labels", {})
            
            assert "app.kubernetes.io/name" in labels, \
                f"{manifest_name} should have app.kubernetes.io/name label"
            assert "app.kubernetes.io/component" in labels, \
                f"{manifest_name} should have app.kubernetes.io/component label"

    @pytest.mark.parametrize("manifest_name", ["app", "worker", "beacon"])
    def test_deployment_selector_matches_template(self, manifest_name: str):
        """Verify deployment selector matches pod template labels."""
        filepath = MANIFEST_FILES[manifest_name]
        documents = load_yaml_documents(filepath)
        deployments = get_resources_by_kind(documents, "Deployment")
        
        for deployment in deployments:
            selector_labels = deployment.get("spec", {}).get("selector", {}).get("matchLabels", {})
            template_labels = deployment.get("spec", {}).get("template", {}).get("metadata", {}).get("labels", {})
            
            for key, value in selector_labels.items():
                assert key in template_labels, \
                    f"Selector label {key} should exist in template"
                assert template_labels[key] == value, \
                    f"Selector label {key} should match template"


# ==============================================================================
# Test: kubectl Validation (Integration)
# ==============================================================================

@pytest.mark.skipif(not kubectl_available(), reason="kubectl not available")
class TestKubectlValidation:
    """Integration tests using kubectl dry-run."""

    @pytest.mark.parametrize("manifest_name", list(MANIFEST_FILES.keys()))
    def test_manifest_passes_kubectl_dry_run(self, manifest_name: str):
        """Verify manifest passes kubectl apply --dry-run."""
        filepath = MANIFEST_FILES[manifest_name]
        if not filepath.exists():
            pytest.skip(f"{manifest_name} manifest not found")
        
        result = run_kubectl_dry_run(filepath)
        
        # Allow warnings but not errors
        assert result.returncode == 0, \
            f"{manifest_name} failed kubectl dry-run: {result.stderr}"
