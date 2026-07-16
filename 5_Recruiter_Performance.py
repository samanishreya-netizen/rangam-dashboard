import streamlit as st
import pandas as pd
import plotly.express as px
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from db import get_recruiter_performance

st.set_page_config(page_title="Recruiter Performance", layout="wide")
st.title("Recruiter Performance")
st.caption("Ratios use the plain formulas as provided (no Pre-ID adjustment needed — Pre-ID and Left Recruiters "
           "are shown separately below so recruiter totals reconcile with company totals).")

FY = st.selectbox("Financial Year", ["FY2026-27", "FY2025-26"])
rp = get_recruiter_performance(FY)
if rp.empty:
    st.info("No data yet for this Financial Year.")
    st.stop()

active = rp[~rp["is_pooled_bucket"]].copy()
pooled = rp[rp["is_pooled_bucket"]]

active["submissions_per_req"] = (active["submissions"] / active["new_reqs"]).round(2)
active["sub_to_int"] = (active["interviews"] / active["submissions"]).round(3)
active["int_to_hire"] = (active["hires"] / active["interviews"]).round(3)
active["close_rate"] = (active["starts"] / active["new_reqs"]).round(3)
active["bad_delivery"] = (active["not_hires"] / active["hires"].replace(0, pd.NA)).round(3)

st.subheader("Productivity vs. Quality")
prod_median = active["submissions"].median()
qual_median = active["sub_to_int"].median()
fig = px.scatter(active, x="submissions", y="sub_to_int", text="recruiter_name",
                  size="hires", color="recruiter_name",
                  labels={"submissions": "Productivity (Submissions)", "sub_to_int": "Quality (Submission-to-Interview)"},
                  color_discrete_sequence=["#F27538", "#28425B", "#848688", "#B85C2E"])
fig.add_vline(x=prod_median, line_dash="dash", line_color="grey")
fig.add_hline(y=qual_median, line_dash="dash", line_color="grey")
fig.update_traces(textposition="top center")
fig.update_layout(height=450)
st.plotly_chart(fig, use_container_width=True)

st.subheader("Recruiter detail")
st.dataframe(active[["recruiter_name", "new_reqs", "worked_reqs", "submissions", "interviews", "hires",
                      "starts", "not_hires", "submissions_per_req", "sub_to_int", "int_to_hire",
                      "close_rate", "bad_delivery"]], use_container_width=True)

st.subheader("Pre-ID / Left Recruiters (reconciliation buckets, not scored)")
st.dataframe(pooled[["recruiter_name", "new_reqs", "worked_reqs", "submissions", "interviews", "hires", "starts", "not_hires"]],
             use_container_width=True)

st.caption(f"Reconciliation: recruiter-table total hires = {int(rp['hires'].sum())} "
           f"(should match Overall Performance total hires for the same period).")
