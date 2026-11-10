"""
SQLite persistence layer for the Loan Approval System.
Uses aiosqlite for non-blocking async I/O compatible with FastAPI's event loop.
"""
from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Any

import aiosqlite

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import BASE_DIR

logger = logging.getLogger(__name__)

DB_PATH = BASE_DIR / "loan_approvals.db"

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS applications (
    application_id       TEXT PRIMARY KEY,
    applicant_id         TEXT NOT NULL,
    age                  INTEGER,
    annual_income        REAL,
    employment_type      TEXT,
    credit_score         INTEGER,
    loan_amount          REAL,
    tenure_months        INTEGER,
    existing_liabilities REAL,
    location             TEXT,
    status               TEXT NOT NULL DEFAULT 'pending',
    decision             TEXT,
    risk_score           REAL,
    confidence_level     REAL,
    case_id              TEXT,
    explanation          TEXT,
    key_factors          TEXT,
    error_message        TEXT,
    full_response        TEXT,
    created_at           TEXT NOT NULL,
    completed_at         TEXT
);
"""

_CREATE_INDEX = """
CREATE INDEX IF NOT EXISTS idx_applications_created
ON applications (created_at DESC);
"""


async def init_db() -> None:
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute(_CREATE_TABLE)
        await conn.execute(_CREATE_INDEX)
        await conn.commit()
    logger.info("Database initialised at %s", DB_PATH)


async def save_application(response: Any, input_data: Any) -> None:
    """Insert a new pending application record."""
    try:
        async with aiosqlite.connect(DB_PATH) as conn:
            await conn.execute(
                """
                INSERT OR IGNORE INTO applications
                    (application_id, applicant_id, age, annual_income, employment_type,
                     credit_score, loan_amount, tenure_months, existing_liabilities,
                     location, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    response.application_id,
                    response.applicant_id,
                    getattr(input_data, "age", None),
                    getattr(input_data, "annual_income", None),
                    getattr(input_data, "employment_type", None) if not hasattr(getattr(input_data, "employment_type", None), "value") else input_data.employment_type.value,
                    getattr(input_data, "credit_score", None),
                    getattr(input_data, "loan_amount", None),
                    getattr(input_data, "tenure_months", None),
                    getattr(input_data, "existing_liabilities", None),
                    getattr(input_data, "location", None),
                    response.status.value if hasattr(response.status, "value") else str(response.status),
                    response.created_at,
                ),
            )
            await conn.commit()
    except Exception as exc:
        logger.error("DB save_application failed: %s", exc)


async def update_application(response: Any) -> None:
    """Update an existing application record with final results."""
    try:
        decision = None
        if response.decision:
            decision = response.decision.value if hasattr(response.decision, "value") else str(response.decision)

        status = response.status.value if hasattr(response.status, "value") else str(response.status)

        key_factors_json = json.dumps(response.key_factors or [])

        # Serialize the full response to JSON for complete record keeping
        full_response_json = _serialize_response(response)

        async with aiosqlite.connect(DB_PATH) as conn:
            await conn.execute(
                """
                UPDATE applications SET
                    status           = ?,
                    decision         = ?,
                    risk_score       = ?,
                    confidence_level = ?,
                    case_id          = ?,
                    explanation      = ?,
                    key_factors      = ?,
                    error_message    = ?,
                    full_response    = ?,
                    completed_at     = ?
                WHERE application_id = ?
                """,
                (
                    status,
                    decision,
                    response.risk_score,
                    response.confidence_level,
                    response.case_id,
                    response.explanation,
                    key_factors_json,
                    response.error_message,
                    full_response_json,
                    response.completed_at,
                    response.application_id,
                ),
            )
            await conn.commit()
    except Exception as exc:
        logger.error("DB update_application failed: %s", exc)


async def get_application(application_id: str) -> dict[str, Any] | None:
    """Retrieve a single application record by ID."""
    try:
        async with aiosqlite.connect(DB_PATH) as conn:
            conn.row_factory = aiosqlite.Row
            async with conn.execute(
                "SELECT * FROM applications WHERE application_id = ?",
                (application_id,),
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return _row_to_dict(row)
    except Exception as exc:
        logger.error("DB get_application failed: %s", exc)
    return None


async def list_applications(limit: int = 200) -> list[dict[str, Any]]:
    """Return all applications ordered by most recent first."""
    try:
        async with aiosqlite.connect(DB_PATH) as conn:
            conn.row_factory = aiosqlite.Row
            async with conn.execute(
                "SELECT * FROM applications ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ) as cursor:
                rows = await cursor.fetchall()
                return [_row_to_dict(r) for r in rows]
    except Exception as exc:
        logger.error("DB list_applications failed: %s", exc)
    return []


# ── Helpers ───────────────────────────────────────────────────────────────────

def _row_to_dict(row: aiosqlite.Row) -> dict[str, Any]:
    d = dict(row)
    if d.get("key_factors"):
        try:
            d["key_factors"] = json.loads(d["key_factors"])
        except Exception:
            d["key_factors"] = []
    if d.get("full_response"):
        try:
            d["full_response"] = json.loads(d["full_response"])
        except Exception:
            pass
    return d


def _serialize_response(response: Any) -> str:
    """Convert a Pydantic LoanApplicationResponse to a JSON string."""
    try:
        return response.model_dump_json()
    except Exception:
        try:
            return json.dumps(response.dict(), default=str)
        except Exception:
            return "{}"
