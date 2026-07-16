import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from db import get_monthly_performance, get_business_target

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
target_inr = target["annual_revenue_target_inr"] if target else None
achievement = (ytd_revenue_inr / target_inr * 100) if target_inr else None

with c1:
    st.metric("YTD Revenue (INR)", f"₹{ytd_revenue_inr/1e7:.2f} Cr",
               f"{achievement:.1f}% of target" if achievement else None)
with c2:
    st.metric("New Requirements", int(mp["new_reqs"].sum()),
               delta(latest["new_reqs"], prev["new_reqs"]) if prev is not None else None)
with c3:
    st.metric("Submissions", int(mp["submissions"].sum()),
               delta(latest["submissions"], prev["submissions"]) if prev is not None else None)
with c4:
    st.metric("Interviews", int(mp["interviews"].sum()))

st.caption("Hires and Starts — Pre-ID (client-sourced) vs. Sourced (Rangam-sourced) shown separately")
c5, c6, c7, c8 = st.columns(4)
with c5:
    st.metric("Hires — Pre-ID", int(mp["hire_preid"].sum()))
with c6:
    st.metric("Hires — Sourced", int(mp["hire_sourced"].sum()))
with c7:
    st.metric("Starts — Pre-ID", int(mp["start_preid"].sum()))
with c8:
    st.metric("Starts — Sourced", int(mp["start_sourced"].sum()))

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
col_chart, col_summary = st.columns([1.3, 1])

with col_chart:
    st.subheader("Revenue vs. target — cumulative")
    month_labels = pd.to_datetime(mp["month"]).dt.strftime("%B'%Y")
    fig = go.Figure()
    fig.add_bar(x=month_labels, y=mp["revenue_inr"] / 1e7, name="Actual (₹ Cr)", marker_color="#F27538")
    if target_inr:
        monthly_target = target_inr / 12 / 1e7
        fig.add_bar(x=month_labels, y=[monthly_target] * len(mp), name="Monthly target (₹ Cr)", marker_color="#28425B")
    fig.update_layout(barmode="group", height=350, legend=dict(orientation="h", y=1.1))
    st.plotly_chart(fig, use_container_width=True)

with col_summary:
    st.subheader("Executive summary")
    bullets = []
    if len(mp) >= 2:
        sub_int_now = mp.iloc[-1]["interviews"] / mp.iloc[-1]["submissions"] if mp.iloc[-1]["submissions"] else 0
        sub_int_prev = mp.iloc[-2]["interviews"] / mp.iloc[-2]["submissions"] if mp.iloc[-2]["submissions"] else 0
        if sub_int_prev:
            chg = (sub_int_now - sub_int_prev) * 100
            direction = "declined" if chg < 0 else "improved"
            bullets.append(f"Submission-to-interview conversion {direction} from {sub_int_prev*100:.0f}% to {sub_int_now*100:.0f}% month-over-month.")
    if open_months:
        bullets.append(f"{', '.join(str(m) for m in open_months)} revenue not yet booked — excluded from target-achievement math above.")
    if target_inr:
        remaining = target_inr - ytd_revenue_inr
        bullets.append(f"₹{remaining/1e7:.2f} Cr remaining against the FY target of ₹{target_inr/1e7:.0f} Cr.")
    if not bullets:
        bullets.append("Not enough months of data yet for trend commentary.")
    for b in bullets:
        st.write(f"- {b}")

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
