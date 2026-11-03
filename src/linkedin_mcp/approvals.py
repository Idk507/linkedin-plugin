"""Immutable local approvals and transactional offline validation.

Local decisions are not authenticated authorization for an external write.
This module provides no network operation or one-time publication claim.
"""

import json
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any

from linkedin_mcp.drafts import _get_draft, content_digest
from linkedin_mcp.storage import WorkflowError, account_id, connect_db, initialize_storage

APPROVAL_TTL_MINUTES = 15


def utc_now() -> datetime:
    """Return UTC time; tests replace this boundary without sleeping."""
    return datetime.now(timezone.utc)


def init_approvals() -> None:
    """Initialize new storage or require explicit legacy migration."""
    initialize_storage()


def canonical_payload(approval: dict[str, Any]) -> str:
    """Serialize the complete offline review tuple deterministically.

    Null author and LOCAL_OFFLINE target prevent representing these bytes as
    a verified LinkedIn request body. No Unicode normalization is performed.
    """
    return json.dumps({
        'schema_version': 1, 'approval_id': approval['id'],
        'account_id': approval['account_id'], 'action': 'PUBLISH',
        'target': 'LOCAL_OFFLINE', 'author_urn': None,
        'draft_id': approval['draft_id'], 'draft_revision': approval['draft_revision'],
        'commentary': approval['content_snapshot'], 'content_sha256': approval['content_hash'],
        'visibility': 'PUBLIC', 'distribution': {'feedDistribution': 'MAIN_FEED',
            'targetEntities': [], 'thirdPartyDistributionChannels': []},
        'requested_at': approval['created_at'], 'expires_at': approval['expires_at'],
    }, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def _validate_snapshot(conn: sqlite3.Connection, approval: dict[str, Any]) -> None:
    """Reject unbound legacy requests, changed drafts and corrupt snapshots."""
    encoded = canonical_payload(approval)
    if not approval['canonical_payload'] or not approval['payload_sha256']:
        raise WorkflowError('APPROVAL_REVIEW_REQUIRED', 'Legacy approval requires a new review request')
    if approval['canonical_payload'] != encoded or approval['payload_sha256'] != content_digest(encoded):
        raise WorkflowError('APPROVAL_INTEGRITY_ERROR', 'Approval payload integrity check failed')
    draft = _get_draft(conn, approval['draft_id'], approval['account_id'])
    revision = conn.execute('''SELECT content, content_sha256 FROM draft_revisions
        WHERE draft_id = ? AND account_id = ? AND revision = ?''',
        (approval['draft_id'], approval['account_id'], approval['draft_revision'])).fetchone()
    if (draft['status'] != 'draft' or draft['revision'] != approval['draft_revision']
        or draft['content'] != approval['content_snapshot']
        or draft['content_sha256'] != approval['content_hash']
        or content_digest(draft['content']) != approval['content_hash']
        or revision is None or revision['content'] != approval['content_snapshot']
        or revision['content_sha256'] != approval['content_hash']):
        raise WorkflowError('DRAFT_REVISION_CONFLICT', 'Approved draft snapshot is no longer valid')


def _read_approval(conn: sqlite3.Connection, approval_id: str, owner: str) -> dict[str, Any]:
    """Read within the caller's server-controlled namespace."""
    row = conn.execute('SELECT * FROM publish_approvals WHERE id = ? AND account_id = ?',
                       (approval_id, owner)).fetchone()
    if row is None:
        raise WorkflowError('APPROVAL_NOT_FOUND', 'Approval not found')
    return dict(row)


def _expire(conn: sqlite3.Connection, approval: dict[str, Any], now: datetime) -> None:
    """Persist effective expiry under the transaction's write lock."""
    if approval['status'] in {'PENDING', 'APPROVED'} and datetime.fromisoformat(approval['expires_at']) <= now:
        conn.execute("UPDATE publish_approvals SET status = 'EXPIRED' WHERE id = ? AND account_id = ?",
                     (approval['id'], approval['account_id']))
        approval['status'] = 'EXPIRED'


def create_approval(draft_id: str) -> dict[str, Any]:
    """Capture an owned draft and canonical request in one transaction."""
    owner = account_id()
    init_approvals()
    with connect_db() as conn:
        conn.execute('BEGIN IMMEDIATE')
        draft = _get_draft(conn, draft_id, owner)
        if draft['status'] != 'draft':
            raise WorkflowError('DRAFT_REVISION_CONFLICT', 'Only editable drafts can be approved')
        now = utc_now()
        approval: dict[str, Any] = {
            'id': secrets.token_urlsafe(24), 'account_id': owner, 'draft_id': draft_id,
            'draft_revision': draft['revision'], 'content_snapshot': draft['content'],
            'content_hash': content_digest(draft['content']), 'status': 'PENDING',
            'created_at': now.isoformat(),
            'expires_at': (now + timedelta(minutes=APPROVAL_TTL_MINUTES)).isoformat(),
            'decided_at': None, 'consumed_at': None,
        }
        approval['canonical_payload'] = canonical_payload(approval)
        approval['payload_sha256'] = content_digest(approval['canonical_payload'])
        _validate_snapshot(conn, approval)
        conn.execute('''INSERT INTO publish_approvals
            (id, account_id, draft_id, draft_revision, content_snapshot, content_hash,
             status, created_at, expires_at, canonical_payload, payload_sha256)
            VALUES (:id, :account_id, :draft_id, :draft_revision, :content_snapshot, :content_hash,
             :status, :created_at, :expires_at, :canonical_payload, :payload_sha256)''', approval)
    return approval


def get_approval(approval_id: str) -> dict[str, Any]:
    """Retrieve an owned approval and durably record effective expiry."""
    owner = account_id()
    init_approvals()
    with connect_db() as conn:
        conn.execute('BEGIN IMMEDIATE')
        approval = _read_approval(conn, approval_id, owner)
        _expire(conn, approval, utc_now())
    return approval


def decide_approval(approval_id: str, approve: bool) -> dict[str, Any]:
    """Record a local offline review decision; never register as an MCP tool.

    The temporary CLI is not an authenticated human boundary. This decision
    must never authorize an external write.
    """
    owner = account_id()
    init_approvals()
    error: WorkflowError | None = None
    with connect_db() as conn:
        conn.execute('BEGIN IMMEDIATE')
        approval = _read_approval(conn, approval_id, owner)
        now = utc_now()
        _expire(conn, approval, now)
        if approval['status'] != 'PENDING':
            error = WorkflowError('APPROVAL_EXPIRED' if approval['status'] == 'EXPIRED' else 'APPROVAL_NOT_PENDING',
                                  'Approval has expired' if approval['status'] == 'EXPIRED' else 'Approval is no longer pending')
        else:
            _validate_snapshot(conn, approval)
            status = 'APPROVED' if approve else 'REJECTED'
            cursor = conn.execute('''UPDATE publish_approvals SET status = ?, decided_at = ?
                WHERE id = ? AND account_id = ? AND status = 'PENDING' ''',
                (status, now.isoformat(), approval_id, owner))
            if cursor.rowcount != 1:
                raise WorkflowError('APPROVAL_NOT_PENDING', 'Approval is no longer pending')
            approval.update(status=status, decided_at=now.isoformat())
    # Raise outside the connection context so expiry commits instead of rolling back.
    if error is not None:
        raise error
    return approval


def dry_run_publish(approval_id: str) -> dict[str, Any]:
    """Validate local review atomically; never consume or send approval bytes."""
    owner = account_id()
    init_approvals()
    error: WorkflowError | None = None
    with connect_db() as conn:
        conn.execute('BEGIN IMMEDIATE')
        approval = _read_approval(conn, approval_id, owner)
        _expire(conn, approval, utc_now())
        if approval['status'] != 'APPROVED':
            error = WorkflowError('APPROVAL_EXPIRED' if approval['status'] == 'EXPIRED' else 'APPROVAL_REQUIRED',
                                  'Valid human approval is required for an offline preview')
        else:
            _validate_snapshot(conn, approval)
    if error is not None:
        raise error
    return {
        'dry_run': True, 'ready_for_live_publish': False,
        'approval_id': approval_id, 'draft_id': approval['draft_id'],
        'draft_revision': approval['draft_revision'], 'content_sha256': approval['content_hash'],
        'payload_sha256': approval['payload_sha256'], 'account_id': owner,
        'preview': {'commentary': approval['content_snapshot'], 'visibility': 'PUBLIC',
                    'feed_distribution': 'MAIN_FEED'},
        'message': 'Local review validated for an offline preview. No LinkedIn API request was made. Live publication is disabled.',
    }
