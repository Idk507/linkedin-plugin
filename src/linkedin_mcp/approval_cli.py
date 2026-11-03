
"""Temporary local offline review CLI; not authenticated write authorization."""

import argparse
import json
import sys

from linkedin_mcp.approvals import (
    decide_approval,
    get_approval,
)


def main() -> int:
    """Review and approve an exact LinkedIn draft snapshot."""
    parser = argparse.ArgumentParser(
        description="Review a LinkedIn publishing request"
    )
    parser.add_argument(
        "approval_id",
        help="ID of the publishing approval request",
    )

    args = parser.parse_args()

    try:
        approval = get_approval(args.approval_id)

        if approval["status"] != "PENDING":
            print(f"Approval status: {approval['status']}")
            return 1

        print("\nLINKEDIN OFFLINE REVIEW (no live authorization)")
        print("=" * 60)
        print(f"Draft: {approval['draft_id']}")
        print(f"Revision: {approval['draft_revision']}")
        print(f"Expires: {approval['expires_at']}")
        print(f"SHA-256: {approval['content_hash']}")
        print(f"Local account: {approval['account_id']}")
        print(f"Payload SHA-256: {approval['payload_sha256']}")
        print("Author: UNVERIFIED | Target: LOCAL_OFFLINE")
        print("Visibility: PUBLIC | Distribution: MAIN_FEED")
        if not approval["canonical_payload"]:
            print("Legacy approval requires a new review request")
            return 1
        print("Exact canonical review payload:")
        print(approval["canonical_payload"])
        print("=" * 60)
        print(approval["content_snapshot"])
        print("=" * 60)

        decision = input(
            "Approve this exact content? Type APPROVE: "
        ).strip()

        # Exact confirmation prevents accidental acceptance.
        approved = decision == "APPROVE"

        result = decide_approval(
            args.approval_id,
            approve=approved,
        )

        print(
            json.dumps(
                {
                    "approval_id": result["id"],
                    "status": result["status"],
                },
                indent=2,
            )
        )

        return 0 if approved else 1

    except (ValueError, OSError) as exc:
        print(f"Approval failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
