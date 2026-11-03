"""Local account namespaces and explicit, backed-up SQLite schema migration.

Namespaces are storage owners, not verified LinkedIn identities. This module
does not access OAuth credentials or perform any external network operation.
"""

import argparse
import hashlib
import os
import sqlite3
from contextlib import closing, contextmanager
from pathlib import Path
from typing import Iterator

SCHEMA_VERSION = 1
DEFAULT_ACCOUNT_ID = "local-single-user"


class WorkflowError(ValueError):
    """A safe workflow failure carrying a stable machine-readable code."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def account_id() -> str:
    """Resolve the server-controlled namespace, never a tool-supplied owner."""
    value = os.getenv("LINKEDIN_LOCAL_ACCOUNT_ID", DEFAULT_ACCOUNT_ID).strip()
    if not value or len(value) > 128:
        raise WorkflowError("INVALID_ACCOUNT", "Invalid local account configuration")
    return value


def database_path() -> Path:
    """Resolve storage without reading or printing private environment files."""
    return Path(os.getenv("LINKEDIN_DRAFT_DB", "data/linkedin_drafts.db"))


@contextmanager
def connect_db() -> Iterator[sqlite3.Connection]:
    """Open a WAL connection; callers explicitly begin read/write transactions."""
    path = database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA busy_timeout=10000")
        conn.execute("PRAGMA journal_mode=WAL")
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


BASE_TABLES = (
    """CREATE TABLE IF NOT EXISTS drafts (
        id TEXT PRIMARY KEY, content TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'draft', revision INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL, updated_at TEXT NOT NULL)""",
    """CREATE TABLE IF NOT EXISTS publish_approvals (
        id TEXT PRIMARY KEY, draft_id TEXT NOT NULL, draft_revision INTEGER NOT NULL,
        content_snapshot TEXT NOT NULL, content_hash TEXT NOT NULL,
        status TEXT NOT NULL CHECK(status IN
            ('PENDING','APPROVED','REJECTED','EXPIRED','CONSUMED')),
        created_at TEXT NOT NULL, expires_at TEXT NOT NULL,
        decided_at TEXT, consumed_at TEXT)""",
)


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    """Inspect only one of the fixed application table identifiers."""
    if table not in {"drafts", "publish_approvals"}:
        raise ValueError("Unknown schema table")
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}


def _install(conn: sqlite3.Connection, legacy_owner: str) -> None:
    """Install v1 additively within the caller's exclusive write transaction."""
    for statement in BASE_TABLES:
        conn.execute(statement)
    conn.execute("ALTER TABLE drafts ADD COLUMN account_id TEXT")
    conn.execute("ALTER TABLE drafts ADD COLUMN content_sha256 TEXT")
    conn.execute("ALTER TABLE publish_approvals ADD COLUMN account_id TEXT")
    conn.execute("ALTER TABLE publish_approvals ADD COLUMN canonical_payload TEXT")
    conn.execute("ALTER TABLE publish_approvals ADD COLUMN payload_sha256 TEXT")
    conn.execute("UPDATE drafts SET account_id = ?", (legacy_owner,))
    conn.execute("UPDATE publish_approvals SET account_id = ?", (legacy_owner,))
    for row in conn.execute("SELECT id, content FROM drafts").fetchall():
        digest = hashlib.sha256(row[1].encode("utf-8")).hexdigest()
        conn.execute("UPDATE drafts SET content_sha256 = ? WHERE id = ?", (digest, row[0]))
    conn.execute("""CREATE TABLE draft_revisions (
        draft_id TEXT NOT NULL, account_id TEXT NOT NULL, revision INTEGER NOT NULL,
        content TEXT NOT NULL, content_sha256 TEXT NOT NULL, created_at TEXT NOT NULL,
        PRIMARY KEY(draft_id, account_id, revision))""")
    conn.execute("""INSERT INTO draft_revisions
        SELECT id, account_id, revision, content, content_sha256, updated_at FROM drafts""")
    statements = (
        "CREATE INDEX IF NOT EXISTS idx_drafts_updated ON drafts(updated_at DESC)",
        "CREATE INDEX idx_drafts_account ON drafts(account_id, updated_at DESC)",
        "CREATE INDEX idx_approvals_account ON publish_approvals(account_id, id)",
        "CREATE TABLE schema_migrations (version INTEGER PRIMARY KEY)",
        "INSERT INTO schema_migrations VALUES (1)",
        """CREATE TRIGGER revisions_no_update BEFORE UPDATE ON draft_revisions
            BEGIN SELECT RAISE(ABORT, 'Immutable revision'); END""",
        """CREATE TRIGGER revisions_no_delete BEFORE DELETE ON draft_revisions
            BEGIN SELECT RAISE(ABORT, 'Immutable revision'); END""",
        """CREATE TRIGGER approval_snapshot_immutable BEFORE UPDATE OF
            id, draft_id, draft_revision, content_snapshot, content_hash, account_id,
            canonical_payload, payload_sha256, created_at, expires_at ON publish_approvals
            BEGIN SELECT RAISE(ABORT, 'Immutable approval snapshot'); END""",
        """CREATE TRIGGER approval_transition BEFORE UPDATE OF status ON publish_approvals
            WHEN NOT (OLD.status = NEW.status OR
                (OLD.status = 'PENDING' AND NEW.status IN ('APPROVED','REJECTED','EXPIRED')) OR
                (OLD.status = 'APPROVED' AND NEW.status = 'EXPIRED'))
            BEGIN SELECT RAISE(ABORT, 'Invalid approval transition'); END""",
        """CREATE TRIGGER draft_account_required BEFORE INSERT ON drafts
            WHEN NEW.account_id IS NULL OR NEW.account_id = '' OR NEW.content_sha256 IS NULL
            BEGIN SELECT RAISE(ABORT, 'Draft binding required'); END""",
        """CREATE TRIGGER draft_owner_immutable BEFORE UPDATE OF id, account_id ON drafts
            BEGIN SELECT RAISE(ABORT, 'Immutable draft owner'); END""",
        """CREATE TRIGGER approval_binding_required BEFORE INSERT ON publish_approvals
            WHEN NEW.account_id IS NULL OR NEW.account_id = '' OR
                NEW.canonical_payload IS NULL OR NEW.payload_sha256 IS NULL
            BEGIN SELECT RAISE(ABORT, 'Approval binding required'); END""",
    )
    for statement in statements:
        conn.execute(statement)


def initialize_storage() -> None:
    """Create empty storage; refuse implicit migration of existing legacy data."""
    with connect_db() as conn:
        conn.execute("BEGIN IMMEDIATE")
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if "schema_migrations" in tables:
            versions = conn.execute("SELECT version FROM schema_migrations ORDER BY version").fetchall()
            if [row[0] for row in versions] != [SCHEMA_VERSION]:
                raise WorkflowError("SCHEMA_UNSUPPORTED", "Unsupported storage schema version")
            return
        if tables:
            raise WorkflowError("MIGRATION_REQUIRED", "Legacy storage requires explicit backed-up migration; see docs/GATE_B.md")
        _install(conn, account_id())


def migrate_legacy_database(path: Path, backup: Path, legacy_account_id: str) -> None:
    """Back up and upgrade the audited legacy schema while the service is stopped.

    Existing decisions are retained for history but remain unbound and unusable.
    No legacy approval is silently promoted into a bound approval.
    """
    if not legacy_account_id.strip() or len(legacy_account_id) > 128:
        raise WorkflowError("INVALID_ACCOUNT", "Explicit legacy account namespace required")
    conn = sqlite3.connect(path.resolve().as_uri() + "?mode=rw", uri=True, timeout=10)
    try:
        expected_drafts = {"id", "content", "status", "revision", "created_at", "updated_at"}
        expected_approvals = {"id", "draft_id", "draft_revision", "content_snapshot", "content_hash",
                              "status", "created_at", "expires_at", "decided_at", "consumed_at"}
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not tables <= {"drafts", "publish_approvals"} or "drafts" not in tables:
            raise WorkflowError("SCHEMA_UNSUPPORTED", "Expected the audited legacy schema")
        if _columns(conn, "drafts") != expected_drafts or (
            "publish_approvals" in tables and _columns(conn, "publish_approvals") != expected_approvals
        ):
            raise WorkflowError("SCHEMA_UNSUPPORTED", "Legacy columns differ from the audited schema")
        backup.parent.mkdir(parents=True, exist_ok=True)
        # Exclusive creation prevents accidental overwrite, including of the source DB.
        with backup.open("xb"):
            pass
        with closing(sqlite3.connect(backup)) as destination:
            conn.backup(destination)
        conn.execute("BEGIN IMMEDIATE")
        _install(conn, legacy_account_id.strip())
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def main() -> None:
    """Provide an explicit offline migration command; never auto-approve writes."""
    parser = argparse.ArgumentParser(description="Migrate local storage with the service stopped")
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--backup", type=Path, required=True)
    parser.add_argument("--legacy-account-id", required=True)
    args = parser.parse_args()
    migrate_legacy_database(args.database, args.backup, args.legacy_account_id)
    print("Migration completed; legacy approvals require fresh review. No LinkedIn request made.")


if __name__ == "__main__":
    main()
