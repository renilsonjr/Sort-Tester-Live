"""Materialize bank questions into durable, immutable question_versions rows.

The bank's question text lives in ``backend/ranked_bank`` (JSON), never in the
database. When an attempt is assigned a question, its identity and content
fingerprint are pinned here so the stored assignment can never silently change
if the bank is later revised. Rows are insert-only (the schema's immutability
trigger forbids updates), so materialization is a get-or-create keyed by
``(bank_key, content_sha256)``.
"""
from backend.db import migrate
from backend.ranked_bank.identity import question_content_digest


def materialize_question_version(conn, question) -> str:
    """Return the ``question_versions`` id for *question*, inserting it if absent.

    Idempotent: the same question content always resolves to the same row.
    Never updates an existing row — question versions are immutable.
    """
    bank_key = question.canonical_id
    digest = question_content_digest(question)
    difficulty = question.difficulty.lower()
    inserted = migrate.fetch_one(
        conn,
        "INSERT INTO question_versions (bank_key, difficulty, content_sha256)"
        " VALUES (%s, %s, %s)"
        " ON CONFLICT (bank_key, content_sha256) DO NOTHING"
        " RETURNING id",
        (bank_key, difficulty, digest),
    )
    if inserted is not None:
        return inserted["id"]
    existing = migrate.fetch_one(
        conn,
        "SELECT id FROM question_versions WHERE bank_key = %s AND content_sha256 = %s",
        (bank_key, digest),
    )
    return existing["id"]
