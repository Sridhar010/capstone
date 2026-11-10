"""
Streamlit UI — Loan Approval Portal
Customer-facing interface for loan application submission and decision display.
"""
from __future__ import annotations

import sys
import time
import uuid as _uuid
from pathlib import Path

import httpx
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import STREAMLIT_API_URL

st.set_page_config(
    page_title="Loan Approval Portal",
    page_icon="🏦",
    layout="centered",
    initial_sidebar_state="collapsed",
)

API_BASE = STREAMLIT_API_URL.rstrip("/")


def _gen_applicant_id(display_name: str = "") -> str:
    """Generate a unique applicant reference — never shown on the form."""
    suffix = _uuid.uuid4().hex[:8].upper()
    if display_name.strip():
        prefix = "".join(c for c in display_name.strip().upper() if c.isalnum())[:10]
        return f"{prefix}-{suffix}"
    return f"CUST-{suffix}"

st.markdown("""
<style>
.result-approved {
    background: rgba(40, 167, 69, 0.15);
    border: 2px solid #28a745;
    border-radius: 16px; padding: 28px; margin: 16px 0; text-align: center;
}
.result-rejected {
    background: rgba(220, 53, 69, 0.15);
    border: 2px solid #dc3545;
    border-radius: 16px; padding: 28px; margin: 16px 0; text-align: center;
}
.result-manual_review {
    background: rgba(255, 193, 7, 0.15);
    border: 2px solid #ffc107;
    border-radius: 16px; padding: 28px; margin: 16px 0; text-align: center;
}
.result-processing {
    background: rgba(23, 162, 184, 0.15);
    border: 2px solid #17a2b8;
    border-radius: 16px; padding: 28px; margin: 16px 0; text-align: center;
}
.info-card {
    border: 1px solid rgba(128,128,128,0.2);
    border-radius: 12px; padding: 20px; margin: 12px 0;
}
</style>
""", unsafe_allow_html=True)


def _init_session() -> None:
    defaults = {
        "submitted": False,
        "app_id": None,
        "result": None,
        "applicant_name": "",     # display-only, not the primary key
        "page": "apply",          # "apply" | "records"
        "selected_record": None,  # application_id of record being viewed
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def _submit(payload: dict) -> dict | None:
    try:
        r = httpx.post(f"{API_BASE}/api/v1/loans", json=payload, timeout=30.0)
        r.raise_for_status()
        return r.json()
    except httpx.ConnectError:
        st.error("Unable to connect to the server. Please try again in a moment.")
        return None
    except Exception as exc:
        st.error(f"Submission failed: {exc}")
        return None


def _get_all_applications(limit: int = 200) -> list[dict]:
    try:
        resp = httpx.get(f"{API_BASE}/api/v1/loans", params={"limit": limit}, timeout=10.0)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return []


def _poll(app_id: str, max_wait: int = 300) -> dict | None:
    start = time.time()
    while time.time() - start < max_wait:
        try:
            r = httpx.get(f"{API_BASE}/api/v1/loans/{app_id}", timeout=10.0)
            r.raise_for_status()
            data = r.json()
            if data.get("status") in ("completed", "failed"):
                return data
            time.sleep(3)
        except Exception:
            time.sleep(3)
    return None


def _render_result(result: dict) -> None:
    decision = result.get("decision") or "manual_review"
    risk_score = result.get("risk_score")
    confidence = result.get("confidence_level")
    explanation = result.get("explanation") or ""
    case_id = result.get("case_id") or "—"
    status = result.get("status", "")

    if status == "failed" and not result.get("decision"):
        st.markdown("""
        <div class="result-processing">
            <h2 style="color:#0c5460; margin:0;">⏳ Still Processing</h2>
            <p style="color:#0c5460; margin-top:8px;">
                Your application is being reviewed. Please check back shortly.
            </p>
        </div>
        """, unsafe_allow_html=True)
        return

    icons = {"approved": "✅", "rejected": "❌", "manual_review": "📋"}
    titles = {
        "approved": "Congratulations — Loan Approved!",
        "rejected": "Application Declined",
        "manual_review": "Application Under Review",
    }
    subtitles = {
        "approved": "Your application meets our lending criteria.",
        "rejected": "Your application did not meet our current requirements.",
        "manual_review": "A loan specialist will contact you within 1–2 business days.",
    }
    css = f"result-{decision}"
    app_ref = result.get("application_id") or case_id

    # ── Decision banner ────────────────────────────────────────────────────────
    st.markdown(f"""
    <div class="{css}">
        <div style="font-size:52px;">{icons.get(decision, "📋")}</div>
        <h2 style="margin:8px 0;">{titles.get(decision, decision.upper())}</h2>
        <p style="margin:4px 0; opacity:0.85;">{subtitles.get(decision, "")}</p>
        <p style="margin-top:14px; font-size:12px; opacity:0.65;">
            Reference: <strong>{app_ref}</strong>
            {f"&nbsp;|&nbsp; Case: <strong>{case_id}</strong>" if case_id and case_id != "—" and case_id != app_ref else ""}
        </p>
    </div>
    """, unsafe_allow_html=True)

    # ── Risk + confidence metrics ──────────────────────────────────────────────
    if risk_score is not None and confidence is not None:
        col1, col2 = st.columns(2)
        with col1:
            risk_label = "Low" if risk_score < 35 else "Moderate" if risk_score < 65 else "High"
            risk_color = "#28a745" if risk_score < 35 else "#ffc107" if risk_score < 65 else "#dc3545"
            st.markdown(f"""
            <div class="info-card" style="text-align:center;">
                <div style="font-size:36px; font-weight:bold; color:{risk_color};">{risk_score:.0f}<span style="font-size:16px;">/100</span></div>
                <div style="color:#6c757d; font-size:13px;">Risk Score — {risk_label}</div>
            </div>""", unsafe_allow_html=True)
        with col2:
            conf_pct = confidence * 100
            conf_color = "#28a745" if conf_pct > 80 else "#ffc107" if conf_pct > 60 else "#dc3545"
            st.markdown(f"""
            <div class="info-card" style="text-align:center;">
                <div style="font-size:36px; font-weight:bold; color:{conf_color};">{conf_pct:.0f}<span style="font-size:16px;">%</span></div>
                <div style="color:#6c757d; font-size:13px;">Decision Confidence</div>
            </div>""", unsafe_allow_html=True)

    # ── Key factors as visual chips ────────────────────────────────────────────
    factors = result.get("key_factors") or []
    if factors:
        st.markdown("**What influenced this decision:**")
        chips_html = '<div style="display:flex; flex-wrap:wrap; gap:8px; margin:10px 0 16px 0;">'
        for f in factors[:6]:
            pos = any(w in f.lower() for w in ["excellent", "good", "stable", "low", "strong", "acceptable"])
            neg = any(w in f.lower() for w in ["poor", "high risk", "anomal", "elevated", "critical", "excessive"])
            if pos and not neg:
                bg, border, color, badge = "rgba(40,167,69,0.12)", "#28a745", "#155724", "✅"
            elif neg:
                bg, border, color, badge = "rgba(220,53,69,0.12)", "#dc3545", "#721c24", "⚠️"
            else:
                bg, border, color, badge = "rgba(108,117,125,0.08)", "#adb5bd", "#495057", "•"
            chips_html += (
                f'<span style="background:{bg}; border:1px solid {border}; color:{color}; '
                f'border-radius:20px; padding:5px 13px; font-size:13px; display:inline-flex; '
                f'align-items:center; gap:5px;">{badge} {f}</span>'
            )
        chips_html += "</div>"
        st.markdown(chips_html, unsafe_allow_html=True)

    # ── Explanation — collapsed by default, one-line preview in header ─────────
    if explanation:
        first_sentence = explanation.split(".")[0].strip()
        preview = first_sentence[:90] + ("…" if len(first_sentence) > 90 else "")
        with st.expander(f"📄 Analysis summary: {preview}"):
            st.write(explanation)

    # ── Conditions (approval only) ─────────────────────────────────────────────
    conditions = (result.get("loan_decision") or {}).get("conditions") if isinstance(result.get("loan_decision"), dict) else []
    if conditions:
        with st.expander("📋 Conditions attached to your approval"):
            for c in conditions:
                st.markdown(f"• {c}")

    # ── Next steps ─────────────────────────────────────────────────────────────
    st.markdown("**What happens next:**")
    if decision == "approved":
        rec = result.get("loan_decision") or {}
        rec_amount = rec.get("recommended_loan_amount") if isinstance(rec, dict) else None
        col1, col2 = st.columns(2)
        with col1:
            amt_str = f"up to **${rec_amount:,.0f}**" if rec_amount else "your requested amount"
            st.success(f"💰 You are approved for {amt_str}.")
        with col2:
            st.info("📞 A loan officer will contact you within 24 hours to finalise your terms.")
    elif decision == "rejected":
        col1, col2 = st.columns(2)
        with col1:
            st.error("🚫 Your application was not approved at this time.")
        with col2:
            st.info("🔄 You may re-apply in 6 months or after improving your financial profile.")
    elif decision == "manual_review":
        col1, col2 = st.columns(2)
        with col1:
            st.warning("🕐 A specialist will reach out within 1–2 business days.")
        with col2:
            st.info("📁 Have these ready: proof of income, bank statements, photo ID.")


def _render_form() -> dict | None:
    # ── Personal details ───────────────────────────────────────────────────────
    st.markdown("""<div class="info-card">""", unsafe_allow_html=True)
    st.markdown("### 👤 About You")

    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        display_name = st.text_input(
            "Your Full Name *",
            value="",
            placeholder="e.g. Jane Smith",
            help="Required. Used to personalise your result and generate a unique application reference.",
        )
    with col2:
        age = st.number_input("Age", min_value=18, max_value=100, value=35, step=1)
    with col3:
        location = st.text_input("City / State", value="New York, NY", placeholder="e.g. Austin, TX")

    st.markdown("</div>", unsafe_allow_html=True)

    # ── Financial profile ──────────────────────────────────────────────────────
    st.markdown("""<div class="info-card">""", unsafe_allow_html=True)
    st.markdown("### 💰 Your Finances")

    col1, col2 = st.columns(2)
    with col1:
        annual_income = st.number_input(
            "Annual Income ($)",
            min_value=10_000.0, max_value=10_000_000.0,
            value=95_000.0, step=1_000.0, format="%.0f",
            help="Your total gross income per year before taxes.",
        )
        employment_type = st.selectbox(
            "Employment Status",
            options=["salaried", "self_employed", "business_owner", "freelancer", "retired", "unemployed"],
            format_func=lambda x: {
                "salaried": "Salaried Employee",
                "self_employed": "Self-Employed",
                "business_owner": "Business Owner",
                "freelancer": "Freelancer / Contractor",
                "retired": "Retired",
                "unemployed": "Not Currently Employed",
            }.get(x, x),
        )
    with col2:
        existing_liabilities = st.number_input(
            "Monthly Debt Payments ($)",
            min_value=0.0, max_value=100_000.0,
            value=200.0, step=100.0, format="%.0f",
            help="Total of all existing monthly obligations: car, rent, other loans, credit cards, etc.",
        )
        credit_score = st.slider(
            "Credit Score",
            min_value=300, max_value=850, value=720, step=5,
            help="Your most recent credit score (300–850). Higher is better.",
        )

    st.markdown("</div>", unsafe_allow_html=True)

    # ── Loan details ───────────────────────────────────────────────────────────
    st.markdown("""<div class="info-card">""", unsafe_allow_html=True)
    st.markdown("### 🏠 Loan Request")

    col1, col2 = st.columns(2)
    with col1:
        loan_amount = st.number_input(
            "Loan Amount ($)",
            min_value=1_000.0, max_value=5_000_000.0,
            value=150_000.0, step=5_000.0, format="%.0f",
        )
    with col2:
        tenure_months = st.selectbox(
            "Repayment Period",
            options=[12, 24, 36, 48, 60, 84, 120, 180, 240, 300, 360],
            index=4,
            format_func=lambda x: f"{x // 12} year{'s' if x // 12 != 1 else ''}" + (f" {x % 12} mo" if x % 12 else ""),
        )

    st.markdown("</div>", unsafe_allow_html=True)

    # ── Live snapshot ──────────────────────────────────────────────────────────
    if annual_income > 0:
        monthly_income = annual_income / 12
        r = 0.085 / 12
        n = tenure_months
        monthly_pmt = loan_amount * (r * (1 + r) ** n) / ((1 + r) ** n - 1) if r else loan_amount / n
        dti = (existing_liabilities + monthly_pmt) / monthly_income * 100
        lti = loan_amount / annual_income
        credit_label = (
            "Excellent" if credit_score >= 750 else
            "Good" if credit_score >= 700 else
            "Fair" if credit_score >= 650 else "Poor"
        )

        st.markdown("""<div class="info-card">""", unsafe_allow_html=True)
        st.markdown("**Application snapshot** *(updates as you type)*")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Est. Monthly Payment", f"${monthly_pmt:,.0f}")
        c2.metric(
            "Debt-to-Income Ratio", f"{dti:.1f}%",
            delta="Within limit" if dti <= 43 else "Above limit",
            delta_color="normal" if dti <= 43 else "inverse",
            help="Should ideally be under 43%.",
        )
        c3.metric(
            "Loan / Annual Income", f"{lti:.1f}×",
            delta="Reasonable" if lti <= 4 else "High",
            delta_color="normal" if lti <= 4 else "inverse",
        )
        c4.metric("Credit Rating", credit_label)
        st.markdown("</div>", unsafe_allow_html=True)

    submitted = st.button("🚀 Submit My Application", type="primary", use_container_width=True)
    if submitted:
        errors = []
        if not display_name.strip():
            errors.append("Please enter your full name.")
        if not location.strip():
            errors.append("Please enter your city / state.")
        if errors:
            for msg in errors:
                st.warning(msg)
            return None
        applicant_id = _gen_applicant_id(display_name)
        st.session_state.applicant_name = display_name.strip()
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


def _render_records_page() -> None:
    """Show all historical loan applications with summary stats and detail view."""
    st.markdown("### 📂 Application Records")
    st.caption("All submitted loan applications — persisted across sessions.")

    apps = _get_all_applications(limit=500)

    if not apps:
        st.info("No applications on record yet. Submit a loan application to get started.")
        return

    # ── Summary stats ──────────────────────────────────────────────────────────
    total = len(apps)
    approved = sum(1 for a in apps if a.get("decision") == "approved")
    rejected = sum(1 for a in apps if a.get("decision") == "rejected")
    review   = sum(1 for a in apps if a.get("decision") == "manual_review")
    pending  = sum(1 for a in apps if not a.get("decision"))

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Total", total)
    c2.metric("✅ Approved", approved)
    c3.metric("❌ Rejected", rejected)
    c4.metric("📋 Under Review", review)
    c5.metric("⏳ Pending", pending)

    st.divider()

    # ── Filters ────────────────────────────────────────────────────────────────
    col_f1, col_f2 = st.columns([2, 1])
    with col_f1:
        search = st.text_input("Search by Applicant ID or Case ID", placeholder="e.g. APPL-001 or LN-...")
    with col_f2:
        filter_decision = st.selectbox(
            "Filter by Decision",
            options=["All", "Approved", "Rejected", "Under Review", "Pending"],
        )

    # Apply filters
    filtered = apps
    if search:
        s = search.lower()
        filtered = [a for a in filtered if s in (a.get("applicant_id") or "").lower()
                    or s in (a.get("case_id") or "").lower()
                    or s in (a.get("application_id") or "").lower()]
    decision_map = {
        "Approved": "approved", "Rejected": "rejected",
        "Under Review": "manual_review", "Pending": None,
    }
    if filter_decision != "All":
        target = decision_map.get(filter_decision)
        if target is None:
            filtered = [a for a in filtered if not a.get("decision")]
        else:
            filtered = [a for a in filtered if a.get("decision") == target]

    st.caption(f"Showing {len(filtered)} of {total} records")

    # ── Table ──────────────────────────────────────────────────────────────────
    decision_icons = {"approved": "✅", "rejected": "❌", "manual_review": "📋"}

    for app in filtered:
        app_id     = app.get("application_id", "—")
        appl_id    = app.get("applicant_id", "—")
        decision   = app.get("decision") or "pending"
        risk       = app.get("risk_score")
        conf       = app.get("confidence_level")
        case_id    = app.get("case_id") or "—"
        created    = (app.get("created_at") or "")[:16].replace("T", " ")
        loan_amt   = app.get("loan_amount") if isinstance(app.get("loan_amount"), (int, float)) else None
        credit     = app.get("credit_score")
        status     = app.get("status", "—")

        icon = decision_icons.get(decision, "⏳")
        loan_str = f"${loan_amt:,.0f}" if loan_amt else "—"
        credit_str = str(credit) if credit else "—"
        label = f"{icon}  {appl_id}  ·  {loan_str}  ·  Credit {credit_str}  ·  {decision.replace('_', ' ').title()}  ·  {created}"

        with st.expander(label):
            col1, col2, col3, col4 = st.columns(4)
            col1.markdown(f"**App ID**\n`{app_id}`")
            col2.markdown(f"**Case ID**\n`{case_id}`")
            col3.markdown(f"**Status**\n{status.replace('_', ' ').title()}")
            col4.markdown(f"**Submitted**\n{created}")

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Loan Amount", f"${loan_amt:,.0f}" if loan_amt else "—")
            c2.metric("Credit Score", credit or "—")
            c3.metric("Risk Score", f"{risk:.1f}/100" if risk is not None else "—")
            c4.metric("Confidence", f"{conf*100:.0f}%" if conf is not None else "—")

            if app.get("explanation"):
                st.markdown("**Decision Explanation:**")
                st.write(app["explanation"])

            factors = app.get("key_factors") or []
            if factors:
                st.markdown("**Key Factors:**")
                for f in factors[:6]:
                    st.markdown(f"• {f}")

            # Button to view full result in Apply page style
            if st.button("View Full Details", key=f"view_{app_id}"):
                st.session_state.selected_record = app
                st.session_state.page = "record_detail"
                st.rerun()

    # ── Full detail view ───────────────────────────────────────────────────────
    if st.session_state.page == "record_detail" and st.session_state.selected_record:
        st.divider()
        st.markdown("### Full Application Detail")
        if st.button("← Back to Records"):
            st.session_state.page = "records"
            st.session_state.selected_record = None
            st.rerun()
        _render_result(st.session_state.selected_record)


def main() -> None:
    _init_session()

    st.title("🏦 Loan Approval Portal")
    st.caption("Get an instant decision on your loan application — securely and confidentially.")

    # ── Page toggle ────────────────────────────────────────────────────────────
    col_nav1, col_nav2, col_nav3 = st.columns([2, 1, 1])
    with col_nav2:
        if st.button("📝 Apply", use_container_width=True,
                     type="primary" if st.session_state.page == "apply" else "secondary"):
            st.session_state.page = "apply"
            st.session_state.result = None
            st.session_state.submitted = False
            st.session_state.app_id = None
            st.session_state.applicant_name = ""
            st.rerun()
    with col_nav3:
        if st.button("📂 Records", use_container_width=True,
                     type="primary" if st.session_state.page in ("records", "record_detail") else "secondary"):
            st.session_state.page = "records"
            st.rerun()

    st.divider()

    # ── Route to correct page ──────────────────────────────────────────────────
    if st.session_state.page in ("records", "record_detail"):
        _render_records_page()
        return

    # ── Apply page ─────────────────────────────────────────────────────────────

    # If we already have a result, show it with an option to start over
    if st.session_state.result:
        name = st.session_state.get("applicant_name", "")
        if name and name != "Applicant":
            st.markdown(f"**Result for {name}**")
        _render_result(st.session_state.result)
        st.divider()
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔄 Apply for Another Loan", use_container_width=True):
                st.session_state.result = None
                st.session_state.app_id = None
                st.session_state.submitted = False
                st.session_state.applicant_name = ""
                st.rerun()
        with col2:
            if st.button("📂 View All Records", use_container_width=True):
                st.session_state.page = "records"
                st.rerun()
        return

    # If submitted and waiting for result
    if st.session_state.submitted and st.session_state.app_id:
        app_id = st.session_state.app_id
        name = st.session_state.get("applicant_name", "")
        greeting = f"Hi {name}, we're reviewing your application…" if name and name != "Applicant" else "Reviewing your application…"
        st.markdown(f"""
        <div class="result-processing">
            <h3 style="color:#0c5460; margin:0;">🔍 {greeting}</h3>
            <p style="color:#0c5460; margin-top:8px;">
                This usually takes 30–60 seconds. Please don't close this page.
            </p>
            <p style="color:#0c5460; font-size:12px; margin-top:6px; opacity:0.7;">
                Reference: <strong>{app_id}</strong>
            </p>
        </div>
        """, unsafe_allow_html=True)

        steps = [
            "Verifying your personal details…",
            "Assessing your financial profile…",
            "Generating your loan decision…",
            "Finalising and recording your case…",
        ]
        progress = st.progress(0)
        status_ph = st.empty()
        for i, step in enumerate(steps):
            progress.progress((i + 1) * 20, text=step)
            status_ph.info(step)
            time.sleep(1.5)

        result = _poll(app_id, max_wait=300)
        progress.progress(100, text="Complete!")
        status_ph.empty()

        if result:
            st.session_state.result = result
            st.rerun()
        else:
            st.warning("The review is taking longer than expected. Please check back in a few minutes.")
            if st.button("Check Status Again"):
                st.rerun()
        return

    # Show form
    form_data = _render_form()
    if form_data:
        with st.spinner("Submitting your application…"):
            resp = _submit(form_data)
        if resp:
            st.session_state.app_id = resp.get("application_id")
            st.session_state.submitted = True
            st.rerun()

    st.divider()
    st.caption(
        "🔒 Your information is encrypted and used only for loan assessment. "
        "All decisions are fair, explainable, and comply with equal credit opportunity laws."
    )


if __name__ == "__main__":
    main()
