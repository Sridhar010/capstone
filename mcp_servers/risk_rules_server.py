"""
MCP Server: RiskRulesDB
Provides financial risk analysis tools for loan applications.
"""
import json
import math
import sys
from pathlib import Path

from fastmcp import FastMCP

sys.path.insert(0, str(Path(__file__).parent.parent))

mcp = FastMCP(
    "RiskRulesDB",
    instructions=(
        "Tools for financial risk analysis including DTI ratio, credit risk assessment, "
        "loan amount risk evaluation, and anomaly detection."
    ),
)


@mcp.tool()
def calculate_debt_to_income_ratio(
    annual_income: float,
    existing_monthly_liabilities: float,
    loan_amount: float,
    tenure_months: int,
    interest_rate_estimate: float = 8.5,
) -> str:
    """
    Calculate the Debt-to-Income (DTI) ratio including the proposed loan.

    Args:
        annual_income: Annual income in USD
        existing_monthly_liabilities: Current monthly debt payments
        loan_amount: Requested loan amount
        tenure_months: Loan tenure in months
        interest_rate_estimate: Estimated annual interest rate (default 8.5%)
    """
    monthly_income = annual_income / 12

    # Estimated monthly payment using standard amortization formula
    monthly_rate = interest_rate_estimate / 100 / 12
    if monthly_rate > 0:
        monthly_payment = (
            loan_amount
            * (monthly_rate * (1 + monthly_rate) ** tenure_months)
            / ((1 + monthly_rate) ** tenure_months - 1)
        )
    else:
        monthly_payment = loan_amount / tenure_months

    total_monthly_debt = existing_monthly_liabilities + monthly_payment
    dti_ratio = (total_monthly_debt / monthly_income * 100) if monthly_income > 0 else 100

    if dti_ratio <= 28:
        dti_category = "EXCELLENT"
        dti_risk = "low"
    elif dti_ratio <= 36:
        dti_category = "ACCEPTABLE"
        dti_risk = "low"
    elif dti_ratio <= 43:
        dti_category = "BORDERLINE"
        dti_risk = "medium"
    elif dti_ratio <= 50:
        dti_category = "HIGH"
        dti_risk = "high"
    else:
        dti_category = "CRITICAL"
        dti_risk = "critical"

    result = {
        "monthly_income": round(monthly_income, 2),
        "existing_monthly_liabilities": existing_monthly_liabilities,
        "estimated_monthly_payment": round(monthly_payment, 2),
        "total_monthly_debt": round(total_monthly_debt, 2),
        "dti_ratio": round(dti_ratio, 2),
        "dti_category": dti_category,
        "dti_risk_level": dti_risk,
        "total_loan_cost": round(monthly_payment * tenure_months, 2),
        "analysis": (
            f"DTI ratio of {dti_ratio:.1f}% ({dti_category}). "
            f"Monthly payment ${monthly_payment:,.0f} on top of "
            f"${existing_monthly_liabilities:,.0f} existing obligations. "
            f"Risk level: {dti_risk.upper()}."
        ),
    }
    return json.dumps(result)


@mcp.tool()
def assess_credit_score_risk(
    credit_score: int,
    loan_amount: float,
    annual_income: float,
) -> str:
    """
    Assess the credit risk level based on FICO score and loan parameters.

    Args:
        credit_score: FICO credit score (300-850)
        loan_amount: Requested loan amount
        annual_income: Annual income
    """
    if credit_score >= 750:
        risk_level = "low"
        approval_probability = 0.95
        recommended_rate_premium = 0.0
    elif credit_score >= 700:
        risk_level = "low"
        approval_probability = 0.85
        recommended_rate_premium = 0.5
    elif credit_score >= 650:
        risk_level = "medium"
        approval_probability = 0.70
        recommended_rate_premium = 1.5
    elif credit_score >= 600:
        risk_level = "medium"
        approval_probability = 0.50
        recommended_rate_premium = 3.0
    elif credit_score >= 550:
        risk_level = "high"
        approval_probability = 0.30
        recommended_rate_premium = 5.0
    else:
        risk_level = "critical"
        approval_probability = 0.10
        recommended_rate_premium = 8.0

    # Adjust for loan-to-income
    lti = loan_amount / max(annual_income, 1)
    if lti > 5:
        approval_probability = max(0.05, approval_probability - 0.20)
    elif lti > 3:
        approval_probability = max(0.05, approval_probability - 0.10)

    result = {
        "credit_score": credit_score,
        "credit_risk_level": risk_level,
        "approval_probability": round(approval_probability, 2),
        "recommended_rate_premium_pct": recommended_rate_premium,
        "loan_to_income_ratio": round(lti, 2),
        "credit_risk_factors": _get_credit_risk_factors(credit_score),
        "assessment": (
            f"Credit score {credit_score} indicates {risk_level.upper()} risk. "
            f"Estimated approval probability: {approval_probability * 100:.0f}%. "
            f"Loan-to-income ratio: {lti:.2f}x."
        ),
    }
    return json.dumps(result)


@mcp.tool()
def evaluate_loan_amount_risk(
    loan_amount: float,
    annual_income: float,
    tenure_months: int,
    credit_score: int,
    existing_liabilities: float,
) -> str:
    """
    Evaluate whether the requested loan amount is appropriate.

    Args:
        loan_amount: Requested loan amount
        annual_income: Annual income
        tenure_months: Loan tenure in months
        credit_score: FICO credit score
        existing_liabilities: Monthly existing debt
    """
    monthly_income = annual_income / 12
    lti_ratio = loan_amount / max(annual_income, 1)

    # Maximum loan thresholds by credit score tier
    if credit_score >= 750:
        max_lti = 5.0
    elif credit_score >= 700:
        max_lti = 4.0
    elif credit_score >= 650:
        max_lti = 3.0
    elif credit_score >= 600:
        max_lti = 2.5
    else:
        max_lti = 1.5

    lti_utilization = lti_ratio / max_lti

    if lti_utilization <= 0.60:
        risk_level = "low"
        risk_description = "Loan amount is well within acceptable limits"
    elif lti_utilization <= 0.85:
        risk_level = "medium"
        risk_description = "Loan amount approaches upper limit for credit profile"
    elif lti_utilization <= 1.0:
        risk_level = "high"
        risk_description = "Loan amount is at the maximum for this credit profile"
    else:
        risk_level = "critical"
        risk_description = "Loan amount exceeds recommended maximum for credit profile"

    max_recommended = round(annual_income * max_lti, 2)

    result = {
        "loan_amount": loan_amount,
        "annual_income": annual_income,
        "loan_to_income_ratio": round(lti_ratio, 2),
        "max_recommended_lti": max_lti,
        "max_recommended_loan": max_recommended,
        "lti_utilization_pct": round(lti_utilization * 100, 1),
        "loan_amount_risk": risk_level,
        "risk_description": risk_description,
        "tenure_years": round(tenure_months / 12, 1),
        "assessment": (
            f"Loan amount ${loan_amount:,.0f} is {lti_utilization * 100:.0f}% of the "
            f"recommended maximum (${max_recommended:,.0f}) for this credit profile. "
            f"Risk: {risk_level.upper()}. {risk_description}."
        ),
    }
    return json.dumps(result)


@mcp.tool()
def detect_financial_anomalies(
    credit_score: int,
    annual_income: float,
    loan_amount: float,
    age: int,
    employment_type: str,
    existing_liabilities: float,
    tenure_months: int,
) -> str:
    """
    Detect suspicious patterns or anomalies in the application.

    Args:
        credit_score: FICO credit score
        annual_income: Annual income
        loan_amount: Requested loan amount
        age: Applicant age
        employment_type: Employment type
        existing_liabilities: Monthly existing debt
        tenure_months: Loan tenure
    """
    anomalies = []
    warnings = []
    risk_score = 0

    monthly_income = annual_income / 12

    # Inconsistency: unemployed with high loan request
    if employment_type.lower() == "unemployed" and loan_amount > 10000:
        anomalies.append(
            f"UNEMPLOYED_HIGH_LOAN: Unemployed applicant requesting ${loan_amount:,.0f}"
        )
        risk_score += 30

    # Inconsistency: low income with large loan
    if annual_income < 30000 and loan_amount > annual_income * 3:
        anomalies.append(
            f"LOW_INCOME_HIGH_LOAN: Income ${annual_income:,.0f} vs loan ${loan_amount:,.0f}"
        )
        risk_score += 25

    # High existing liabilities relative to income
    if monthly_income > 0:
        existing_dti = existing_liabilities / monthly_income
        if existing_dti > 0.5:
            anomalies.append(
                f"EXCESSIVE_EXISTING_DEBT: Existing obligations are {existing_dti * 100:.0f}% of income"
            )
            risk_score += 20

    # Very young applicant with high loan
    if age < 22 and loan_amount > 50000:
        warnings.append(f"YOUNG_APPLICANT_HIGH_LOAN: Age {age} requesting ${loan_amount:,.0f}")
        risk_score += 10

    # Loan amount is round number (potential fabrication signal)
    if loan_amount % 100000 == 0 and loan_amount >= 500000:
        warnings.append("ROUND_NUMBER_LARGE_LOAN: Suspiciously round large loan amount")
        risk_score += 5

    # Very long tenure with high credit score (might be avoiding large payments)
    if credit_score >= 750 and tenure_months > 240:
        warnings.append(
            "UNNECESSARILY_LONG_TENURE: High credit score but very long loan tenure"
        )
        risk_score += 5

    # Income/credit score mismatch
    if annual_income > 200000 and credit_score < 600:
        anomalies.append(
            "INCOME_CREDIT_MISMATCH: High income but poor credit score suggests recent financial distress"
        )
        risk_score += 20

    result = {
        "anomalies_detected": anomalies,
        "warnings": warnings,
        "anomaly_count": len(anomalies),
        "warning_count": len(warnings),
        "anomaly_risk_score": min(risk_score, 100),
        "is_clean": len(anomalies) == 0,
        "summary": (
            f"Anomaly detection: {len(anomalies)} critical anomaly(ies), "
            f"{len(warnings)} warning(s). "
            f"Anomaly risk score: {min(risk_score, 100)}/100."
        ),
    }
    return json.dumps(result)


def _get_credit_risk_factors(score: int) -> list:
    factors = []
    if score < 580:
        factors.extend([
            "History of missed payments likely",
            "High credit utilization probable",
            "May have collections or charge-offs",
        ])
    elif score < 670:
        factors.extend([
            "Some payment delays on record",
            "Moderate credit utilization",
        ])
    elif score < 740:
        factors.extend(["Generally responsible credit usage"])
    else:
        factors.extend([
            "Consistent on-time payments",
            "Low credit utilization",
            "Diverse credit mix",
        ])
    return factors


if __name__ == "__main__":
    mcp.run()
