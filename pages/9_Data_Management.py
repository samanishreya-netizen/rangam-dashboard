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
st.caption("Upload the monthly Excel file. New months are appended automatically — existing months are never touched unless you explicitly choose to replace one.")

uploaded = st.file_uploader("Upload monthly workbook (.xlsx)", type=["xlsx"])

if uploaded:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
        tmp.write(uploaded.read())
        tmp_path = tmp.name

    with st.spinner("Validating and parsing..."):
        try:
            data = ep.parse_workbook(tmp_path)
        except Exception as e:
            st.error(f"Could not parse this file: {e}")
            st.stop()

    if data["warnings"]:
        st.warning("Validation warnings:\n" + "\n".join(f"- {w}" for w in data["warnings"]))
    else:
        st.success("Workbook structure validated — all required sheets present.")

    existing_months = months_already_in_db()
    detected = data["months_detected"]
    new_months = [m for m in detected if m not in existing_months]
    dup_months = [m for m in detected if m in existing_months]

    col1, col2 = st.columns(2)
    with col1:
        st.metric("Months detected in file", len(detected))
        st.write(detected)
    with col2:
        st.metric("Already in database (will be skipped)", len(dup_months))
        st.write(dup_months if dup_months else "None")

    if not new_months:
        st.info("No new months to import — every month in this file is already in the database. "
                "If you need to correct an existing month's data, use the 'Replace a month' section below instead.")
    else:
        st.subheader(f"Preview — {len(new_months)} new month(s) will be imported")
        overall_new = data["overall"][data["overall"]["month"].astype(str).isin(new_months)]
        st.dataframe(overall_new, use_container_width=True)

        client_new = data["clientwise"][data["clientwise"]["month"].astype(str).isin(new_months)]
        st.write(f"Client-level rows to import: {len(client_new)}")
        st.dataframe(client_new[["month", "msp", "client", "new_reqs", "submissions", "revenue_usd", "is_month_closed"]],
                     use_container_width=True)

        st.write(f"Recruiter rows to import: {len(data['recruiters'])} (period {data['recruiters']['period_start'].min() if len(data['recruiters']) else '—'} "
                 f"to {data['recruiters']['period_end'].max() if len(data['recruiters']) else '—'})")
        st.write(f"Onboarding rows to import: {len(data['onboarding'])}")

        if st.button(f"Import {len(new_months)} new month(s)", type="primary"):
            sb = get_client()
            with st.spinner("Importing..."):
                upload_row = sb.table("upload_log").insert({
                    "file_name": uploaded.name,
                    "months_detected": detected,
                    "months_imported": new_months,
                    "months_skipped_as_duplicate": dup_months,
                    "status": "success",
                }).execute()
                upload_id = upload_row.data[0]["upload_id"]

                clients_df = pd.DataFrame(sb.table("dim_client").select("client_id, client_name").execute().data)
                msps_df = pd.DataFrame(sb.table("dim_msp").select("msp_id, msp_name").execute().data)

                for _, r in overall_new.iterrows():
                    row = r.to_dict()
                    row["month"] = str(row["month"])
                    row["source_upload_id"] = upload_id
                    row = {k: (None if pd.isna(v) else v) for k, v in row.items()}
                    sb.table("fact_monthly_performance").insert(row).execute()

                for _, r in client_new.iterrows():
                    row = r.to_dict()
                    row["month"] = str(row["month"])
                    cid = clients_df.loc[clients_df.client_name == row.pop("client"), "client_id"]
                    mid = msps_df.loc[msps_df.msp_name == row.pop("msp"), "msp_id"]
                    if cid.empty or mid.empty:
                        st.error(f"Unknown client/MSP in row: {r.to_dict()} — add it in Client Master first.")
                        continue
                    row["client_id"] = int(cid.iloc[0])
                    row["msp_id"] = int(mid.iloc[0])
                    row["source_upload_id"] = upload_id
                    row = {k: (None if pd.isna(v) else v) for k, v in row.items()}
                    sb.table("fact_client_monthly_performance").insert(row).execute()

                if len(data["recruiters"]):
                    existing_recruiters = pd.DataFrame(sb.table("dim_recruiter").select("recruiter_id, recruiter_name").execute().data)
                    for _, r in data["recruiters"].iterrows():
                        if r["recruiter_name"] not in existing_recruiters.recruiter_name.values:
                            new_rec = sb.table("dim_recruiter").insert({
                                "recruiter_name": r["recruiter_name"],
                                "is_pooled_bucket": bool(r["is_pooled_bucket"]),
                            }).execute()
                            existing_recruiters = pd.concat([existing_recruiters, pd.DataFrame(new_rec.data)], ignore_index=True)
                    for _, r in data["recruiters"].iterrows():
                        row = r.to_dict()
                        row["period_start"] = str(row["period_start"])
                        row["period_end"] = str(row["period_end"])
                        rid = existing_recruiters.loc[existing_recruiters.recruiter_name == row.pop("recruiter_name"), "recruiter_id"]
                        row.pop("is_pooled_bucket", None)
                        row["recruiter_id"] = int(rid.iloc[0])
                        row["source_upload_id"] = upload_id
                        row = {k: (None if pd.isna(v) else v) for k, v in row.items()}
                        existing = sb.table("fact_recruiter_period_performance").select("fact_id").eq(
                            "period_start", row["period_start"]).eq("period_end", row["period_end"]).eq(
                            "recruiter_id", row["recruiter_id"]).execute()
                        if not existing.data:
                            sb.table("fact_recruiter_period_performance").insert(row).execute()

                if len(data["onboarding"]):
                    existing_onb = pd.DataFrame(sb.table("dim_onboarding_specialist").select("onboarding_id, name").execute().data)
                    for _, r in data["onboarding"].iterrows():
                        if r["specialist_name"] not in existing_onb.name.values:
                            new_onb = sb.table("dim_onboarding_specialist").insert({"name": r["specialist_name"]}).execute()
                            existing_onb = pd.concat([existing_onb, pd.DataFrame(new_onb.data)], ignore_index=True)
                    for _, r in data["onboarding"].iterrows():
                        row = r.to_dict()
                        row["period_start"] = str(row["period_start"])
                        row["period_end"] = str(row["period_end"])
                        oid = existing_onb.loc[existing_onb.name == row.pop("specialist_name"), "onboarding_id"]
                        row["onboarding_id"] = int(oid.iloc[0])
                        row["source_upload_id"] = upload_id
                        row = {k: (None if pd.isna(v) else v) for k, v in row.items()}
                        existing = sb.table("fact_onboarding_period_performance").select("fact_id").eq(
                            "period_start", row["period_start"]).eq("period_end", row["period_end"]).eq(
                            "onboarding_id", row["onboarding_id"]).execute()
                        if not existing.data:
                            sb.table("fact_onboarding_period_performance").insert(row).execute()

            clear_caches()
            st.success(f"Imported {len(new_months)} new month(s): {new_months}. Nothing existing was modified.")
            st.balloons()

    os.unlink(tmp_path)

st.divider()
st.subheader("Replace a month's data (correction)")
st.caption("Use this only when a past month's figures need correcting. This overwrites that month only — every other month is untouched, and the change is logged. "
           "Note: this updates company-wide and client-level monthly figures only — recruiter and onboarding data are stored per quarter, not per month, so they aren't touched by this flow.")
sb = get_client()
existing = sorted(months_already_in_db())
if existing:
    month_to_replace = st.selectbox("Month to replace", existing)
    replace_file = st.file_uploader("Corrected workbook for this month", type=["xlsx"], key="replace_upload")

    if replace_file:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
            tmp.write(replace_file.read())
            replace_tmp_path = tmp.name
        try:
            rep_data = ep.parse_workbook(replace_tmp_path)
        except Exception as e:
            st.error(f"Could not parse this file: {e}")
            rep_data = None
        finally:
            os.unlink(replace_tmp_path)

        if rep_data is not None:
            new_overall_row = rep_data["overall"][rep_data["overall"]["month"].astype(str) == month_to_replace]
            new_client_rows = rep_data["clientwise"][rep_data["clientwise"]["month"].astype(str) == month_to_replace]

            if new_overall_row.empty:
                st.error(f"This file doesn't contain data for {month_to_replace}. Upload the corrected file that "
                         f"actually includes this month.")
            else:
                old_overall_res = sb.table("fact_monthly_performance").select("*").eq("month", month_to_replace).execute().data
                old_overall = old_overall_res[0] if old_overall_res else None
                new_row_dict = {k: (None if pd.isna(v) else v) for k, v in new_overall_row.iloc[0].to_dict().items()}

                st.subheader(f"Preview — {month_to_replace}")
                st.write("**Company-wide — current vs. corrected**")
                compare_fields = ["new_reqs", "worked_reqs", "submissions", "interviews", "hire_preid", "hire_sourced",
                                   "start_preid", "start_sourced", "nothire_preid", "nothire_sourced", "concluded",
                                   "headcount", "revenue_inr", "revenue_usd"]
                compare_rows = []
                for f in compare_fields:
                    old_v = old_overall.get(f) if old_overall else None
                    new_v = new_row_dict.get(f)
                    compare_rows.append({
                        "Field": f, "Current (database)": old_v if old_v is not None else "—",
                        "Corrected (file)": new_v if new_v is not None else "—",
                        "Changes": "Yes" if str(old_v) != str(new_v) else "",
                    })
                st.dataframe(pd.DataFrame(compare_rows), use_container_width=True, hide_index=True)

                old_client_res = sb.table("fact_client_monthly_performance").select(
                    "*, dim_client(client_name)").eq("month", month_to_replace).execute().data
                old_client_map = {r["dim_client"]["client_name"]: r for r in old_client_res if r.get("dim_client")}

                if not new_client_rows.empty:
                    st.write(f"**Client-level — {len(new_client_rows)} client rows, current vs. corrected**")
                    client_compare = []
                    for _, r in new_client_rows.iterrows():
                        old_r = old_client_map.get(r["client"], {})
                        client_compare.append({
                            "Client": r["client"],
                            "New Reqs": f"{old_r.get('new_reqs', '—')} → {r['new_reqs']}",
                            "Submissions": f"{old_r.get('submissions', '—')} → {r['submissions']}",
                            "Interviews": f"{old_r.get('interviews', '—')} → {r['interviews']}",
                            "Revenue USD": f"{old_r.get('revenue_usd', '—')} → {r['revenue_usd']}",
                        })
                    st.dataframe(pd.DataFrame(client_compare), use_container_width=True, hide_index=True)

                confirm = st.checkbox(f"I've reviewed the changes above and want to overwrite {month_to_replace} with these corrected values.")
                if confirm and st.button("Confirm replacement", type="primary"):
                    update_dict = {k: v for k, v in new_row_dict.items() if k != "month"}
                    sb.table("fact_monthly_performance").update(update_dict).eq("month", month_to_replace).execute()
                    sb.table("data_correction_log").insert({
                        "month": month_to_replace, "table_affected": "fact_monthly_performance",
                        "old_values": old_overall, "new_values": update_dict,
                        "reason": "Replaced via corrected monthly file re-upload",
                    }).execute()

                    clients_df = pd.DataFrame(sb.table("dim_client").select("client_id, client_name").execute().data)
                    msps_df = pd.DataFrame(sb.table("dim_msp").select("msp_id, msp_name").execute().data)
                    for _, r in new_client_rows.iterrows():
                        row = {k: (None if pd.isna(v) else v) for k, v in r.to_dict().items()}
                        row["month"] = str(row["month"])
                        client_name = row.pop("client")
                        msp_name = row.pop("msp")
                        cid_series = clients_df.loc[clients_df.client_name == client_name, "client_id"]
                        mid_series = msps_df.loc[msps_df.msp_name == msp_name, "msp_id"]
                        if cid_series.empty:
                            st.error(f"Unknown client '{client_name}' — skipped. Add it in Client Master first.")
                            continue
                        cid = int(cid_series.iloc[0])
                        old_row = old_client_map.get(client_name)
                        existing_check = sb.table("fact_client_monthly_performance").select("fact_id").eq(
                            "month", month_to_replace).eq("client_id", cid).execute().data
                        if existing_check:
                            sb.table("fact_client_monthly_performance").update(row).eq(
                                "month", month_to_replace).eq("client_id", cid).execute()
                        else:
                            row["client_id"] = cid
                            row["msp_id"] = int(mid_series.iloc[0]) if not mid_series.empty else None
                            sb.table("fact_client_monthly_performance").insert(row).execute()
                        sb.table("data_correction_log").insert({
                            "month": month_to_replace, "table_affected": "fact_client_monthly_performance",
                            "old_values": old_row, "new_values": row,
                            "reason": f"Replaced via corrected monthly file re-upload ({client_name})",
                        }).execute()

                    clear_caches()
                    st.success(f"{month_to_replace} has been replaced with the corrected data. Every field changed is logged below.")
                    st.rerun()
else:
    st.write("No months in the database yet.")

st.divider()
st.subheader("Manual edit — Company-wide monthly performance")
st.caption("Add, edit, or delete rows directly here — no file needed. Useful for quick fixes, like filling in "
           "a month's revenue once it's finalized. Note: this table is separate from the per-client breakdown, "
           "so editing a number here does not change the matching client-level rows — for anything beyond a "
           "quick correction, use the file upload above instead so everything stays in sync.")

sb = get_client()
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

st.caption("Correction history (manual edits and deletes)")
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
