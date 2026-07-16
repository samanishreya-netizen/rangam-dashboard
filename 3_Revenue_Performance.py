import streamlit as st
import plotly.graph_objects as go
import datetime
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from db import get_monthly_performance, get_client_monthly_performance, get_business_target

st.set_page_config(page_title="Revenue Performance", layout="wide")
st.title("Revenue Performance")

FY = st.selectbox("Financial Year", ["FY2026-27", "FY2025-26"])
mp = get_monthly_performance(FY).sort_values("month")
cmp_df = get_client_monthly_performance(FY)
target = get_business_target(FY)

if mp.empty:
    st.info("No data yet for this Financial Year.")
    st.stop()

closed = mp[mp["is_month_closed"]]
ytd_inr = closed["revenue_inr"].sum()
target_inr = target["annual_revenue_target_inr"] if target else None

c1, c2, c3, c4 = st.columns(4)
c1.metric("YTD Actual (₹ Cr)", f"{ytd_inr/1e7:.2f}")
c2.metric("Annual Target (₹ Cr)", f"{target_inr/1e7:.0f}" if target_inr else "not set")
if target_inr:
    remaining = target_inr - ytd_inr
    c3.metric("Remaining Target (₹ Cr)", f"{remaining/1e7:.2f}")
    fy_start_year = int(FY[2:6])
    fy_end = datetime.date(fy_start_year + 1, 3, 31)
    months_elapsed = len(closed)
    months_remaining = max(12 - months_elapsed, 1)
    run_rate = remaining / months_remaining
    c4.metric("Required Monthly Run Rate (₹ Cr)", f"{run_rate/1e7:.2f}")
else:
    c3.metric("Remaining Target", "—")
    c4.metric("Required Run Rate", "—")

st.divider()
st.subheader("Cumulative revenue vs. target (estimates labeled)")
fig = go.Figure()
mp["cum_revenue"] = mp["revenue_inr"].fillna(0).cumsum() / 1e7
fig.add_scatter(x=mp["month"].astype(str), y=mp["cum_revenue"], name="Actual cumulative (₹ Cr)",
                 line=dict(color="#F27538", width=3))
if target_inr:
    monthly_target = target_inr / 12 / 1e7
    cum_target = [(i + 1) * monthly_target for i in range(len(mp))]
    fig.add_scatter(x=mp["month"].astype(str), y=cum_target, name="Target cumulative (₹ Cr)",
                     line=dict(color="#28425B", dash="dash"))
    if len(closed) >= 2:
        avg_monthly = closed["revenue_inr"].mean()
        projected_year_end = (avg_monthly * 12) / 1e7
        st.caption(f"Projected year-end revenue (ESTIMATE, based on {len(closed)}-month average run rate): ₹{projected_year_end:.2f} Cr")
fig.update_layout(height=350)
st.plotly_chart(fig, use_container_width=True)

st.divider()
col1, col2 = st.columns(2)
if not cmp_df.empty:
    client_rev = cmp_df.groupby("client_name")["revenue_usd"].sum().sort_values(ascending=False)
    with col1:
        st.subheader("Client-wise revenue (USD)")
        st.bar_chart(client_rev)
    msp_rev = cmp_df.groupby("msp_name")["revenue_usd"].sum().sort_values(ascending=False)
    with col2:
        st.subheader("MSP-wise revenue (USD)")
        st.bar_chart(msp_rev)
