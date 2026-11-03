
"""Entry point for the LinkedIn MCP server."""

import logging

from mcp.server import MCPServer

from linkedin_mcp.capabilities import get_capability_manifest
from linkedin_mcp.credential_store import load_token
from linkedin_mcp.linkedin_client import (
    LinkedInAPIError,
    get_my_profile as fetch_linkedin_profile,
)
from linkedin_mcp.author_identity import diagnose_author_identity
from linkedin_mcp.storage import WorkflowError

from linkedin_mcp.approvals import (
    create_approval,
    get_approval,
    dry_run_publish,
)


from linkedin_mcp.drafts import (
    create_draft,
    get_draft,
    list_drafts,
    update_draft,
    delete_draft,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    handlers=[logging.StreamHandler()],
)

logger = logging.getLogger(__name__)

mcp = MCPServer("LinkedIn MCP Assistant")


def _local_error(exc: ValueError | OSError) -> dict:
    """Expose safe local workflow errors with stable codes to MCP clients."""
    return {
        "success": False,
        "error": str(exc),
        "code": exc.code if isinstance(exc, WorkflowError) else "LOCAL_OPERATION_FAILED",
    }


@mcp.tool()
def health_check() -> dict[str, str]:
    """Return the current health of the local MCP process.

    This tool does not perform an external LinkedIn request.
    """
    return {
        "service": "linkedin-mcp",
        "status": "healthy",
        "phase": "foundation",
    }


@mcp.tool()
def get_account_capabilities() -> dict:
    """Return features supported by the current application state.

    Features that require LinkedIn authorization remain disabled
    until the OAuth integration is implemented and validated.
    """
    try:
        return get_capability_manifest()
    except Exception:
        logger.exception("Capability manifest retrieval failed")
        raise RuntimeError(
            "Unable to retrieve account capabilities"
        ) from None



@mcp.tool()
def get_linkedin_connection_status() -> dict:
    """Report whether usable local LinkedIn credentials exist."""
    try:
        credential = load_token()
    except RuntimeError:
        logger.exception("LinkedIn credential read failed")
        return {
            "connected": False,
            "reason": "Local credential storage error",
        }

    if not credential:
        return {
            "connected": False,
            "reason": "Not connected or authorization expired",
        }

    return {
        "connected": True,
        "granted_scope": credential.get("scope", ""),
    }


@mcp.tool()
def get_my_profile() -> dict:
    """Read the authenticated personal LinkedIn profile."""
    try:
        return fetch_linkedin_profile()

    except LinkedInAPIError as exc:
        logger.warning("LinkedIn profile retrieval failed")
        return {
            "success": False,
            "error": str(exc),
        }


@mcp.tool()
def verify_linkedin_connection() -> dict:
    """Verify authentication against the real LinkedIn UserInfo API.

    Returns a minimal result without exposing access tokens,
    email addresses, or unnecessary personally identifiable data.
    """
    try:
        profile = fetch_linkedin_profile()

        return {
            "connected": True,
            "verified": True,
            "provider": "linkedin",
            "profile_id_present": bool(profile.get("id")),
            "message": "LinkedIn API authentication successful",
        }

    except LinkedInAPIError as exc:
        logger.warning(
            "LinkedIn connection verification failed: %s",
            type(exc).__name__,
        )

        return {
            "connected": False,
            "verified": False,
            "provider": "linkedin",
            "message": "LinkedIn API verification failed",
        }


@mcp.tool()
def create_linkedin_draft(content: str) -> dict:
    """Save a LinkedIn post draft locally without publishing it."""
    try:
        return create_draft(content)
    except (ValueError, OSError) as exc:
        return _local_error(exc)


@mcp.tool()
def get_linkedin_draft(draft_id: str) -> dict:
    """Retrieve one local LinkedIn draft."""
    try:
        return get_draft(draft_id)
    except ValueError as exc:
        return _local_error(exc)


@mcp.tool()
def list_linkedin_drafts(limit: int = 20) -> list[dict]:
    """List local drafts without accessing LinkedIn's API."""
    return list_drafts(limit)


@mcp.tool()
def update_linkedin_draft(
    draft_id: str,
    content: str,
    expected_revision: int,
) -> dict:
    """Update an existing draft if its revision has not changed."""
    try:
        return update_draft(
            draft_id,
            content,
            expected_revision,
        )
    except ValueError as exc:
        return _local_error(exc)


@mcp.tool()
def delete_linkedin_draft(draft_id: str) -> dict:
    """Delete a local draft without deleting a LinkedIn post."""
    try:
        return delete_draft(draft_id)
    except ValueError as exc:
        return _local_error(exc)


@mcp.tool()
def request_publish_approval(draft_id: str) -> dict:
    """Request independent human review for a local draft.

    This operation never publishes externally.
    """
    try:
        return create_approval(draft_id)
    except (ValueError, OSError) as exc:
        logger.warning("Approval request failed: %s", type(exc).__name__)
        return _local_error(exc)


@mcp.tool()
def get_publish_approval_status(approval_id: str) -> dict:
    """Read approval status, persisting expiry without making a decision."""
    try:
        return get_approval(approval_id)
    except ValueError as exc:
        return _local_error(exc)


@mcp.tool()
def preview_approved_publish(approval_id: str) -> dict:
    """Validate approval and preview an offline publish action.

    No network request to LinkedIn is performed.
    """
    try:
        return dry_run_publish(approval_id)
    except ValueError as exc:
        return _local_error(exc)



@mcp.tool()
def check_linkedin_author_identity() -> dict:
    """Check access to the authorized LinkedIn Person identity.

    Read-only: never creates, modifies, or deletes a post.
    """
    return diagnose_author_identity()




if __name__ == "__main__":
    mcp.run(transport="stdio")
