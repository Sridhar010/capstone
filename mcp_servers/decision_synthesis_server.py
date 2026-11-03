"""
MCP Server: DecisionSynthesis
Combines all risk signals to produce a final loan classification.
"""
import json
import sys
from pathlib import Path

from fastmcp import FastMCP

sys.path.insert(0, str(Path(__file__).parent.parent))

mcp = FastMCP(
    "DecisionSynthesis",
    instructions=(
        "Tools for synthesizing all risk signals into a final loan decision including "
        "composite risk scoring, classification, confidence estimation, and factor extraction."
    ),
)


@mcp.tool()
def compute_composite_risk_score(
    income_stability_score: float,
    employment_risk_level: str,
    credit_score: int,
    dti_ratio: float,
    credit_risk_level: str,
    loan_amount_risk: str,
    anomaly_risk_score: int,
    anomaly_count: int,
) -> str:
    """
    Compute a weighted composite risk score (0-100) from all signals.
    Higher score = higher risk.

    Args:
        income_stability_score: 0-1 (higher = more stable)
        employment_risk_level: low/medium/high/critical
        credit_score: 300-850
        dti_ratio: Debt-to-income ratio (percentage)
        credit_risk_level: low/medium/high/critical
        loan_amount_risk: low/medium/high/critical
        anomaly_risk_score: 0-100
        anomaly_count: Number of detected anomalies
    """
    risk_level_to_score = {"low": 20, "medium": 45, "high": 70, "critical": 90}

    # Component scores (all normalized to 0-100, higher = riskier)
    income_risk = round((1 - income_stability_score) * 100, 1)
    employment_risk_score = risk_level_to_score.get(employment_risk_level.lower(), 50)
    credit_score_risk = max(0, min(100, round((850 - credit_score) / 5.5, 1)))
    dti_risk = min(100, max(0, round((dti_ratio - 20) * 2, 1)))
    credit_level_risk = risk_level_to_score.get(credit_risk_level.lower(), 50)
    loan_risk = risk_level_to_score.get(loan_amount_risk.lower(), 50)
    anomaly_factor = min(100, anomaly_risk_score + anomaly_count * 10)

    # Weighted composite (weights sum to 1.0)
    weights = {
        "income_risk": 0.15,
        "employment_risk": 0.15,
        "credit_score_risk": 0.20,
        "dti_risk": 0.20,
        "credit_level_risk": 0.10,
        "loan_risk": 0.10,
        "anomaly_factor": 0.10,
    }

    composite = (
        income_risk * weights["income_risk"]
        + employment_risk_score * weights["employment_risk"]
        + credit_score_risk * weights["credit_score_risk"]
        + dti_risk * weights["dti_risk"]
        + credit_level_risk * weights["credit_level_risk"]
        + loan_risk * weights["loan_risk"]
        + anomaly_factor * weights["anomaly_factor"]
    )
    composite = round(min(100, max(0, composite)), 2)

    component_breakdown = {
        "income_stability_risk": income_risk,
        "employment_risk": employment_risk_score,
        "credit_score_risk": credit_score_risk,
        "dti_risk": dti_risk,
        "credit_level_risk": credit_level_risk,
        "loan_amount_risk": loan_risk,
        "anomaly_risk": anomaly_factor,
    }

    result = {
        "composite_risk_score": composite,
        "component_breakdown": component_breakdown,
        "risk_category": _score_to_category(composite),
        "analysis": (
            f"Composite risk score: {composite:.1f}/100 ({_score_to_category(composite)}). "
            f"Primary drivers: credit ({credit_score_risk:.0f}), "
            f"DTI ({dti_risk:.0f}), income stability ({income_risk:.0f})."
        ),
    }
    return json.dumps(result)


@mcp.tool()
def classify_loan_application(
    composite_risk_score: float,
    credit_score: int,
    dti_ratio: float,
    anomaly_count: int,
    income_stability_score: float,
    employment_risk_level: str,
) -> str:
    """
    Classify the loan application as APPROVED, REJECTED, or MANUAL_REVIEW.

    Args:
        composite_risk_score: 0-100 overall risk score
        credit_score: FICO credit score
        dti_ratio: Debt-to-income ratio (%)
        anomaly_count: Number of detected anomalies
        income_stability_score: 0-1 stability score
        employment_risk_level: Risk level string
    """
    hard_rejects = []

    # Automatic rejection criteria
    if credit_score < 500:
        hard_rejects.append(f"Credit score {credit_score} below minimum threshold of 500")
    if dti_ratio > 55:
        hard_rejects.append(f"DTI ratio {dti_ratio:.1f}% exceeds maximum of 55%")
    if anomaly_count >= 3:
        hard_rejects.append(f"{anomaly_count} critical anomalies detected — fraud risk")
    if employment_risk_level.lower() == "critical" and credit_score < 600:
        hard_rejects.append("Unemployed applicant with poor credit — dual high-risk factors")

    if hard_rejects:
        classification = "rejected"
        reason = "Hard rejection criteria met"
        return json.dumps({
            "classification": classification,
            "reason": reason,
            "rejection_reasons": hard_rejects,
            "requires_manual_review": False,
            "summary": f"REJECTED: {hard_rejects[0]}",
        })

    # Automatic approval criteria
    if (
        composite_risk_score <= 30
        and credit_score >= 700
        and dti_ratio <= 36
        and anomaly_count == 0
        and income_stability_score >= 0.70
    ):
        classification = "approved"
        reason = "Strong credit profile across all indicators"
        return json.dumps({
            "classification": classification,
            "reason": reason,
            "rejection_reasons": [],
            "requires_manual_review": False,
            "summary": f"APPROVED: {reason}",
        })

    # Manual review for borderline cases
    classification = "manual_review"
    review_reasons = []
    if 30 < composite_risk_score <= 60:
        review_reasons.append(f"Moderate composite risk score ({composite_risk_score:.1f})")
    if 580 <= credit_score < 700:
        review_reasons.append(f"Fair-to-good credit score ({credit_score}) warrants review")
    if 36 < dti_ratio <= 50:
        review_reasons.append(f"Elevated DTI ratio ({dti_ratio:.1f}%)")
    if anomaly_count == 1:
        review_reasons.append("One anomaly flagged — manual verification recommended")
    if income_stability_score < 0.60:
        review_reasons.append(f"Income stability concern ({income_stability_score:.2f})")

    if not review_reasons:
        review_reasons.append("Borderline case requiring human judgment")

    result = {
        "classification": classification,
        "reason": "Requires manual underwriter review",
        "review_reasons": review_reasons,
        "rejection_reasons": [],
        "requires_manual_review": True,
        "summary": f"MANUAL_REVIEW: {review_reasons[0] if review_reasons else 'Borderline case'}",
    }
    return json.dumps(result)


@mcp.tool()
def calculate_confidence_level(
    composite_risk_score: float,
    classification: str,
    anomaly_count: int,
    data_completeness_score: float,
    dti_ratio: float,
    credit_score: int,
) -> str:
    """
    Calculate the confidence level in the classification decision.

    Args:
        composite_risk_score: 0-100 composite risk
        classification: approved/rejected/manual_review
        anomaly_count: Number of anomalies
        data_completeness_score: 0-1 how complete the application is
        dti_ratio: Debt-to-income ratio
        credit_score: FICO credit score
    """
    base_confidence = 0.95

    # Reduce confidence for borderline scores
    if 35 <= composite_risk_score <= 65:
        base_confidence -= 0.20

    # Anomalies reduce confidence
    base_confidence -= anomaly_count * 0.05

    # Manual review inherently lower confidence
    if classification == "manual_review":
        base_confidence -= 0.10

    # Incomplete data reduces confidence
    base_confidence -= (1 - data_completeness_score) * 0.10

    # Borderline credit score reduces confidence
    if 620 <= credit_score <= 700:
        base_confidence -= 0.05

    confidence = round(max(0.40, min(0.99, base_confidence)), 2)

    if confidence >= 0.90:
        confidence_label = "VERY_HIGH"
    elif confidence >= 0.75:
        confidence_label = "HIGH"
    elif confidence >= 0.60:
        confidence_label = "MODERATE"
    else:
        confidence_label = "LOW"

    result = {
        "confidence_level": confidence,
        "confidence_label": confidence_label,
        "classification": classification,
        "confidence_factors": {
            "risk_score_clarity": composite_risk_score < 35 or composite_risk_score > 65,
            "no_anomalies": anomaly_count == 0,
            "data_complete": data_completeness_score >= 0.90,
        },
        "summary": (
            f"Decision confidence: {confidence:.0%} ({confidence_label}) "
            f"for {classification.upper()} classification."
        ),
    }
    return json.dumps(result)


@mcp.tool()
def extract_key_decision_factors(
    credit_score: int,
    dti_ratio: float,
    income_stability_score: float,
    loan_to_income_ratio: float,
    anomalies: str,
    employment_risk_level: str,
    classification: str,
    composite_risk_score: float,
) -> str:
    """
    Extract the top factors that influenced the loan decision.

    Args:
        credit_score: FICO credit score
        dti_ratio: DTI ratio (%)
        income_stability_score: 0-1 stability
        loan_to_income_ratio: Loan/income ratio
        anomalies: Comma-separated list of detected anomalies
        employment_risk_level: Employment risk
        classification: Final decision
        composite_risk_score: Overall risk score
    """
    factors = []
    positive_factors = []
    negative_factors = []

    # Credit score factors
    if credit_score >= 750:
        positive_factors.append(f"Excellent credit score ({credit_score}) — top-tier borrower")
    elif credit_score >= 700:
        positive_factors.append(f"Good credit score ({credit_score})")
    elif credit_score >= 650:
        negative_factors.append(f"Fair credit score ({credit_score}) — moderate risk")
    else:
        negative_factors.append(f"Poor credit score ({credit_score}) — high default risk")

    # DTI factors
    if dti_ratio <= 28:
        positive_factors.append(f"Low DTI ratio ({dti_ratio:.1f}%) — strong repayment capacity")
    elif dti_ratio <= 36:
        positive_factors.append(f"Acceptable DTI ratio ({dti_ratio:.1f}%)")
    elif dti_ratio <= 43:
        negative_factors.append(f"Borderline DTI ratio ({dti_ratio:.1f}%) — limited capacity")
    else:
        negative_factors.append(f"High DTI ratio ({dti_ratio:.1f}%) — stretched finances")

    # Income stability
    if income_stability_score >= 0.80:
        positive_factors.append(
            f"High income stability ({income_stability_score:.0%}) — reliable repayment source"
        )
    elif income_stability_score < 0.50:
        negative_factors.append(
            f"Low income stability ({income_stability_score:.0%}) — variable repayment risk"
        )

    # Loan size
    if loan_to_income_ratio <= 2.0:
        positive_factors.append(f"Conservative loan-to-income ratio ({loan_to_income_ratio:.1f}x)")
    elif loan_to_income_ratio > 4.0:
        negative_factors.append(f"High loan-to-income ratio ({loan_to_income_ratio:.1f}x)")

    # Employment
    if employment_risk_level.lower() in ("low",):
        positive_factors.append("Stable employment type")
    elif employment_risk_level.lower() in ("high", "critical"):
        negative_factors.append(f"High-risk employment status ({employment_risk_level})")

    # Anomalies
    if anomalies and anomalies.strip() and anomalies.lower() not in ("none", "[]", ""):
        negative_factors.append(f"Application anomalies detected: {anomalies[:100]}")

    # Sort by importance (negatives first for rejections)
    if classification in ("rejected", "manual_review"):
        factors = negative_factors + positive_factors
    else:
        factors = positive_factors + negative_factors

    result = {
        "key_factors": factors[:6],
        "positive_factors": positive_factors,
        "negative_factors": negative_factors,
        "decision_summary": (
            f"Decision '{classification.upper()}' driven primarily by: "
            f"{factors[0] if factors else 'composite risk assessment'}."
        ),
    }
    return json.dumps(result)


def _score_to_category(score: float) -> str:
    if score <= 25:
        return "LOW_RISK"
    elif score <= 45:
        return "MODERATE_RISK"
    elif score <= 65:
        return "HIGH_RISK"
    else:
        return "CRITICAL_RISK"


if __name__ == "__main__":
    mcp.run()
