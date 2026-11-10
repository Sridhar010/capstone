"""
FastAPI Microservice — Loan Approval System
Receives loan applications, triggers the LangGraph orchestration pipeline,
and streams real-time progress via WebSocket.
All applications are persisted to SQLite via write-through cache.
"""
from __future__ import annotations

import asyncio
import logging
import sys
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import API_HOST, API_PORT, LOG_DIR, LOG_LEVEL
from database import init_db, list_applications as db_list, save_application, update_application
from models.schemas import (
    LoanApplication,
    LoanApplicationResponse,
    ProcessingStatus,
    ProgressUpdate,
)
from orchestrator import LoanApprovalOrchestrator

# ── Logging ────────────────────────────────────────────────────────────────────
_log_fmt = logging.Formatter(
    "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
_root = logging.getLogger()
_root.setLevel(getattr(logging, LOG_LEVEL.upper(), logging.INFO))

_file_handler = logging.FileHandler(LOG_DIR / "api.log", mode="a", encoding="utf-8")
_file_handler.setFormatter(_log_fmt)
_root.addHandler(_file_handler)

_stream_handler = logging.StreamHandler(sys.stdout)
_stream_handler.setFormatter(_log_fmt)
_root.addHandler(_stream_handler)

logger = logging.getLogger(__name__)

# ── In-process cache (write-through to SQLite) ────────────────────────────────
_applications: dict[str, LoanApplicationResponse] = {}
_ws_connections: dict[str, list[WebSocket]] = {}
_orchestrator: LoanApprovalOrchestrator | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _orchestrator
    logger.info("Initialising database...")
    await init_db()

    # Reload recent applications from DB into the in-memory cache
    rows = await db_list(limit=500)
    for row in rows:
        try:
            full = row.get("full_response")
            if isinstance(full, dict):
                resp = LoanApplicationResponse(**full)
                # Backfill input snapshot fields from flat columns (pre-schema-change records)
                _backfill_input_fields_from_row(resp, row)
                _applications[row["application_id"]] = resp
        except Exception:
            pass
    logger.info("Loaded %d existing applications from database", len(_applications))

    logger.info("Initialising LangGraph orchestrator...")
    _orchestrator = LoanApprovalOrchestrator()
    logger.info("Loan Approval API ready")
    yield
    logger.info("API shutting down")


# ── Application ────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Loan Approval System API",
    description=(
        "Multi-agent AI loan approval system — "
        "LangGraph orchestration, FastMCP servers, Anthropic Claude."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── WebSocket helpers ──────────────────────────────────────────────────────────

async def _broadcast(application_id: str, status: str, message: str) -> None:
    update = ProgressUpdate(
        application_id=application_id,
        status=ProcessingStatus(status) if status in ProcessingStatus._value2member_map_ else ProcessingStatus.PENDING,
        message=message,
    )
    payload = update.model_dump()
    dead: list[WebSocket] = []
    for ws in _ws_connections.get(application_id, []):
        try:
            await ws.send_json(payload)
        except Exception:
            dead.append(ws)
    for ws in dead:
        _ws_connections.get(application_id, []).remove(ws)


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


@app.post("/api/v1/loans", response_model=LoanApplicationResponse, status_code=202)
async def submit_loan_application(application: LoanApplication) -> LoanApplicationResponse:
    """Submit a new loan application for multi-agent processing."""
    application_id = f"APP-{str(uuid.uuid4())[:8].upper()}"

    pending_response = LoanApplicationResponse(
        application_id=application_id,
        applicant_id=application.applicant_id,
        status=ProcessingStatus.PENDING,
        # Carry input snapshot so Records page can display them
        loan_amount=application.loan_amount,
        credit_score=application.credit_score,
        annual_income=application.annual_income,
        employment_type=application.employment_type.value,
        tenure_months=application.tenure_months,
        existing_liabilities=application.existing_liabilities,
        age=application.age,
        location=application.location,
    )
    # Write-through: memory + DB
    _applications[application_id] = pending_response
    _ws_connections[application_id] = []
    await save_application(pending_response, application)

    logger.info("Received application %s for applicant %s", application_id, application.applicant_id)

    asyncio.create_task(_process_application(application_id, application))
    return pending_response


@app.get("/api/v1/loans/{application_id}", response_model=LoanApplicationResponse)
async def get_loan_status(application_id: str) -> LoanApplicationResponse:
    """Retrieve the current status and result of a loan application."""
    # Fast path: in-memory cache
    if application_id in _applications:
        return _applications[application_id]
    # Fallback: query DB (e.g. after a restart mid-processing)
    row = await _get_from_db(application_id)
    if row:
        return row
    raise HTTPException(status_code=404, detail=f"Application {application_id} not found")


@app.get("/api/v1/loans", response_model=list[LoanApplicationResponse])
async def list_all_applications(limit: int = 200) -> list[LoanApplicationResponse]:
    """List all loan applications from the database (most recent first)."""
    rows = await db_list(limit=limit)
    result = []
    for row in rows:
        # Prefer the in-memory version if available (more up-to-date during processing)
        if row["application_id"] in _applications:
            cached = _applications[row["application_id"]]
            # Ensure input fields are populated (older cache entries may lack them)
            _backfill_input_fields_from_row(cached, row)
            result.append(cached)
        else:
            full = row.get("full_response")
            if isinstance(full, dict):
                try:
                    resp = LoanApplicationResponse(**full)
                    # Backfill input fields from flat DB columns (older records
                    # pre-date the schema change and won't have them in the JSON)
                    _backfill_input_fields_from_row(resp, row)
                    result.append(resp)
                    continue
                except Exception:
                    pass
            # Build a partial response from flat DB columns
            result.append(_row_to_response(row))
    return result


@app.delete("/api/v1/loans/{application_id}")
async def delete_application(application_id: str) -> dict[str, str]:
    """Remove an application from the in-memory cache (DB record is kept for audit)."""
    if application_id not in _applications:
        raise HTTPException(status_code=404, detail=f"Application {application_id} not found")
    del _applications[application_id]
    _ws_connections.pop(application_id, None)
    return {"message": f"Application {application_id} removed from active cache"}


@app.websocket("/ws/loans/{application_id}")
async def websocket_progress(websocket: WebSocket, application_id: str) -> None:
    """WebSocket endpoint for real-time processing progress updates."""
    await websocket.accept()

    if application_id not in _ws_connections:
        _ws_connections[application_id] = []
    _ws_connections[application_id].append(websocket)

    try:
        existing = _applications.get(application_id)
        if existing and existing.status in (ProcessingStatus.COMPLETED, ProcessingStatus.FAILED):
            await websocket.send_json(existing.model_dump())
            return

        while True:
            existing = _applications.get(application_id)
            if existing and existing.status in (ProcessingStatus.COMPLETED, ProcessingStatus.FAILED):
                await websocket.send_json(existing.model_dump())
                break
            await asyncio.sleep(0.5)

    except WebSocketDisconnect:
        pass
    finally:
        conns = _ws_connections.get(application_id, [])
        if websocket in conns:
            conns.remove(websocket)


# ── Background processing ──────────────────────────────────────────────────────

async def _process_application(application_id: str, application: LoanApplication) -> None:
    """Run the full orchestration pipeline for a loan application."""
    global _orchestrator

    def progress_callback(status: str, message: str) -> None:
        asyncio.create_task(_broadcast(application_id, status, message))
        if application_id in _applications:
            try:
                _applications[application_id].status = ProcessingStatus(status)
            except ValueError:
                pass

    try:
        await _broadcast(application_id, ProcessingStatus.PENDING.value, "Application received. Starting analysis...")

        result = await _orchestrator.process(
            application=application,
            application_id=application_id,
            progress_callback=progress_callback,
        )
        _applications[application_id] = result
        await update_application(result)  # persist to DB

        await _broadcast(
            application_id,
            ProcessingStatus.COMPLETED.value,
            f"Processing complete. Decision: {result.decision.value.upper() if result.decision else 'N/A'}",
        )
        logger.info(
            "Application %s completed: decision=%s risk_score=%.1f",
            application_id,
            result.decision,
            result.risk_score or 0,
        )

    except Exception as exc:
        logger.exception("Unhandled error processing application %s", application_id)
        error_response = LoanApplicationResponse(
            application_id=application_id,
            applicant_id=application.applicant_id,
            status=ProcessingStatus.FAILED,
            error_message=str(exc),
        )
        _applications[application_id] = error_response
        await update_application(error_response)  # persist failure to DB

        await _broadcast(
            application_id,
            ProcessingStatus.FAILED.value,
            f"Processing failed: {exc}",
        )


# ── Internal helpers ──────────────────────────────────────────────────────────

async def _get_from_db(application_id: str) -> LoanApplicationResponse | None:
    from database.db import get_application
    row = await get_application(application_id)
    if not row:
        return None
    full = row.get("full_response")
    if isinstance(full, dict):
        try:
            resp = LoanApplicationResponse(**full)
            _backfill_input_fields_from_row(resp, row)
            return resp
        except Exception:
            pass
    return _row_to_response(row)


def _backfill_input_fields_from_row(resp: LoanApplicationResponse, row: dict) -> None:
    """Fill input snapshot fields from flat DB columns when missing from JSON blob."""
    if resp.loan_amount is None:
        resp.loan_amount = row.get("loan_amount")
    if resp.credit_score is None:
        resp.credit_score = row.get("credit_score")
    if resp.annual_income is None:
        resp.annual_income = row.get("annual_income")
    if resp.employment_type is None:
        resp.employment_type = row.get("employment_type")
    if resp.tenure_months is None:
        resp.tenure_months = row.get("tenure_months")
    if resp.existing_liabilities is None:
        resp.existing_liabilities = row.get("existing_liabilities")
    if resp.age is None:
        resp.age = row.get("age")
    if resp.location is None:
        resp.location = row.get("location")


def _row_to_response(row: dict) -> LoanApplicationResponse:
    from models.schemas import LoanDecision
    decision = None
    if row.get("decision"):
        try:
            decision = LoanDecision(row["decision"])
        except ValueError:
            pass
    try:
        status = ProcessingStatus(row.get("status", "pending"))
    except ValueError:
        status = ProcessingStatus.PENDING

    return LoanApplicationResponse(
        application_id=row["application_id"],
        applicant_id=row["applicant_id"],
        status=status,
        decision=decision,
        risk_score=row.get("risk_score"),
        confidence_level=row.get("confidence_level"),
        case_id=row.get("case_id"),
        explanation=row.get("explanation"),
        key_factors=row.get("key_factors") or [],
        error_message=row.get("error_message"),
        created_at=row.get("created_at", datetime.now().isoformat()),
        completed_at=row.get("completed_at"),
        # Input snapshot from flat DB columns (populated at submission time)
        loan_amount=row.get("loan_amount"),
        credit_score=row.get("credit_score"),
        annual_income=row.get("annual_income"),
        employment_type=row.get("employment_type"),
        tenure_months=row.get("tenure_months"),
        existing_liabilities=row.get("existing_liabilities"),
        age=row.get("age"),
        location=row.get("location"),
    )


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    uvicorn.run(
        "api.main:app",
        host=API_HOST,
        port=API_PORT,
        reload=False,
        log_level=LOG_LEVEL.lower(),
    )
