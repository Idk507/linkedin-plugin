"""Read-only author diagnostics and an offline, fail-closed identity resolver.

No result from this gate supplies verified authorization for publication.
"""

import re
from dataclasses import dataclass
from enum import Enum

import httpx

from linkedin_mcp.credential_store import load_token
from linkedin_mcp.storage import account_id


class AuthorState(str, Enum):
    """Identity lifecycle; VERIFIED is reserved for a future approved binding."""

    UNVERIFIED = 'UNVERIFIED'
    VERIFIED = 'VERIFIED'
    UNAVAILABLE = 'UNAVAILABLE'
    EXPIRED = 'EXPIRED'


@dataclass(frozen=True)
class AuthorResolution:
    """Safe status without a token, subject identifier or guessed Person URN."""

    state: AuthorState
    reason_code: str
    reason: str

    @property
    def available(self) -> bool:
        """Live author authorization is deliberately unavailable in Gate C."""
        return False

    def as_dict(self) -> dict[str, str | bool | int]:
        """Represent status for the existing MCP diagnostic tool."""
        return {
            'available': self.available,
            'identity_state': self.state.value,
            'reason_code': self.reason_code,
            'reason': self.reason,
            'ready_for_live_publish': False,
        }


class AuthorResolver:
    """Evaluate synthetic/read-only evidence without network or credential I/O.

    Neither a local namespace nor equal-looking OIDC/profile identifiers proves
    that the authorized LinkedIn author is bound to the active account. There
    is intentionally no VERIFIED transition or Person-URN construction here.
    """

    def resolve(
        self, *, account_id: str, oidc_subject: str | None = None,
        profile_id: str | None = None, credential_expired: bool = False,
    ) -> AuthorResolution:
        """Return a fail-closed identity status from offline evidence."""
        if not account_id.strip():
            return AuthorResolution(AuthorState.UNAVAILABLE, 'ACCOUNT_UNAVAILABLE',
                                    'The local account namespace is unavailable')
        if credential_expired:
            return AuthorResolution(AuthorState.EXPIRED, 'CREDENTIAL_EXPIRED',
                                    'LinkedIn authorization has expired')
        if profile_id:
            return AuthorResolution(AuthorState.UNVERIFIED, 'ACCOUNT_BINDING_UNVERIFIED',
                                    'Profile endpoint returned an ID; durable account and author binding is not verified')
        if oidc_subject:
            return AuthorResolution(AuthorState.UNVERIFIED, 'AUTHOR_UNVERIFIED',
                                    'OIDC subject is not established as a Posts API Person URN')
        return AuthorResolution(AuthorState.UNAVAILABLE, 'AUTHOR_UNAVAILABLE',
                                'No authorized author evidence is available')


def _unavailable(code: str, reason: str) -> dict[str, str | bool | int]:
    """Build a sanitized failure response without including exception details."""
    return AuthorResolution(AuthorState.UNAVAILABLE, code, reason).as_dict()


def diagnose_author_identity(
    *, transport: httpx.BaseTransport | None = None,
) -> dict[str, str | bool | int]:
    """Probe the existing authorized GET endpoint, never a publishing endpoint.

    Transport injection supports fully offline HTTP tests. Endpoint availability
    is distinct from verified identity. A successful probe alone cannot make
    an author available for publication. This does not persist personal data.
    """
    try:
        credential = load_token()
    except Exception:
        # Keyring backends expose different error types and potentially private
        # details; none of those exception strings belong in an MCP response.
        return _unavailable('CREDENTIAL_UNAVAILABLE', 'Local LinkedIn credentials are unavailable')
    if not credential:
        return _unavailable('NOT_AUTHENTICATED', 'LinkedIn authorization is unavailable or expired')

    try:
        owner = account_id()
        token = credential.get('access_token')
        if not isinstance(token, str) or not token:
            return _unavailable('CREDENTIAL_UNAVAILABLE', 'Local LinkedIn credentials are unavailable')
        with httpx.Client(timeout=15.0, transport=transport) as client:
            response = client.get(
                'https://api.linkedin.com/v2/me',
                headers={'Authorization': f'Bearer {token}',
                         'X-Restli-Protocol-Version': '2.0.0', 'Accept': 'application/json'},
            )
        status = response.status_code
        if not 200 <= status < 300:
            codes = {401: 'NOT_AUTHENTICATED', 403: 'UPSTREAM_FORBIDDEN', 429: 'RATE_LIMITED'}
            result = _unavailable(codes.get(status, 'UPSTREAM_UNAVAILABLE'),
                                  'Current-member Profile API authorization or response is unavailable')
            result.update(status_code=status, endpoint_available=False)
            return result
        profile = response.json()
        member_id = profile.get('id') if isinstance(profile, dict) else None
        if not isinstance(member_id, str) or re.fullmatch(r'[A-Za-z0-9_-]+', member_id) is None:
            return _unavailable('MALFORMED_RESPONSE', 'No valid Profile API Person ID returned')
        result = AuthorResolver().resolve(account_id=owner, profile_id=member_id).as_dict()
        result.update(endpoint_available=True, status_code=status)
        return result
    except (httpx.HTTPError, ValueError, KeyError):
        return _unavailable('UPSTREAM_UNAVAILABLE', 'Author identity diagnostic could not be completed')
