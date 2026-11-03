"""
FastAPI Microservice — Loan Approval System
Receives loan applications, triggers the LangGraph orchestration pipeline,
and streams real-time progress via WebSocket.
"""
from __future__ import annotations

import asyncio
import logging
import sys
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import API_HOST, API_PORT, LOG_LEVEL
from models.schemas import (
    LoanApplication,
    LoanApplicationResponse,
    ProcessingStatus,
    ProgressUpdate,
)
from orchestrator import LoanApprovalOrchestrator

# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ── In-memory storage (production: replace with Redis/DB) ─────────────────────
_applications: dict[str, LoanApplicationResponse] = {}
_ws_connections: dict[str, list[WebSocket]] = {}
_orchestrator: LoanApprovalOrchestrator | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _orchestrator
    logger.info("Initialising LangGraph orchestrator...")
    _orchestrator = LoanApprovalOrchestrator()
    logger.info("Loan Approval API ready")
    yield
    logger.info("API shutting down")


# ── Application ────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Agentic AI Loan Approval System",
    description=(
        "Multi-agent system for intelligent loan approval using "
        "LangGraph orchestration, FastMCP servers, and Claude AI."
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

    # Create a pending response immediately
    pending_response = LoanApplicationResponse(
        application_id=application_id,
        applicant_id=application.applicant_id,
        status=ProcessingStatus.PENDING,
    )
    _applications[application_id] = pending_response
    _ws_connections[application_id] = []

    logger.info("Received application %s for applicant %s", application_id, application.applicant_id)

    # Process asynchronously
    asyncio.create_task(
        _process_application(application_id, application)
    )

    return pending_response


@app.get("/api/v1/loans/{application_id}", response_model=LoanApplicationResponse)
async def get_loan_status(application_id: str) -> LoanApplicationResponse:
    """Retrieve the current status and result of a loan application."""
    if application_id not in _applications:
        raise HTTPException(status_code=404, detail=f"Application {application_id} not found")
    return _applications[application_id]


@app.get("/api/v1/loans", response_model=list[LoanApplicationResponse])
async def list_applications() -> list[LoanApplicationResponse]:
    """List all loan applications (most recent first)."""
    return list(reversed(list(_applications.values())))


@app.delete("/api/v1/loans/{application_id}")
async def delete_application(application_id: str) -> dict[str, str]:
    """Remove an application record."""
    if application_id not in _applications:
        raise HTTPException(status_code=404, detail=f"Application {application_id} not found")
    del _applications[application_id]
    _ws_connections.pop(application_id, None)
    return {"message": f"Application {application_id} deleted"}


@app.websocket("/ws/loans/{application_id}")
async def websocket_progress(websocket: WebSocket, application_id: str) -> None:
    """WebSocket endpoint for real-time processing progress updates."""
    await websocket.accept()

    if application_id not in _ws_connections:
        _ws_connections[application_id] = []
    _ws_connections[application_id].append(websocket)

    try:
        # If already completed, send the final state immediately
        existing = _applications.get(application_id)
        if existing and existing.status in (ProcessingStatus.COMPLETED, ProcessingStatus.FAILED):
            await websocket.send_json(existing.model_dump())
            return

        # Keep alive until the application finishes or client disconnects
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
        # Also update the stored response status
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
        await _broadcast(
            application_id,
            ProcessingStatus.FAILED.value,
            f"Processing failed: {exc}",
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
