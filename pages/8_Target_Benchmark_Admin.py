import streamlit as st
import pandas as pd
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from db import (get_client, require_admin_gate, get_business_target, clear_caches,
                 get_client_monthly_performance, get_recruiter_performance, get_onboarding_performance)

st.set_page_config(page_title="Target & Benchmark Admin", layout="wide")
require_admin_gate()

st.title("Target & Benchmark Management")
sb = get_client()

FY = st.selectbox("Financial Year", ["FY2026-27", "FY2025-26"])
current = get_business_target(FY)

# ---------------------------------------------------------------------------
# Readable change history — shared by Business Target and KPI Benchmarks
# ---------------------------------------------------------------------------
def render_history(table_name, title):
    st.subheader(title)
    history = sb.table("target_change_log").select("*").eq("fy_code", FY).eq(
        "target_table", table_name).order("changed_at", desc=True).limit(50).execute().data
    if not history:
        st.write("No changes logged yet for this FY.")
        return
    rows = []
    for h in history:
        old = h.get("old_values") or {}
        new = h.get("new_values") or {}
        all_keys = set(old.keys()) | set(new.keys())
        skip_keys = {"target_id", "benchmark_id", "effective_from", "created_by", "is_active"}
        for k in sorted(all_keys - skip_keys):
            old_v, new_v = old.get(k), new.get(k)
            if old_v != new_v:
                rows.append({
                    "Date": h["changed_at"][:16].replace("T", " "),
                    "Changed by": h.get("changed_by") or "admin",
                    "Field": k,
                    "Old value": old_v if old_v is not None else "—",
                    "New value": new_v if new_v is not None else "—",
                })
    if rows:
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.write("No field-level changes detected in the logged entries.")

# ---------------------------------------------------------------------------
# Business Target
# ---------------------------------------------------------------------------
st.subheader("Business Target")
with st.form("business_target_form"):
    rev_inr = st.number_input("Annual Revenue Target (INR)", value=float(current["annual_revenue_target_inr"]) if current else 0.0, step=1000000.0)
    rev_usd = st.number_input("Annual Revenue Target (USD)", value=float(current["annual_revenue_target_usd"]) if current else 0.0, step=10000.0)
    exch = st.number_input("Exchange Rate Assumption", value=float(current["exchange_rate_assumption"]) if current else 90.0)
    hiring_target = st.number_input("Annual Hiring Target", value=int(current["annual_hiring_target"]) if current and current.get("annual_hiring_target") else 0, step=1)
    headcount_target = st.number_input("Headcount Target", value=int(current["headcount_target"]) if current and current.get("headcount_target") else 0, step=1)
    submitted = st.form_submit_button("Save target (keeps version history)")

    if submitted:
        old_values = current
        if current:
            sb.table("config_business_target").update({"is_active": False}).eq("target_id", current["target_id"]).execute()
        new_row = sb.table("config_business_target").insert({
            "fy_code": FY, "annual_revenue_target_inr": rev_inr, "annual_revenue_target_usd": rev_usd,
            "exchange_rate_assumption": exch, "annual_hiring_target": hiring_target,
            "headcount_target": headcount_target, "is_active": True,
        }).execute()
        sb.table("target_change_log").insert({
            "target_table": "config_business_target", "target_row_id": new_row.data[0]["target_id"],
            "fy_code": FY, "old_values": old_values, "new_values": new_row.data[0],
        }).execute()
        clear_caches()
        st.success(f"Target saved for {FY}. Monthly figures are derived automatically (annual ÷ 12) — no need to enter them separately.")
        st.rerun()

if current:
    st.caption(f"Implied monthly target: ₹{current['annual_revenue_target_inr']/12/1e7:.2f} Cr / ${current['annual_revenue_target_usd']/12:,.0f}")

st.divider()
render_history("config_business_target", "Business target change history")

# ---------------------------------------------------------------------------
# KPI Benchmarks — full add/edit/delete, per level (client / recruiter / onboarding)
# ---------------------------------------------------------------------------
st.divider()
st.subheader("KPI Benchmarks")
st.caption("Define the targets used to judge performance on the Client, Recruiter, and Onboarding pages. "
           "Add, edit, or delete rows directly in the table below, then click Save.")

STANDARD_KPIS = [
    {"kpi_name": "Response Rate", "target_value": 80, "min_value": None, "max_value": None,
     "comparison_type": ">=", "unit": "%", "description": "Average response rate to submissions"},
    {"kpi_name": "Submission Per Req", "target_value": None, "min_value": 3, "max_value": 5,
     "comparison_type": "between", "unit": "count", "description": "Qualified submissions per role"},
    {"kpi_name": "Submission to Interview", "target_value": 33, "min_value": None, "max_value": None,
     "comparison_type": ">=", "unit": "%", "description": "1 interview per <=3 submissions"},
    {"kpi_name": "Interview to Hire", "target_value": 20, "min_value": None, "max_value": None,
     "comparison_type": ">=", "unit": "%", "description": "1 hire per <=5 interviews"},
    {"kpi_name": "Close Rate", "target_value": 25, "min_value": None, "max_value": None,
     "comparison_type": ">=", "unit": "%", "description": ""},
    {"kpi_name": "Back Out", "target_value": 20, "min_value": None, "max_value": None,
     "comparison_type": "<=", "unit": "%", "description": ""},
]

seed_col1, seed_col2 = st.columns([1, 3])
with seed_col1:
    seed_level = st.selectbox("Level to seed", ["client", "recruiter"], key="seed_level")
with seed_col2:
    st.write("")
    if st.button(f"Load the 6 standard KPIs for '{seed_level}'"):
        existing_names = {b["kpi_name"].lower() for b in
                           sb.table("config_kpi_benchmark").select("kpi_name").eq("fy_code", FY).eq(
                               "applies_to_level", seed_level).execute().data}
        inserted = 0
        for kpi in STANDARD_KPIS:
            if kpi["kpi_name"].lower() not in existing_names:
                new_row = sb.table("config_kpi_benchmark").insert({
                    **kpi, "fy_code": FY, "applies_to_level": seed_level, "is_active": True,
                }).execute()
                sb.table("target_change_log").insert({
                    "target_table": "config_kpi_benchmark", "target_row_id": new_row.data[0]["benchmark_id"],
                    "fy_code": FY, "old_values": None, "new_values": new_row.data[0],
                }).execute()
                inserted += 1
        clear_caches()
        st.success(f"Added {inserted} new benchmark(s) for '{seed_level}' (skipped any already present).")
        st.rerun()

benchmark_rows = sb.table("config_kpi_benchmark").select("*").eq("fy_code", FY).eq("is_active", True).execute().data
bm_df = pd.DataFrame(benchmark_rows)
bm_cols = ["benchmark_id", "kpi_name", "applies_to_level", "target_value", "min_value", "max_value",
           "comparison_type", "unit", "description"]
if bm_df.empty:
    bm_df = pd.DataFrame(columns=bm_cols)

edited_bm = st.data_editor(
    bm_df[bm_cols], num_rows="dynamic", use_container_width=True, key="benchmark_editor",
    column_config={
        "benchmark_id": st.column_config.NumberColumn("ID", disabled=True, help="Leave blank for a new row"),
        "applies_to_level": st.column_config.SelectboxColumn("Level", options=["client", "recruiter", "onboarding", "company"]),
        "comparison_type": st.column_config.SelectboxColumn("Comparison", options=[">=", "<=", "between"]),
    },
)

def _normalize_bm(v):
    if v is None:
        return None
    if isinstance(v, bool):
        return v
    try:
        return round(float(v), 4)
    except (TypeError, ValueError):
        return str(v).strip()

if st.button("Save benchmark changes", type="primary"):
    original_ids = set(bm_df["benchmark_id"].dropna().astype(int)) if "benchmark_id" in bm_df else set()
    edited_ids = set(edited_bm["benchmark_id"].dropna().astype(int)) if "benchmark_id" in edited_bm else set()
    deleted_ids = original_ids - edited_ids

    for bid in deleted_ids:
        old_row = bm_df[bm_df["benchmark_id"] == bid].iloc[0].to_dict()
        sb.table("config_kpi_benchmark").delete().eq("benchmark_id", int(bid)).execute()
        sb.table("target_change_log").insert({
            "target_table": "config_kpi_benchmark", "target_row_id": int(bid), "fy_code": FY,
            "old_values": old_row, "new_values": None,
        }).execute()

    any_changes = False
    for _, row in edited_bm.iterrows():
        row_dict = {k: (None if pd.isna(v) else v) for k, v in row.to_dict().items()}
        if row_dict.get("benchmark_id") is None:
            if not row_dict.get("kpi_name"):
                continue
            row_dict.pop("benchmark_id", None)
            row_dict["fy_code"] = FY
            new_row = sb.table("config_kpi_benchmark").insert(row_dict).execute()
            sb.table("target_change_log").insert({
                "target_table": "config_kpi_benchmark", "target_row_id": new_row.data[0]["benchmark_id"],
                "fy_code": FY, "old_values": None, "new_values": new_row.data[0],
            }).execute()
            any_changes = True
        else:
            bid = int(row_dict["benchmark_id"])
            orig_row = bm_df[bm_df["benchmark_id"] == bid].iloc[0].to_dict()
            orig_clean = {k: (None if pd.isna(v) else v) for k, v in orig_row.items()}
            new_cmp = {k: _normalize_bm(v) for k, v in row_dict.items() if k != "benchmark_id"}
            old_cmp = {k: _normalize_bm(v) for k, v in orig_clean.items() if k != "benchmark_id"}
            if new_cmp != old_cmp:
                update_dict = {k: v for k, v in row_dict.items() if k != "benchmark_id"}
                sb.table("config_kpi_benchmark").update(update_dict).eq("benchmark_id", bid).execute()
                sb.table("target_change_log").insert({
                    "target_table": "config_kpi_benchmark", "target_row_id": bid, "fy_code": FY,
                    "old_values": orig_clean, "new_values": row_dict,
                }).execute()
                any_changes = True

    clear_caches()
    if any_changes or deleted_ids:
        st.success("Benchmark changes saved.")
    else:
        st.info("No changes detected.")
    st.rerun()

st.divider()
render_history("config_kpi_benchmark", "Benchmark change history")
