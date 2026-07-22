import streamlit as st
import pandas as pd
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from db import get_client_monthly_performance, get_benchmarks, evaluate_benchmark

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
nothire_preid_sum = filtered["nothire_preid"].fillna(0).sum()
nothire_sourced_sum = filtered["nothire_sourced"].fillna(0).sum() + filtered["nothire_combined"].fillna(0).sum()
hire_total = hire_preid_sum + hire_sourced_sum
start_total = start_preid_sum + start_sourced_sum
nothire_total = nothire_preid_sum + nothire_sourced_sum
revenue_inr_sum = filtered["revenue_inr"].fillna(0).sum()
revenue_usd_sum = filtered["revenue_usd"].fillna(0).sum()

c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("New Reqs", int(new_reqs_sum))
c2.metric("Worked Reqs", int(worked_reqs_sum))
c3.metric("Submissions", int(submissions_sum))
c4.metric("Interviews", int(interviews_sum))
c5.metric("Hires (total)", int(hire_total))
c6.metric("Starts (total)", int(start_total))

st.caption("Hires, Starts, Not Hires — Pre-ID vs. Sourced (combined-column clients counted as Sourced)")
p1, p2, p3, p4, p5, p6 = st.columns(6)
p1.metric("Hires — Pre-ID", int(hire_preid_sum))
p2.metric("Hires — Sourced", int(hire_sourced_sum))
p3.metric("Starts — Pre-ID", int(start_preid_sum))
p4.metric("Starts — Sourced", int(start_sourced_sum))
p5.metric("Not Hires — Pre-ID", int(nothire_preid_sum))
p6.metric("Not Hires — Sourced", int(nothire_sourced_sum))

c7, c8 = st.columns(2)
c7.metric("Revenue (INR)", f"₹{revenue_inr_sum/1e7:.2f} Cr")
c8.metric("Revenue (USD)", f"${revenue_usd_sum:,.2f}")

st.caption("Note: 'New Reqs' summed here may not exactly match Executive Overview — the source Excel's "
           "'Overall Performance' sheet and per-client sheets are entered separately and don't always agree "
           "(a source data issue, not a calculation error). Submissions/Interviews/Hires/Starts do reconcile.")

st.caption("Ratios — combined-column clients (no Pre-ID/Sourced split available) are counted as Sourced. "
           "Formulas: Submission Per Req = Submissions/New Reqs · Submission-to-Interview = Interviews/Submissions · "
           "Interview-to-Hire = Hires/Interviews · Hire-to-Start = Starts/Hires · Close Rate = Starts/New Reqs · "
           "Back Out = Not Hires/Hires. Badges compare against the 'client' targets set on the Target & Benchmark "
           "Admin page.")
submission_per_req = (submissions_sum / new_reqs_sum) if new_reqs_sum else None
sub_to_int = (interviews_sum / submissions_sum) if submissions_sum else None
int_to_hire = (hire_total / interviews_sum) if interviews_sum else None
hire_to_start = (start_total / hire_total) if hire_total else None
close_rate = (start_total / new_reqs_sum) if new_reqs_sum else None
back_out = (nothire_total / hire_total) if hire_total else None

benchmarks = get_benchmarks(FY, "client")
status_colors = {"Meeting": "#2E7D6B", "Not Meeting": "#F27538", "No live data": "#848688", "No target set": "#848688"}

def _ratio_card(col, label, key, value, is_percent=True):
    with col:
        display_val = f"{value*100:.2f}%" if (value is not None and is_percent) else (f"{value:.2f}" if value is not None else "—")
        st.metric(label, display_val)
        benchmark = benchmarks.get(key)
        actual_for_compare = (value * 100) if (value is not None and is_percent) else value
        status, target_str = evaluate_benchmark(actual_for_compare, benchmark)
        color = status_colors[status]
        target_line = f"Target: {target_str}" if target_str else "No target set"
        st.markdown(f"<span style='color:{color}; font-weight:600; font-size:13px;'>{status}</span>"
                    f"<br><span style='color:#848688; font-size:12px;'>{target_line}</span>", unsafe_allow_html=True)

rr1, rr2, rr3, rr4, rr5 = st.columns(5)
_ratio_card(rr1, "Submission Per Req", "submission per req", submission_per_req, is_percent=False)
_ratio_card(rr2, "Submission-to-Interview", "submission to interview", sub_to_int)
_ratio_card(rr3, "Interview-to-Hire", "interview to hire", int_to_hire)
_ratio_card(rr4, "Close Rate", "close rate", close_rate)
_ratio_card(rr5, "Back Out", "back out", back_out)

# ---------------------------------------------------------------------------
# Detail table — cleaned up
# ---------------------------------------------------------------------------
st.divider()
st.subheader(f"Detail — {len(filtered)} rows")
detail = filtered[["month_label", "msp_name", "client_name", "hours_worked", "avg_recruiters", "new_reqs",
                    "worked_reqs", "submissions", "interviews", "hire_preid", "hire_sourced", "hire_combined",
                    "start_preid", "start_sourced", "start_combined", "nothire_preid", "nothire_sourced",
                    "nothire_combined", "concluded", "headcount",
                    "revenue_inr", "revenue_usd", "is_month_closed"]].rename(columns={"month_label": "month"}).copy()
detail["revenue_inr"] = detail["revenue_inr"].apply(lambda v: f"₹{v:,.2f}" if pd.notna(v) else "—")
detail["revenue_usd"] = detail["revenue_usd"].apply(lambda v: f"${v:,.2f}" if pd.notna(v) else "—")
st.dataframe(detail, use_container_width=True, hide_index=True)

# ---------------------------------------------------------------------------
# Period comparison — any client, any two periods (month / quarter / year)
# ---------------------------------------------------------------------------
st.divider()
st.subheader("Period comparison")
st.caption("Compare any two periods for a client (or all clients / an MSP) — e.g. April 2025 vs. April 2026, "
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

granularity = st.radio("Compare by", ["Month", "Quarter", "Year"], horizontal=True, key="comp_granularity")
LIMITS = {"Month": (2, 3), "Quarter": (2, 4), "Year": (2, 5)}
min_n, max_n = LIMITS[granularity]

available_months = sorted(all_data["month"].dt.to_period("M").unique())
available_years = sorted({p.year for p in available_months})
available_quarters = sorted({(p.year, (p.month - 1) // 3 + 1) for p in available_months})

def period_bounds_month(period):
    return period.to_timestamp(), period.to_timestamp(how="end").normalize(), period.strftime("%B'%Y")

def period_bounds_quarter(year, q):
    start_month = (q - 1) * 3 + 1
    start = pd.Timestamp(year=year, month=start_month, day=1)
    end = (start + pd.DateOffset(months=3)) - pd.DateOffset(days=1)
    return start, end, f"Q{q} {year}"

def period_bounds_year(year):
    return pd.Timestamp(year=year, month=1, day=1), pd.Timestamp(year=year, month=12, day=31), str(year)

st.caption(f"Select {min_n} to {max_n} {granularity.lower()}(s) to compare.")
if granularity == "Month":
    selected = st.multiselect("Periods", available_months, default=available_months[-min_n:],
                                format_func=lambda p: p.strftime("%B'%Y"), key="cmp_months")
    periods = [period_bounds_month(p) for p in selected]
elif granularity == "Quarter":
    selected = st.multiselect("Periods", available_quarters, default=available_quarters[-min_n:],
                                format_func=lambda t: f"Q{t[1]} {t[0]}", key="cmp_quarters")
    periods = [period_bounds_quarter(*t) for t in selected]
else:
    selected = st.multiselect("Periods", available_years, default=available_years[-min_n:], key="cmp_years")
    periods = [period_bounds_year(y) for y in selected]

def summarize_period(df, start, end):
    sub = df[(df["month"] >= start) & (df["month"] <= end)]
    if sub.empty:
        return None
    return {
        "New Reqs": sub["new_reqs"].fillna(0).sum(),
        "Submissions": sub["submissions"].fillna(0).sum(),
        "Interviews": sub["interviews"].fillna(0).sum(),
        "Hires": sub["hire_preid"].fillna(0).sum() + sub["hire_sourced"].fillna(0).sum() + sub["hire_combined"].fillna(0).sum(),
        "Starts": sub["start_preid"].fillna(0).sum() + sub["start_sourced"].fillna(0).sum() + sub["start_combined"].fillna(0).sum(),
        "Not Hires": sub["nothire_preid"].fillna(0).sum() + sub["nothire_sourced"].fillna(0).sum() + sub["nothire_combined"].fillna(0).sum(),
        "Revenue (USD)": sub["revenue_usd"].fillna(0).sum(),
        "Revenue (INR)": sub["revenue_inr"].fillna(0).sum(),
    }

def _format_value(metric, val):
    if metric == "Revenue (USD)":
        return f"${val:,.2f}"
    if metric == "Revenue (INR)":
        return f"₹{val:,.2f}"
    return f"{val:,.0f}"

if len(selected) < min_n:
    st.warning(f"Select at least {min_n} {granularity.lower()}(s).")
elif len(selected) > max_n:
    st.warning(f"Select at most {max_n} {granularity.lower()}(s).")
else:
    summaries = [(label, summarize_period(comp_scoped, start, end)) for start, end, label in periods]
    summaries = [(l, s) for l, s in summaries if s is not None]
    if len(summaries) < 2:
        st.info("Not enough data in the selected periods to compare.")
    else:
        metrics = list(summaries[0][1].keys())
        rows = []
        for m in metrics:
            row = {"Metric": m}
            for label, s in summaries:
                row[label] = _format_value(m, s[m])
            rows.append(row)
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
