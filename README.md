# Agentic AI Intelligent Loan Approval System

A production-grade **Multi-Agent Agentic AI** system that evaluates loan applications and classifies them as **Approved**, **Rejected**, or **Requires Manual Review** — with full explainability and audit trails.

---

## Architecture Overview

```
[Streamlit UI] ──POST──► [FastAPI Microservice]
                               │
                        [LangGraph Orchestrator]
                               │
              ┌────────────────┼────────────────┐
              ▼                ▼                ▼
   [ApplicantProfile    [FinancialRisk     [LoanDecision
      Agent]               Agent]            Agent]
      MCP: ApplicantDB     MCP: RiskRulesDB  MCP: DecisionSynthesis
              └────────────────┼────────────────┘
                               ▼
                    [Compliance Agent]
                    MCP: NotificationSystem
                               │
                        [Decision + Case ID]
                               │
                        [WebSocket ──► UI]
```

### Layers

| Layer | Technology | Responsibility |
|-------|-----------|---------------|
| **Presentation** | Streamlit | Chatbot UI — form submission & result display |
| **Microservice** | FastAPI | REST API — validate, queue, serve results |
| **Orchestration** | LangGraph | Sequential 4-node agent pipeline |
| **Agents** | Anthropic Claude SDK | Domain-specific AI reasoning per agent |
| **Communication** | FastMCP (stdio) | Tool servers for each agent |

---

## Agents & MCP Servers

### 1. Applicant Profile Agent → `ApplicantDB` MCP
Outputs: Income Stability Score · Employment Risk · Credit History Summary · Application Completeness Flags

### 2. Financial Risk Analysis Agent → `RiskRulesDB` MCP
Outputs: Debt-to-Income Ratio · Credit Score Risk Level · Loan Amount Risk · Anomaly Detection · Reasoning

### 3. Loan Decision Agent → `DecisionSynthesis` MCP
Outputs: Classification (Approve/Reject/Review) · Risk Score · Confidence Level · Key Decision Factors · Explanation

### 4. Compliance & Action Orchestrator Agent → `NotificationSystem` MCP
Outputs: Action Taken · Notification Sent · Case ID · Timestamp · Summary · Audit Trail

---

## Technology Stack

| Component | Technology |
|-----------|-----------|
| Chatbot UI | Streamlit (Python) |
| Microservice API | FastAPI + Uvicorn |
| Orchestration | LangGraph |
| MCP Framework | FastMCP |
| LLM | Anthropic Claude Sonnet 4.6 |
| Agent SDK | Anthropic AsyncAnthropic |
| Transport | MCP stdio (subprocess per agent call) |

---

## Input Parameters

| Field | Type | Description |
|-------|------|-------------|
| `applicant_id` | string | Unique applicant identifier |
| `age` | int (18–100) | Applicant age |
| `annual_income` | float | Annual income in USD |
| `employment_type` | enum | salaried / self_employed / business_owner / freelancer / retired / unemployed |
| `credit_score` | int (300–850) | FICO credit score |
| `loan_amount` | float | Requested loan amount |
| `tenure_months` | int (6–360) | Loan tenure |
| `existing_liabilities` | float | Current monthly debt obligations |
| `location` | string | Applicant city/state |

---

## Quick Start

### 1. Clone & configure

```bash
cd /home/ubuntu/loan_approval_system
cp .env.example .env
# Edit .env and set your ANTHROPIC_API_KEY
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Start all services

```bash
./start_services.sh
```

### 4. Open the UI

| Service | URL |
|---------|-----|
| Streamlit UI | http://localhost:8501 |
| FastAPI Docs | http://localhost:8000/docs |
| Health Check | http://localhost:8000/health |

---

## API Reference

### Submit a Loan Application
```bash
POST /api/v1/loans
Content-Type: application/json

{
  "applicant_id": "APPL-001",
  "age": 35,
  "annual_income": 75000,
  "employment_type": "salaried",
  "credit_score": 720,
  "loan_amount": 50000,
  "tenure_months": 60,
  "existing_liabilities": 500,
  "location": "New York, NY"
}
```

### Poll Application Status
```bash
GET /api/v1/loans/{application_id}
```

### WebSocket — Real-time Progress
```
ws://localhost:8000/ws/loans/{application_id}
```

---

## Decision Logic

| Condition | Decision |
|-----------|---------|
| Risk score ≤ 30 AND credit ≥ 700 AND DTI ≤ 36% AND no anomalies | **APPROVED** |
| Credit < 500 OR DTI > 55% OR ≥ 3 anomalies | **REJECTED** |
| All other cases | **MANUAL REVIEW** |

---

## Project Structure

```
loan_approval_system/
├── config.py                        # Centralised config (env vars)
├── requirements.txt
├── .env.example                     # Template — copy to .env
├── start_services.sh                # One-command launcher
├── models/schemas.py                # Pydantic models
├── mcp_servers/
│   ├── applicant_db_server.py       # ApplicantDB MCP (4 tools)
│   ├── risk_rules_server.py         # RiskRulesDB MCP (4 tools)
│   ├── decision_synthesis_server.py # DecisionSynthesis MCP (4 tools)
│   └── notification_server.py      # NotificationSystem MCP (4 tools)
├── agents/
│   ├── base_agent.py                # MCP + AsyncAnthropic tool-use loop
│   ├── applicant_profile_agent.py
│   ├── financial_risk_agent.py
│   ├── loan_decision_agent.py
│   └── compliance_agent.py
├── orchestrator/
│   ├── state.py                     # LangGraph TypedDict state
│   └── graph.py                     # 4-node sequential pipeline
├── api/main.py                      # FastAPI — REST + WebSocket
└── ui/app.py                        # Streamlit chatbot UI
```

---

## Evaluation Criteria Addressed

| Criterion | Implementation |
|-----------|---------------|
| Agentic AI architecture | 4 domain agents, each with own MCP server and Claude LLM loop |
| LangGraph orchestration | Sequential StateGraph with 4 nodes and failure routing |
| Clear agent responsibilities | Each agent has a single domain, dedicated MCP server, and strict output schema |
| MCP usage | FastMCP stdio servers with 4 tools each (16 tools total) |
| Explainable AI outputs | Key decision factors, confidence level, reasoning paragraphs, full audit trail |
| Auditable decisions | Case ID, compliance log, ECOA notices, 7-year data retention flag |
