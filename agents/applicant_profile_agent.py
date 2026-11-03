"""
Agent 1: Applicant Profile Agent
Analyzes applicant demographics, income stability, employment risk,
and credit history using the ApplicantDB MCP server.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.base_agent import BaseAgent
from config import APPLICANT_DB_SERVER
from models.schemas import LoanApplication

SYSTEM_PROMPT = """You are the Applicant Profile Agent for an Agentic AI Loan Approval System.

Your responsibility is to thoroughly analyze the applicant's profile using the available tools.

WORKFLOW:
1. First call `check_application_completeness` to validate all fields are present and valid
2. Call `analyze_income_stability` to compute income stability score
3. Call `assess_employment_risk` to determine employment risk level
4. Call `get_credit_history_summary` to summarize credit history and DTI context

After calling all tools, synthesize the findings and respond with a JSON object in this EXACT format:

```json
{
  "income_stability_score": <float 0.0-1.0>,
  "employment_risk": "<low|medium|high|critical>",
  "credit_history_summary": "<detailed summary string>",
  "application_completeness_flags": ["<flag1>", "<flag2>"],
  "monthly_income": <float>,
  "debt_to_income_ratio": <float percentage>,
  "analysis_notes": "<comprehensive analysis paragraph>"
}
```

Be precise and objective. Use exact values from tool outputs.
"""


class ApplicantProfileAgent(BaseAgent):
    def __init__(self) -> None:
        super().__init__(
            mcp_server_script=APPLICANT_DB_SERVER,
            agent_name="ApplicantProfileAgent",
            system_prompt=SYSTEM_PROMPT,
        )

    async def analyze(self, application: LoanApplication) -> dict[str, Any]:
        prompt = f"""Analyze the following loan applicant's profile:

Applicant ID: {application.applicant_id}
Age: {application.age}
Annual Income: ${application.annual_income:,.2f}
Employment Type: {application.employment_type.value}
Credit Score: {application.credit_score}
Loan Amount Requested: ${application.loan_amount:,.2f}
Loan Tenure: {application.tenure_months} months
Existing Monthly Liabilities: ${application.existing_liabilities:,.2f}
Location: {application.location}
Application Timestamp: {application.application_timestamp}

Use ALL available tools to perform a comprehensive profile analysis.
After completing all tool calls, output your final analysis as JSON."""

        return await self.run(prompt)
