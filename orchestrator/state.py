"""
LangGraph state definition for the Loan Approval workflow.
"""
from __future__ import annotations

from typing import Any, Callable, Optional
from typing_extensions import TypedDict


class LoanApplicationState(TypedDict, total=False):
    # ── Input fields ──────────────────────────────────────────────────────────
    application_id: str
    applicant_id: str
    age: int
    annual_income: float
    employment_type: str
    credit_score: int
    loan_amount: float
    tenure_months: int
    existing_liabilities: float
    location: str
    application_timestamp: str

    # ── Agent outputs ─────────────────────────────────────────────────────────
    applicant_profile_result: Optional[dict[str, Any]]
    financial_risk_result: Optional[dict[str, Any]]
    loan_decision_result: Optional[dict[str, Any]]
    compliance_result: Optional[dict[str, Any]]

    # ── Workflow control ─────────────────────────────────────────────────────
    processing_status: str
    error_message: Optional[str]

    # ── Progress callback (not serialised) ────────────────────────────────────
    progress_callback: Optional[Callable[[str, str], None]]
