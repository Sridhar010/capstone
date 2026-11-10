"""
LangGraph orchestration engine for the Loan Approval System.
Coordinates 4 domain agents in a sequential pipeline:
  ApplicantProfile → FinancialRisk → LoanDecision → Compliance
"""
from __future__ import annotations

import logging
import sys
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any

from langgraph.graph import END, StateGraph

sys.path.insert(0, str(Path(__file__).parent.parent))

from agents import (
    ApplicantProfileAgent,
    ComplianceAgent,
    FinancialRiskAgent,
    LoanDecisionAgent,
)
from models.schemas import LoanApplication, LoanApplicationResponse, ProcessingStatus
from orchestrator.state import LoanApplicationState

logger = logging.getLogger(__name__)


# ── Node functions ─────────────────────────────────────────────────────────────

async def applicant_profile_node(state: LoanApplicationState) -> dict[str, Any]:
    """Node 1: Analyze applicant profile via ApplicantDB MCP server."""
    app_id = state["application_id"]
    logger.info("[%s] Entering applicant_profile_node", app_id)

    _notify(state, ProcessingStatus.ANALYZING_PROFILE, "Analyzing applicant profile...")

    try:
        application = _state_to_application(state)
        agent = ApplicantProfileAgent()
        result = await agent.analyze(application)
        logger.info("[%s] Profile analysis complete: income_stability=%.2f",
                    app_id, result.get("income_stability_score", 0))
        return {
            "applicant_profile_result": result,
            "processing_status": ProcessingStatus.ANALYZING_PROFILE.value,
        }
    except Exception as exc:
        logger.error("[%s] Profile agent failed: %s", app_id, exc)
        return {
            "applicant_profile_result": {"error": str(exc)},
            "processing_status": ProcessingStatus.FAILED.value,
            "error_message": f"Profile analysis failed: {exc}",
        }


async def financial_risk_node(state: LoanApplicationState) -> dict[str, Any]:
    """Node 2: Perform financial risk analysis via RiskRulesDB MCP server."""
    app_id = state["application_id"]
    logger.info("[%s] Entering financial_risk_node", app_id)

    if state.get("processing_status") == ProcessingStatus.FAILED.value:
        return {}

    _notify(state, ProcessingStatus.ANALYZING_RISK, "Running financial risk analysis...")

    try:
        application = _state_to_application(state)
        profile_result = state.get("applicant_profile_result") or {}
        agent = FinancialRiskAgent()
        result = await agent.analyze(application, profile_result)
        logger.info("[%s] Risk analysis complete: dti=%.1f%%",
                    app_id, result.get("debt_to_income_ratio", 0))
        return {
            "financial_risk_result": result,
            "processing_status": ProcessingStatus.ANALYZING_RISK.value,
        }
    except Exception as exc:
        logger.error("[%s] Risk agent failed: %s", app_id, exc)
        return {
            "financial_risk_result": {"error": str(exc)},
            "processing_status": ProcessingStatus.FAILED.value,
            "error_message": f"Risk analysis failed: {exc}",
        }


async def loan_decision_node(state: LoanApplicationState) -> dict[str, Any]:
    """Node 3: Make the final loan decision via DecisionSynthesis MCP server."""
    app_id = state["application_id"]
    logger.info("[%s] Entering loan_decision_node", app_id)

    if state.get("processing_status") == ProcessingStatus.FAILED.value:
        return {}

    _notify(state, ProcessingStatus.MAKING_DECISION, "Making loan decision...")

    try:
        application = _state_to_application(state)
        profile_result = state.get("applicant_profile_result") or {}
        risk_result = state.get("financial_risk_result") or {}
        agent = LoanDecisionAgent()
        result = await agent.decide(application, profile_result, risk_result)
        logger.info("[%s] Decision made: %s (risk_score=%.1f)",
                    app_id, result.get("classification", "?"), result.get("risk_score", 0))
        return {
            "loan_decision_result": result,
            "processing_status": ProcessingStatus.MAKING_DECISION.value,
        }
    except Exception as exc:
        logger.error("[%s] Decision agent failed: %s", app_id, exc)
        return {
            "loan_decision_result": {"error": str(exc)},
            "processing_status": ProcessingStatus.FAILED.value,
            "error_message": f"Decision making failed: {exc}",
        }


async def compliance_node(state: LoanApplicationState) -> dict[str, Any]:
    """Node 4: Compliance, notification, and audit trail via NotificationSystem MCP server."""
    app_id = state["application_id"]
    logger.info("[%s] Entering compliance_node", app_id)

    if state.get("processing_status") == ProcessingStatus.FAILED.value:
        return {"processing_status": ProcessingStatus.FAILED.value}

    _notify(state, ProcessingStatus.PROCESSING_COMPLIANCE, "Processing compliance and notifications...")

    try:
        application = _state_to_application(state)
        profile_result = state.get("applicant_profile_result") or {}
        risk_result = state.get("financial_risk_result") or {}
        decision_result = state.get("loan_decision_result") or {}
        agent = ComplianceAgent()
        result = await agent.process(application, profile_result, risk_result, decision_result)
        logger.info("[%s] Compliance complete: case_id=%s", app_id, result.get("case_id", "?"))
        return {
            "compliance_result": result,
            "processing_status": ProcessingStatus.COMPLETED.value,
        }
    except Exception as exc:
        logger.error("[%s] Compliance agent failed: %s", app_id, exc)
        return {
            "compliance_result": {"error": str(exc)},
            "processing_status": ProcessingStatus.FAILED.value,
            "error_message": f"Compliance processing failed: {exc}",
        }


# ── Routing ───────────────────────────────────────────────────────────────────

def should_continue(state: LoanApplicationState) -> str:
    if state.get("processing_status") == ProcessingStatus.FAILED.value:
        return "end"
    return "continue"


# ── Graph builder ─────────────────────────────────────────────────────────────

def build_graph() -> Any:
    workflow = StateGraph(LoanApplicationState)

    workflow.add_node("applicant_profile", applicant_profile_node)
    workflow.add_node("financial_risk", financial_risk_node)
    workflow.add_node("loan_decision", loan_decision_node)
    workflow.add_node("compliance", compliance_node)

    workflow.set_entry_point("applicant_profile")
    workflow.add_edge("applicant_profile", "financial_risk")
    workflow.add_edge("financial_risk", "loan_decision")
    workflow.add_edge("loan_decision", "compliance")
    workflow.add_edge("compliance", END)

    return workflow.compile()


# ── Orchestrator ──────────────────────────────────────────────────────────────

class LoanApprovalOrchestrator:
    """
    High-level orchestrator that initialises the LangGraph workflow and
    provides a simple `process` coroutine for FastAPI to call.
    """

    def __init__(self) -> None:
        self._graph = build_graph()

    async def process(
        self,
        application: LoanApplication,
        application_id: str,
        progress_callback=None,
    ) -> LoanApplicationResponse:
        initial_state: LoanApplicationState = {
            "application_id": application_id,
            "applicant_id": application.applicant_id,
            "age": application.age,
            "annual_income": application.annual_income,
            "employment_type": application.employment_type.value,
            "credit_score": application.credit_score,
            "loan_amount": application.loan_amount,
            "tenure_months": application.tenure_months,
            "existing_liabilities": application.existing_liabilities,
            "location": application.location,
            "application_timestamp": application.application_timestamp or datetime.now().isoformat(),
            "applicant_profile_result": None,
            "financial_risk_result": None,
            "loan_decision_result": None,
            "compliance_result": None,
            "processing_status": ProcessingStatus.PENDING.value,
            "error_message": None,
            "progress_callback": progress_callback,
        }

        logger.info("[%s] Starting LangGraph workflow", application_id)
        final_state = await self._graph.ainvoke(initial_state)
        return _state_to_response(application, application_id, final_state)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _state_to_application(state: LoanApplicationState) -> LoanApplication:
    from models.schemas import EmploymentType
    return LoanApplication(
        applicant_id=state["applicant_id"],
        age=state["age"],
        annual_income=state["annual_income"],
        employment_type=EmploymentType(state["employment_type"]),
        credit_score=state["credit_score"],
        loan_amount=state["loan_amount"],
        tenure_months=state["tenure_months"],
        existing_liabilities=state.get("existing_liabilities", 0.0),
        location=state["location"],
        application_timestamp=state.get("application_timestamp"),
    )


def _notify(state: LoanApplicationState, status: ProcessingStatus, message: str) -> None:
    cb = state.get("progress_callback")
    if cb:
        try:
            cb(status.value, message)
        except Exception:
            pass


def _state_to_response(
    application: LoanApplication,
    application_id: str,
    state: LoanApplicationState,
) -> LoanApplicationResponse:
    from models.schemas import ApplicantProfileResult, ComplianceResult, FinancialRiskResult, LoanDecisionResult, LoanDecision, RiskLevel

    status_str = state.get("processing_status", ProcessingStatus.COMPLETED.value)
    try:
        status = ProcessingStatus(status_str)
    except ValueError:
        status = ProcessingStatus.COMPLETED

    decision_raw = state.get("loan_decision_result") or {}
    risk_raw = state.get("financial_risk_result") or {}
    profile_raw = state.get("applicant_profile_result") or {}
    compliance_raw = state.get("compliance_result") or {}

    # Safely parse sub-results
    profile_result = _safe_parse_profile(profile_raw)
    risk_result = _safe_parse_risk(risk_raw)
    decision_result = _safe_parse_decision(decision_raw)
    compliance_result = _safe_parse_compliance(compliance_raw)

    decision_value = None
    if decision_result:
        try:
            decision_value = LoanDecision(decision_result.classification)
        except (ValueError, AttributeError):
            pass

    return LoanApplicationResponse(
        application_id=application_id,
        applicant_id=application.applicant_id,
        status=status,
        decision=decision_value,
        risk_score=decision_result.risk_score if decision_result else None,
        confidence_level=decision_result.confidence_level if decision_result else None,
        case_id=compliance_result.case_id if compliance_result else None,
        key_factors=decision_result.key_decision_factors if decision_result else None,
        explanation=decision_result.explanation if decision_result else state.get("error_message"),
        conditions=decision_result.conditions if decision_result else None,
        applicant_profile=profile_result,
        financial_risk=risk_result,
        loan_decision=decision_result,
        compliance=compliance_result,
        error_message=state.get("error_message"),
        completed_at=datetime.now().isoformat(),
    )


def _safe_parse_profile(raw: dict) -> Any:
    from models.schemas import ApplicantProfileResult, RiskLevel
    try:
        return ApplicantProfileResult(
            income_stability_score=float(raw.get("income_stability_score", 0.5)),
            employment_risk=RiskLevel(raw.get("employment_risk", "medium")),
            credit_history_summary=str(raw.get("credit_history_summary", "")),
            application_completeness_flags=raw.get("application_completeness_flags", []),
            monthly_income=float(raw.get("monthly_income", 0)),
            debt_to_income_ratio=float(raw.get("debt_to_income_ratio", 0)),
            analysis_notes=str(raw.get("analysis_notes", "")),
        )
    except Exception as e:
        logger.warning("Failed to parse profile result: %s", e)
        return None


def _safe_parse_risk(raw: dict) -> Any:
    from models.schemas import FinancialRiskResult, RiskLevel
    try:
        return FinancialRiskResult(
            debt_to_income_ratio=float(raw.get("debt_to_income_ratio", 0)),
            credit_score_risk_level=RiskLevel(raw.get("credit_score_risk_level", "medium")),
            loan_amount_risk=RiskLevel(raw.get("loan_amount_risk", "medium")),
            anomalies_detected=raw.get("anomalies_detected", []),
            loan_to_income_ratio=float(raw.get("loan_to_income_ratio", 0)),
            monthly_payment_estimate=float(raw.get("monthly_payment_estimate", 0)),
            payment_to_income_ratio=float(raw.get("payment_to_income_ratio", 0)),
            reasoning=str(raw.get("reasoning", "")),
        )
    except Exception as e:
        logger.warning("Failed to parse risk result: %s", e)
        return None


def _safe_parse_decision(raw: dict) -> Any:
    from models.schemas import LoanDecisionResult, LoanDecision
    # Only parse if we have a real decision — avoids misleading 50/50 defaults
    if not raw or "classification" not in raw:
        return None
    try:
        return LoanDecisionResult(
            classification=LoanDecision(raw["classification"]),
            risk_score=float(raw.get("risk_score", 50)),
            confidence_level=float(raw.get("confidence_level", 0.5)),
            key_decision_factors=raw.get("key_decision_factors", []),
            explanation=str(raw.get("explanation", "")),
            recommended_loan_amount=raw.get("recommended_loan_amount"),
            recommended_tenure_months=raw.get("recommended_tenure_months"),
            conditions=raw.get("conditions", []),
        )
    except Exception as e:
        logger.warning("Failed to parse decision result: %s", e)
        return None


def _safe_parse_compliance(raw: dict) -> Any:
    from models.schemas import ComplianceResult
    from datetime import datetime
    try:
        return ComplianceResult(
            action_taken=str(raw.get("action_taken", "")),
            notification_sent=bool(raw.get("notification_sent", False)),
            case_id=str(raw.get("case_id", f"CASE-{datetime.now().strftime('%Y%m%d%H%M%S')}")),
            timestamp=str(raw.get("timestamp", datetime.now().isoformat())),
            summary=str(raw.get("summary", "")),
            compliance_flags=raw.get("compliance_flags", []),
            audit_trail=raw.get("audit_trail", []),
        )
    except Exception as e:
        logger.warning("Failed to parse compliance result: %s", e)
        return None
