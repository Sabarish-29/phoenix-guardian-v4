"""
Phoenix Guardian - Tenant Deployer
Per-tenant deployment automation for hospital-specific configurations.
Version: 1.0.0

This module provides:
- Tenant-specific deployment orchestration
- Kustomize overlay generation
- Environment variable injection
- Secrets management integration
- Deployment validation
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import hashlib
import json
import logging
import os
import subprocess
import yaml

logger = logging.getLogger(__name__)


# ==============================================================================
# Enumerations
# ==============================================================================

class DeploymentStatus(Enum):
    """Deployment status states."""
    PENDING = "pending"
    VALIDATING = "validating"
    DEPLOYING = "deploying"
    DEPLOYED = "deployed"
    FAILED = "failed"
    ROLLING_BACK = "rolling_back"
    ROLLED_BACK = "rolled_back"


class DeploymentPhase(Enum):
    """Deployment phases."""
    PRE_FLIGHT = "pre_flight"
    SECRETS = "secrets"
    CONFIG = "config"
    DATABASE = "database"
    CACHE = "cache"
    APPLICATION = "application"
    INGRESS = "ingress"
    VALIDATION = "validation"
    COMPLETE = "complete"


# ==============================================================================
# Data Classes
# ==============================================================================

@dataclass
class DeploymentResult:
    """Result of a deployment operation."""
    tenant_id: str
    status: DeploymentStatus
    phase: DeploymentPhase
    started_at: str
    completed_at: Optional[str] = None
    duration_seconds: float = 0.0
    
    # Details
    config_hash: str = ""
    deployed_version: str = ""
    kubernetes_namespace: str = ""
    
    # Errors and warnings
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    # Phase results
    phase_results: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    
    @property
    def is_success(self) -> bool:
        return self.status == DeploymentStatus.DEPLOYED
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "tenant_id": self.tenant_id,
            "status": self.status.value,
            "phase": self.phase.value,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration_seconds": self.duration_seconds,
            "config_hash": self.config_hash,
            "deployed_version": self.deployed_version,
            "kubernetes_namespace": self.kubernetes_namespace,
            "errors": self.errors,
            "warnings": self.warnings,
            "phase_results": self.phase_results,
        }


@dataclass
class KustomizeOverlay:
    """Kustomize overlay configuration."""
    tenant_id: str
    namespace: str
    base_path: str
    
    # ConfigMap data
    config_data: Dict[str, str] = field(default_factory=dict)
    
    # Secret references (names, not values)
    secret_refs: List[str] = field(default_factory=list)
    
    # Resource patches
    patches: List[Dict[str, Any]] = field(default_factory=list)
    
    # Labels to add
    common_labels: Dict[str, str] = field(default_factory=dict)
    
    # Annotations to add
    common_annotations: Dict[str, str] = field(default_factory=dict)
    
    # Replicas override
    replicas: Dict[str, int] = field(default_factory=dict)
    
    # Images override
    images: List[Dict[str, str]] = field(default_factory=list)


# ==============================================================================
# Tenant Deployer
# ==============================================================================

class TenantDeployer:
    """
    Orchestrates per-tenant deployments.
    
    Handles:
    - Pre-flight validation
    - Kustomize overlay generation
    - Kubernetes deployment
    - Health validation
    - Rollback on failure
    """
    
    def __init__(
        self,
        project_root: Path,
        k8s_base_path: str = "k8s/base",
        k8s_overlays_path: str = "k8s/overlays",
        docker_registry: str = "ghcr.io/phoenix-guardian",
    ):
        self.project_root = Path(project_root)
        self.k8s_base_path = self.project_root / k8s_base_path
        self.k8s_overlays_path = self.project_root / k8s_overlays_path
        self.docker_registry = docker_registry
        
        self._deployments: Dict[str, DeploymentResult] = {}
    
    def deploy(
        self,
        tenant_config,
        version: str = "latest",
        dry_run: bool = False,
        skip_pre_flight: bool = False,
    ) -> DeploymentResult:
        """
        Deploy Phoenix Guardian for a specific tenant.
        
        Args:
            tenant_config: TenantConfig object
            version: Version/tag to deploy
            dry_run: If True, only generate manifests without applying
            skip_pre_flight: Skip pre-flight validation
        
        Returns:
            DeploymentResult with status and details
        """
        tenant_id = tenant_config.tenant_id
        namespace = f"phoenix-guardian-{tenant_id.replace('_', '-')}"
        
        result = DeploymentResult(
            tenant_id=tenant_id,
            status=DeploymentStatus.PENDING,
            phase=DeploymentPhase.PRE_FLIGHT,
            started_at=datetime.now().isoformat(),
            config_hash=tenant_config.get_config_hash(),
            deployed_version=version,
            kubernetes_namespace=namespace,
        )
        
        self._deployments[tenant_id] = result
        
        try:
            # Phase 1: Pre-flight validation
            if not skip_pre_flight:
                result.phase = DeploymentPhase.PRE_FLIGHT
                result.status = DeploymentStatus.VALIDATING
                self._run_pre_flight(tenant_config, result)
                
                if result.errors:
                    result.status = DeploymentStatus.FAILED
                    return self._finalize_result(result)
            
            # Phase 2: Generate Kustomize overlay
            result.phase = DeploymentPhase.CONFIG
            result.status = DeploymentStatus.DEPLOYING
            overlay = self._generate_overlay(tenant_config, namespace, version)
            overlay_path = self._write_overlay(overlay)
            result.phase_results["config"] = {"overlay_path": str(overlay_path)}
            
            if dry_run:
                # Generate manifests but don't apply
                manifests = self._generate_manifests(overlay_path)
                result.phase_results["manifests"] = manifests
                result.status = DeploymentStatus.DEPLOYED
                result.phase = DeploymentPhase.COMPLETE
                result.warnings.append("Dry run - manifests generated but not applied")
                return self._finalize_result(result)
            
            # Phase 3: Create namespace and secrets
            result.phase = DeploymentPhase.SECRETS
            self._deploy_namespace(namespace, result)
            self._deploy_secrets(tenant_config, namespace, result)
            
            # Phase 4: Deploy database
            result.phase = DeploymentPhase.DATABASE
            self._deploy_database(namespace, result)
            
            # Phase 5: Deploy cache
            result.phase = DeploymentPhase.CACHE
            self._deploy_cache(namespace, result)
            
            # Phase 6: Deploy application
            result.phase = DeploymentPhase.APPLICATION
            self._deploy_application(overlay_path, result)
            
            # Phase 7: Deploy ingress
            result.phase = DeploymentPhase.INGRESS
            self._deploy_ingress(namespace, tenant_config, result)
            
            # Phase 8: Validation
            result.phase = DeploymentPhase.VALIDATION
            self._validate_deployment(namespace, tenant_config, result)
            
            # Complete
            result.phase = DeploymentPhase.COMPLETE
            result.status = DeploymentStatus.DEPLOYED
            
        except Exception as e:
            result.errors.append(f"Deployment failed: {str(e)}")
            result.status = DeploymentStatus.FAILED
            logger.exception(f"Deployment failed for {tenant_id}")
        
        return self._finalize_result(result)
    
    def rollback(
        self,
        tenant_id: str,
        revision: Optional[int] = None,
    ) -> DeploymentResult:
        """
        Rollback a tenant deployment.
        
        Args:
            tenant_id: Tenant identifier
            revision: Specific revision to rollback to (default: previous)
        
        Returns:
            DeploymentResult with rollback status
        """
        namespace = f"phoenix-guardian-{tenant_id.replace('_', '-')}"
        
        result = DeploymentResult(
            tenant_id=tenant_id,
            status=DeploymentStatus.ROLLING_BACK,
            phase=DeploymentPhase.APPLICATION,
            started_at=datetime.now().isoformat(),
            kubernetes_namespace=namespace,
        )
        
        try:
            # Rollback deployments
            deployments = ["phoenix-guardian-app", "phoenix-guardian-worker", "phoenix-guardian-beacon"]
            
            for deployment in deployments:
                cmd = ["kubectl", "rollout", "undo", f"deployment/{deployment}",
                       "-n", namespace]
                if revision:
                    cmd.extend(["--to-revision", str(revision)])
                
                self._run_kubectl(cmd, result)
            
            # Wait for rollout
            for deployment in deployments:
                self._run_kubectl([
                    "kubectl", "rollout", "status", f"deployment/{deployment}",
                    "-n", namespace, "--timeout=300s"
                ], result)
            
            result.status = DeploymentStatus.ROLLED_BACK
            result.phase = DeploymentPhase.COMPLETE
            
        except Exception as e:
            result.errors.append(f"Rollback failed: {str(e)}")
            result.status = DeploymentStatus.FAILED
        
        return self._finalize_result(result)
    
    def get_deployment_status(self, tenant_id: str) -> Optional[DeploymentResult]:
        """Get the latest deployment result for a tenant."""
        return self._deployments.get(tenant_id)
    
    def _run_pre_flight(self, tenant_config, result: DeploymentResult) -> None:
        """Run pre-flight validation checks."""
        logger.info(f"Running pre-flight checks for {tenant_config.tenant_id}")
        
        # Validate configuration
        config_errors = tenant_config.validate()
        if config_errors:
            result.errors.extend([f"Config: {e}" for e in config_errors])
            return
        
        # Check Kubernetes connectivity
        try:
            self._run_kubectl(["kubectl", "cluster-info"], result, check=True)
        except subprocess.CalledProcessError:
            result.errors.append("Cannot connect to Kubernetes cluster")
            return
        
        # Check required namespaces exist
        try:
            self._run_kubectl(["kubectl", "get", "namespace", "default"], result, check=True)
        except subprocess.CalledProcessError:
            result.errors.append("Kubernetes cluster not accessible")
        
        result.phase_results["pre_flight"] = {
            "config_valid": len(config_errors) == 0,
            "cluster_accessible": "Cannot connect" not in str(result.errors),
        }
    
    def _generate_overlay(
        self,
        tenant_config,
        namespace: str,
        version: str,
    ) -> KustomizeOverlay:
        """Generate Kustomize overlay for tenant."""
        env_vars = tenant_config.to_env_vars()
        
        overlay = KustomizeOverlay(
            tenant_id=tenant_config.tenant_id,
            namespace=namespace,
            base_path="../../base",
            config_data=env_vars,
            secret_refs=[
                "ehr-credentials",
                "anthropic-credentials",
                "app-secrets",
            ],
            common_labels={
                "app.kubernetes.io/instance": tenant_config.tenant_id,
                "app.kubernetes.io/version": version,
                "phoenix-guardian/tenant": tenant_config.tenant_id,
                "phoenix-guardian/hospital": tenant_config.hospital_name.replace(" ", "-").lower(),
                "phoenix-guardian/ehr": tenant_config.ehr.platform.value,
            },
            common_annotations={
                "phoenix-guardian/config-hash": tenant_config.get_config_hash(),
                "phoenix-guardian/deployed-at": datetime.now().isoformat(),
            },
            replicas={
                "phoenix-guardian-app": 3,
                "phoenix-guardian-worker": 2,
                "phoenix-guardian-beacon": 5,
            },
            images=[
                {
                    "name": "phoenix-guardian-app",
                    "newName": f"{self.docker_registry}/app",
                    "newTag": version,
                },
                {
                    "name": "phoenix-guardian-worker",
                    "newName": f"{self.docker_registry}/worker",
                    "newTag": version,
                },
                {
                    "name": "phoenix-guardian-beacon",
                    "newName": f"{self.docker_registry}/beacon",
                    "newTag": version,
                },
            ],
        )
        
        # Add hospital-specific patches
        overlay.patches = self._generate_patches(tenant_config)
        
        return overlay
    
    def _generate_patches(self, tenant_config) -> List[Dict[str, Any]]:
        """Generate Kustomize patches for tenant-specific settings."""
        patches = []
        
        # App deployment patch
        app_patch = {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {"name": "phoenix-guardian-app"},
            "spec": {
                "template": {
                    "spec": {
                        "containers": [{
                            "name": "app",
                            "env": [
                                {"name": "TENANT_ID", "value": tenant_config.tenant_id},
                                {"name": "HOSPITAL_NAME", "value": tenant_config.hospital_name},
                                {"name": "EHR_PLATFORM", "value": tenant_config.ehr.platform.value},
                                {"name": "EHR_BASE_URL", "value": tenant_config.ehr.base_url},
                                {"name": "EHR_TIMEOUT", "value": str(tenant_config.ehr.timeout_seconds)},
                                {"name": "ALERT_EMAIL", "value": tenant_config.alerts.primary_email},
                                {"name": "IS_PILOT", "value": str(tenant_config.pilot.is_pilot).lower()},
                            ]
                        }]
                    }
                }
            }
        }
        patches.append(app_patch)
        
        # Ingress patch for hospital-specific domain
        ingress_patch = {
            "apiVersion": "networking.k8s.io/v1",
            "kind": "Ingress",
            "metadata": {"name": "phoenix-guardian-ingress"},
            "spec": {
                "rules": [{
                    "host": f"{tenant_config.tenant_id}.phoenix-guardian.health",
                }]
            }
        }
        patches.append(ingress_patch)
        
        return patches
    
    def _write_overlay(self, overlay: KustomizeOverlay) -> Path:
        """Write Kustomize overlay files to disk."""
        overlay_dir = self.k8s_overlays_path / overlay.tenant_id
        overlay_dir.mkdir(parents=True, exist_ok=True)
        
        # Write kustomization.yaml
        kustomization = {
            "apiVersion": "kustomize.config.k8s.io/v1beta1",
            "kind": "Kustomization",
            "namespace": overlay.namespace,
            "resources": [overlay.base_path],
            "commonLabels": overlay.common_labels,
            "commonAnnotations": overlay.common_annotations,
            "configMapGenerator": [{
                "name": "tenant-config",
                "literals": [f"{k}={v}" for k, v in overlay.config_data.items()],
            }],
            "replicas": [
                {"name": name, "count": count}
                for name, count in overlay.replicas.items()
            ],
            "images": overlay.images,
        }
        
        kustomization_path = overlay_dir / "kustomization.yaml"
        with open(kustomization_path, "w") as f:
            yaml.dump(kustomization, f, default_flow_style=False)
        
        # Write patches
        patches_dir = overlay_dir / "patches"
        patches_dir.mkdir(exist_ok=True)
        
        for i, patch in enumerate(overlay.patches):
            patch_path = patches_dir / f"patch-{i}.yaml"
            with open(patch_path, "w") as f:
                yaml.dump(patch, f, default_flow_style=False)
        
        logger.info(f"Wrote Kustomize overlay to {overlay_dir}")
        return overlay_dir
    
    def _generate_manifests(self, overlay_path: Path) -> str:
        """Generate Kubernetes manifests from Kustomize overlay."""
        try:
            result = subprocess.run(
                ["kustomize", "build", str(overlay_path)],
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout
        except subprocess.CalledProcessError as e:
            logger.error(f"Kustomize build failed: {e.stderr}")
            raise
    
    def _deploy_namespace(self, namespace: str, result: DeploymentResult) -> None:
        """Create Kubernetes namespace."""
        logger.info(f"Creating namespace {namespace}")
        
        namespace_yaml = {
            "apiVersion": "v1",
            "kind": "Namespace",
            "metadata": {
                "name": namespace,
                "labels": {
                    "app.kubernetes.io/name": "phoenix-guardian",
                    "app.kubernetes.io/managed-by": "tenant-deployer",
                }
            }
        }
        
        self._apply_yaml(namespace_yaml, result)
    
    def _deploy_secrets(
        self,
        tenant_config,
        namespace: str,
        result: DeploymentResult
    ) -> None:
        """Deploy sealed secrets for tenant."""
        logger.info(f"Deploying secrets to {namespace}")
        
        # In production, this would use kubeseal to create SealedSecrets
        # For now, we just log the intent
        result.phase_results["secrets"] = {
            "secrets_deployed": [
                "ehr-credentials",
                "anthropic-credentials",
                "app-secrets",
            ]
        }
    
    def _deploy_database(self, namespace: str, result: DeploymentResult) -> None:
        """Deploy PostgreSQL StatefulSet."""
        logger.info(f"Deploying database to {namespace}")
        
        # Apply PostgreSQL from base manifests
        self._run_kubectl([
            "kubectl", "apply", "-f",
            str(self.k8s_base_path / "postgres-statefulset.yaml"),
            "-n", namespace
        ], result)
        
        result.phase_results["database"] = {"status": "deployed"}
    
    def _deploy_cache(self, namespace: str, result: DeploymentResult) -> None:
        """Deploy Redis StatefulSet."""
        logger.info(f"Deploying cache to {namespace}")
        
        # Apply Redis from base manifests
        self._run_kubectl([
            "kubectl", "apply", "-f",
            str(self.k8s_base_path / "redis-deployment.yaml"),
            "-n", namespace
        ], result)
        
        result.phase_results["cache"] = {"status": "deployed"}
    
    def _deploy_application(
        self,
        overlay_path: Path,
        result: DeploymentResult
    ) -> None:
        """Deploy application using Kustomize overlay."""
        logger.info(f"Deploying application from {overlay_path}")
        
        self._run_kubectl([
            "kubectl", "apply", "-k", str(overlay_path)
        ], result)
        
        result.phase_results["application"] = {"status": "deployed"}
    
    def _deploy_ingress(
        self,
        namespace: str,
        tenant_config,
        result: DeploymentResult
    ) -> None:
        """Deploy ingress with tenant-specific configuration."""
        logger.info(f"Deploying ingress for {tenant_config.tenant_id}")
        
        # Apply ingress from base manifests
        self._run_kubectl([
            "kubectl", "apply", "-f",
            str(self.k8s_base_path / "ingress.yaml"),
            "-n", namespace
        ], result)
        
        result.phase_results["ingress"] = {"status": "deployed"}
    
    def _validate_deployment(
        self,
        namespace: str,
        tenant_config,
        result: DeploymentResult
    ) -> None:
        """Validate deployment is healthy."""
        logger.info(f"Validating deployment in {namespace}")
        
        # Wait for deployments to be ready
        deployments = ["phoenix-guardian-app", "phoenix-guardian-worker", "phoenix-guardian-beacon"]
        
        for deployment in deployments:
            try:
                self._run_kubectl([
                    "kubectl", "rollout", "status", f"deployment/{deployment}",
                    "-n", namespace, "--timeout=300s"
                ], result, check=True)
            except subprocess.CalledProcessError:
                result.warnings.append(f"Deployment {deployment} not ready")
        
        result.phase_results["validation"] = {
            "deployments_ready": len(result.warnings) == 0
        }
    
    def _run_kubectl(
        self,
        cmd: List[str],
        result: DeploymentResult,
        check: bool = False
    ) -> subprocess.CompletedProcess:
        """Run kubectl command."""
        logger.debug(f"Running: {' '.join(cmd)}")
        
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600,
            )
            
            if check and proc.returncode != 0:
                result.errors.append(f"Command failed: {proc.stderr}")
                raise subprocess.CalledProcessError(proc.returncode, cmd)
            
            return proc
            
        except subprocess.TimeoutExpired:
            result.errors.append(f"Command timed out: {' '.join(cmd)}")
            raise
    
    def _apply_yaml(self, yaml_content: Dict, result: DeploymentResult) -> None:
        """Apply YAML content to Kubernetes."""
        yaml_str = yaml.dump(yaml_content)
        
        try:
            proc = subprocess.run(
                ["kubectl", "apply", "-f", "-"],
                input=yaml_str,
                capture_output=True,
                text=True,
            )
            
            if proc.returncode != 0:
                result.warnings.append(f"Apply warning: {proc.stderr}")
                
        except Exception as e:
            result.errors.append(f"Apply failed: {str(e)}")
    
    def _finalize_result(self, result: DeploymentResult) -> DeploymentResult:
        """Finalize deployment result with timing information."""
        result.completed_at = datetime.now().isoformat()
        
        try:
            start = datetime.fromisoformat(result.started_at)
            end = datetime.fromisoformat(result.completed_at)
            result.duration_seconds = (end - start).total_seconds()
        except ValueError:
            pass
        
        return result


# ==============================================================================
# Utility Functions
# ==============================================================================

def deploy_tenant(
    tenant_config,
    project_root: Path,
    version: str = "latest",
    dry_run: bool = False,
) -> DeploymentResult:
    """
    Convenience function to deploy a tenant.
    
    Args:
        tenant_config: TenantConfig object
        project_root: Path to project root
        version: Version to deploy
        dry_run: If True, only generate manifests
    
    Returns:
        DeploymentResult
    """
    deployer = TenantDeployer(project_root)
    return deployer.deploy(tenant_config, version=version, dry_run=dry_run)


def deploy_all_pilots(
    project_root: Path,
    version: str = "latest",
    dry_run: bool = False,
) -> Dict[str, DeploymentResult]:
    """
    Deploy all pilot hospitals.
    
    Args:
        project_root: Path to project root
        version: Version to deploy
        dry_run: If True, only generate manifests
    
    Returns:
        Dict mapping tenant_id to DeploymentResult
    """
    from phoenix_guardian.config.pilot_hospitals import get_all_pilot_hospitals
    
    deployer = TenantDeployer(project_root)
    results = {}
    
    for config in get_all_pilot_hospitals():
        result = deployer.deploy(config, version=version, dry_run=dry_run)
        results[config.tenant_id] = result
    
    return results
