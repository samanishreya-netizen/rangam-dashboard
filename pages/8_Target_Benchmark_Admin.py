import streamlit as st
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from db import get_client, require_admin_gate, get_business_target, clear_caches

st.set_page_config(page_title="Target & Benchmark Admin", layout="wide")
require_admin_gate()

st.title("Target & Benchmark Management")
sb = get_client()

FY = st.selectbox("Financial Year", ["FY2026-27", "FY2025-26"])
current = get_business_target(FY)

st.subheader("Business Target")
with st.form("business_target_form"):
    rev_inr = st.number_input("Annual Revenue Target (INR)", value=float(current["annual_revenue_target_inr"]) if current else 0.0, step=1000000.0)
    rev_usd = st.number_input("Annual Revenue Target (USD)", value=float(current["annual_revenue_target_usd"]) if current else 0.0, step=10000.0)
    exch = st.number_input("Exchange Rate Assumption", value=float(current["exchange_rate_assumption"]) if current else 90.0)
    hiring_target = st.number_input("Annual Hiring Target", value=int(current["annual_hiring_target"]) if current and current.get("annual_hiring_target") else 0, step=1)
    headcount_target = st.number_input("Headcount Target", value=int(current["headcount_target"]) if current and current.get("headcount_target") else 0, step=1)
    submitted = st.form_submit_button("Save target (keeps version history)")

    if submitted:
        old_values = current
        if current:
            sb.table("config_business_target").update({"is_active": False}).eq("target_id", current["target_id"]).execute()
        new_row = sb.table("config_business_target").insert({
            "fy_code": FY, "annual_revenue_target_inr": rev_inr, "annual_revenue_target_usd": rev_usd,
            "exchange_rate_assumption": exch, "annual_hiring_target": hiring_target,
            "headcount_target": headcount_target, "is_active": True,
        }).execute()
        sb.table("target_change_log").insert({
            "target_table": "config_business_target", "target_row_id": new_row.data[0]["target_id"],
            "fy_code": FY, "old_values": old_values, "new_values": new_row.data[0],
        }).execute()
        clear_caches()
        st.success(f"Target saved for {FY}. Monthly figures are derived automatically (annual ÷ 12) — no need to enter them separately.")
        st.rerun()

if current:
    st.caption(f"Implied monthly target: ₹{current['annual_revenue_target_inr']/12/1e7:.2f} Cr / ${current['annual_revenue_target_usd']/12:,.0f}")

st.divider()
st.subheader("Target change history")
history = sb.table("target_change_log").select("*").eq("fy_code", FY).order("changed_at", desc=True).execute().data
if history:
    for h in history:
        st.write(f"**{h['changed_at']}** — {h['target_table']}")
        col1, col2 = st.columns(2)
        col1.write("Before:"); col1.json(h["old_values"] or {})
        col2.write("After:"); col2.json(h["new_values"] or {})
else:
    st.write("No changes logged yet for this FY.")

st.divider()
st.subheader("KPI Benchmarks")
st.caption("Standard ratios: Response Rate >=80%, Submission per Req 3-5, Submission-to-Interview >=33%, "
           "Interview-to-Hire >=20%, Close Rate >=25%, Back Out <=20%.")
with st.form("benchmark_form"):
    kpi_name = st.text_input("KPI name")
    applies_to = st.selectbox("Applies to", ["company", "client", "recruiter"])
    target_val = st.number_input("Target value", format="%.4f")
    comparison = st.selectbox("Comparison type", [">=", "<=", "between"])
    unit = st.text_input("Unit", value="%")
    if st.form_submit_button("Add benchmark"):
        sb.table("config_kpi_benchmark").insert({
            "fy_code": FY, "kpi_name": kpi_name, "applies_to_level": applies_to,
            "target_value": target_val, "comparison_type": comparison, "unit": unit,
        }).execute()
        st.success("Benchmark added.")
        st.rerun()

benchmarks = sb.table("config_kpi_benchmark").select("*").eq("fy_code", FY).eq("is_active", True).execute().data
if benchmarks:
    import pandas as pd
    st.dataframe(pd.DataFrame(benchmarks), use_container_width=True)
