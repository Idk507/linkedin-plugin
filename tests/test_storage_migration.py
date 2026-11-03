"""Real SQLite migration tests, always using temporary offline databases."""

import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from linkedin_mcp import approvals, drafts
from linkedin_mcp.storage import WorkflowError, migrate_legacy_database

LEGACY_DRAFTS = """CREATE TABLE drafts (
    id TEXT PRIMARY KEY, content TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'draft',
    revision INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)"""
LEGACY_APPROVALS = """CREATE TABLE publish_approvals (
    id TEXT PRIMARY KEY, draft_id TEXT NOT NULL, draft_revision INTEGER NOT NULL,
    content_snapshot TEXT NOT NULL, content_hash TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('PENDING','APPROVED','REJECTED','EXPIRED','CONSUMED')),
    created_at TEXT NOT NULL, expires_at TEXT NOT NULL, decided_at TEXT, consumed_at TEXT)"""


@pytest.fixture
def legacy_database(tmp_path, monkeypatch):
    """Reproduce the audited schema and a historical approved review."""
    path = tmp_path / "legacy.db"
    monkeypatch.setenv("LINKEDIN_DRAFT_DB", str(path))
    monkeypatch.setenv("LINKEDIN_LOCAL_ACCOUNT_ID", "legacy-owner")
    now = datetime.now(timezone.utc)
    with sqlite3.connect(path) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute(LEGACY_DRAFTS)
        conn.execute(LEGACY_APPROVALS)
        conn.execute("INSERT INTO drafts VALUES (?, ?, 'draft', 3, ?, ?)",
                     ("draft-id", "Existing content", now.isoformat(), now.isoformat()))
        conn.execute("INSERT INTO publish_approvals VALUES (?, ?, 3, ?, ?, 'APPROVED', ?, ?, ?, NULL)",
                     ("approval-id", "draft-id", "Existing content", approvals.content_digest("Existing content"),
                      now.isoformat(), (now + timedelta(minutes=15)).isoformat(), now.isoformat()))
    return path


def test_legacy_requires_explicit_migration(legacy_database):
    """Opening old data cannot silently assign ownership or rewrite approvals."""
    with pytest.raises(WorkflowError) as error:
        drafts.list_drafts()
    assert error.value.code == "MIGRATION_REQUIRED"
    with sqlite3.connect(legacy_database) as conn:
        assert "account_id" not in {row[1] for row in conn.execute("PRAGMA table_info(drafts)")}


def test_backup_and_migration_preserve_data(legacy_database, tmp_path, monkeypatch):
    """Upgrade is additive; backup remains usable by the original code."""
    backup = tmp_path / "backup.db"
    migrate_legacy_database(legacy_database, backup, "legacy-owner")
    with sqlite3.connect(backup) as conn:
        assert conn.execute("SELECT content, revision FROM drafts").fetchone() == ("Existing content", 3)
        assert conn.execute("SELECT status FROM publish_approvals").fetchone() == ("APPROVED",)
        assert "account_id" not in {row[1] for row in conn.execute("PRAGMA table_info(drafts)")}
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    draft = drafts.get_draft("draft-id")
    assert draft["revision"] == 3
    assert draft["content"] == "Existing content"
    assert approvals.get_approval("approval-id")["status"] == "APPROVED"
    with pytest.raises(WorkflowError) as error:
        approvals.dry_run_publish("approval-id")
    assert error.value.code == "APPROVAL_REVIEW_REQUIRED"
    fresh = approvals.create_approval("draft-id")
    approvals.decide_approval(fresh["id"], True)
    assert approvals.dry_run_publish(fresh["id"])["ready_for_live_publish"] is False
    monkeypatch.setenv("LINKEDIN_LOCAL_ACCOUNT_ID", "different-owner")
    assert drafts.list_drafts() == []


def test_migration_never_overwrites_backup(legacy_database, tmp_path):
    """A reserved backup destination fails before any schema update."""
    backup = tmp_path / "backup.db"
    backup.write_bytes(b"keep")
    with pytest.raises(FileExistsError):
        migrate_legacy_database(legacy_database, backup, "legacy-owner")
    assert backup.read_bytes() == b"keep"
    with sqlite3.connect(legacy_database) as conn:
        assert "account_id" not in {row[1] for row in conn.execute("PRAGMA table_info(drafts)")}


def test_unrecognized_schema_is_not_migrated(legacy_database, tmp_path):
    """Reject drift instead of guessing a migration."""
    with sqlite3.connect(legacy_database) as conn:
        conn.execute("ALTER TABLE drafts ADD COLUMN surprise TEXT")
    backup = tmp_path / "backup.db"
    with pytest.raises(WorkflowError) as error:
        migrate_legacy_database(legacy_database, backup, "legacy-owner")
    assert error.value.code == "SCHEMA_UNSUPPORTED"
    assert not backup.exists()


def test_failed_migration_rolls_back(legacy_database, tmp_path, monkeypatch):
    """Partial DDL never leaks out of a failed migration transaction."""
    from linkedin_mcp import storage

    install = storage._install

    def fail_after_install(conn, owner):
        install(conn, owner)
        raise RuntimeError("Simulated failure")

    monkeypatch.setattr(storage, "_install", fail_after_install)
    backup = tmp_path / "backup.db"
    with pytest.raises(RuntimeError, match="Simulated failure"):
        migrate_legacy_database(legacy_database, backup, "legacy-owner")
    with sqlite3.connect(legacy_database) as conn:
        assert "account_id" not in {row[1] for row in conn.execute("PRAGMA table_info(drafts)")}
        assert conn.execute("SELECT status FROM publish_approvals").fetchone() == ("APPROVED",)
    assert backup.exists()


def test_fresh_initialization_is_idempotent(tmp_path, monkeypatch):
    """A current schema is never migrated or reinstalled on repeated opens."""
    monkeypatch.setenv("LINKEDIN_DRAFT_DB", str(tmp_path / "new.db"))
    draft = drafts.create_draft("Keep")
    drafts.init_db()
    drafts.init_db()
    assert drafts.get_draft(draft["id"])["content"] == "Keep"
    with drafts.connect_db() as conn:
        assert conn.execute("SELECT version FROM schema_migrations").fetchall()[0][0] == 1


def test_schema_state_transition_guards(tmp_path, monkeypatch):
    """Terminal local review states cannot be revived with ordinary SQL updates."""
    monkeypatch.setenv("LINKEDIN_DRAFT_DB", str(tmp_path / "new.db"))
    approval = approvals.create_approval(drafts.create_draft("Reject")["id"])
    approvals.decide_approval(approval["id"], False)
    with drafts.connect_db() as conn:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("UPDATE publish_approvals SET status = 'APPROVED'")
