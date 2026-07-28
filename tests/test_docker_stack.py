from __future__ import annotations

import subprocess

import pytest
import requests

REQUIRED_CONTAINERS = [
    "freight-visibility-api",
    "freight-visibility-ui",
    "freight-visibility-neo4j",
]


def _docker_available() -> bool:
    try:
        subprocess.run(["docker", "--version"], capture_output=True, timeout=10)
        return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _container_running(name: str) -> bool:
    result = subprocess.run(
        ["docker", "ps", "--filter", f"name=^{name}$", "--format", "{{.Names}}"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    return name in result.stdout.split()


@pytest.fixture(scope="module")
def require_docker() -> None:
    if not _docker_available():
        pytest.skip("Docker is not available in this environment; skipping Docker stack tests.")


@pytest.fixture(scope="module")
def require_docker_stack(require_docker: None) -> None:
    missing = [name for name in REQUIRED_CONTAINERS if not _container_running(name)]
    if missing:
        pytest.skip(
            f"Application containers not running (missing: {', '.join(missing)}); "
            "start them with `docker compose up --build -d` to run these tests."
        )


pytestmark = pytest.mark.usefixtures("require_docker")


def test_compose_config_is_valid() -> None:
    """docker compose config --quiet never prints anything, including the password."""
    result = subprocess.run(
        ["docker", "compose", "config", "--quiet"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout == ""


@pytest.mark.usefixtures("require_docker_stack")
def test_api_container_is_healthy() -> None:
    response = requests.get("http://127.0.0.1:8000/health", timeout=10)
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.usefixtures("require_docker_stack")
def test_ui_container_is_available() -> None:
    response = requests.get("http://127.0.0.1:8501", timeout=10)
    assert response.status_code == 200


@pytest.mark.usefixtures("require_docker_stack")
def test_api_connects_to_neo4j() -> None:
    """Exercises the running api container's real connection to the neo4j service.

    Only checks connectivity here; graph data correctness is covered by
    tests/test_graph.py against the isolated neo4j-test service, never this
    development graph.
    """
    response = requests.get("http://127.0.0.1:8000/health/graph", timeout=10)
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.usefixtures("require_docker_stack")
def test_ui_connects_to_api_by_service_name() -> None:
    result = subprocess.run(
        [
            "docker",
            "exec",
            "freight-visibility-ui",
            "python",
            "-c",
            "import os, urllib.request; "
            "print(urllib.request.urlopen(os.environ['API_BASE_URL'] + '/health').read().decode())",
        ],
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stderr
    assert '"status":"ok"' in result.stdout
    assert result.stdout.strip().startswith("{")
