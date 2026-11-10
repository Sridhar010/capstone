from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator


class EmploymentType(str, Enum):
    SALARIED = "salaried"
    SELF_EMPLOYED = "self_employed"
    BUSINESS_OWNER = "business_owner"
    FREELANCER = "freelancer"
    RETIRED = "retired"
    UNEMPLOYED = "unemployed"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class LoanDecision(str, Enum):
    APPROVED = "approved"
    REJECTED = "rejected"
    MANUAL_REVIEW = "manual_review"


class ProcessingStatus(str, Enum):
    PENDING = "pending"
    ANALYZING_PROFILE = "analyzing_profile"
    ANALYZING_RISK = "analyzing_risk"
    MAKING_DECISION = "making_decision"
    PROCESSING_COMPLIANCE = "processing_compliance"
    COMPLETED = "completed"
    FAILED = "failed"


# ── Input ─────────────────────────────────────────────────────────────────────

class LoanApplication(BaseModel):
    applicant_id: str = Field(..., description="Unique applicant identifier")
    age: int = Field(..., ge=18, le=100, description="Applicant age in years")
    annual_income: float = Field(..., gt=0, description="Annual income in USD")
    employment_type: EmploymentType = Field(..., description="Type of employment")
    credit_score: int = Field(..., ge=300, le=850, description="FICO credit score")
    loan_amount: float = Field(..., gt=0, description="Requested loan amount in USD")
    tenure_months: int = Field(..., ge=6, le=360, description="Loan tenure in months")
    existing_liabilities: float = Field(default=0.0, ge=0, description="Total existing monthly debt payments")
    location: str = Field(..., description="Applicant city/state location")
    application_timestamp: Optional[str] = Field(
        default_factory=lambda: datetime.now().isoformat(),
        description="ISO timestamp of application submission",
    )

    @field_validator("loan_amount")
    @classmethod
    def validate_loan_amount(cls, v: float) -> float:
        if v > 10_000_000:
            raise ValueError("Loan amount exceeds maximum limit of $10,000,000")
        return round(v, 2)


# ── Agent Outputs ──────────────────────────────────────────────────────────────

class ApplicantProfileResult(BaseModel):
    income_stability_score: float = Field(..., ge=0.0, le=1.0)
    employment_risk: RiskLevel
    credit_history_summary: str
    application_completeness_flags: List[str] = Field(default_factory=list)
    monthly_income: float
    debt_to_income_ratio: float
    analysis_notes: str


class FinancialRiskResult(BaseModel):
    debt_to_income_ratio: float
    credit_score_risk_level: RiskLevel
    loan_amount_risk: RiskLevel
    anomalies_detected: List[str] = Field(default_factory=list)
    loan_to_income_ratio: float
    monthly_payment_estimate: float
    payment_to_income_ratio: float
    reasoning: str


class LoanDecisionResult(BaseModel):
    classification: LoanDecision
    risk_score: float = Field(..., ge=0.0, le=100.0)
    confidence_level: float = Field(..., ge=0.0, le=1.0)
    key_decision_factors: List[str]
    explanation: str
    recommended_loan_amount: Optional[float] = None
    recommended_tenure_months: Optional[int] = None
    conditions: List[str] = Field(default_factory=list)


class ComplianceResult(BaseModel):
    action_taken: str
    notification_sent: bool
    case_id: str
    timestamp: str
    summary: str
    compliance_flags: List[str] = Field(default_factory=list)
    audit_trail: List[str] = Field(default_factory=list)


# ── API Response ───────────────────────────────────────────────────────────────

class LoanApplicationResponse(BaseModel):
    application_id: str
    applicant_id: str
    status: ProcessingStatus
    decision: Optional[LoanDecision] = None
    risk_score: Optional[float] = None
    confidence_level: Optional[float] = None
    case_id: Optional[str] = None
    key_factors: Optional[List[str]] = None
    explanation: Optional[str] = None
    conditions: Optional[List[str]] = None
    # Input snapshot — carried through so the Records page can display them
    loan_amount: Optional[float] = None
    credit_score: Optional[int] = None
    annual_income: Optional[float] = None
    employment_type: Optional[str] = None
    tenure_months: Optional[int] = None
    existing_liabilities: Optional[float] = None
    age: Optional[int] = None
    location: Optional[str] = None
    applicant_profile: Optional[ApplicantProfileResult] = None
    financial_risk: Optional[FinancialRiskResult] = None
    loan_decision: Optional[LoanDecisionResult] = None
    compliance: Optional[ComplianceResult] = None
    error_message: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    completed_at: Optional[str] = None


class ProgressUpdate(BaseModel):
    application_id: str
    status: ProcessingStatus
    message: str
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
