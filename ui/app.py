"""
Streamlit Chatbot UI — Agentic AI Loan Approval System
Provides an interactive interface for loan application submission,
real-time processing status, and detailed decision display.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import httpx
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import STREAMLIT_API_URL

# ── Page configuration ─────────────────────────────────────────────────────────
st.set_page_config(
    page_title="AI Loan Approval System",
    page_icon="🏦",
    layout="wide",
    initial_sidebar_state="expanded",
)

API_BASE = STREAMLIT_API_URL.rstrip("/")

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* Main theme */
.stApp { background-color: #0f1117; color: #e0e0e0; }

/* Decision cards */
.decision-approved {
    background: linear-gradient(135deg, #0d4f1c, #1a7a2e);
    border: 2px solid #2ecc71;
    border-radius: 12px; padding: 20px; margin: 10px 0;
}
.decision-rejected {
    background: linear-gradient(135deg, #4f0d0d, #7a1a1a);
    border: 2px solid #e74c3c;
    border-radius: 12px; padding: 20px; margin: 10px 0;
}
.decision-manual_review {
    background: linear-gradient(135deg, #4f3a0d, #7a5a1a);
    border: 2px solid #f39c12;
    border-radius: 12px; padding: 20px; margin: 10px 0;
}

/* Chat messages */
.chat-message-user {
    background: #1e2334; border-left: 4px solid #3498db;
    border-radius: 8px; padding: 12px 16px; margin: 8px 0;
}
.chat-message-system {
    background: #1a1f2e; border-left: 4px solid #9b59b6;
    border-radius: 8px; padding: 12px 16px; margin: 8px 0;
}
.chat-message-agent {
    background: #1a2a1a; border-left: 4px solid #27ae60;
    border-radius: 8px; padding: 12px 16px; margin: 8px 0;
}

/* Risk score gauge */
.risk-gauge {
    text-align: center; padding: 15px;
    background: #1a1f2e; border-radius: 10px; margin: 10px 0;
}

/* Status badge */
.status-badge {
    display: inline-block; padding: 4px 12px;
    border-radius: 20px; font-size: 12px; font-weight: bold;
}
.badge-pending { background: #34495e; color: #bdc3c7; }
.badge-processing { background: #1a5276; color: #85c1e9; }
.badge-completed { background: #0d4f1c; color: #82e0aa; }
.badge-failed { background: #4f0d0d; color: #f1948a; }

/* Factor list */
.factor-positive { color: #2ecc71; }
.factor-negative { color: #e74c3c; }
.factor-neutral  { color: #f39c12; }

/* Metric boxes */
.metric-box {
    background: #1a1f2e; border-radius: 8px;
    padding: 12px; text-align: center; border: 1px solid #2c3e50;
}
</style>
""", unsafe_allow_html=True)


# ── Session state initialisation ───────────────────────────────────────────────
def _init_session() -> None:
    defaults = {
        "chat_messages": [],
        "current_application_id": None,
        "last_result": None,
        "form_submitted": False,
        "applications_history": [],
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


# ── API helpers ────────────────────────────────────────────────────────────────
def _submit_application(payload: dict) -> dict | None:
    try:
        response = httpx.post(
            f"{API_BASE}/api/v1/loans",
            json=payload,
            timeout=30.0,
        )
        response.raise_for_status()
        return response.json()
    except httpx.ConnectError:
        st.error("❌ Cannot connect to API server. Make sure the FastAPI service is running on port 8000.")
        return None
    except Exception as exc:
        st.error(f"❌ Submission error: {exc}")
        return None


def _poll_result(application_id: str, max_wait: int = 300) -> dict | None:
    """Poll until the application is completed or failed."""
    start = time.time()
    while time.time() - start < max_wait:
        try:
            resp = httpx.get(
                f"{API_BASE}/api/v1/loans/{application_id}",
                timeout=10.0,
            )
            resp.raise_for_status()
            data = resp.json()
            if data.get("status") in ("completed", "failed"):
                return data
            time.sleep(2)
        except Exception:
            time.sleep(2)
    return None


def _get_all_applications() -> list[dict]:
    try:
        resp = httpx.get(f"{API_BASE}/api/v1/loans", timeout=10.0)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return []


# ── Chat helpers ───────────────────────────────────────────────────────────────
def _add_message(role: str, content: str, avatar: str = "") -> None:
    st.session_state.chat_messages.append({
        "role": role, "content": content, "avatar": avatar,
        "timestamp": time.strftime("%H:%M:%S"),
    })


def _render_chat() -> None:
    for msg in st.session_state.chat_messages:
        role = msg["role"]
        avatar = msg.get("avatar", "💬")
        with st.chat_message(role, avatar=avatar):
            st.markdown(msg["content"])


# ── Result rendering ───────────────────────────────────────────────────────────
def _render_decision_card(result: dict) -> None:
    decision = result.get("decision", "manual_review")
    risk_score = result.get("risk_score", 0) or 0
    confidence = result.get("confidence_level", 0) or 0
    explanation = result.get("explanation", "No explanation provided")
    case_id = result.get("case_id", "N/A")
    factors = result.get("key_factors") or []

    decision_icons = {
        "approved": "✅",
        "rejected": "❌",
        "manual_review": "🔍",
    }
    decision_labels = {
        "approved": "LOAN APPROVED",
        "rejected": "LOAN REJECTED",
        "manual_review": "MANUAL REVIEW REQUIRED",
    }

    icon = decision_icons.get(decision, "📋")
    label = decision_labels.get(decision, decision.upper())
    css_class = f"decision-{decision}"

    st.markdown(f"""
    <div class="{css_class}">
        <h2 style="margin:0; color: white;">{icon} {label}</h2>
        <p style="color: #ccc; margin: 4px 0;">Case ID: <strong>{case_id}</strong></p>
    </div>
    """, unsafe_allow_html=True)

    col1, col2, col3, col4 = st.columns(4)

    risk_color = "#2ecc71" if risk_score < 35 else "#f39c12" if risk_score < 65 else "#e74c3c"
    risk_label = "Low" if risk_score < 35 else "Moderate" if risk_score < 65 else "High"

    with col1:
        st.markdown(f"""
        <div class="metric-box">
            <div style="font-size:28px; color:{risk_color}; font-weight:bold;">{risk_score:.1f}</div>
            <div style="font-size:12px; color:#aaa;">Risk Score /100</div>
            <div style="font-size:11px; color:{risk_color};">{risk_label}</div>
        </div>""", unsafe_allow_html=True)

    with col2:
        conf_color = "#2ecc71" if confidence > 0.8 else "#f39c12" if confidence > 0.6 else "#e74c3c"
        st.markdown(f"""
        <div class="metric-box">
            <div style="font-size:28px; color:{conf_color}; font-weight:bold;">{confidence*100:.0f}%</div>
            <div style="font-size:12px; color:#aaa;">Confidence</div>
        </div>""", unsafe_allow_html=True)

    with col3:
        credit_score = result.get("applicant_profile", {})
        if isinstance(credit_score, dict):
            cs = "N/A"
        else:
            cs = str(getattr(credit_score, "credit_history_summary", "N/A"))[:20]
        loan_decision = result.get("loan_decision") or {}
        if isinstance(loan_decision, dict):
            rec_amount = loan_decision.get("recommended_loan_amount")
        else:
            rec_amount = getattr(loan_decision, "recommended_loan_amount", None)
        display = f"${rec_amount:,.0f}" if rec_amount else "—"
        st.markdown(f"""
        <div class="metric-box">
            <div style="font-size:24px; color:#85c1e9; font-weight:bold;">{display}</div>
            <div style="font-size:12px; color:#aaa;">Recommended Amount</div>
        </div>""", unsafe_allow_html=True)

    with col4:
        notification = result.get("compliance", {})
        notif_sent = False
        if isinstance(notification, dict):
            notif_sent = notification.get("notification_sent", False)
        else:
            notif_sent = getattr(notification, "notification_sent", False)
        notif_label = "✅ Sent" if notif_sent else "⏳ Pending"
        notif_color = "#2ecc71" if notif_sent else "#f39c12"
        st.markdown(f"""
        <div class="metric-box">
            <div style="font-size:22px; color:{notif_color}; font-weight:bold;">{notif_label}</div>
            <div style="font-size:12px; color:#aaa;">Notification</div>
        </div>""", unsafe_allow_html=True)

    st.markdown("#### 📋 Decision Explanation")
    st.info(explanation)

    if factors:
        st.markdown("#### 🎯 Key Decision Factors")
        for i, factor in enumerate(factors[:6], 1):
            is_positive = any(w in factor.lower() for w in [
                "excellent", "good", "stable", "low", "strong", "acceptable", "conservative"
            ])
            is_negative = any(w in factor.lower() for w in [
                "poor", "high", "risk", "anomal", "elevated", "critical", "excessive"
            ])
            color = "#2ecc71" if is_positive and not is_negative else "#e74c3c" if is_negative else "#f39c12"
            bullet = "✅" if is_positive and not is_negative else "⚠️" if is_negative else "ℹ️"
            st.markdown(f'<p style="color:{color}; margin:4px 0;">{bullet} {factor}</p>', unsafe_allow_html=True)

    # Conditions
    loan_d = result.get("loan_decision") or {}
    conditions = loan_d.get("conditions") if isinstance(loan_d, dict) else getattr(loan_d, "conditions", [])
    if conditions:
        st.markdown("#### 📌 Conditions")
        for cond in conditions:
            st.markdown(f"• {cond}")


def _render_detail_tabs(result: dict) -> None:
    tab1, tab2, tab3, tab4 = st.tabs([
        "👤 Applicant Profile", "⚠️ Risk Analysis", "⚖️ Decision Details", "🔒 Compliance"
    ])

    with tab1:
        profile = result.get("applicant_profile") or {}
        if isinstance(profile, dict):
            _render_dict_as_table(profile, "Applicant Profile Analysis")
        else:
            d = profile.model_dump()
            _render_dict_as_table(d, "Applicant Profile Analysis")

    with tab2:
        risk = result.get("financial_risk") or {}
        if isinstance(risk, dict):
            _render_dict_as_table(risk, "Financial Risk Analysis")
        else:
            _render_dict_as_table(risk.model_dump(), "Financial Risk Analysis")

    with tab3:
        decision = result.get("loan_decision") or {}
        if isinstance(decision, dict):
            _render_dict_as_table(decision, "Loan Decision Details")
        else:
            _render_dict_as_table(decision.model_dump(), "Loan Decision Details")

    with tab4:
        compliance = result.get("compliance") or {}
        if isinstance(compliance, dict):
            _render_dict_as_table(compliance, "Compliance Record")
        else:
            _render_dict_as_table(compliance.model_dump(), "Compliance Record")


def _render_dict_as_table(data: dict, title: str) -> None:
    st.markdown(f"**{title}**")
    for key, value in data.items():
        if value is None:
            continue
        display_key = key.replace("_", " ").title()
        if isinstance(value, list):
            if value:
                st.markdown(f"**{display_key}:**")
                for item in value:
                    st.markdown(f"  • {item}")
        elif isinstance(value, dict):
            st.markdown(f"**{display_key}:**")
            for k, v in value.items():
                st.markdown(f"  • {k.replace('_', ' ').title()}: `{v}`")
        elif isinstance(value, float):
            st.markdown(f"**{display_key}:** `{value:.3f}`")
        elif isinstance(value, bool):
            st.markdown(f"**{display_key}:** {'✅ Yes' if value else '❌ No'}")
        else:
            st.markdown(f"**{display_key}:** `{value}`")


# ── Sidebar ────────────────────────────────────────────────────────────────────
def _render_sidebar() -> None:
    with st.sidebar:
        st.image("https://img.icons8.com/fluency/96/bank.png", width=60)
        st.title("🏦 AI Loan System")
        st.caption("Powered by Claude Sonnet 4.6 + LangGraph")
        st.divider()

        st.markdown("### 🏗️ Architecture")
        st.markdown("""
        **Agents:**
        1. 👤 Applicant Profile (ApplicantDB MCP)
        2. 📊 Financial Risk (RiskRulesDB MCP)
        3. ⚖️ Loan Decision (DecisionSynthesis MCP)
        4. 🔒 Compliance (NotificationSystem MCP)

        **Stack:**
        - 🤖 Claude Sonnet 4.6 LLM
        - 🕸️ LangGraph Orchestration
        - 🔌 FastMCP Servers
        - ⚡ FastAPI Backend
        """)
        st.divider()

        st.markdown("### 📊 Recent Applications")
        apps = _get_all_applications()
        if apps:
            for app in apps[:5]:
                status_icon = {
                    "completed": "✅",
                    "failed": "❌",
                    "pending": "⏳",
                }.get(app.get("status", ""), "🔄")
                decision_label = (app.get("decision") or "—").upper()
                st.markdown(
                    f"{status_icon} `{app.get('application_id', '?')}` — {decision_label}"
                )
        else:
            st.caption("No applications yet")

        st.divider()
        if st.button("🗑️ Clear Chat", use_container_width=True):
            st.session_state.chat_messages = []
            st.session_state.last_result = None
            st.rerun()


# ── Main application form ──────────────────────────────────────────────────────
def _render_application_form() -> dict | None:
    with st.expander("📝 New Loan Application", expanded=not bool(st.session_state.last_result)):
        st.markdown("### Applicant Information")
        col1, col2, col3 = st.columns(3)

        with col1:
            applicant_id = st.text_input(
                "Applicant ID *",
                value="APPL-001",
                placeholder="e.g. APPL-001",
                help="Unique identifier for the applicant",
            )
            age = st.number_input("Age *", min_value=18, max_value=100, value=35, step=1)
            annual_income = st.number_input(
                "Annual Income ($) *",
                min_value=10000.0,
                max_value=10_000_000.0,
                value=75000.0,
                step=1000.0,
                format="%.0f",
            )

        with col2:
            employment_type = st.selectbox(
                "Employment Type *",
                options=["salaried", "self_employed", "business_owner", "freelancer", "retired", "unemployed"],
                index=0,
                format_func=lambda x: x.replace("_", " ").title(),
            )
            credit_score = st.slider(
                "Credit Score *",
                min_value=300,
                max_value=850,
                value=720,
                step=5,
                help="FICO credit score",
            )
            existing_liabilities = st.number_input(
                "Monthly Existing Debt ($)",
                min_value=0.0,
                max_value=100_000.0,
                value=500.0,
                step=100.0,
                format="%.0f",
                help="Current monthly debt obligations",
            )

        with col3:
            loan_amount = st.number_input(
                "Loan Amount ($) *",
                min_value=1000.0,
                max_value=5_000_000.0,
                value=150000.0,
                step=5000.0,
                format="%.0f",
            )
            tenure_months = st.selectbox(
                "Loan Tenure",
                options=[12, 24, 36, 48, 60, 84, 120, 180, 240, 300, 360],
                index=4,
                format_func=lambda x: f"{x} months ({x//12} yrs)" if x >= 12 else f"{x} months",
            )
            location = st.text_input(
                "Location *",
                value="New York, NY",
                placeholder="City, State",
            )

        st.markdown("---")
        _render_quick_summary(annual_income, loan_amount, tenure_months, credit_score, existing_liabilities)

        submitted = st.button(
            "🚀 Submit Application for AI Analysis",
            type="primary",
            use_container_width=True,
        )

        if submitted:
            if not all([applicant_id, location]):
                st.warning("Please fill in all required fields.")
                return None
            return {
                "applicant_id": applicant_id,
                "age": age,
                "annual_income": annual_income,
                "employment_type": employment_type,
                "credit_score": credit_score,
                "loan_amount": loan_amount,
                "tenure_months": tenure_months,
                "existing_liabilities": existing_liabilities,
                "location": location,
            }
    return None


def _render_quick_summary(income, loan, tenure, credit, liabilities) -> None:
    """Show quick pre-analysis metrics before submission."""
    monthly_income = income / 12
    monthly_rate = 0.085 / 12
    if monthly_rate > 0:
        monthly_payment = loan * (monthly_rate * (1 + monthly_rate) ** tenure) / ((1 + monthly_rate) ** tenure - 1)
    else:
        monthly_payment = loan / tenure

    dti = ((liabilities + monthly_payment) / monthly_income * 100) if monthly_income > 0 else 100
    lti = loan / income

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        delta_color = "normal" if dti <= 36 else "inverse"
        st.metric("Est. DTI Ratio", f"{dti:.1f}%", delta=f"{'✅ OK' if dti <= 43 else '⚠️ High'}", delta_color=delta_color)
    with col2:
        st.metric("Loan/Income", f"{lti:.1f}x", delta=f"{'✅ OK' if lti <= 4 else '⚠️ High'}")
    with col3:
        cs_label = "Excellent" if credit >= 750 else "Good" if credit >= 700 else "Fair" if credit >= 650 else "Poor"
        st.metric("Credit Grade", cs_label, f"{credit}")
    with col4:
        st.metric("Est. Monthly Payment", f"${monthly_payment:,.0f}")


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    _init_session()
    _render_sidebar()

    st.title("🏦 Agentic AI Intelligent Loan Approval System")
    st.caption(
        "Multi-agent system powered by Claude Sonnet 4.6 · LangGraph · FastMCP · FastAPI"
    )
    st.divider()

    # Application form
    form_data = _render_application_form()

    if form_data:
        # Add user message to chat
        _add_message(
            "user",
            f"📋 **Loan Application Submitted**\n\n"
            f"- **Applicant ID:** {form_data['applicant_id']}\n"
            f"- **Loan Amount:** ${form_data['loan_amount']:,.0f}\n"
            f"- **Annual Income:** ${form_data['annual_income']:,.0f}\n"
            f"- **Credit Score:** {form_data['credit_score']}\n"
            f"- **Employment:** {form_data['employment_type'].replace('_', ' ').title()}\n"
            f"- **Tenure:** {form_data['tenure_months']} months",
            "👤",
        )

        # Submit to API
        _add_message("assistant", "⏳ Submitting application to the AI analysis pipeline...", "🤖")
        st.session_state.form_submitted = True

        with st.spinner("Submitting application..."):
            submission = _submit_application(form_data)

        if submission:
            app_id = submission.get("application_id")
            st.session_state.current_application_id = app_id

            _add_message(
                "assistant",
                f"✅ Application accepted!\n\n"
                f"**Application ID:** `{app_id}`\n\n"
                f"The multi-agent system is now analyzing your application:\n"
                f"1. 👤 **Applicant Profile Agent** — analyzing income & employment...\n"
                f"2. 📊 **Financial Risk Agent** — computing DTI & risk metrics...\n"
                f"3. ⚖️ **Loan Decision Agent** — synthesizing decision...\n"
                f"4. 🔒 **Compliance Agent** — generating case record...",
                "🤖",
            )

            # Poll for result with live progress
            progress_bar = st.progress(0, text="Starting analysis pipeline...")
            status_text = st.empty()
            progress_stages = [
                (25, "👤 Analyzing applicant profile..."),
                (50, "📊 Running financial risk analysis..."),
                (75, "⚖️ Making loan decision..."),
                (90, "🔒 Processing compliance and notifications..."),
            ]

            for progress_val, stage_text in progress_stages:
                time.sleep(1.5)
                progress_bar.progress(progress_val, text=stage_text)
                status_text.markdown(f"**Status:** {stage_text}")

            # Wait for completion
            result = _poll_result(app_id, max_wait=300)
            progress_bar.progress(100, text="✅ Analysis complete!")
            status_text.empty()

            if result:
                st.session_state.last_result = result
                decision = result.get("decision", "unknown")
                decision_msg = {
                    "approved": "🎉 **APPROVED!** Your loan application has been approved.",
                    "rejected": "❌ **REJECTED.** Your application was declined.",
                    "manual_review": "🔍 **MANUAL REVIEW.** Your application needs human review.",
                }.get(decision, f"**{decision.upper()}**")

                _add_message(
                    "assistant",
                    f"{decision_msg}\n\n"
                    f"**Risk Score:** {result.get('risk_score', 0):.1f}/100\n"
                    f"**Confidence:** {(result.get('confidence_level') or 0)*100:.0f}%\n"
                    f"**Case ID:** `{result.get('case_id', 'N/A')}`\n\n"
                    f"See the full analysis below ↓",
                    "🤖",
                )
            else:
                _add_message("assistant", "⚠️ Analysis timed out. Check application status manually.", "⚠️")

    # Render chat
    st.divider()
    st.markdown("### 💬 Analysis Chat")
    _render_chat()

    # Render full result if available
    if st.session_state.last_result:
        st.divider()
        st.markdown("### 📊 Full Analysis Report")
        _render_decision_card(st.session_state.last_result)
        st.divider()
        _render_detail_tabs(st.session_state.last_result)

    # Footer
    st.divider()
    st.caption(
        "🔒 This system uses explainable AI. All decisions are auditable. "
        "Built with Anthropic Claude Sonnet 4.6, LangGraph, FastMCP, FastAPI & Streamlit."
    )


if __name__ == "__main__":
    main()
