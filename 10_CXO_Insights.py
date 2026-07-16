import streamlit as st
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from db import get_monthly_performance, get_client_monthly_performance, get_business_target

st.set_page_config(page_title="CXO Insights", layout="wide")
st.title("CXO Insights")
st.caption("Every insight below is generated from the actual numbers in the database — nothing here is invented.")

FY = st.selectbox("Financial Year", ["FY2026-27", "FY2025-26"])
mp = get_monthly_performance(FY).sort_values("month")
cmp_df = get_client_monthly_performance(FY)
target = get_business_target(FY)

if len(mp) < 2:
    st.info("Need at least 2 months of data to generate month-over-month insights.")
    st.stop()

insights = []  # (tag, text)

latest, prev = mp.iloc[-1], mp.iloc[-2]

# Conversion trend
sub_int_now = latest["interviews"] / latest["submissions"] if latest["submissions"] else 0
sub_int_prev = prev["interviews"] / prev["submissions"] if prev["submissions"] else 0
if sub_int_prev:
    chg = (sub_int_now - sub_int_prev) * 100
    tag = "risk" if chg < -3 else ("opportunity" if chg > 3 else "neutral")
    insights.append((tag, f"Submission-to-interview conversion moved from {sub_int_prev*100:.0f}% in "
                           f"{prev['month']} to {sub_int_now*100:.0f}% in {latest['month']}, "
                           f"a {abs(chg):.0f} percentage-point {'decline' if chg<0 else 'increase'}."))

# Revenue vs target
closed = mp[mp["is_month_closed"]]
if target and len(closed):
    ytd = closed["revenue_inr"].sum()
    target_inr = target["annual_revenue_target_inr"]
    pct = ytd / target_inr * 100
    tag = "risk" if pct < 40 else "neutral"
    insights.append((tag, f"YTD revenue is ₹{ytd/1e7:.2f} Cr against an annual target of ₹{target_inr/1e7:.0f} Cr "
                           f"({pct:.1f}% achieved through {len(closed)} closed month(s))."))

# Open months
open_months = mp[~mp["is_month_closed"]]["month"].tolist()
if open_months:
    insights.append(("neutral", f"{', '.join(str(m) for m in open_months)} revenue not yet booked — excluded from the figures above."))

# Client concentration
if not cmp_df.empty:
    rev_by_client = cmp_df.groupby("client_name")["revenue_usd"].sum().sort_values(ascending=False)
    total_rev = rev_by_client.sum()
    if total_rev:
        top_client, top_rev = rev_by_client.index[0], rev_by_client.iloc[0]
        top_pct = top_rev / total_rev * 100
        tag = "risk" if top_pct > 35 else "neutral"
        insights.append((tag, f"{top_client} accounts for {top_pct:.0f}% of total revenue this FY "
                               f"(${top_rev:,.0f} of ${total_rev:,.0f}) — {'a concentration risk worth monitoring' if top_pct > 35 else 'within a healthy concentration range'}."))

    declining = []
    for client in cmp_df["client_name"].dropna().unique():
        cdata = cmp_df[cmp_df["client_name"] == client].sort_values("month")
        if len(cdata) >= 2 and cdata.iloc[-2]["submissions"] > 0:
            chg = (cdata.iloc[-1]["submissions"] - cdata.iloc[-2]["submissions"]) / cdata.iloc[-2]["submissions"] * 100
            if chg < -30:
                declining.append((client, chg))
    for client, chg in declining:
        insights.append(("risk", f"{client}'s submissions dropped {abs(chg):.0f}% month-over-month — worth a check-in."))

# Headcount trend
hc_chg = latest["headcount"] - prev["headcount"]
if hc_chg != 0:
    tag = "opportunity" if hc_chg > 0 else "risk"
    insights.append((tag, f"Headcount {'grew' if hc_chg > 0 else 'declined'} by {abs(hc_chg)} from {prev['month']} to {latest['month']} "
                           f"({prev['headcount']} → {latest['headcount']})."))

tag_colors = {"risk": "#F27538", "opportunity": "#2E7D6B", "neutral": "#848688"}
tag_labels = {"risk": "RISK", "opportunity": "OPPORTUNITY", "neutral": "OBSERVATION"}

for tag, text in insights:
    st.markdown(f"""
    <div style="border-left: 4px solid {tag_colors[tag]}; padding: 10px 14px; margin-bottom: 10px; background: #F4F5F7; border-radius: 0 8px 8px 0;">
        <span style="font-size:11px; font-weight:600; color:{tag_colors[tag]};">{tag_labels[tag]}</span>
        <p style="margin:4px 0 0; color:#28425B;">{text}</p>
    </div>
    """, unsafe_allow_html=True)

if not insights:
    st.write("No notable changes detected this period.")
