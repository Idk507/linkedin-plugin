
"""Official LinkedIn API client for permitted profile retrieval."""

from typing import Any

import httpx

from linkedin_mcp.credential_store import load_token


class LinkedInAPIError(RuntimeError):
    """Raised when a LinkedIn API request cannot be completed."""


def get_my_profile() -> dict[str, Any]:
    """Retrieve the authenticated member's OpenID profile.

    Requires a valid access token with the appropriate scopes.
    Never returns access tokens or client credentials.
    """
    credential = load_token()

    if not credential:
        raise LinkedInAPIError(
            "LinkedIn is not connected or the token has expired"
        )

    try:
        with httpx.Client(timeout=15.0) as client:
            response = client.get(
                "https://api.linkedin.com/v2/userinfo",
                headers={
                    "Authorization": (
                        f"Bearer {credential['access_token']}"
                    ),
                    "Accept": "application/json",
                },
            )

            response.raise_for_status()
            profile = response.json()

    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code

        raise LinkedInAPIError(
            f"LinkedIn profile request failed (HTTP {status})"
        ) from None

    except (httpx.RequestError, ValueError) as exc:
        raise LinkedInAPIError(
            "LinkedIn profile request failed"
        ) from exc

    if not isinstance(profile, dict) or not profile.get("sub"):
        raise LinkedInAPIError(
            "LinkedIn returned an invalid OpenID profile"
        )

    return {
        "id": profile["sub"],
        "name": profile.get("name"),
        "given_name": profile.get("given_name"),
        "family_name": profile.get("family_name"),
        "email": profile.get("email"),
        "picture": profile.get("picture"),
    }
