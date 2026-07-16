import streamlit as st
import plotly.graph_objects as go
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from db import get_monthly_performance, get_client_monthly_performance

st.set_page_config(page_title="Recruitment Funnel", layout="wide")
st.title("Recruitment Funnel")

FY = st.selectbox("Financial Year", ["FY2026-27", "FY2025-26"])
mp = get_monthly_performance(FY)
cmp_df = get_client_monthly_performance(FY)
if mp.empty:
    st.info("No data yet for this Financial Year.")
    st.stop()

client_filter = st.selectbox("Client", ["All (company-wide)"] + sorted(cmp_df["client_name"].dropna().unique().tolist()))

if client_filter == "All (company-wide)":
    new_reqs = mp["new_reqs"].sum()
    submissions = mp["submissions"].sum()
    interviews = mp["interviews"].sum()
    hires = mp["hire_preid"].sum() + mp["hire_sourced"].sum()
    starts = mp["start_preid"].sum() + mp["start_sourced"].sum()
else:
    sub = cmp_df[cmp_df["client_name"] == client_filter]
    new_reqs = sub["new_reqs"].sum()
    submissions = sub["submissions"].sum()
    interviews = sub["interviews"].sum()
    hires = sub[["hire_preid", "hire_sourced", "hire_combined"]].fillna(0).sum().sum()
    starts = sub[["start_preid", "start_sourced", "start_combined"]].fillna(0).sum().sum()

stages = ["Requirements", "Submissions", "Interviews", "Hires", "Starts"]
values = [new_reqs, submissions, interviews, hires, starts]

fig = go.Figure(go.Funnel(
    y=stages, x=values,
    textinfo="value+percent initial",
    marker={"color": ["#28425B", "#3a5a7a", "#F27538", "#e0472a", "#848688"]},
))
fig.update_layout(height=450)
st.plotly_chart(fig, use_container_width=True)

st.subheader("Stage-to-stage conversion")
for i in range(len(stages) - 1):
    rate = (values[i+1] / values[i] * 100) if values[i] else 0
    st.write(f"**{stages[i]} → {stages[i+1]}**: {rate:.1f}%")
