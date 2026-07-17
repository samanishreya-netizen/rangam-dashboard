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

c7, c8, c9 = st.columns(3)
c7.metric("Not Hires (total)", int(nothire_total))
c8.metric("Revenue (INR)", f"₹{revenue_inr_sum/1e7:.2f} Cr")
c9.metric("Revenue (USD)", f"${revenue_usd_sum:,.2f}")

st.caption("Ratios — combined-column clients (no Pre-ID/Sourced split available) are counted as Sourced. "
           "Formulas: Submission-to-Interview = Interviews/Submissions · Interview-to-Hire = Hires/Interviews · "
           "Hire-to-Start = Starts/Hires · Close Rate = Starts/New Reqs · Back Out = Not Hires/Hires.")
r1, r2, r3, r4, r5 = st.columns(5)
sub_to_int = (interviews_sum / submissions_sum) if submissions_sum else None
int_to_hire = (hire_total / interviews_sum) if interviews_sum else None
hire_to_start = (start_total / hire_total) if hire_total else None
close_rate = (start_total / new_reqs_sum) if new_reqs_sum else None
back_out = (nothire_total / hire_total) if hire_total else None

r1.metric("Submission-to-Interview", f"{sub_to_int*100:.2f}%" if sub_to_int is not None else "—")
r2.metric("Interview-to-Hire", f"{int_to_hire*100:.2f}%" if int_to_hire is not None else "—")
r3.metric("Hire-to-Start", f"{hire_to_start*100:.2f}%" if hire_to_start is not None else "—")
r4.metric("Close Rate", f"{close_rate*100:.2f}%" if close_rate is not None else "—")
r5.metric("Back Out", f"{back_out*100:.2f}%" if back_out is not None else "—")

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

available_months = sorted(all_data["month"].dt.to_period("M").unique())
available_years = sorted({p.year for p in available_months})
available_quarters = sorted({(p.year, (p.month - 1) // 3 + 1) for p in available_months})

def period_bounds_month(period):
    start = period.to_timestamp()
    end = period.to_timestamp(how="end").normalize()
    return start, end, period.strftime("%B'%Y")

def period_bounds_quarter(year, q):
    start_month = (q - 1) * 3 + 1
    start = pd.Timestamp(year=year, month=start_month, day=1)
    end = (start + pd.DateOffset(months=3)) - pd.DateOffset(days=1)
    return start, end, f"Q{q} {year}"

def period_bounds_year(year):
    start = pd.Timestamp(year=year, month=1, day=1)
    end = pd.Timestamp(year=year, month=12, day=31)
    return start, end, str(year)

pcol1, pcol2 = st.columns(2)
if granularity == "Month":
    with pcol1:
        month_a = st.selectbox("Period A", available_months, index=max(0, len(available_months) - 2),
                                 format_func=lambda p: p.strftime("%B'%Y"), key="month_a")
    with pcol2:
        month_b = st.selectbox("Period B", available_months, index=len(available_months) - 1,
                                 format_func=lambda p: p.strftime("%B'%Y"), key="month_b")
    start_a, end_a, label_a = period_bounds_month(month_a)
    start_b, end_b, label_b = period_bounds_month(month_b)
elif granularity == "Quarter":
    with pcol1:
        q_a = st.selectbox("Period A", available_quarters, index=max(0, len(available_quarters) - 2),
                             format_func=lambda t: f"Q{t[1]} {t[0]}", key="q_a")
    with pcol2:
        q_b = st.selectbox("Period B", available_quarters, index=len(available_quarters) - 1,
                             format_func=lambda t: f"Q{t[1]} {t[0]}", key="q_b")
    start_a, end_a, label_a = period_bounds_quarter(*q_a)
    start_b, end_b, label_b = period_bounds_quarter(*q_b)
else:
    with pcol1:
        y_a = st.selectbox("Period A", available_years, index=max(0, len(available_years) - 2), key="y_a")
    with pcol2:
        y_b = st.selectbox("Period B", available_years, index=len(available_years) - 1, key="y_b")
    start_a, end_a, label_a = period_bounds_year(y_a)
    start_b, end_b, label_b = period_bounds_year(y_b)

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

summary_a = summarize_period(comp_scoped, start_a, end_a)
summary_b = summarize_period(comp_scoped, start_b, end_b)

def _format_value(metric, val):
    if metric == "Revenue (USD)":
        return f"${val:,.2f}"
    if metric == "Revenue (INR)":
        return f"₹{val:,.2f}"
    return f"{val:,.0f}"

if summary_a and summary_b:
    rows = []
    for k in summary_a:
        a_val, b_val = summary_a[k], summary_b[k]
        pct_change = ((b_val - a_val) / a_val * 100) if a_val else None
        change_val = b_val - a_val
        rows.append({
            "Metric": k,
            label_a: _format_value(k, a_val),
            label_b: _format_value(k, b_val),
            "Change": _format_value(k, change_val) if k not in ("Revenue (USD)", "Revenue (INR)")
                      else (f"+{_format_value(k, change_val)}" if change_val >= 0 else _format_value(k, change_val)),
            "% Change": f"{pct_change:+.1f}%" if pct_change is not None else "—",
        })
    comp_df_display = pd.DataFrame(rows)

    def _color_change(val):
        if isinstance(val, str):
            if val == "—":
                return ""
            try:
                num = float(val.replace("%", "").replace("+", "").replace("$", "").replace("₹", "").replace(",", ""))
            except ValueError:
                return ""
        else:
            num = val
        if num > 0:
            return "color: #2E7D6B; font-weight: 600"
        if num < 0:
            return "color: #F27538; font-weight: 600"
        return ""

    styled = comp_df_display.style.map(_color_change, subset=["Change", "% Change"])
    st.dataframe(styled, use_container_width=True, hide_index=True)
    st.caption("Green = increase, orange = decrease. Note: for 'Not Hires,' green (an increase) is actually "
               "the unfavorable direction — read each metric in context, not just by color.")
else:
    st.info("Not enough data in one or both selected periods to compare.")

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
