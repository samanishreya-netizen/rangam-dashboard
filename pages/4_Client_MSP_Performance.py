import streamlit as st
import pandas as pd
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

cmp_df["month"] = pd.to_datetime(cmp_df["month"])
cmp_df["month_label"] = cmp_df["month"].dt.strftime("%B'%Y")

# ---------------------------------------------------------------------------
# Filters — all optional, default to everything selected
# ---------------------------------------------------------------------------
st.subheader("Filters")
f1, f2, f3 = st.columns(3)
with f1:
    month_options = sorted(cmp_df["month"].unique())
    month_labels_map = {m: pd.Timestamp(m).strftime("%B'%Y") for m in month_options}
    selected_months = st.multiselect("Month (leave empty = all)", options=month_options,
                                       format_func=lambda m: month_labels_map[m])
with f2:
    msp_filter = st.selectbox("MSP", ["All"] + sorted(cmp_df["msp_name"].dropna().unique().tolist()))
with f3:
    msp_scoped = cmp_df if msp_filter == "All" else cmp_df[cmp_df["msp_name"] == msp_filter]
    client_filter = st.selectbox("Client", ["All"] + sorted(msp_scoped["client_name"].dropna().unique().tolist()))

filtered = cmp_df.copy()
if selected_months:
    filtered = filtered[filtered["month"].isin(selected_months)]
if msp_filter != "All":
    filtered = filtered[filtered["msp_name"] == msp_filter]
if client_filter != "All":
    filtered = filtered[filtered["client_name"] == client_filter]

if filtered.empty:
    st.warning("No rows match this filter combination.")
    st.stop()

# ---------------------------------------------------------------------------
# Summary totals + ratios, based on the current filter — same style as
# Executive Overview's KPI cards.
# ---------------------------------------------------------------------------
st.divider()
st.subheader("Summary — based on filters above")

new_reqs_sum = filtered["new_reqs"].fillna(0).sum()
worked_reqs_sum = filtered["worked_reqs"].fillna(0).sum()
submissions_sum = filtered["submissions"].fillna(0).sum()
interviews_sum = filtered["interviews"].fillna(0).sum()
hire_preid_sum = filtered["hire_preid"].fillna(0).sum()
# combined-column clients (no Pre-ID/Sourced split) are counted as sourced,
# since that's the closest available approximation for those rows
hire_sourced_sum = filtered["hire_sourced"].fillna(0).sum() + filtered["hire_combined"].fillna(0).sum()
start_preid_sum = filtered["start_preid"].fillna(0).sum()
start_sourced_sum = filtered["start_sourced"].fillna(0).sum() + filtered["start_combined"].fillna(0).sum()
nothire_sourced_sum = filtered["nothire_sourced"].fillna(0).sum() + filtered["nothire_combined"].fillna(0).sum()
hire_total = hire_preid_sum + hire_sourced_sum
start_total = start_preid_sum + start_sourced_sum
revenue_inr_sum = filtered["revenue_inr"].fillna(0).sum()
revenue_usd_sum = filtered["revenue_usd"].fillna(0).sum()

c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("New Reqs", int(new_reqs_sum))
c2.metric("Worked Reqs", int(worked_reqs_sum))
c3.metric("Submissions", int(submissions_sum))
c4.metric("Interviews", int(interviews_sum))
c5.metric("Hires (total)", int(hire_total))
c6.metric("Starts (total)", int(start_total))

c7, c8 = st.columns(2)
c7.metric("Revenue (INR)", f"₹{revenue_inr_sum/1e7:.2f} Cr")
c8.metric("Revenue (USD)", f"${revenue_usd_sum:,.0f}")

st.caption("Ratios — combined-column clients (no Pre-ID/Sourced split available) are counted as Sourced.")
r1, r2, r3, r4, r5 = st.columns(5)
sub_to_int = (interviews_sum / submissions_sum) if submissions_sum else None
int_to_hire = (hire_sourced_sum / (interviews_sum - hire_sourced_sum)) if (interviews_sum - hire_sourced_sum) > 0 else None
close_rate = (hire_sourced_sum / (new_reqs_sum - hire_preid_sum)) if (new_reqs_sum - hire_preid_sum) > 0 else None
back_out = (nothire_sourced_sum / hire_sourced_sum) if hire_sourced_sum else None
hire_to_start = (start_total / hire_total) if hire_total else None

r1.metric("Submission-to-Interview", f"{sub_to_int*100:.1f}%" if sub_to_int is not None else "—")
r2.metric("Interview-to-Hire", f"{int_to_hire*100:.1f}%" if int_to_hire is not None else "—")
r3.metric("Hire-to-Start", f"{hire_to_start*100:.1f}%" if hire_to_start is not None else "—")
r4.metric("Close Rate", f"{close_rate*100:.1f}%" if close_rate is not None else "—")
r5.metric("Back Out", f"{back_out*100:.1f}%" if back_out is not None else "—")

# ---------------------------------------------------------------------------
# Detail table — cleaned up
# ---------------------------------------------------------------------------
st.divider()
st.subheader(f"Detail — {len(filtered)} rows")
detail = filtered[["month_label", "msp_name", "client_name", "hours_worked", "avg_recruiters", "new_reqs",
                    "worked_reqs", "submissions", "interviews", "hire_preid", "hire_sourced", "hire_combined",
                    "start_preid", "start_sourced", "start_combined", "concluded", "headcount",
                    "revenue_inr", "revenue_usd", "is_month_closed"]].rename(columns={"month_label": "month"})
st.dataframe(detail, use_container_width=True, hide_index=True)

# ---------------------------------------------------------------------------
# Period comparison — any client, any two date ranges (month / quarter / year)
# ---------------------------------------------------------------------------
st.divider()
st.subheader("Period comparison")
st.caption("Compare any two date ranges for a client (or all clients / an MSP) — e.g. April 2025 vs. April 2026, "
           "Q1 2025 vs. Q1 2026, or full year 2025 vs. full year 2026. Uses all financial years in the database, "
           "not just the one selected above.")

all_data = get_client_monthly_performance()  # every FY, for cross-year comparison
all_data["month"] = pd.to_datetime(all_data["month"])

comp_scope_col, comp_client_col = st.columns(2)
with comp_scope_col:
    comp_msp = st.selectbox("MSP (comparison)", ["All"] + sorted(all_data["msp_name"].dropna().unique().tolist()), key="comp_msp")
comp_scoped = all_data if comp_msp == "All" else all_data[all_data["msp_name"] == comp_msp]
with comp_client_col:
    comp_client = st.selectbox("Client (comparison)", ["All"] + sorted(comp_scoped["client_name"].dropna().unique().tolist()), key="comp_client")
if comp_client != "All":
    comp_scoped = comp_scoped[comp_scoped["client_name"] == comp_client]

min_date, max_date = all_data["month"].min().date(), all_data["month"].max().date()

pcol1, pcol2 = st.columns(2)
with pcol1:
    st.write("**Period A**")
    period_a = st.date_input("Date range A", value=(min_date, max_date), key="period_a")
with pcol2:
    st.write("**Period B**")
    period_b = st.date_input("Date range B", value=(min_date, max_date), key="period_b")

def summarize_period(df, date_range):
    if len(date_range) != 2:
        return None
    start, end = pd.Timestamp(date_range[0]), pd.Timestamp(date_range[1])
    sub = df[(df["month"] >= start) & (df["month"] <= end)]
    if sub.empty:
        return None
    return {
        "New Reqs": sub["new_reqs"].fillna(0).sum(),
        "Submissions": sub["submissions"].fillna(0).sum(),
        "Interviews": sub["interviews"].fillna(0).sum(),
        "Hires": sub["hire_preid"].fillna(0).sum() + sub["hire_sourced"].fillna(0).sum() + sub["hire_combined"].fillna(0).sum(),
        "Starts": sub["start_preid"].fillna(0).sum() + sub["start_sourced"].fillna(0).sum() + sub["start_combined"].fillna(0).sum(),
        "Revenue (USD)": sub["revenue_usd"].fillna(0).sum(),
        "Revenue (INR)": sub["revenue_inr"].fillna(0).sum(),
        "months_included": sub["month"].dt.strftime("%B'%Y").unique().tolist(),
    }

summary_a = summarize_period(comp_scoped, period_a)
summary_b = summarize_period(comp_scoped, period_b)

if summary_a and summary_b:
    st.write(f"Period A covers: {', '.join(summary_a.pop('months_included'))}")
    st.write(f"Period B covers: {', '.join(summary_b.pop('months_included'))}")

    rows = []
    for k in summary_a:
        a_val, b_val = summary_a[k], summary_b[k]
        pct_change = ((b_val - a_val) / a_val * 100) if a_val else None
        rows.append({
            "Metric": k, "Period A": round(a_val, 2), "Period B": round(b_val, 2),
            "Change": round(b_val - a_val, 2),
            "% Change": f"{pct_change:+.1f}%" if pct_change is not None else "—",
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
else:
    st.info("Not enough data in one or both selected ranges to compare.")

st.divider()
st.subheader("Client summary — flags")
summary = filtered.groupby("client_name").agg(
    new_reqs=("new_reqs", "sum"), submissions=("submissions", "sum"),
    interviews=("interviews", "sum"), revenue_usd=("revenue_usd", "sum"),
).reset_index()
summary["submission_per_req"] = (summary["submissions"] / summary["new_reqs"]).round(2)
low_coverage = summary[summary["submission_per_req"] < 2]
if not low_coverage.empty:
    st.write("**Low requirement coverage (< 2 submissions per requirement):**", ", ".join(low_coverage["client_name"]))
else:
    st.write("No clients flagged for low requirement coverage in this filter.")
