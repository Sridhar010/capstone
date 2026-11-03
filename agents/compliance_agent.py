"""
Agent 4: Compliance & Action Orchestrator Agent
Handles case ID generation, decision notifications, compliance logging,
and final summary composition via the NotificationSystem MCP server.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.base_agent import BaseAgent
from config import NOTIFICATION_SERVER
from models.schemas import LoanApplication

SYSTEM_PROMPT = """You are the Compliance & Action Orchestrator Agent for an Agentic AI Loan Approval System.

Your responsibility is to handle all post-decision compliance, notifications, and record-keeping.

WORKFLOW:
1. Call `generate_case_id` to create a unique case identifier
2. Call `record_compliance_log` to create the regulatory audit trail
3. Call `dispatch_notification` to send the decision notification to the applicant
4. Call `compose_decision_summary` to create the comprehensive final summary

After calling all tools, respond with a JSON object in this EXACT format:

```json
{
  "action_taken": "<description of actions taken>",
  "notification_sent": <true|false>,
  "case_id": "<case ID string>",
  "timestamp": "<ISO timestamp>",
  "summary": "<brief one-paragraph summary>",
  "compliance_flags": ["<flag1>", "<flag2>"],
  "audit_trail": ["<entry1>", "<entry2>"]
}
```

Ensure all regulatory requirements are met and the audit trail is complete.
"""


class ComplianceAgent(BaseAgent):
    def __init__(self) -> None:
        super().__init__(
            mcp_server_script=NOTIFICATION_SERVER,
            agent_name="ComplianceAgent",
            system_prompt=SYSTEM_PROMPT,
        )

    async def process(
        self,
        application: LoanApplication,
        profile_result: dict[str, Any],
        risk_result: dict[str, Any],
        decision_result: dict[str, Any],
    ) -> dict[str, Any]:
        key_factors = decision_result.get("key_decision_factors", [])
        factors_pipe = " | ".join(key_factors[:5]) if key_factors else "N/A"

        agent_trace = (
            "ApplicantProfileAgent → FinancialRiskAgent → LoanDecisionAgent → ComplianceAgent"
        )

        anomalies = risk_result.get("anomalies_detected", [])
        regulatory_flags = "AML_REVIEW_REQUIRED" if len(anomalies) >= 2 else ""

        prompt = f"""Process compliance and notifications for the completed loan decision:

APPLICATION DETAILS:
- Applicant ID: {application.applicant_id}
- Loan Amount: ${application.loan_amount:,.2f}
- Tenure: {application.tenure_months} months
- Credit Score: {application.credit_score}
- Location: {application.location}

FINAL DECISION:
- Classification: {decision_result.get('classification', 'unknown').upper()}
- Risk Score: {decision_result.get('risk_score', 0):.1f}/100
- Confidence Level: {decision_result.get('confidence_level', 0):.0%}
- Explanation: {decision_result.get('explanation', 'No explanation provided')[:300]}

KEY DECISION FACTORS: {factors_pipe}

RISK SUMMARY:
- DTI Ratio: {risk_result.get('debt_to_income_ratio', 0):.1f}%
- Anomalies: {', '.join(anomalies) if anomalies else 'None'}
- Regulatory Flags: {regulatory_flags or 'None'}

AGENT PROCESSING TRACE: {agent_trace}

Execute the full compliance workflow:
1. Generate a case ID
2. Log compliance record with full audit trail
3. Dispatch notification to applicant
4. Compose the final decision summary

Output the compliance results as JSON."""

        return await self.run(prompt)
