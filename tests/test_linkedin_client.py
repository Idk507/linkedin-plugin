
"""Unit tests for the LinkedIn UserInfo API adapter."""

from unittest.mock import patch

import httpx
import pytest

from linkedin_mcp.linkedin_client import (
    LinkedInAPIError,
    get_my_profile,
)


@patch("linkedin_mcp.linkedin_client.load_token")
@patch("linkedin_mcp.linkedin_client.httpx.Client")
def test_profile_success(mock_client, mock_token):
    """Verify valid LinkedIn UserInfo responses are normalized."""
    mock_token.return_value = {
        "access_token": "fake-test-token",
        "expires_at": 9999999999,
        "scope": "openid,profile,email",
    }

    mock_response = mock_client.return_value.__enter__.return_value.get.return_value
    mock_response.json.return_value = {
        "sub": "test-member-123",
        "name": "Test Member",
        "email": "test@example.com",
    }

    profile = get_my_profile()

    assert profile["id"] == "test-member-123"
    assert profile["name"] == "Test Member"
    assert profile["email"] == "test@example.com"


@patch("linkedin_mcp.linkedin_client.load_token")
def test_missing_token(mock_token):
    """Ensure unauthenticated calls fail before external requests."""
    mock_token.return_value = None

    with pytest.raises(LinkedInAPIError):
        get_my_profile()


@patch("linkedin_mcp.linkedin_client.load_token")
@patch("linkedin_mcp.linkedin_client.httpx.Client")
def test_linkedin_http_failure(mock_client, mock_token):
    """Verify LinkedIn HTTP failures raise controlled exceptions."""
    mock_token.return_value = {
        "access_token": "fake-test-token",
    }

    request = httpx.Request(
        "GET",
        "https://api.linkedin.com/v2/userinfo",
    )

    response = httpx.Response(
        401,
        request=request,
    )

    mock_response = (
        mock_client.return_value
        .__enter__.return_value.get.return_value
    )
    mock_response.raise_for_status.side_effect = (
        httpx.HTTPStatusError(
            "Unauthorized",
            request=request,
            response=response,
        )
    )

    with pytest.raises(LinkedInAPIError):
        get_my_profile()
