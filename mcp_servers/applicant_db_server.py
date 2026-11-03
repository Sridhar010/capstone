"""
MCP Server: ApplicantDB
Provides tools for analyzing applicant profile data.
"""
import json
import sys
from pathlib import Path

from fastmcp import FastMCP

sys.path.insert(0, str(Path(__file__).parent.parent))

mcp = FastMCP(
    "ApplicantDB",
    instructions=(
        "Tools for analyzing loan applicant profile data including income stability, "
        "employment risk, and credit history."
    ),
)


@mcp.tool()
def analyze_income_stability(
    annual_income: float,
    employment_type: str,
    loan_amount: float,
) -> str:
    """
    Analyze the income stability of an applicant.
    Returns a stability score (0-1) and stability category.

    Args:
        annual_income: Annual income in USD
        employment_type: Type of employment (salaried/self_employed/business_owner/freelancer/retired/unemployed)
        loan_amount: Requested loan amount
    """
    stability_weights = {
        "salaried": 0.90,
        "business_owner": 0.75,
        "self_employed": 0.65,
        "retired": 0.80,
        "freelancer": 0.55,
        "unemployed": 0.10,
    }
    base_score = stability_weights.get(employment_type.lower(), 0.50)

    # Adjust for income-to-loan ratio
    income_to_loan = annual_income / max(loan_amount, 1)
    if income_to_loan > 5:
        base_score = min(1.0, base_score + 0.10)
    elif income_to_loan < 1:
        base_score = max(0.0, base_score - 0.20)
    elif income_to_loan < 2:
        base_score = max(0.0, base_score - 0.10)

    if base_score >= 0.80:
        category = "HIGHLY_STABLE"
    elif base_score >= 0.60:
        category = "STABLE"
    elif base_score >= 0.40:
        category = "MODERATELY_STABLE"
    else:
        category = "UNSTABLE"

    result = {
        "income_stability_score": round(base_score, 3),
        "stability_category": category,
        "annual_income": annual_income,
        "monthly_income": round(annual_income / 12, 2),
        "employment_type": employment_type,
        "income_to_loan_ratio": round(income_to_loan, 2),
        "analysis": (
            f"Applicant with {employment_type} employment and annual income of "
            f"${annual_income:,.0f} has a stability score of {base_score:.2f} "
            f"({category}). Income-to-loan ratio: {income_to_loan:.2f}x."
        ),
    }
    return json.dumps(result)


@mcp.tool()
def assess_employment_risk(
    employment_type: str,
    age: int,
    years_in_current_job: int = 0,
) -> str:
    """
    Assess employment risk for the applicant.

    Args:
        employment_type: Type of employment
        age: Applicant age in years
        years_in_current_job: Years in current position (0 if unknown)
    """
    risk_map = {
        "salaried": "low",
        "retired": "low",
        "business_owner": "medium",
        "self_employed": "medium",
        "freelancer": "high",
        "unemployed": "critical",
    }
    base_risk = risk_map.get(employment_type.lower(), "medium")

    risk_scores = {"low": 1, "medium": 2, "high": 3, "critical": 4}
    score = risk_scores[base_risk]

    # Age adjustments
    if age < 25:
        score = min(score + 1, 4)
    elif age > 60 and employment_type not in ("retired", "business_owner"):
        score = min(score + 1, 4)

    # Tenure adjustment
    if years_in_current_job >= 5:
        score = max(score - 1, 1)

    final_risk = {v: k for k, v in risk_scores.items()}[min(score, 4)]

    risk_factors = []
    if employment_type == "unemployed":
        risk_factors.append("Applicant is currently unemployed")
    if age < 25:
        risk_factors.append("Young applicant — limited work history likely")
    if employment_type in ("freelancer", "self_employed"):
        risk_factors.append("Variable income stream from non-salaried work")
    if years_in_current_job < 2 and employment_type != "unemployed":
        risk_factors.append("Less than 2 years in current position")

    result = {
        "employment_risk_level": final_risk,
        "risk_score": score,
        "employment_type": employment_type,
        "age": age,
        "risk_factors": risk_factors,
        "assessment": (
            f"{employment_type.replace('_', ' ').title()} at age {age} "
            f"presents {final_risk.upper()} employment risk."
        ),
    }
    return json.dumps(result)


@mcp.tool()
def get_credit_history_summary(
    credit_score: int,
    existing_liabilities: float,
    annual_income: float,
) -> str:
    """
    Generate a credit history summary based on credit score and liabilities.

    Args:
        credit_score: FICO credit score (300-850)
        existing_liabilities: Total existing monthly debt payments in USD
        annual_income: Annual income in USD
    """
    if credit_score >= 800:
        grade = "EXCEPTIONAL"
        description = "Exceptional credit — applicant demonstrates outstanding credit management"
    elif credit_score >= 740:
        grade = "VERY_GOOD"
        description = "Very good credit — well above average financial responsibility"
    elif credit_score >= 670:
        grade = "GOOD"
        description = "Good credit — meets most lender requirements comfortably"
    elif credit_score >= 580:
        grade = "FAIR"
        description = "Fair credit — may face stricter terms or higher rates"
    else:
        grade = "POOR"
        description = "Poor credit — significant risk indicator; high likelihood of default"

    monthly_income = annual_income / 12
    existing_dti = (existing_liabilities / monthly_income * 100) if monthly_income > 0 else 0

    result = {
        "credit_score": credit_score,
        "credit_grade": grade,
        "credit_description": description,
        "existing_monthly_liabilities": existing_liabilities,
        "existing_dti_percentage": round(existing_dti, 2),
        "credit_percentile": _score_to_percentile(credit_score),
        "summary": (
            f"Credit score {credit_score} ({grade}). {description}. "
            f"Existing monthly obligations of ${existing_liabilities:,.0f} "
            f"represent {existing_dti:.1f}% of monthly income."
        ),
    }
    return json.dumps(result)


@mcp.tool()
def check_application_completeness(
    applicant_id: str,
    age: int,
    annual_income: float,
    employment_type: str,
    credit_score: int,
    loan_amount: float,
    tenure_months: int,
    existing_liabilities: float,
    location: str,
) -> str:
    """
    Verify that all required fields are present and within valid ranges.

    Args:
        applicant_id: Unique applicant ID
        age: Applicant age
        annual_income: Annual income
        employment_type: Employment type
        credit_score: FICO credit score
        loan_amount: Requested loan amount
        tenure_months: Loan tenure in months
        existing_liabilities: Monthly existing debt
        location: Applicant location
    """
    flags = []
    warnings = []

    if age < 18:
        flags.append("AGE_BELOW_MINIMUM: Applicant must be at least 18 years old")
    if age > 75:
        warnings.append("AGE_ABOVE_THRESHOLD: Applicant is above 75 — review repayment timeline")

    if annual_income <= 0:
        flags.append("INVALID_INCOME: Income must be greater than zero")
    elif annual_income < 15000:
        warnings.append("LOW_INCOME: Annual income below $15,000")

    if credit_score < 300 or credit_score > 850:
        flags.append(f"INVALID_CREDIT_SCORE: Score {credit_score} outside valid range 300-850")

    if loan_amount <= 0:
        flags.append("INVALID_LOAN_AMOUNT: Loan amount must be positive")
    if loan_amount > annual_income * 10:
        warnings.append("HIGH_LOAN_TO_INCOME: Loan exceeds 10x annual income")

    if tenure_months < 6 or tenure_months > 360:
        flags.append(f"INVALID_TENURE: {tenure_months} months outside allowed range 6-360")

    valid_employment = {
        "salaried", "self_employed", "business_owner", "freelancer", "retired", "unemployed"
    }
    if employment_type.lower() not in valid_employment:
        flags.append(f"INVALID_EMPLOYMENT_TYPE: '{employment_type}' is not recognized")

    if not location or len(location.strip()) < 2:
        flags.append("MISSING_LOCATION: Location information is required")

    is_complete = len(flags) == 0
    result = {
        "applicant_id": applicant_id,
        "is_complete": is_complete,
        "critical_flags": flags,
        "warnings": warnings,
        "completeness_score": 1.0 - (len(flags) * 0.25),
        "status": "COMPLETE" if is_complete else "INCOMPLETE",
        "summary": (
            f"Application {applicant_id}: {'Complete' if is_complete else 'Incomplete'}. "
            f"{len(flags)} critical flag(s), {len(warnings)} warning(s)."
        ),
    }
    return json.dumps(result)


def _score_to_percentile(score: int) -> int:
    """Approximate FICO percentile mapping."""
    if score >= 800:
        return 99
    elif score >= 750:
        return 85
    elif score >= 700:
        return 65
    elif score >= 650:
        return 45
    elif score >= 600:
        return 25
    else:
        return 10


if __name__ == "__main__":
    mcp.run()
