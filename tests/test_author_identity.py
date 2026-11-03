"""Author diagnostics use fake HTTP and cannot establish live authorization."""

import httpx
import pytest

from linkedin_mcp import author_identity


@pytest.fixture
def credential(monkeypatch):
    """Avoid OS keyring access for every diagnostic."""
    monkeypatch.setattr(author_identity, "load_token", lambda: {"access_token": "fake-sensitive-token"})


def test_oidc_subject_never_becomes_author():
    """Even an ID-shaped OIDC subject must not be mapped by assumption."""
    result = author_identity.AuthorResolver().resolve(account_id="local-a", oidc_subject="member-123")
    assert result.state.value == "UNVERIFIED"
    assert result.available is False
    assert "urn:li:person:" not in str(result)


def test_profile_id_does_not_establish_account_binding():
    """A profile ID alone is not durable evidence of the active owner."""
    result = author_identity.AuthorResolver().resolve(
        account_id="local-a", oidc_subject="same-id", profile_id="same-id",
    )
    assert result.state.value == "UNVERIFIED"
    assert result.reason_code == "ACCOUNT_BINDING_UNVERIFIED"
    assert result.available is False


def test_resolver_expired_or_missing_credentials():
    """Offline fixtures distinguish expired and unavailable evidence."""
    resolver = author_identity.AuthorResolver()
    assert resolver.resolve(account_id="a", credential_expired=True).state.value == "EXPIRED"
    assert resolver.resolve(account_id="a").state.value == "UNAVAILABLE"


def test_missing_token_does_not_attempt_http(monkeypatch):
    """No credential means no attempt to probe the remote endpoint."""
    monkeypatch.setattr(author_identity, "load_token", lambda: None)
    def forbidden(request):
        pytest.fail("HTTP attempted without credentials")
    result = author_identity.diagnose_author_identity(transport=httpx.MockTransport(forbidden))
    assert result["available"] is False
    assert result["identity_state"] == "UNAVAILABLE"


@pytest.mark.parametrize("status", [401, 403, 429, 500, 503])
def test_upstream_error_is_sanitized(credential, status):
    """Remote bodies and credential material never leak into tool results."""
    def response(request):
        assert request.method == "GET"
        assert str(request.url) == "https://api.linkedin.com/v2/me"
        return httpx.Response(status, text="sensitive-upstream-body", request=request)
    result = author_identity.diagnose_author_identity(transport=httpx.MockTransport(response))
    assert result["available"] is False
    assert result["status_code"] == status
    assert result["ready_for_live_publish"] is False
    assert "sensitive" not in str(result)


@pytest.mark.parametrize("payload", [[], {}, {"sub": "oidc-only"}, {"id": 123}, {"id": " "}, {"id": "bad\nheader"}])
def test_malformed_profile_never_resolves_author(credential, payload):
    """Only a valid profile ID can count as successful endpoint evidence."""
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json=payload))
    result = author_identity.diagnose_author_identity(transport=transport)
    assert result["available"] is False
    assert result["identity_state"] == "UNAVAILABLE"
    assert "person_urn" not in result


def test_successful_probe_is_still_unverified(credential):
    """Successful reads do not substitute for identity/account verification."""
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json={"id": "member-123"}))
    result = author_identity.diagnose_author_identity(transport=transport)
    assert result["endpoint_available"] is True
    assert result["identity_state"] == "UNVERIFIED"
    assert result["available"] is False
    assert result["ready_for_live_publish"] is False
    assert "person_urn" not in result


def test_timeout_is_sanitized(credential):
    """Even exception strings containing secrets must not reach the client."""
    def timeout(request):
        raise httpx.ReadTimeout("fake-sensitive-token", request=request)
    result = author_identity.diagnose_author_identity(transport=httpx.MockTransport(timeout))
    assert result["reason_code"] == "UPSTREAM_UNAVAILABLE"
    assert "sensitive" not in str(result)


def test_malformed_json_is_sanitized(credential):
    """A successful HTTP status with invalid JSON is not identity evidence."""
    transport = httpx.MockTransport(lambda request: httpx.Response(200, text="not-json"))
    result = author_identity.diagnose_author_identity(transport=transport)
    assert result["available"] is False
    assert result["identity_state"] == "UNAVAILABLE"


def test_keyring_failure_is_sanitized(monkeypatch):
    """Credential-backend failures fail closed before any HTTP operation."""
    def failed():
        raise RuntimeError("fake-sensitive-token")
    monkeypatch.setattr(author_identity, "load_token", failed)
    result = author_identity.diagnose_author_identity()
    assert result["reason_code"] == "CREDENTIAL_UNAVAILABLE"
    assert "sensitive" not in str(result)
