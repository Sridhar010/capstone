"""
MCP Server: NotificationSystem
Handles compliance logging, case management, and decision notifications.
"""
import json
import sys
import uuid
from datetime import datetime
from pathlib import Path

from fastmcp import FastMCP

sys.path.insert(0, str(Path(__file__).parent.parent))

mcp = FastMCP(
    "NotificationSystem",
    instructions=(
        "Tools for compliance and action management including case ID generation, "
        "decision notifications, compliance logging, and summary generation."
    ),
)


@mcp.tool()
def generate_case_id(applicant_id: str) -> str:
    """
    Generate a unique case identifier for this loan application.

    Args:
        applicant_id: The applicant's unique identifier
    """
    prefix = "LN"
    timestamp_part = datetime.now().strftime("%Y%m%d%H%M")
    unique_part = str(uuid.uuid4()).replace("-", "")[:6].upper()
    safe_applicant = applicant_id.replace("-", "").upper()[:6]
    case_id = f"{prefix}-{safe_applicant}-{timestamp_part}-{unique_part}"

    result = {
        "case_id": case_id,
        "applicant_id": applicant_id,
        "generated_at": datetime.now().isoformat(),
        "case_id_format": "LN-{APPLICANT}-{YYYYMMDDHHMM}-{RANDOM6}",
    }
    return json.dumps(result)


@mcp.tool()
def dispatch_notification(
    case_id: str,
    applicant_id: str,
    decision: str,
    explanation: str,
    risk_score: float,
    channel: str = "email",
) -> str:
    """
    Dispatch a decision notification to the applicant (simulated).

    Args:
        case_id: Unique case identifier
        applicant_id: Applicant's ID
        decision: approved/rejected/manual_review
        explanation: Human-readable explanation
        risk_score: Overall risk score
        channel: Notification channel (email/sms/push)
    """
    timestamp = datetime.now().isoformat()

    decision_messages = {
        "approved": (
            f"Congratulations! Your loan application (Case {case_id}) has been APPROVED. "
            f"Our team will contact you within 2 business days with the final terms and conditions."
        ),
        "rejected": (
            f"We regret to inform you that your loan application (Case {case_id}) has been REJECTED. "
            f"You may request a detailed explanation and reapply after 90 days. "
            f"Reason: {explanation[:200]}"
        ),
        "manual_review": (
            f"Your loan application (Case {case_id}) is under MANUAL REVIEW. "
            f"A loan officer will contact you within 3-5 business days. "
            f"Please keep your documents ready."
        ),
    }

    message_body = decision_messages.get(
        decision.lower(),
        f"Your application (Case {case_id}) status: {decision.upper()}"
    )

    # Simulate notification dispatch with delivery confirmation
    notification_record = {
        "notification_id": f"NOTIF-{str(uuid.uuid4())[:8].upper()}",
        "case_id": case_id,
        "applicant_id": applicant_id,
        "channel": channel,
        "decision": decision,
        "message": message_body,
        "sent_at": timestamp,
        "delivery_status": "DELIVERED",
        "delivery_timestamp": timestamp,
    }

    result = {
        "success": True,
        "notification_sent": True,
        "notification_record": notification_record,
        "action_taken": f"Notification sent via {channel.upper()} for decision: {decision.upper()}",
        "summary": f"Case {case_id}: {decision.upper()} notification dispatched via {channel}",
    }
    return json.dumps(result)


@mcp.tool()
def record_compliance_log(
    case_id: str,
    applicant_id: str,
    decision: str,
    risk_score: float,
    key_factors: str,
    agent_trace: str,
    regulatory_flags: str = "",
) -> str:
    """
    Record a compliance log entry for regulatory audit trail.

    Args:
        case_id: Case identifier
        applicant_id: Applicant identifier
        decision: Final decision
        risk_score: Computed risk score
        key_factors: Comma-separated key decision factors
        agent_trace: Summary of agents that processed this application
        regulatory_flags: Any regulatory compliance flags
    """
    timestamp = datetime.now().isoformat()
    log_id = f"COMP-LOG-{str(uuid.uuid4()).replace('-', '')[:12].upper()}"

    # Determine regulatory compliance status
    ecoa_compliant = True
    fair_lending_notes = []

    if "anomaly" in key_factors.lower() or "fraud" in key_factors.lower():
        fair_lending_notes.append(
            "BSA/AML review triggered — anomalies flagged in application"
        )

    if decision.lower() == "rejected":
        fair_lending_notes.append(
            "ECOA adverse action notice required within 30 days"
        )
        ecoa_compliant = bool(risk_score)

    compliance_record = {
        "log_id": log_id,
        "case_id": case_id,
        "applicant_id": applicant_id,
        "decision": decision.upper(),
        "risk_score": risk_score,
        "key_factors": key_factors,
        "agent_processing_trace": agent_trace,
        "regulatory_flags": regulatory_flags or "NONE",
        "ecoa_compliant": ecoa_compliant,
        "fair_lending_notes": fair_lending_notes,
        "data_retention_period": "7 years",
        "review_required": decision.lower() in ("rejected", "manual_review"),
        "logged_at": timestamp,
        "logged_by": "AUTOMATED_AGENTIC_SYSTEM_v1",
    }

    result = {
        "success": True,
        "log_id": log_id,
        "compliance_record": compliance_record,
        "audit_trail_entry": (
            f"[{timestamp}] Case {case_id} | Applicant {applicant_id} | "
            f"Decision: {decision.upper()} | Risk: {risk_score:.1f} | "
            f"Logged by: AGENTIC_SYSTEM"
        ),
        "regulatory_requirements": fair_lending_notes,
    }
    return json.dumps(result)


@mcp.tool()
def compose_decision_summary(
    case_id: str,
    applicant_id: str,
    decision: str,
    risk_score: float,
    confidence_level: float,
    key_factors: str,
    loan_amount: float,
    tenure_months: int,
    credit_score: int,
    dti_ratio: float,
    explanation: str,
) -> str:
    """
    Compose a comprehensive, human-readable decision summary.

    Args:
        case_id: Case identifier
        applicant_id: Applicant identifier
        decision: Final decision
        risk_score: 0-100 risk score
        confidence_level: 0-1 confidence
        key_factors: Pipe-separated key factors
        loan_amount: Requested loan amount
        tenure_months: Loan tenure
        credit_score: FICO score
        dti_ratio: Debt-to-income ratio
        explanation: Detailed explanation
    """
    timestamp = datetime.now().isoformat()

    decision_emoji = {"approved": "✅", "rejected": "❌", "manual_review": "🔍"}.get(
        decision.lower(), "📋"
    )

    decision_title = {
        "approved": "LOAN APPLICATION APPROVED",
        "rejected": "LOAN APPLICATION REJECTED",
        "manual_review": "LOAN APPLICATION — MANUAL REVIEW REQUIRED",
    }.get(decision.lower(), f"LOAN APPLICATION — {decision.upper()}")

    factors_list = [f.strip() for f in key_factors.split("|") if f.strip()]

    tenure_years = tenure_months / 12
    risk_level_label = (
        "Low" if risk_score <= 30 else
        "Moderate" if risk_score <= 55 else
        "High" if risk_score <= 75 else "Critical"
    )

    summary = {
        "case_id": case_id,
        "applicant_id": applicant_id,
        "decision": decision.upper(),
        "decision_title": decision_title,
        "timestamp": timestamp,
        "risk_score": risk_score,
        "risk_level": risk_level_label,
        "confidence": f"{confidence_level * 100:.0f}%",
        "application_details": {
            "loan_amount": f"${loan_amount:,.0f}",
            "tenure": f"{tenure_months} months ({tenure_years:.1f} years)",
            "credit_score": credit_score,
            "dti_ratio": f"{dti_ratio:.1f}%",
        },
        "key_decision_factors": factors_list,
        "explanation": explanation,
        "next_steps": _get_next_steps(decision),
        "formatted_report": _format_report(
            decision_title, case_id, applicant_id, loan_amount,
            tenure_months, credit_score, dti_ratio, risk_score,
            confidence_level, factors_list, explanation, timestamp
        ),
    }
    return json.dumps(summary)


def _get_next_steps(decision: str) -> list:
    steps = {
        "approved": [
            "Review and sign the loan agreement documents",
            "Provide any outstanding supporting documents",
            "Complete identity verification if not already done",
            "Funds will be disbursed within 3-5 business days after signing",
        ],
        "rejected": [
            "Request a written explanation of the rejection (ECOA right)",
            "Review your credit report for errors at annualcreditreport.com",
            "Work on improving credit score and reducing debt",
            "Reapply after 90 days or when financial situation improves",
        ],
        "manual_review": [
            "A loan officer will contact you within 3-5 business days",
            "Prepare additional income verification documents",
            "Be ready to explain any credit inquiries or recent changes",
            "Check your email for further instructions",
        ],
    }
    return steps.get(decision.lower(), ["Contact customer support for further assistance"])


def _format_report(
    title, case_id, applicant_id, loan_amount, tenure_months,
    credit_score, dti_ratio, risk_score, confidence, factors, explanation, ts
) -> str:
    factors_text = "\n".join(f"  • {f}" for f in factors[:5])
    return (
        f"{'=' * 60}\n"
        f"{title}\n"
        f"{'=' * 60}\n"
        f"Case ID:        {case_id}\n"
        f"Applicant ID:   {applicant_id}\n"
        f"Processed At:   {ts[:19].replace('T', ' ')}\n"
        f"{'─' * 60}\n"
        f"LOAN DETAILS\n"
        f"  Amount:       ${loan_amount:,.0f}\n"
        f"  Tenure:       {tenure_months} months\n"
        f"  Credit Score: {credit_score}\n"
        f"  DTI Ratio:    {dti_ratio:.1f}%\n"
        f"{'─' * 60}\n"
        f"RISK ASSESSMENT\n"
        f"  Risk Score:   {risk_score:.1f}/100\n"
        f"  Confidence:   {confidence * 100:.0f}%\n"
        f"{'─' * 60}\n"
        f"KEY DECISION FACTORS\n"
        f"{factors_text}\n"
        f"{'─' * 60}\n"
        f"EXPLANATION\n"
        f"  {explanation[:400]}\n"
        f"{'=' * 60}\n"
    )


if __name__ == "__main__":
    mcp.run()
