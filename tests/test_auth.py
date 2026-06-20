import pytest
from fastapi import HTTPException

from app.api.routes.auth import login
from app.core.config import settings
from app.core.security import hash_password
from app.schemas.entities import LoginRequest


@pytest.fixture
def configured_admin(monkeypatch):
    password = "test-only-secure-password"
    monkeypatch.setattr(settings, "admin_username", "test-operator")
    monkeypatch.setattr(settings, "admin_password_hash", hash_password(password))
    return password


def test_login_uses_environment_backed_password_hash(configured_admin):
    response = login(LoginRequest(username="test-operator", password=configured_admin))

    assert response.token_type == "bearer"
    assert response.access_token


def test_login_rejects_invalid_credentials(configured_admin):
    with pytest.raises(HTTPException) as exc_info:
        login(LoginRequest(username="test-operator", password="incorrect-password"))

    assert exc_info.value.status_code == 401


def test_login_is_disabled_when_admin_is_not_configured(monkeypatch):
    monkeypatch.setattr(settings, "admin_username", None)
    monkeypatch.setattr(settings, "admin_password_hash", None)

    with pytest.raises(HTTPException) as exc_info:
        login(LoginRequest(username="any-user", password="any-password"))

    assert exc_info.value.status_code == 503


def test_initial_admin_builder_returns_hash_not_plaintext():
    from app.scripts.create_initial_admin import build_admin_environment

    username, password_hash = build_admin_environment(
        " operator ",
        "another-test-password",
        "another-test-password",
    )

    assert username == "operator"
    assert password_hash != "another-test-password"


def test_initial_admin_builder_rejects_short_password():
    from app.scripts.create_initial_admin import build_admin_environment

    with pytest.raises(ValueError, match="at least 12"):
        build_admin_environment("operator", "short", "short")
