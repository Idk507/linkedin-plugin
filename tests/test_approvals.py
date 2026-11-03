
"""Unit tests for LinkedIn publishing approvals."""

import pytest

from linkedin_mcp import approvals, drafts


@pytest.fixture(autouse=True)
def isolated_storage(tmp_path, monkeypatch):
    """Use isolated SQLite storage for every test."""
    monkeypatch.setenv(
        "LINKEDIN_DRAFT_DB",
        str(tmp_path / "test.db"),
    )


def test_pending_cannot_publish():
    """An unapproved request must fail validation."""
    draft = drafts.create_draft("Test post")
    approval = approvals.create_approval(draft["id"])

    assert approval["status"] == "PENDING"

    with pytest.raises(ValueError):
        approvals.dry_run_publish(approval["id"])


def test_approved_dry_run():
    """An approved draft generates an offline preview."""
    draft = drafts.create_draft("Test post")
    approval = approvals.create_approval(draft["id"])

    approvals.decide_approval(approval["id"], True)

    result = approvals.dry_run_publish(approval["id"])

    assert result["dry_run"] is True
    assert result["ready_for_live_publish"] is False
    assert result["preview"]["commentary"] == "Test post"


def test_rejected_cannot_publish():
    """A rejected approval cannot pass the publish gate."""
    draft = drafts.create_draft("Test post")
    approval = approvals.create_approval(draft["id"])

    approvals.decide_approval(approval["id"], False)

    with pytest.raises(ValueError):
        approvals.dry_run_publish(approval["id"])


def test_draft_change_invalidates_approval():
    """Changes after approval invalidate the approved snapshot."""
    draft = drafts.create_draft("First version")
    approval = approvals.create_approval(draft["id"])

    approvals.decide_approval(approval["id"], True)

    drafts.update_draft(
        draft["id"],
        "Second version",
        expected_revision=1,
    )

    with pytest.raises(ValueError):
        approvals.dry_run_publish(approval["id"])


def test_duplicate_decision_rejected():
    """An approval cannot be decided twice."""
    draft = drafts.create_draft("Test post")
    approval = approvals.create_approval(draft["id"])

    approvals.decide_approval(approval["id"], True)

    with pytest.raises(ValueError):
        approvals.decide_approval(approval["id"], True)

