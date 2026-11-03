"""
Agent 2: Financial Risk Analysis Agent
Computes DTI ratio, credit risk level, loan amount risk,
and detects anomalies using the RiskRulesDB MCP server.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.base_agent import BaseAgent
from config import RISK_RULES_SERVER
from models.schemas import LoanApplication

SYSTEM_PROMPT = """You are the Financial Risk Analysis Agent for an Agentic AI Loan Approval System.

Your responsibility is to perform comprehensive financial risk analysis using the available tools.

WORKFLOW:
1. Call `calculate_debt_to_income_ratio` to compute the DTI ratio and monthly payment estimate
2. Call `assess_credit_score_risk` to evaluate credit-based risk
3. Call `evaluate_loan_amount_risk` to assess whether the loan amount is appropriate
4. Call `detect_financial_anomalies` to identify any suspicious patterns

After calling all tools, synthesize the findings and respond with a JSON object in this EXACT format:

```json
{
  "debt_to_income_ratio": <float percentage>,
  "credit_score_risk_level": "<low|medium|high|critical>",
  "loan_amount_risk": "<low|medium|high|critical>",
  "anomalies_detected": ["<anomaly1>", "<anomaly2>"],
  "loan_to_income_ratio": <float>,
  "monthly_payment_estimate": <float>,
  "payment_to_income_ratio": <float percentage>,
  "reasoning": "<comprehensive risk reasoning paragraph>"
}
```

Be analytical and precise. Base all values on tool outputs.
"""


class FinancialRiskAgent(BaseAgent):
    def __init__(self) -> None:
        super().__init__(
            mcp_server_script=RISK_RULES_SERVER,
            agent_name="FinancialRiskAgent",
            system_prompt=SYSTEM_PROMPT,
        )

    async def analyze(
        self,
        application: LoanApplication,
        profile_result: dict[str, Any],
    ) -> dict[str, Any]:
        prompt = f"""Perform financial risk analysis for the following loan application:

Applicant ID: {application.applicant_id}
Annual Income: ${application.annual_income:,.2f}
Monthly Income: ${profile_result.get('monthly_income', application.annual_income / 12):,.2f}
Employment Type: {application.employment_type.value}
Credit Score: {application.credit_score}
Loan Amount Requested: ${application.loan_amount:,.2f}
Loan Tenure: {application.tenure_months} months
Existing Monthly Liabilities: ${application.existing_liabilities:,.2f}
Age: {application.age}

Profile Analysis Results:
- Income Stability Score: {profile_result.get('income_stability_score', 'N/A')}
- Employment Risk: {profile_result.get('employment_risk', 'N/A')}

Use ALL available tools to perform comprehensive financial risk analysis.
After completing all tool calls, output your final risk assessment as JSON."""

        return await self.run(prompt)
