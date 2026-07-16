import streamlit as st
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from db import get_onboarding_performance

st.set_page_config(page_title="Onboarding Performance", layout="wide")
st.title("Onboarding Performance")

FY = st.selectbox("Financial Year", ["FY2026-27", "FY2025-26"])
onb = get_onboarding_performance(FY)
if onb.empty:
    st.info("No data yet for this Financial Year.")
    st.stop()

c1, c2, c3 = st.columns(3)
c1.metric("Total Hires", int(onb["hires"].sum()))
c2.metric("Total Starts", int(onb["starts"].sum()))
avg_hours = onb["avg_doc_completion_hours"].mean()
c3.metric("Avg. Doc Completion (Hours)", f"{avg_hours:.0f}" if avg_hours == avg_hours else "—",
          help="Goal: <= 48 Hours")

st.divider()
st.subheader("By specialist")
st.dataframe(onb[["specialist_name", "hires", "starts", "avg_doc_completion_hours",
                   "avg_survey_completion_ratio", "avg_survey_satisfaction_ratio"]], use_container_width=True)

st.caption("Goals: Doc completion <= 48 hours · Survey completion >= 80% · Survey satisfaction >= 80%")
