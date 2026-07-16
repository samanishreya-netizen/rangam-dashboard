import streamlit as st
import plotly.express as px
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from db import get_monthly_performance

st.set_page_config(page_title="Business Performance", layout="wide")
st.title("Overall Business Performance")

FY = st.selectbox("Financial Year", ["FY2026-27", "FY2025-26"])
mp = get_monthly_performance(FY)
if mp.empty:
    st.info("No data yet for this Financial Year.")
    st.stop()
mp = mp.sort_values("month")
mp["hires_total"] = mp["hire_preid"] + mp["hire_sourced"]
mp["starts_total"] = mp["start_preid"] + mp["start_sourced"]

metric = st.selectbox("Metric", ["new_reqs", "worked_reqs", "submissions", "interviews",
                                   "hires_total", "starts_total", "concluded", "headcount"])
fig = px.line(mp, x="month", y=metric, markers=True, color_discrete_sequence=["#F27538"])
fig.update_layout(height=400)
st.plotly_chart(fig, use_container_width=True)

st.subheader("All metrics by month")
st.dataframe(mp[["month", "new_reqs", "worked_reqs", "submissions", "interviews",
                  "hires_total", "starts_total", "concluded", "headcount"]], use_container_width=True)
