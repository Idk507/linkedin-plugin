"""SQLite-backed drafts scoped to a server-controlled local namespace."""

import hashlib
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any

# Preserve existing public imports.
from linkedin_mcp.storage import (
    WorkflowError, account_id, connect_db, database_path, initialize_storage,
)


def init_db() -> None:
    """Create new storage; require explicit migration for legacy data."""
    initialize_storage()


def content_digest(content: str) -> str:
    """Hash exact UTF-8 bytes without normalization."""
    return hashlib.sha256(content.encode('utf-8')).hexdigest()


def validate_content(content: str) -> str:
    """Preserve trimming and the existing 3000-character limit."""
    if not isinstance(content, str):
        raise WorkflowError('INVALID_CONTENT', 'Content must be a string')
    content = content.strip()
    if not content:
        raise WorkflowError('INVALID_CONTENT', 'Draft content cannot be empty')
    if len(content) > 3000:
        raise WorkflowError('INVALID_CONTENT', 'Draft exceeds the configured 3000-character limit')
    return content


def _get_draft(conn: sqlite3.Connection, draft_id: str, owner: str) -> dict[str, Any]:
    """Read an owned draft within the caller's transaction."""
    row = conn.execute('SELECT * FROM drafts WHERE id = ? AND account_id = ?', (draft_id, owner)).fetchone()
    if row is None:
        raise WorkflowError('DRAFT_NOT_FOUND', 'Draft not found')
    return dict(row)


def _record_revision(conn: sqlite3.Connection, draft: dict[str, Any]) -> None:
    """Append history atomically with its draft mutation."""
    conn.execute('''INSERT INTO draft_revisions
        (draft_id, account_id, revision, content, content_sha256, created_at)
        VALUES (?, ?, ?, ?, ?, ?)''',
        (draft['id'], draft['account_id'], draft['revision'], draft['content'],
         draft['content_sha256'], draft['updated_at']))


def create_draft(content: str) -> dict[str, Any]:
    """Create a draft and its immutable first revision atomically."""
    content = validate_content(content)
    owner = account_id()
    init_db()
    now = datetime.now(timezone.utc).isoformat()
    draft: dict[str, Any] = {
        'id': str(uuid.uuid4()), 'account_id': owner, 'content': content,
        'content_sha256': content_digest(content), 'status': 'draft', 'revision': 1,
        'created_at': now, 'updated_at': now,
    }
    with connect_db() as conn:
        conn.execute('BEGIN IMMEDIATE')
        conn.execute('''INSERT INTO drafts
            (id, account_id, content, content_sha256, status, revision, created_at, updated_at)
            VALUES (:id, :account_id, :content, :content_sha256, :status, :revision, :created_at, :updated_at)''', draft)
        _record_revision(conn, draft)
    return draft


def get_draft(draft_id: str) -> dict[str, Any]:
    """Retrieve a draft within the configured namespace."""
    owner = account_id()
    init_db()
    with connect_db() as conn:
        return _get_draft(conn, draft_id, owner)


def list_drafts(limit: int = 20) -> list[dict[str, Any]]:
    """List only drafts in the configured local namespace."""
    if not 1 <= limit <= 100:
        raise WorkflowError('INVALID_LIMIT', 'Limit must be between 1 and 100')
    owner = account_id()
    init_db()
    with connect_db() as conn:
        rows = conn.execute('''SELECT * FROM drafts WHERE account_id = ?
            ORDER BY updated_at DESC, id LIMIT ?''', (owner, limit)).fetchall()
    return [dict(row) for row in rows]


def update_draft(draft_id: str, content: str, expected_revision: int) -> dict[str, Any]:
    """Update an owned draft and append its next immutable revision atomically."""
    content = validate_content(content)
    owner = account_id()
    init_db()
    now = datetime.now(timezone.utc).isoformat()
    with connect_db() as conn:
        conn.execute('BEGIN IMMEDIATE')
        cursor = conn.execute('''UPDATE drafts SET content = ?, content_sha256 = ?,
            revision = revision + 1, updated_at = ?
            WHERE id = ? AND account_id = ? AND revision = ? AND status = 'draft' ''',
            (content, content_digest(content), now, draft_id, owner, expected_revision))
        if cursor.rowcount != 1:
            raise WorkflowError('DRAFT_REVISION_CONFLICT', 'Draft not found or revision conflict')
        draft = _get_draft(conn, draft_id, owner)
        _record_revision(conn, draft)
    return draft


def delete_draft(draft_id: str) -> dict[str, Any]:
    """Delete an owned draft, preserving revision and approval history."""
    owner = account_id()
    init_db()
    with connect_db() as conn:
        conn.execute('BEGIN IMMEDIATE')
        cursor = conn.execute("DELETE FROM drafts WHERE id = ? AND account_id = ? AND status = 'draft'", (draft_id, owner))
        if cursor.rowcount != 1:
            raise WorkflowError('DRAFT_NOT_FOUND', 'Draft not found')
    return {'deleted': True, 'draft_id': draft_id}
