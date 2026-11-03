"""
Agent 3: Loan Decision Agent
Synthesizes profile and risk results to produce a final loan classification
with confidence level and key decision factors, via the DecisionSynthesis MCP server.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.base_agent import BaseAgent
from config import DECISION_SYNTHESIS_SERVER
from models.schemas import LoanApplication

SYSTEM_PROMPT = """You are the Loan Decision Agent for an Agentic AI Loan Approval System.

Your responsibility is to make a final, explainable loan decision by synthesizing all prior analysis.

WORKFLOW:
1. Call `compute_composite_risk_score` to produce a weighted overall risk score
2. Call `classify_loan_application` using the composite score and key signals
3. Call `calculate_confidence_level` to determine decision confidence
4. Call `extract_key_decision_factors` to identify the top factors driving the decision

After calling all tools, synthesize the findings and respond with a JSON object in this EXACT format:

```json
{
  "classification": "<approved|rejected|manual_review>",
  "risk_score": <float 0.0-100.0>,
  "confidence_level": <float 0.0-1.0>,
  "key_decision_factors": ["<factor1>", "<factor2>", "<factor3>"],
  "explanation": "<detailed, human-readable explanation of the decision>",
  "recommended_loan_amount": <float or null>,
  "recommended_tenure_months": <int or null>,
  "conditions": ["<condition1>", "<condition2>"]
}
```

For `recommended_loan_amount`: if approved or manual review, suggest an amount (same or reduced if warranted); set to null if rejected.
For `conditions`: list any conditions that must be met (e.g., "Provide 6 months of bank statements").
Be transparent, fair, and provide a clear explanation.
"""


class LoanDecisionAgent(BaseAgent):
    def __init__(self) -> None:
        super().__init__(
            mcp_server_script=DECISION_SYNTHESIS_SERVER,
            agent_name="LoanDecisionAgent",
            system_prompt=SYSTEM_PROMPT,
        )

    async def decide(
        self,
        application: LoanApplication,
        profile_result: dict[str, Any],
        risk_result: dict[str, Any],
    ) -> dict[str, Any]:
        anomalies = risk_result.get("anomalies_detected", [])
        anomaly_str = ", ".join(anomalies) if anomalies else "None detected"

        prompt = f"""Make a final loan decision for the following application:

APPLICATION DETAILS:
- Applicant ID: {application.applicant_id}
- Loan Amount: ${application.loan_amount:,.2f}
- Tenure: {application.tenure_months} months
- Credit Score: {application.credit_score}

PROFILE ANALYSIS:
- Income Stability Score: {profile_result.get('income_stability_score', 0)}
- Employment Risk Level: {profile_result.get('employment_risk', 'unknown')}
- Monthly Income: ${profile_result.get('monthly_income', 0):,.2f}
- Profile DTI: {profile_result.get('debt_to_income_ratio', 0):.1f}%

FINANCIAL RISK ANALYSIS:
- Debt-to-Income Ratio: {risk_result.get('debt_to_income_ratio', 0):.1f}%
- Credit Score Risk Level: {risk_result.get('credit_score_risk_level', 'unknown')}
- Loan Amount Risk: {risk_result.get('loan_amount_risk', 'unknown')}
- Loan-to-Income Ratio: {risk_result.get('loan_to_income_ratio', 0):.2f}x
- Monthly Payment Estimate: ${risk_result.get('monthly_payment_estimate', 0):,.2f}
- Anomalies Detected: {anomaly_str}
- Anomaly Count: {len(anomalies)}

Use ALL available tools in sequence to compute risk score, classify the application,
determine confidence, and extract key factors.
Then output your final decision as JSON."""

        return await self.run(prompt)
