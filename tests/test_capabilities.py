
"""Tests for LinkedIn OAuth-aware capability discovery."""

from unittest.mock import patch

from linkedin_mcp.capabilities import (
    get_capability_manifest,
    parse_scopes,
)


def test_scope_parsing() -> None:
    """Verify comma and whitespace separated scopes."""
    assert parse_scopes("email,openid,profile") == {
        "email", "openid", "profile"
    }
    assert parse_scopes("openid profile email") == {
        "openid", "profile", "email"
    }


@patch("linkedin_mcp.capabilities.load_token")
def test_unauthenticated(mock_load_token) -> None:
    """Verify missing credentials disable remote capabilities."""
    mock_load_token.return_value = None

    result = get_capability_manifest()

    assert result["authenticated"] is False
    assert result["capabilities"]["profile_read"]["available"] is False


@patch("linkedin_mcp.capabilities.load_token")
def test_authenticated_profile(mock_load_token) -> None:
    """Verify authorized profile access is reported."""
    mock_load_token.return_value = {
        "access_token": "test-token",
        "scope": "email,openid,profile",
    }

    result = get_capability_manifest()

    assert result["authenticated"] is True
    assert result["capabilities"]["profile_read"]["available"] is True
    assert result["capabilities"]["post_publish"]["available"] is False


@patch("linkedin_mcp.capabilities.load_token")
def test_publishing_requires_implementation(mock_load_token) -> None:
    """Ensure OAuth scope alone cannot enable an absent write tool."""
    mock_load_token.return_value = {
        "access_token": "test-token",
        "scope": "openid,profile,w_member_social",
    }

    result = get_capability_manifest()

    assert result["capabilities"]["post_publish"]["available"] is False


@patch("linkedin_mcp.capabilities.load_token")
def test_restricted_read_disabled(mock_load_token) -> None:
    """Ensure restricted read capability stays disabled."""
    mock_load_token.return_value = {
        "access_token": "test-token",
        "scope": "openid,profile",
    }

    result = get_capability_manifest()

    assert (
        result["capabilities"]["post_history_read"]["available"]
        is False
    )
