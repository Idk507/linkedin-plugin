
"""Dynamic LinkedIn capabilities based on local OAuth credentials."""

import re
from typing import Any

from linkedin_mcp.credential_store import load_token


def parse_scopes(raw_scopes: str) -> set[str]:
    """Normalize LinkedIn OAuth scopes into a set.

    Handles both comma-separated and whitespace-separated
    scope values returned by OAuth providers.
    """
    return {
        value
        for value in re.split(r"[,\s]+", raw_scopes.strip())
        if value
    }


def get_capability_manifest() -> dict[str, Any]:
    """Build a permission-aware LinkedIn capability manifest.

    A stored token is not proof that every requested LinkedIn
    API endpoint is authorized. Each remote action still needs
    its own authorization and API-level verification.
    """
    credential = load_token()
    authenticated = credential is not None

    granted_scopes = parse_scopes(
        str(credential.get("scope", "")) if credential else ""
    )

    def capability(scope: str) -> dict[str, Any]:
        """Describe whether a required OAuth scope is present."""
        available = authenticated and scope in granted_scopes

        return {
            "required_scope": scope,
            "available": available,
            "reason": (
                "Required OAuth scope is present"
                if available
                else "OAuth scope is missing or token has expired"
            ),
        }

    return {
        "provider": "linkedin",
        "authenticated": authenticated,
        "granted_scopes": sorted(granted_scopes),
        "capabilities": {
            "profile_read": capability("profile"),
            "post_publish": {
                **capability("w_member_social"),
                "reason": (
                    "Publishing tool is not implemented"
                    if "w_member_social" in granted_scopes
                    else "w_member_social permission is not granted"
                ),
                "available": False,
            },
            "post_history_read": {
                "required_scope": "r_member_social",
                "available": False,
                "reason": (
                    "Restricted permission and read tool "
                    "not implemented"
                ),
            },
            "draft_local": {
                "required_scope": None,
                "available": False,
                "reason": "Draft storage is not implemented",
            },
        },
    }
