"""docker-compose.yml follows docs/ops/DOCKER_CONVENTIONS.md.

Docker is not installed on the server, so `docker compose config` cannot run there;
these checks run in CI instead. Each rule is a failure seen elsewhere: a bare
`"8000:8000"` binds every interface and Docker's rules sit AHEAD of ufw; an
`env_file:` copies every app secret into a container that needs none of them; a
worker inheriting the API image's HTTP health check reads "unhealthy" forever.
"""
from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
COMPOSE = ROOT / "docker-compose.yml"


def _services() -> dict:
    return yaml.safe_load(COMPOSE.read_text())["services"]


def test_every_published_port_is_bound_to_localhost():
    for name, svc in _services().items():
        for port in svc.get("ports", []):
            assert str(port).startswith("127.0.0.1:"), f"{name}: {port}"


def test_no_service_takes_a_whole_env_file():
    for name, svc in _services().items():
        assert "env_file" not in svc, name


def test_every_service_restarts_and_reports_health():
    for name, svc in _services().items():
        assert svc.get("restart") == "unless-stopped", name
        # the api's check is the image's own HEALTHCHECK (backend/Dockerfile)
        assert "healthcheck" in svc or name == "api", name


def test_a_worker_never_inherits_the_api_http_check():
    for name in ("worker", "worker-assist"):
        test = " ".join(_services()[name]["healthcheck"]["test"])
        assert "inspect ping" in test and ":8000" not in test, name
    assert "127.0.0.1:8000/health" in (ROOT / "backend" / "Dockerfile").read_text()


def test_dependencies_wait_for_health_not_just_start():
    for name, svc in _services().items():
        for dep, cond in (svc.get("depends_on") or {}).items():
            assert cond == {"condition": "service_healthy"}, f"{name} -> {dep}"


def test_data_lives_in_named_volumes():
    services = _services()
    assert "db_data:/var/lib/postgresql/data" in services["db"]["volumes"]
    for name in ("api", "worker", "worker-assist"):
        assert "documents:/var/lib/legalmind/documents" in services[name]["volumes"]
    assert set(yaml.safe_load(COMPOSE.read_text())["volumes"]) >= {"db_data", "documents"}


def test_health_checks_read_secrets_at_run_time_and_the_run_command_is_stated():
    text = COMPOSE.read_text()
    assert "$$POSTGRES_USER" in text                 # not ${...}, which compose bakes in
    assert "docker compose --env-file .env.local up -d" in text
