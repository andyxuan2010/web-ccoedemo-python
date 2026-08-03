import base64
import json
from unittest.mock import Mock, patch

import pytest

import app as app_module


@pytest.fixture
def client(monkeypatch):
    monkeypatch.delenv("WEBSITE_SITE_NAME", raising=False)
    monkeypatch.delenv("FLASK_SECRET_KEY", raising=False)
    monkeypatch.delenv("TRUST_EASY_AUTH_HEADERS", raising=False)
    application = app_module.create_app()
    application.config.update(TESTING=True)
    return application.test_client()


def encode_principal(principal):
    return base64.b64encode(json.dumps(principal).encode()).decode()


def test_home_renders_expected_navigation(client):
    response = client.get("/")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Refresh Latest" in html
    assert "Projects" not in html
    assert "Standards" not in html
    assert "Contact" not in html
    assert 'id="themeSwitch"' in html
    assert 'data-language="en"' in html
    assert 'data-language="fr"' in html
    assert "CCOE Identity Demo" in html
    assert "Auto Sign-out" not in html


def test_identity_empty_easy_auth_header_does_not_start_auto_signout(monkeypatch):
    monkeypatch.setenv("TRUST_EASY_AUTH_HEADERS", "true")
    application = app_module.create_app()
    application.config.update(TESTING=True)
    client = application.test_client()

    response = client.get(
        "/",
        headers={"X-MS-CLIENT-PRINCIPAL": encode_principal({"claims": []})},
    )

    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Auto Sign-out" not in html
    assert 'id="idleCountdown"' not in html


def test_health_endpoint_and_security_headers(client):
    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json == {"status": "ok"}
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert response.headers["Permissions-Policy"] == "camera=(), geolocation=(), microphone=()"


def test_easy_auth_header_is_ignored_outside_trusted_boundary(client):
    principal = {
        "userDetails": "spoofed@example.com",
        "claims": [{"typ": "name", "val": "Spoofed User"}],
    }
    response = client.get(
        "/profile/easyauth",
        headers={"X-MS-CLIENT-PRINCIPAL": encode_principal(principal)},
    )

    assert response.status_code == 302
    assert response.location.endswith("/login/easyauth")


def test_easy_auth_header_is_parsed_when_explicitly_trusted(monkeypatch):
    monkeypatch.setenv("TRUST_EASY_AUTH_HEADERS", "true")
    application = app_module.create_app()
    application.config.update(TESTING=True)
    client = application.test_client()
    principal = {
        "userDetails": "user@example.com",
        "userId": "object-id",
        "claims": [
            {"typ": "name", "val": "Demo User"},
            {"typ": "tid", "val": "tenant-id"},
        ],
    }

    response = client.get(
        "/profile/easyauth",
        headers={"X-MS-CLIENT-PRINCIPAL": encode_principal(principal)},
    )

    assert response.status_code == 200
    assert "Demo User" in response.get_data(as_text=True)


@pytest.mark.parametrize(
    "header",
    [
        "not-base64!",
        base64.b64encode(b"[]").decode(),
        encode_principal({"claims": "not-a-list"}),
        encode_principal({"claims": ["not-an-object"]}),
    ],
)
def test_malformed_easy_auth_header_is_rejected(monkeypatch, header):
    monkeypatch.setenv("TRUST_EASY_AUTH_HEADERS", "true")
    application = app_module.create_app()
    application.config.update(TESTING=True)

    response = application.test_client().get(
        "/profile/easyauth",
        headers={"X-MS-CLIENT-PRINCIPAL": header},
    )

    assert response.status_code == 302
    assert response.location.endswith("/login/easyauth")


def test_msal_callback_does_not_store_access_token(client):
    flow = {"state": "expected-state"}
    with client.session_transaction() as flask_session:
        flask_session["auth_flow"] = flow

    msal_client = Mock()
    msal_client.acquire_token_by_auth_code_flow.return_value = {
        "access_token": "sensitive-bearer-token",
        "id_token_claims": {"name": "Demo User", "preferred_username": "user@example.com"},
    }

    with patch.object(app_module, "build_msal_app", return_value=msal_client):
        response = client.get("/auth/callback?code=test&state=expected-state")

    assert response.status_code == 302
    with client.session_transaction() as flask_session:
        assert "msal_access_token" not in flask_session
        assert "auth_flow" not in flask_session
        assert flask_session["msal_user"]["name"] == "Demo User"


def test_msal_callback_error_clears_flow_and_returns_bad_request(client):
    with client.session_transaction() as flask_session:
        flask_session["auth_flow"] = {"state": "expected-state"}

    response = client.get("/auth/callback?error=access_denied&error_description=Denied")

    assert response.status_code == 400
    with client.session_transaction() as flask_session:
        assert "auth_flow" not in flask_session


def test_app_service_requires_explicit_secret(monkeypatch):
    monkeypatch.setenv("WEBSITE_SITE_NAME", "demo-app")
    monkeypatch.delenv("FLASK_SECRET_KEY", raising=False)

    with pytest.raises(RuntimeError, match="FLASK_SECRET_KEY"):
        app_module.create_app()
