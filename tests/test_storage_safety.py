"""Offline integration tests for account and approval persistence boundaries."""

import asyncio
import hashlib
import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Barrier

import pytest

from linkedin_mcp import approvals, drafts


@pytest.fixture(autouse=True)
def isolated_storage(tmp_path, monkeypatch):
    """Never touch the operator's database or configured namespace."""
    monkeypatch.setenv("LINKEDIN_DRAFT_DB", str(tmp_path / "test.db"))
    monkeypatch.setenv("LINKEDIN_LOCAL_ACCOUNT_ID", "owner-a")


def test_wrong_account_cannot_access_or_mutate(monkeypatch):
    """Knowing an ID does not grant access in a different namespace."""
    draft = drafts.create_draft("Private draft")
    approval = approvals.create_approval(draft["id"])
    monkeypatch.setenv("LINKEDIN_LOCAL_ACCOUNT_ID", "owner-b")
    assert drafts.list_drafts() == []
    operations = (
        lambda: drafts.get_draft(draft["id"]),
        lambda: drafts.update_draft(draft["id"], "Hijack", 1),
        lambda: drafts.delete_draft(draft["id"]),
        lambda: approvals.create_approval(draft["id"]),
        lambda: approvals.get_approval(approval["id"]),
        lambda: approvals.decide_approval(approval["id"], True),
        lambda: approvals.dry_run_publish(approval["id"]),
    )
    for operation in operations:
        with pytest.raises(ValueError):
            operation()
    monkeypatch.setenv("LINKEDIN_LOCAL_ACCOUNT_ID", "owner-a")
    assert drafts.get_draft(draft["id"])["content"] == "Private draft"
    assert approvals.get_approval(approval["id"])["status"] == "PENDING"


def test_canonical_payload_and_immutable_snapshots():
    """Approval binds exact Unicode bytes and revision history cannot change."""
    draft = drafts.create_draft("Café\nSecond line")
    approval = approvals.create_approval(draft["id"])
    payload = json.loads(approval["canonical_payload"])
    assert payload["account_id"] == "owner-a"
    assert payload["draft_revision"] == 1
    assert payload["commentary"] == draft["content"]
    assert payload["author_urn"] is None
    assert payload["action"] == "PUBLISH"
    assert payload["visibility"] == "PUBLIC"
    assert payload["expires_at"] == approval["expires_at"]
    assert approval["payload_sha256"] == hashlib.sha256(
        approval["canonical_payload"].encode("utf-8")
    ).hexdigest()
    with drafts.connect_db() as conn:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("UPDATE publish_approvals SET content_snapshot = 'tampered'")
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("UPDATE draft_revisions SET content = 'tampered'")
    drafts.update_draft(draft["id"], "New version", 1)
    with drafts.connect_db() as conn:
        rows = conn.execute("SELECT revision, content FROM draft_revisions ORDER BY revision").fetchall()
    assert [tuple(row) for row in rows] == [(1, draft["content"]), (2, "New version")]


@pytest.mark.parametrize("decided", [False, True])
def test_expiry_is_durable(monkeypatch, decided):
    """Expiry at the boundary commits even when a decision/preview fails."""
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    monkeypatch.setattr(approvals, "utc_now", lambda: now)
    draft = drafts.create_draft("Expires")
    approval = approvals.create_approval(draft["id"])
    if decided:
        approvals.decide_approval(approval["id"], True)
    monkeypatch.setattr(approvals, "utc_now", lambda: now + timedelta(minutes=15))
    operation = approvals.dry_run_publish if decided else lambda aid: approvals.decide_approval(aid, True)
    with pytest.raises(ValueError):
        operation(approval["id"])
    with drafts.connect_db() as conn:
        assert conn.execute("SELECT status FROM publish_approvals").fetchone()[0] == "EXPIRED"


def test_concurrent_decisions_have_one_winner():
    """Independent SQLite connections cannot both decide the same request."""
    approval = approvals.create_approval(drafts.create_draft("Concurrent")["id"])
    barrier = Barrier(2)

    def decide(value):
        barrier.wait(timeout=10)
        try:
            return approvals.decide_approval(approval["id"], value)["status"]
        except ValueError:
            return "DENIED"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(decide, [True, False]))
    assert results.count("DENIED") == 1
    assert approvals.get_approval(approval["id"])["status"] in {"APPROVED", "REJECTED"}


def test_concurrent_edits_have_one_winner():
    """Only one update can consume a particular expected revision."""
    draft = drafts.create_draft("Original")
    barrier = Barrier(2)

    def edit(content):
        barrier.wait(timeout=10)
        try:
            drafts.update_draft(draft["id"], content, 1)
            return "UPDATED"
        except ValueError:
            return "DENIED"

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(edit, ["First", "Second"])) == ["DENIED", "UPDATED"]
    assert drafts.get_draft(draft["id"])["revision"] == 2


def test_deleted_draft_cannot_be_previewed():
    """Retained approval history cannot authorize a deleted draft."""
    draft = drafts.create_draft("Delete me")
    approval = approvals.create_approval(draft["id"])
    approvals.decide_approval(approval["id"], True)
    drafts.delete_draft(draft["id"])
    with pytest.raises(ValueError):
        approvals.dry_run_publish(approval["id"])


def test_mcp_does_not_expose_account_or_decision_controls():
    """Storage scoping cannot be overridden through tool arguments."""
    from linkedin_mcp.server import mcp

    tools = asyncio.run(mcp.list_tools())
    assert len(tools) == 14
    assert not {"decide_approval", "execute_approved_publish"} & {t.name for t in tools}
    for tool in tools:
        assert "account_id" not in tool.input_schema.get("properties", {})


@pytest.mark.parametrize("field,value", [
    ("visibility", "CONNECTIONS"), ("author_urn", "urn:li:person:unverified"),
    ("target", "LINKEDIN"), ("expires_at", "2099-01-01T00:00:00+00:00"),
    ("distribution", {"feedDistribution": "NONE"}),
])
def test_changed_payload_cannot_be_previewed(field, value):
    """Even a recomputed digest cannot authorize altered targeting bytes."""
    approval = approvals.create_approval(drafts.create_draft("Bound payload")["id"])
    approvals.decide_approval(approval["id"], True)
    payload = json.loads(approval["canonical_payload"])
    payload[field] = value
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    with drafts.connect_db() as conn:
        # Simulate corruption below the trigger boundary in this temporary DB.
        conn.execute("DROP TRIGGER approval_snapshot_immutable")
        conn.execute("UPDATE publish_approvals SET canonical_payload = ?, payload_sha256 = ?",
                     (encoded, approvals.content_digest(encoded)))
    with pytest.raises(ValueError) as error:
        approvals.dry_run_publish(approval["id"])
    assert error.value.code == "APPROVAL_INTEGRITY_ERROR"


def test_changed_before_decision_is_rejected():
    """Review must validate revision again when the operator decides."""
    draft = drafts.create_draft("Before")
    approval = approvals.create_approval(draft["id"])
    drafts.update_draft(draft["id"], "After", 1)
    with pytest.raises(ValueError):
        approvals.decide_approval(approval["id"], True)
    assert approvals.get_approval(approval["id"])["status"] == "PENDING"


def test_preview_is_repeatable_and_remains_offline():
    """No claim or live readiness can be created by repeating a preview."""
    approval = approvals.create_approval(drafts.create_draft("Offline")["id"])
    approvals.decide_approval(approval["id"], True)
    first = approvals.dry_run_publish(approval["id"])
    assert approvals.dry_run_publish(approval["id"]) == first
    assert first["ready_for_live_publish"] is False
    assert approvals.get_approval(approval["id"])["consumed_at"] is None


def test_local_cli_displays_exact_binding(monkeypatch, capsys):
    """The existing CLI shows the full bound tuple before local confirmation."""
    from linkedin_mcp import approval_cli

    approval = approvals.create_approval(drafts.create_draft("CLI review")["id"])
    monkeypatch.setattr("sys.argv", ["approval_cli", approval["id"]])
    monkeypatch.setattr("builtins.input", lambda prompt: "APPROVE")
    assert approval_cli.main() == 0
    output = capsys.readouterr().out
    assert approval["canonical_payload"] in output
    assert approval["payload_sha256"] in output
    assert "no live authorization" in output
    assert approvals.get_approval(approval["id"])["status"] == "APPROVED"


def test_mcp_local_errors_include_stable_code():
    """Local workflow codes survive the existing tool wrapper boundary."""
    from linkedin_mcp import server

    result = server.get_linkedin_draft("missing")
    assert result["success"] is False
    assert result["code"] == "DRAFT_NOT_FOUND"


def test_expiry_read_does_not_change_rejection(monkeypatch):
    """Expiry cannot revive or rewrite a terminal rejection."""
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    monkeypatch.setattr(approvals, "utc_now", lambda: now)
    approval = approvals.create_approval(drafts.create_draft("Rejected")["id"])
    approvals.decide_approval(approval["id"], False)
    monkeypatch.setattr(approvals, "utc_now", lambda: now + timedelta(days=1))
    assert approvals.get_approval(approval["id"])["status"] == "REJECTED"
