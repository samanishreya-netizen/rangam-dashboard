import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from db import get_monthly_performance, get_business_target, get_benchmarks, evaluate_benchmark

st.set_page_config(page_title="Executive Overview", layout="wide")
st.title("Executive Overview")

FY = st.selectbox("Financial Year", ["FY2026-27", "FY2025-26"])
mp = get_monthly_performance(FY)

if mp.empty:
    st.info("No data yet for this Financial Year. Upload a file in Data Management.")
    st.stop()

mp = mp.sort_values("month")
latest = mp.iloc[-1]
prev = mp.iloc[-2] if len(mp) > 1 else None
target = get_business_target(FY)

def delta(cur, prv):
    if prv in (None, 0) or prv is None:
        return None
    return f"{((cur - prv) / prv * 100):+.1f}%"

c1, c2, c3, c4 = st.columns(4)
closed_months = mp[mp["is_month_closed"]]
ytd_revenue_inr = closed_months["revenue_inr"].sum()
ytd_revenue_usd = closed_months["revenue_usd"].sum()
target_inr = target["annual_revenue_target_inr"] if target else None
quarterly_target_inr = target_inr / 4 if target_inr else None
achievement = (ytd_revenue_inr / target_inr * 100) if target_inr else None

with c1:
    st.metric("YTD Revenue (INR)", f"₹{ytd_revenue_inr/1e7:.2f} Cr",
               f"{achievement:.1f}% of target" if achievement else None)
with c2:
    st.metric("YTD Revenue (USD)", f"${ytd_revenue_usd:,.2f}")
with c3:
    st.metric("Quarterly Revenue Target (INR)", f"₹{quarterly_target_inr/1e7:.2f} Cr" if quarterly_target_inr else "—")
with c4:
    st.metric("Interviews", int(mp["interviews"].sum()))

c1b, c2b = st.columns(2)
with c1b:
    st.metric("New Requirements", int(mp["new_reqs"].sum()))
with c2b:
    st.metric("Submissions", int(mp["submissions"].sum()))

st.caption("Hires, Starts, Not Hires — Pre-ID (client-sourced) vs. Sourced (Rangam-sourced) shown separately")
c5, c6, c7, c8 = st.columns(4)
with c5:
    st.metric("Hires — Pre-ID", int(mp["hire_preid"].sum()))
with c6:
    st.metric("Hires — Sourced", int(mp["hire_sourced"].sum()))
with c7:
    st.metric("Starts — Pre-ID", int(mp["start_preid"].sum()))
with c8:
    st.metric("Starts — Sourced", int(mp["start_sourced"].sum()))

c8a, c8b = st.columns(2)
with c8a:
    st.metric("Not Hires — Pre-ID", int(mp["nothire_preid"].sum()))
with c8b:
    st.metric("Not Hires — Sourced", int(mp["nothire_sourced"].sum()))

c9, c10, c11 = st.columns(3)
with c9:
    st.metric("Headcount (latest)", int(latest["headcount"]))
with c10:
    open_months = mp[~mp["is_month_closed"]]["month"].tolist()
    st.metric("Months not yet closed", len(open_months), help=", ".join(str(m) for m in open_months) if open_months else None)
with c11:
    total_hires = int(mp["hire_preid"].sum() + mp["hire_sourced"].sum())
    total_starts = int(mp["start_preid"].sum() + mp["start_sourced"].sum())
    st.metric("Total Hires / Starts (combined)", f"{total_hires} / {total_starts}")

st.divider()
st.subheader("Performance vs. Target")
st.caption("Targets are set on the Target & Benchmark Admin page ('client' level). Actuals are the sourced-only "
           "figures for this Financial Year.")

new_reqs_sum = mp["new_reqs"].sum()
submissions_sum = mp["submissions"].sum()
interviews_sum = mp["interviews"].sum()
hire_sourced_sum = mp["hire_sourced"].sum()
start_sourced_sum = mp["start_sourced"].sum()
nothire_sourced_sum = mp["nothire_sourced"].sum()

pvt_actuals = {
    "submission per req": (submissions_sum / new_reqs_sum) if new_reqs_sum else None,
    "submission to interview": (interviews_sum / submissions_sum * 100) if submissions_sum else None,
    "interview to hire": (hire_sourced_sum / interviews_sum * 100) if interviews_sum else None,
    "close rate": (start_sourced_sum / new_reqs_sum * 100) if new_reqs_sum else None,
    "back out": (nothire_sourced_sum / hire_sourced_sum * 100) if hire_sourced_sum else None,
}
pvt_labels = {
    "submission per req": "Submission Per Req", "submission to interview": "Submission-to-Interview",
    "interview to hire": "Interview-to-Hire", "close rate": "Close Rate", "back out": "Back Out",
}
benchmarks = get_benchmarks(FY, "client")

status_colors = {"Meeting": "#2E7D6B", "Not Meeting": "#F27538", "No live data": "#848688", "No target set": "#848688"}
pvt_cols = st.columns(5)
for col, key in zip(pvt_cols, pvt_labels.keys()):
    actual = pvt_actuals[key]
    benchmark = benchmarks.get(key)
    status, target_str = evaluate_benchmark(actual, benchmark)
    with col:
        st.metric(pvt_labels[key], f"{actual:.2f}%" if actual is not None and key != "submission per req"
                   else (f"{actual:.2f}" if actual is not None else "—"))
        color = status_colors[status]
        target_line = f"Target: {target_str}" if target_str else "No target set"
        st.markdown(f"<span style='color:{color}; font-weight:600; font-size:13px;'>{status}</span>"
                    f"<br><span style='color:#848688; font-size:12px;'>{target_line}</span>", unsafe_allow_html=True)

st.divider()
st.subheader("Revenue vs. target — cumulative")
month_labels = pd.to_datetime(mp["month"]).dt.strftime("%B'%Y")
fig = go.Figure()
fig.add_bar(x=month_labels, y=mp["revenue_inr"] / 1e7, name="Actual (₹ Cr)", marker_color="#F27538")
if target_inr:
    monthly_target = target_inr / 12 / 1e7
    fig.add_bar(x=month_labels, y=[monthly_target] * len(mp), name="Monthly target (₹ Cr)", marker_color="#28425B")
fig.update_layout(barmode="group", height=350, legend=dict(orientation="h", y=1.1))
st.plotly_chart(fig, use_container_width=True)

st.divider()
st.subheader("Business performance trend")
mp["hires_total"] = mp["hire_preid"] + mp["hire_sourced"]
mp["starts_total"] = mp["start_preid"] + mp["start_sourced"]
metric = st.selectbox("Metric", ["new_reqs", "worked_reqs", "submissions", "interviews",
                                   "hires_total", "starts_total", "concluded", "headcount"])
trend_fig = px.line(mp, x=month_labels, y=metric, markers=True, color_discrete_sequence=["#F27538"])
trend_fig.update_layout(height=350, xaxis_title="Month", yaxis_title=metric)
st.plotly_chart(trend_fig, use_container_width=True)

st.divider()
st.subheader("Monthly detail")
mp_display = mp[["month", "new_reqs", "worked_reqs", "submissions", "interviews", "hire_preid", "hire_sourced",
                  "start_preid", "start_sourced", "headcount", "revenue_inr", "revenue_usd", "is_month_closed"]].copy()
mp_display["month"] = pd.to_datetime(mp_display["month"]).dt.strftime("%B'%Y")
st.dataframe(mp_display, use_container_width=True, hide_index=True)
