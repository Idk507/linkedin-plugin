
"""Local LinkedIn OAuth 2.0 authorization-code callback application."""

import os
import secrets
import time
from urllib.parse import urlencode

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import RedirectResponse, PlainTextResponse

from linkedin_mcp.credential_store import save_token

load_dotenv()

app = FastAPI(
    title="LinkedIn MCP Local OAuth",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

AUTHORIZE_URL = "https://www.linkedin.com/oauth/v2/authorization"
TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"

# Only one pending authorization is supported in this local POC.
pending_state: str | None = None
pending_expiry: float = 0.0


def get_config() -> tuple[str, str, str, str]:
    """Return required OAuth settings or fail closed."""
    client_id = os.getenv("LINKEDIN_CLIENT_ID", "").strip()
    client_secret = os.getenv("LINKEDIN_CLIENT_SECRET", "").strip()
    redirect_uri = os.getenv("LINKEDIN_REDIRECT_URI", "").strip()
    scopes = os.getenv(
        "LINKEDIN_SCOPES",
        "openid profile email",
    ).strip()

    if not all((client_id, client_secret, redirect_uri, scopes)):
        raise HTTPException(
            status_code=500,
            detail="LinkedIn OAuth configuration is incomplete",
        )

    if not redirect_uri.startswith(
        ("http://localhost:", "https://")
    ):
        raise HTTPException(
            status_code=500,
            detail="Invalid configured OAuth redirect URI",
        )

    return client_id, client_secret, redirect_uri, scopes


@app.get("/connect")
def connect() -> RedirectResponse:
    """Start the LinkedIn authorization-code flow."""
    global pending_state, pending_expiry

    client_id, _, redirect_uri, scopes = get_config()

    pending_state = secrets.token_urlsafe(32)
    pending_expiry = time.monotonic() + 600

    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "state": pending_state,
        "scope": scopes,
    }

    url = f"{AUTHORIZE_URL}?{urlencode(params)}"

    return RedirectResponse(url, status_code=302)


@app.get("/auth/linkedin/callback")
def callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
) -> PlainTextResponse:
    """Validate OAuth state and exchange the one-time code."""
    global pending_state, pending_expiry

    valid_state = (
        state is not None
        and pending_state is not None
        and secrets.compare_digest(state, pending_state)
        and time.monotonic() < pending_expiry
    )

    # Invalidate the state before any external network request.
    pending_state = None
    pending_expiry = 0.0

    if not valid_state:
        raise HTTPException(
            status_code=403,
            detail="Invalid or expired OAuth state",
        )

    if error:
        raise HTTPException(
            status_code=400,
            detail="LinkedIn authorization was not completed",
        )

    if not code:
        raise HTTPException(
            status_code=400,
            detail="LinkedIn authorization code is missing",
        )

    client_id, client_secret, redirect_uri, _ = get_config()

    try:
        with httpx.Client(timeout=20.0) as client:
            response = client.post(
                TOKEN_URL,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": redirect_uri,
                    "client_id": client_id,
                    "client_secret": client_secret,
                },
            )
            response.raise_for_status()
            token_response = response.json()

        save_token(token_response)

    except (httpx.HTTPError, ValueError, RuntimeError):
        raise HTTPException(
            status_code=502,
            detail="LinkedIn token exchange or storage failed",
        ) from None

    return PlainTextResponse(
        "LinkedIn authorization successful. "
        "Return to MCP Inspector and run get_my_profile."
    )
