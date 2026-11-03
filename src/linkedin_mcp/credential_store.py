
"""Local credential storage for one LinkedIn account.

Development-only implementation. Multi-user deployments require
authenticated per-user storage and encrypted database records.
"""

import json
import time
from typing import Any

import keyring

SERVICE = "linkedin-mcp-local"
ACCOUNT = "personal-linkedin-token"


def save_token(token_response: dict[str, Any]) -> None:
    """Store a LinkedIn token and calculate its expiry."""
    access_token = token_response.get("access_token")

    if not isinstance(access_token, str) or not access_token:
        raise ValueError("LinkedIn did not return an access token")

    record = {
        "access_token": access_token,
        "expires_at": time.time() + int(
            token_response.get("expires_in", 0)
        ),
        "scope": token_response.get("scope", ""),
    }

    keyring.set_password(
        SERVICE,
        ACCOUNT,
        json.dumps(record),
    )


def load_token() -> dict[str, Any] | None:
    """Load the token and reject expired credentials."""
    raw = keyring.get_password(SERVICE, ACCOUNT)

    if not raw:
        return None

    try:
        record = json.loads(raw)

        if not isinstance(record, dict):
            raise ValueError("Invalid credential structure")

        if time.time() >= float(record["expires_at"]) - 60:
            return None

        return record
    except (ValueError, TypeError, KeyError) as exc:
        raise RuntimeError(
            "Invalid locally stored LinkedIn credentials"
        ) from exc


def delete_token() -> None:
    """Remove the saved LinkedIn token from local storage."""
    try:
        keyring.delete_password(SERVICE, ACCOUNT)
    except keyring.errors.PasswordDeleteError:
        pass
