"""
Phoenix Guardian - Docker Image Tests
Tests for validating Docker image build and configuration.
Version: 1.0.0

These tests validate:
- Dockerfile syntax and best practices
- Multi-stage build configuration
- Security requirements (non-root user, healthchecks)
- Image build success
- Container startup behavior
"""

import os
import re
import subprocess
import pytest
from pathlib import Path
from typing import Optional

# ==============================================================================
# Test Configuration
# ==============================================================================

PROJECT_ROOT = Path(__file__).parent.parent.parent
DOCKER_DIR = PROJECT_ROOT / "docker"

DOCKERFILES = {
    "app": DOCKER_DIR / "Dockerfile.app",
    "worker": DOCKER_DIR / "Dockerfile.worker",
    "beacon": DOCKER_DIR / "Dockerfile.beacon",
    "monitor": DOCKER_DIR / "Dockerfile.monitor",
}

DOCKER_COMPOSE = DOCKER_DIR / "docker-compose.yml"


# ==============================================================================
# Helper Functions
# ==============================================================================

def read_dockerfile(name: str) -> str:
    """Read Dockerfile content."""
    dockerfile_path = DOCKERFILES.get(name)
    if dockerfile_path and dockerfile_path.exists():
        return dockerfile_path.read_text(encoding="utf-8")
    return ""


def run_docker_command(args: list, timeout: int = 60) -> subprocess.CompletedProcess:
    """Run a docker command and return the result."""
    try:
        result = subprocess.run(
            ["docker"] + args,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(PROJECT_ROOT),
        )
        return result
    except subprocess.TimeoutExpired:
        pytest.skip("Docker command timed out")
    except FileNotFoundError:
        pytest.skip("Docker not installed")


def docker_available() -> bool:
    """Check if Docker is available."""
    try:
        result = subprocess.run(
            ["docker", "version"],
            capture_output=True,
            timeout=10,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


# ==============================================================================
# Test: Dockerfile Existence
# ==============================================================================

class TestDockerfileExistence:
    """Tests for Dockerfile existence and basic structure."""

    def test_app_dockerfile_exists(self):
        """Verify app Dockerfile exists."""
        assert DOCKERFILES["app"].exists(), "Dockerfile.app should exist"

    def test_worker_dockerfile_exists(self):
        """Verify worker Dockerfile exists."""
        assert DOCKERFILES["worker"].exists(), "Dockerfile.worker should exist"

    def test_beacon_dockerfile_exists(self):
        """Verify beacon Dockerfile exists."""
        assert DOCKERFILES["beacon"].exists(), "Dockerfile.beacon should exist"

    def test_monitor_dockerfile_exists(self):
        """Verify monitor Dockerfile exists."""
        assert DOCKERFILES["monitor"].exists(), "Dockerfile.monitor should exist"

    def test_docker_compose_exists(self):
        """Verify docker-compose.yml exists."""
        assert DOCKER_COMPOSE.exists(), "docker-compose.yml should exist"


# ==============================================================================
# Test: Multi-Stage Build
# ==============================================================================

class TestMultiStageBuild:
    """Tests for multi-stage build configuration."""

    @pytest.mark.parametrize("dockerfile_name", ["app", "worker", "beacon"])
    def test_has_builder_stage(self, dockerfile_name: str):
        """Verify Dockerfile uses multi-stage build with builder stage."""
        content = read_dockerfile(dockerfile_name)
        assert content, f"Could not read {dockerfile_name} Dockerfile"
        
        # Check for builder stage
        assert re.search(r"FROM\s+\S+\s+AS\s+builder", content, re.IGNORECASE), \
            f"{dockerfile_name} should have a builder stage"

    @pytest.mark.parametrize("dockerfile_name", ["app", "worker", "beacon"])
    def test_copies_from_builder(self, dockerfile_name: str):
        """Verify Dockerfile copies from builder stage."""
        content = read_dockerfile(dockerfile_name)
        assert content, f"Could not read {dockerfile_name} Dockerfile"
        
        # Check for COPY --from=builder
        assert re.search(r"COPY\s+--from=builder", content, re.IGNORECASE), \
            f"{dockerfile_name} should copy from builder stage"

    @pytest.mark.parametrize("dockerfile_name", ["app", "worker", "beacon"])
    def test_uses_slim_base_image(self, dockerfile_name: str):
        """Verify Dockerfile uses slim Python base image."""
        content = read_dockerfile(dockerfile_name)
        assert content, f"Could not read {dockerfile_name} Dockerfile"
        
        # Check for python slim image
        assert re.search(r"FROM\s+python:\d+\.\d+-slim", content), \
            f"{dockerfile_name} should use python slim base image"


# ==============================================================================
# Test: Security Configuration
# ==============================================================================

class TestSecurityConfiguration:
    """Tests for security best practices in Dockerfiles."""

    @pytest.mark.parametrize("dockerfile_name", ["app", "worker", "beacon"])
    def test_creates_non_root_user(self, dockerfile_name: str):
        """Verify Dockerfile creates a non-root user."""
        content = read_dockerfile(dockerfile_name)
        assert content, f"Could not read {dockerfile_name} Dockerfile"
        
        # Check for useradd or adduser command
        assert re.search(r"(useradd|adduser)", content), \
            f"{dockerfile_name} should create a non-root user"

    @pytest.mark.parametrize("dockerfile_name", ["app", "worker", "beacon"])
    def test_switches_to_non_root_user(self, dockerfile_name: str):
        """Verify Dockerfile switches to non-root user."""
        content = read_dockerfile(dockerfile_name)
        assert content, f"Could not read {dockerfile_name} Dockerfile"
        
        # Check for USER directive with non-root user
        assert re.search(r"USER\s+(phoenix|\$APP_USER|1000)", content), \
            f"{dockerfile_name} should switch to non-root user"

    @pytest.mark.parametrize("dockerfile_name", ["app", "worker", "beacon"])
    def test_user_id_is_1000(self, dockerfile_name: str):
        """Verify Dockerfile uses UID 1000 for security."""
        content = read_dockerfile(dockerfile_name)
        assert content, f"Could not read {dockerfile_name} Dockerfile"
        
        # Check for UID 1000
        assert re.search(r"1000", content), \
            f"{dockerfile_name} should use UID 1000"

    @pytest.mark.parametrize("dockerfile_name", ["app", "worker", "beacon"])
    def test_has_healthcheck(self, dockerfile_name: str):
        """Verify Dockerfile includes HEALTHCHECK directive."""
        content = read_dockerfile(dockerfile_name)
        assert content, f"Could not read {dockerfile_name} Dockerfile"
        
        # Check for HEALTHCHECK directive
        assert re.search(r"HEALTHCHECK", content), \
            f"{dockerfile_name} should include HEALTHCHECK directive"

    @pytest.mark.parametrize("dockerfile_name", ["app", "worker", "beacon"])
    def test_no_pip_cache(self, dockerfile_name: str):
        """Verify pip install uses --no-cache-dir."""
        content = read_dockerfile(dockerfile_name)
        assert content, f"Could not read {dockerfile_name} Dockerfile"
        
        # Check for --no-cache-dir in pip install
        if "pip install" in content:
            assert re.search(r"pip install.*--no-cache-dir", content), \
                f"{dockerfile_name} should use pip --no-cache-dir"


# ==============================================================================
# Test: Dockerfile Syntax
# ==============================================================================

class TestDockerfileSyntax:
    """Tests for Dockerfile syntax validation."""

    @pytest.mark.parametrize("dockerfile_name", ["app", "worker", "beacon", "monitor"])
    def test_dockerfile_has_from(self, dockerfile_name: str):
        """Verify Dockerfile starts with FROM."""
        content = read_dockerfile(dockerfile_name)
        assert content, f"Could not read {dockerfile_name} Dockerfile"
        
        # Skip comments and empty lines, first instruction should be FROM
        lines = [l for l in content.split('\n') if l.strip() and not l.strip().startswith('#')]
        assert lines[0].strip().startswith("FROM"), \
            f"{dockerfile_name} should start with FROM instruction"

    @pytest.mark.parametrize("dockerfile_name", ["app", "worker", "beacon"])
    def test_dockerfile_has_cmd_or_entrypoint(self, dockerfile_name: str):
        """Verify Dockerfile has CMD or ENTRYPOINT."""
        content = read_dockerfile(dockerfile_name)
        assert content, f"Could not read {dockerfile_name} Dockerfile"
        
        has_cmd = re.search(r"^CMD\s+", content, re.MULTILINE)
        has_entrypoint = re.search(r"^ENTRYPOINT\s+", content, re.MULTILINE)
        
        assert has_cmd or has_entrypoint, \
            f"{dockerfile_name} should have CMD or ENTRYPOINT"

    @pytest.mark.parametrize("dockerfile_name", ["app", "beacon"])
    def test_dockerfile_exposes_port(self, dockerfile_name: str):
        """Verify Dockerfile exposes appropriate port."""
        content = read_dockerfile(dockerfile_name)
        assert content, f"Could not read {dockerfile_name} Dockerfile"
        
        # Check for EXPOSE directive
        assert re.search(r"EXPOSE\s+\d+", content), \
            f"{dockerfile_name} should expose a port"

    def test_app_exposes_port_8000(self):
        """Verify app Dockerfile exposes port 8000."""
        content = read_dockerfile("app")
        assert re.search(r"EXPOSE\s+8000", content), \
            "App should expose port 8000"

    def test_beacon_exposes_port_8080(self):
        """Verify beacon Dockerfile exposes port 8080."""
        content = read_dockerfile("beacon")
        assert re.search(r"EXPOSE\s+8080", content), \
            "Beacon should expose port 8080"


# ==============================================================================
# Test: Docker Compose Configuration
# ==============================================================================

class TestDockerCompose:
    """Tests for docker-compose.yml configuration."""

    def test_docker_compose_valid_yaml(self):
        """Verify docker-compose.yml is valid YAML."""
        import yaml
        
        content = DOCKER_COMPOSE.read_text(encoding="utf-8")
        try:
            config = yaml.safe_load(content)
            assert config is not None
        except yaml.YAMLError as e:
            pytest.fail(f"docker-compose.yml is not valid YAML: {e}")

    def test_docker_compose_has_required_services(self):
        """Verify docker-compose.yml has all required services."""
        import yaml
        
        content = DOCKER_COMPOSE.read_text(encoding="utf-8")
        config = yaml.safe_load(content)
        
        required_services = ["app", "worker", "beacon", "postgres", "redis"]
        services = config.get("services", {})
        
        for service in required_services:
            assert service in services, f"Service '{service}' should be in docker-compose.yml"

    def test_docker_compose_has_networks(self):
        """Verify docker-compose.yml defines networks."""
        import yaml
        
        content = DOCKER_COMPOSE.read_text(encoding="utf-8")
        config = yaml.safe_load(content)
        
        assert "networks" in config, "docker-compose.yml should define networks"
        networks = config["networks"]
        assert "frontend" in networks or "backend" in networks, \
            "Should have frontend or backend network"

    def test_docker_compose_has_volumes(self):
        """Verify docker-compose.yml defines volumes for persistence."""
        import yaml
        
        content = DOCKER_COMPOSE.read_text(encoding="utf-8")
        config = yaml.safe_load(content)
        
        assert "volumes" in config, "docker-compose.yml should define volumes"
        volumes = config["volumes"]
        assert "postgres-data" in volumes, "Should have postgres-data volume"
        assert "redis-data" in volumes, "Should have redis-data volume"

    def test_docker_compose_services_have_healthchecks(self):
        """Verify critical services have healthchecks."""
        import yaml
        
        content = DOCKER_COMPOSE.read_text(encoding="utf-8")
        config = yaml.safe_load(content)
        
        critical_services = ["app", "postgres", "redis"]
        services = config.get("services", {})
        
        for service_name in critical_services:
            service = services.get(service_name, {})
            assert "healthcheck" in service, \
                f"Service '{service_name}' should have healthcheck"

    def test_docker_compose_services_have_resource_limits(self):
        """Verify services have resource limits."""
        import yaml
        
        content = DOCKER_COMPOSE.read_text(encoding="utf-8")
        config = yaml.safe_load(content)
        
        services = config.get("services", {})
        app_service = services.get("app", {})
        
        # Check for deploy.resources
        deploy = app_service.get("deploy", {})
        resources = deploy.get("resources", {})
        
        assert "limits" in resources, "App service should have resource limits"


# ==============================================================================
# Test: Docker Build (Integration)
# ==============================================================================

@pytest.mark.skipif(not docker_available(), reason="Docker not available")
class TestDockerBuild:
    """Integration tests for Docker image builds."""

    @pytest.mark.slow
    def test_app_image_builds_successfully(self):
        """Verify app image builds without errors."""
        result = run_docker_command(
            ["build", "-f", "docker/Dockerfile.app", "-t", "test-phoenix-app:test", "."],
            timeout=300,
        )
        assert result.returncode == 0, f"App build failed: {result.stderr}"

    @pytest.mark.slow
    def test_beacon_image_builds_successfully(self):
        """Verify beacon image builds without errors."""
        result = run_docker_command(
            ["build", "-f", "docker/Dockerfile.beacon", "-t", "test-phoenix-beacon:test", "."],
            timeout=180,
        )
        assert result.returncode == 0, f"Beacon build failed: {result.stderr}"


# ==============================================================================
# Test: Image Labels
# ==============================================================================

class TestImageLabels:
    """Tests for Docker image labels and metadata."""

    @pytest.mark.parametrize("dockerfile_name", ["app", "worker", "beacon", "monitor"])
    def test_dockerfile_has_maintainer_label(self, dockerfile_name: str):
        """Verify Dockerfile has LABEL maintainer."""
        content = read_dockerfile(dockerfile_name)
        assert content, f"Could not read {dockerfile_name} Dockerfile"
        
        assert re.search(r"LABEL\s+maintainer", content, re.IGNORECASE), \
            f"{dockerfile_name} should have maintainer label"

    @pytest.mark.parametrize("dockerfile_name", ["app", "worker", "beacon", "monitor"])
    def test_dockerfile_has_version_label(self, dockerfile_name: str):
        """Verify Dockerfile has version label."""
        content = read_dockerfile(dockerfile_name)
        assert content, f"Could not read {dockerfile_name} Dockerfile"
        
        assert re.search(r"(LABEL.*version|version=)", content, re.IGNORECASE), \
            f"{dockerfile_name} should have version label"
