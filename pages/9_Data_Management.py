import streamlit as st
import pandas as pd
import tempfile, os
import sys
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from db import get_client, require_admin_gate, clear_caches, months_already_in_db
import etl_parser as ep

st.set_page_config(page_title="Data Management", layout="wide")
require_admin_gate()

st.title("Data Management")
st.caption("Upload the monthly Excel file here — new months are added automatically, and any month that already "
           "exists in the database is shown separately so you can choose whether to update it. One upload handles both.")

sb = get_client()
uploaded = st.file_uploader("Upload workbook (.xlsx)", type=["xlsx"])

if uploaded:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
        tmp.write(uploaded.read())
        tmp_path = tmp.name

    with st.spinner("Validating and parsing..."):
        data = ep.parse_workbook(tmp_path)
    os.unlink(tmp_path)

    if data["errors"]:
        st.error("This file doesn't match the expected template, so nothing has been uploaded:\n\n" +
                  "\n".join(f"- {e}" for e in data["errors"]))
        st.info("Fix the file to match the standard monthly template and try again. No changes were made to the database.")
        st.stop()

    if data["warnings"]:
        st.warning("Validation warnings (upload allowed, but double-check these):\n" +
                    "\n".join(f"- {w}" for w in data["warnings"]))
    else:
        st.success("Workbook structure validated — matches the expected template.")

    existing_months = months_already_in_db()
    detected = data["months_detected"]
    new_months = [m for m in detected if m not in existing_months]
    existing_in_file = [m for m in detected if m in existing_months]

    col1, col2 = st.columns(2)
    with col1:
        st.metric("New months (will be added)", len(new_months))
        st.write(new_months if new_months else "None")
    with col2:
        st.metric("Months already in database", len(existing_in_file))
        st.write(existing_in_file if existing_in_file else "None")

    overall_new = data["overall"][data["overall"]["month"].astype(str).isin(new_months)]
    client_new = data["clientwise"][data["clientwise"]["month"].astype(str).isin(new_months)]

    if new_months:
        st.subheader(f"New — {len(new_months)} month(s) will be added")
        st.dataframe(overall_new, use_container_width=True)
        st.write(f"Client-level rows to add: {len(client_new)}")

    months_to_update = []
    if existing_in_file:
        st.subheader(f"Already in database — {len(existing_in_file)} month(s)")
        st.caption("These months already have data. Nothing is changed unless you tick a box below.")
        for m in existing_in_file:
            if st.checkbox(f"Update {m} with the figures from this file", key=f"update_{m}"):
                months_to_update.append(m)
                old_overall = sb.table("fact_monthly_performance").select("*").eq("month", m).execute().data
                old_overall = old_overall[0] if old_overall else None
                new_row = data["overall"][data["overall"]["month"].astype(str) == m].iloc[0].to_dict()
                compare_fields = ["new_reqs", "worked_reqs", "submissions", "interviews", "hire_preid", "hire_sourced",
                                   "start_preid", "start_sourced", "nothire_preid", "nothire_sourced", "concluded",
                                   "headcount", "revenue_inr", "revenue_usd"]
                rows = []
                for f in compare_fields:
                    old_v = old_overall.get(f) if old_overall else None
                    new_v = new_row.get(f)
                    new_v = None if pd.isna(new_v) else new_v
                    rows.append({"Field": f, "Current": old_v if old_v is not None else "—",
                                  "In this file": new_v if new_v is not None else "—",
                                  "Changes": "Yes" if str(old_v) != str(new_v) else ""})
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    if not new_months and not months_to_update:
        st.info("Nothing to do — either tick a box above to update an existing month, or upload a file containing a new month.")
    else:
        action_label = []
        if new_months:
            action_label.append(f"add {len(new_months)} new month(s)")
        if months_to_update:
            action_label.append(f"update {len(months_to_update)} existing month(s)")
        if st.button(f"Confirm: {' and '.join(action_label)}", type="primary"):
            clients_df = pd.DataFrame(sb.table("dim_client").select("client_id, client_name").execute().data)
            msps_df = pd.DataFrame(sb.table("dim_msp").select("msp_id, msp_name").execute().data)

            upload_row = sb.table("upload_log").insert({
                "file_name": uploaded.name, "months_detected": detected,
                "months_imported": new_months, "months_skipped_as_duplicate": [m for m in existing_in_file if m not in months_to_update],
                "months_replaced": months_to_update, "status": "success",
            }).execute()
            upload_id = upload_row.data[0]["upload_id"]

            with st.spinner("Saving..."):
                # --- new months: company-wide ---
                for _, r in overall_new.iterrows():
                    row = {k: (None if pd.isna(v) else v) for k, v in r.to_dict().items()}
                    row["month"] = str(row["month"])
                    row["source_upload_id"] = upload_id
                    sb.table("fact_monthly_performance").insert(row).execute()

                # --- new months: client-level ---
                for _, r in client_new.iterrows():
                    row = {k: (None if pd.isna(v) else v) for k, v in r.to_dict().items()}
                    row["month"] = str(row["month"])
                    cid = clients_df.loc[clients_df.client_name == row.pop("client"), "client_id"]
                    mid = msps_df.loc[msps_df.msp_name == row.pop("msp"), "msp_id"]
                    if cid.empty or mid.empty:
                        st.error(f"Unknown client/MSP in row: {r.to_dict()} — add it in Client Master first.")
                        continue
                    row["client_id"] = int(cid.iloc[0])
                    row["msp_id"] = int(mid.iloc[0])
                    row["source_upload_id"] = upload_id
                    sb.table("fact_client_monthly_performance").insert(row).execute()

                # --- new months: recruiters ---
                if len(data["recruiters"]):
                    existing_recruiters = pd.DataFrame(sb.table("dim_recruiter").select("recruiter_id, recruiter_name").execute().data)
                    for _, r in data["recruiters"].iterrows():
                        if r["recruiter_name"] not in existing_recruiters.recruiter_name.values:
                            new_rec = sb.table("dim_recruiter").insert({
                                "recruiter_name": r["recruiter_name"], "is_pooled_bucket": bool(r["is_pooled_bucket"]),
                            }).execute()
                            existing_recruiters = pd.concat([existing_recruiters, pd.DataFrame(new_rec.data)], ignore_index=True)
                    for _, r in data["recruiters"].iterrows():
                        row = {k: (None if pd.isna(v) else v) for k, v in r.to_dict().items()}
                        row["period_start"] = str(row["period_start"])
                        row["period_end"] = str(row["period_end"])
                        rid = existing_recruiters.loc[existing_recruiters.recruiter_name == row.pop("recruiter_name"), "recruiter_id"]
                        row.pop("is_pooled_bucket", None)
                        row["recruiter_id"] = int(rid.iloc[0])
                        row["source_upload_id"] = upload_id
                        existing = sb.table("fact_recruiter_period_performance").select("fact_id").eq(
                            "period_start", row["period_start"]).eq("period_end", row["period_end"]).eq(
                            "recruiter_id", row["recruiter_id"]).execute()
                        if not existing.data:
                            sb.table("fact_recruiter_period_performance").insert(row).execute()

                # --- new months: onboarding ---
                if len(data["onboarding"]):
                    existing_onb = pd.DataFrame(sb.table("dim_onboarding_specialist").select("onboarding_id, name").execute().data)
                    for _, r in data["onboarding"].iterrows():
                        if r["specialist_name"] not in existing_onb.name.values:
                            new_onb = sb.table("dim_onboarding_specialist").insert({"name": r["specialist_name"]}).execute()
                            existing_onb = pd.concat([existing_onb, pd.DataFrame(new_onb.data)], ignore_index=True)
                    for _, r in data["onboarding"].iterrows():
                        row = {k: (None if pd.isna(v) else v) for k, v in r.to_dict().items()}
                        row["period_start"] = str(row["period_start"])
                        row["period_end"] = str(row["period_end"])
                        oid = existing_onb.loc[existing_onb.name == row.pop("specialist_name"), "onboarding_id"]
                        row["onboarding_id"] = int(oid.iloc[0])
                        row["source_upload_id"] = upload_id
                        existing = sb.table("fact_onboarding_period_performance").select("fact_id").eq(
                            "period_start", row["period_start"]).eq("period_end", row["period_end"]).eq(
                            "onboarding_id", row["onboarding_id"]).execute()
                        if not existing.data:
                            sb.table("fact_onboarding_period_performance").insert(row).execute()

                # --- existing months the user opted to update ---
                for m in months_to_update:
                    old_overall = sb.table("fact_monthly_performance").select("*").eq("month", m).execute().data
                    old_overall = old_overall[0] if old_overall else None
                    new_row = {k: (None if pd.isna(v) else v) for k, v in
                               data["overall"][data["overall"]["month"].astype(str) == m].iloc[0].to_dict().items()}
                    update_dict = {k: v for k, v in new_row.items() if k != "month"}
                    sb.table("fact_monthly_performance").update(update_dict).eq("month", m).execute()
                    sb.table("data_correction_log").insert({
                        "month": m, "table_affected": "fact_monthly_performance",
                        "old_values": old_overall, "new_values": update_dict,
                        "reason": "Updated via combined monthly upload",
                    }).execute()

                    old_client_res = sb.table("fact_client_monthly_performance").select(
                        "*, dim_client(client_name)").eq("month", m).execute().data
                    old_client_map = {r["dim_client"]["client_name"]: r for r in old_client_res if r.get("dim_client")}
                    month_client_rows = data["clientwise"][data["clientwise"]["month"].astype(str) == m]
                    for _, r in month_client_rows.iterrows():
                        row = {k: (None if pd.isna(v) else v) for k, v in r.to_dict().items()}
                        row["month"] = str(row["month"])
                        client_name = row.pop("client")
                        msp_name = row.pop("msp")
                        cid_series = clients_df.loc[clients_df.client_name == client_name, "client_id"]
                        mid_series = msps_df.loc[msps_df.msp_name == msp_name, "msp_id"]
                        if cid_series.empty:
                            st.error(f"Unknown client '{client_name}' — skipped.")
                            continue
                        cid = int(cid_series.iloc[0])
                        old_row = old_client_map.get(client_name)
                        existing_check = sb.table("fact_client_monthly_performance").select("fact_id").eq(
                            "month", m).eq("client_id", cid).execute().data
                        if existing_check:
                            sb.table("fact_client_monthly_performance").update(row).eq(
                                "month", m).eq("client_id", cid).execute()
                        else:
                            row["client_id"] = cid
                            row["msp_id"] = int(mid_series.iloc[0]) if not mid_series.empty else None
                            sb.table("fact_client_monthly_performance").insert(row).execute()
                        sb.table("data_correction_log").insert({
                            "month": m, "table_affected": "fact_client_monthly_performance",
                            "old_values": old_row, "new_values": row,
                            "reason": f"Updated via combined monthly upload ({client_name})",
                        }).execute()

            clear_caches()
            msg_parts = []
            if new_months:
                msg_parts.append(f"added {len(new_months)} new month(s): {new_months}")
            if months_to_update:
                msg_parts.append(f"updated {len(months_to_update)} month(s): {months_to_update}")
            st.success("Done — " + " and ".join(msg_parts) + ".")
            st.balloons()

st.divider()
st.subheader("Manual edit — Company-wide monthly performance")
st.caption("Add, edit, or delete rows directly here — no file needed. Useful for quick fixes, like filling in "
           "a month's revenue once it's finalized. Note: this table is separate from the per-client breakdown, "
           "so editing a number here does not change the matching client-level rows — for anything beyond a "
           "quick correction, use the file upload above instead so everything stays in sync.")

mp_rows = sb.table("fact_monthly_performance").select("*").order("month").execute().data
mp_df = pd.DataFrame(mp_rows)
if mp_df.empty:
    mp_df = pd.DataFrame(columns=["fact_id", "month", "fy_code", "new_reqs", "worked_reqs", "submissions",
                                    "interviews", "hire_preid", "hire_sourced", "start_preid", "start_sourced",
                                    "nothire_preid", "nothire_sourced", "concluded", "headcount",
                                    "revenue_inr", "revenue_usd", "is_month_closed"])

editable_cols = ["fact_id", "month", "fy_code", "new_reqs", "worked_reqs", "submissions", "interviews",
                  "hire_preid", "hire_sourced", "start_preid", "start_sourced", "nothire_preid", "nothire_sourced",
                  "concluded", "headcount", "revenue_inr", "revenue_usd", "is_month_closed"]

edited = st.data_editor(
    mp_df[editable_cols], num_rows="dynamic", use_container_width=True, key="mp_manual_editor",
    column_config={
        "fact_id": st.column_config.NumberColumn("ID", disabled=True, help="Leave blank for a new row"),
        "month": st.column_config.TextColumn("Month (YYYY-MM-01)", help="e.g. 2026-07-01"),
        "fy_code": st.column_config.TextColumn("FY", help="e.g. FY2026-27"),
        "is_month_closed": st.column_config.CheckboxColumn(
            "Revenue closed?", disabled=True,
            help="Set automatically — becomes checked as soon as both Revenue INR and Revenue USD are filled in."),
    },
)

def _normalize_for_compare(v):
    """Numbers-as-text from the database and numbers-as-numbers from the
    edit widget should compare equal if the value is the same."""
    if v is None:
        return None
    if isinstance(v, bool):
        return v
    try:
        return round(float(v), 4)
    except (TypeError, ValueError):
        return str(v).strip()

if st.button("Save changes", type="primary"):
    original_ids = set(mp_df["fact_id"].dropna().astype(int)) if "fact_id" in mp_df else set()
    edited_ids = set(edited["fact_id"].dropna().astype(int)) if "fact_id" in edited else set()
    deleted_ids = original_ids - edited_ids

    for fid in deleted_ids:
        old_row = mp_df[mp_df["fact_id"] == fid].iloc[0].to_dict()
        sb.table("fact_monthly_performance").delete().eq("fact_id", int(fid)).execute()
        sb.table("data_correction_log").insert({
            "month": old_row["month"], "table_affected": "fact_monthly_performance",
            "old_values": old_row, "new_values": None, "reason": "Manually deleted via Data Management page",
        }).execute()

    any_changes = False
    for _, row in edited.iterrows():
        row_dict = {k: (None if pd.isna(v) else v) for k, v in row.to_dict().items()}
        row_dict["is_month_closed"] = row_dict.get("revenue_inr") is not None and row_dict.get("revenue_usd") is not None
        if row_dict.get("fact_id") is None:
            if not row_dict.get("month"):
                continue
            row_dict.pop("fact_id", None)
            if not row_dict.get("fy_code"):
                row_dict["fy_code"] = "FY2026-27" if str(row_dict["month"]) >= "2026-04-01" else "FY2025-26"
            sb.table("fact_monthly_performance").insert(row_dict).execute()
            any_changes = True
        else:
            fid = int(row_dict["fact_id"])
            orig_row = mp_df[mp_df["fact_id"] == fid].iloc[0].to_dict()
            orig_clean = {k: (None if pd.isna(v) else v) for k, v in orig_row.items()}
            new_compare = {k: _normalize_for_compare(v) for k, v in row_dict.items() if k != "fact_id"}
            old_compare = {k: _normalize_for_compare(v) for k, v in orig_clean.items() if k != "fact_id"}
            if new_compare != old_compare:
                update_dict = {k: v for k, v in row_dict.items() if k != "fact_id"}
                sb.table("fact_monthly_performance").update(update_dict).eq("fact_id", fid).execute()
                sb.table("data_correction_log").insert({
                    "month": row_dict["month"], "table_affected": "fact_monthly_performance",
                    "old_values": orig_clean, "new_values": row_dict,
                    "reason": "Manually edited via Data Management page",
                }).execute()
                any_changes = True

    clear_caches()
    if any_changes or deleted_ids:
        st.success("Saved. Only the row(s) you actually changed are logged below for audit.")
    else:
        st.info("No changes detected — nothing was updated.")
    st.rerun()

st.caption("Correction history (manual edits, deletes, and file-based updates)")
corrections = sb.table("data_correction_log").select("*").order("corrected_at", desc=True).limit(20).execute().data
if corrections:
    st.dataframe(pd.DataFrame(corrections), use_container_width=True)
else:
    st.write("No manual corrections logged yet.")

st.divider()
st.subheader("Upload history")
history = sb.table("upload_log").select("*").order("uploaded_at", desc=True).execute().data
if history:
    st.dataframe(pd.DataFrame(history), use_container_width=True)
else:
    st.write("No uploads yet.")
