
"""Tests for local LinkedIn draft CRUD operations."""

import pytest

from linkedin_mcp import drafts


@pytest.fixture(autouse=True)
def isolated_database(tmp_path, monkeypatch):
    """Use a fresh SQLite database for every test."""
    monkeypatch.setenv(
        "LINKEDIN_DRAFT_DB",
        str(tmp_path / "drafts.db"),
    )


def test_create_and_retrieve():
    """Verify that new drafts can be persisted and retrieved."""
    created = drafts.create_draft("My first LinkedIn MCP post")
    retrieved = drafts.get_draft(created["id"])

    assert retrieved["content"] == "My first LinkedIn MCP post"
    assert retrieved["revision"] == 1


def test_list_drafts():
    """Verify that saved drafts appear in listings."""
    drafts.create_draft("Draft one")
    drafts.create_draft("Draft two")

    assert len(drafts.list_drafts()) == 2


def test_update_draft():
    """Verify that an edit increments the revision."""
    created = drafts.create_draft("Original content")

    updated = drafts.update_draft(
        created["id"],
        "Updated content",
        expected_revision=1,
    )

    assert updated["content"] == "Updated content"
    assert updated["revision"] == 2


def test_revision_conflict():
    """Reject updates made using stale revision numbers."""
    created = drafts.create_draft("Original content")

    drafts.update_draft(
        created["id"],
        "First edit",
        expected_revision=1,
    )

    with pytest.raises(ValueError, match="revision conflict"):
        drafts.update_draft(
            created["id"],
            "Conflicting edit",
            expected_revision=1,
        )


def test_delete_draft():
    """Verify deletion removes the local draft."""
    created = drafts.create_draft("Temporary draft")

    result = drafts.delete_draft(created["id"])

    assert result["deleted"] is True

    with pytest.raises(ValueError, match="not found"):
        drafts.get_draft(created["id"])


def test_empty_content_rejected():
    """Reject whitespace-only content."""
    with pytest.raises(ValueError):
        drafts.create_draft("   ")

