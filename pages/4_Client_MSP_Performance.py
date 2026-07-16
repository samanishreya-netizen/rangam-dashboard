import streamlit as st
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from db import get_client_monthly_performance

st.set_page_config(page_title="Client & MSP Performance", layout="wide")
st.title("Client & MSP Performance")

FY = st.selectbox("Financial Year", ["FY2026-27", "FY2025-26"])
cmp_df = get_client_monthly_performance(FY)
if cmp_df.empty:
    st.info("No data yet for this Financial Year.")
    st.stop()

msp_filter = st.selectbox("MSP", ["All"] + sorted(cmp_df["msp_name"].dropna().unique().tolist()))
filtered = cmp_df if msp_filter == "All" else cmp_df[cmp_df["msp_name"] == msp_filter]

client_filter = st.selectbox("Client", ["All"] + sorted(filtered["client_name"].dropna().unique().tolist()))
if client_filter != "All":
    filtered = filtered[filtered["client_name"] == client_filter]

st.subheader(f"Detail — {len(filtered)} rows")
st.dataframe(filtered[["month", "msp_name", "client_name", "hours_worked", "avg_recruiters", "new_reqs",
                        "worked_reqs", "submissions", "interviews", "hire_preid", "hire_sourced", "hire_combined",
                        "concluded", "headcount", "revenue_inr", "revenue_usd", "is_month_closed"]],
             use_container_width=True)

st.divider()
st.subheader("Client summary (this FY)")
summary = filtered.groupby("client_name").agg(
    new_reqs=("new_reqs", "sum"), submissions=("submissions", "sum"),
    interviews=("interviews", "sum"), revenue_usd=("revenue_usd", "sum"),
).reset_index()
summary["submission_per_req"] = (summary["submissions"] / summary["new_reqs"]).round(2)
st.dataframe(summary, use_container_width=True)

st.caption("Flags: clients below are worth a closer look based on this FY's totals.")
low_coverage = summary[summary["submission_per_req"] < 2]
if not low_coverage.empty:
    st.write("**Low requirement coverage (< 2 submissions per requirement):**", ", ".join(low_coverage["client_name"]))
