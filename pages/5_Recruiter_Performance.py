import streamlit as st
import pandas as pd
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from db import get_recruiter_performance, get_benchmarks, evaluate_benchmark

st.set_page_config(page_title="Recruiter Performance", layout="wide")
st.title("Recruiter Performance")

FY = st.selectbox("Financial Year", ["FY2026-27", "FY2025-26"])
rp = get_recruiter_performance(FY)
if rp.empty:
    st.info("No data yet for this Financial Year.")
    st.stop()

active_all = rp.copy()
pooled = rp[rp["is_pooled_bucket"]]

recruiter_filter = st.selectbox("Recruiter", ["All"] + sorted(active_all["recruiter_name"].dropna().unique().tolist()))
active = active_all if recruiter_filter == "All" else active_all[active_all["recruiter_name"] == recruiter_filter]

st.subheader("Summary — based on filter above")
new_reqs_sum = active["new_reqs"].fillna(0).sum()
submissions_sum = active["submissions"].fillna(0).sum()
interviews_sum = active["interviews"].fillna(0).sum()
hires_sum = active["hires"].fillna(0).sum()
starts_sum = active["starts"].fillna(0).sum()
not_hires_sum = active["not_hires"].fillna(0).sum()

c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("New Reqs", int(new_reqs_sum))
c2.metric("Submissions", int(submissions_sum))
c3.metric("Interviews", int(interviews_sum))
c4.metric("Hires", int(hires_sum))
c5.metric("Starts", int(starts_sum))
c6.metric("Not Hires", int(not_hires_sum))

submission_per_req = (submissions_sum / new_reqs_sum) if new_reqs_sum else None
sub_to_int = (interviews_sum / submissions_sum) if submissions_sum else None
int_to_hire = (hires_sum / interviews_sum) if interviews_sum else None
hire_to_start = (starts_sum / hires_sum) if hires_sum else None
close_rate = (starts_sum / new_reqs_sum) if new_reqs_sum else None
back_out = (not_hires_sum / hires_sum) if hires_sum else None

benchmarks = get_benchmarks(FY, "recruiter")
status_colors = {"Meeting": "#2E7D6B", "Not Meeting": "#F27538", "No live data": "#848688", "No target set": "#848688"}

def _ratio_card(col, label, key, value, is_percent=True):
    with col:
        display_val = f"{value*100:.2f}%" if (value is not None and is_percent) else (f"{value:.2f}" if value is not None else "—")
        st.metric(label, display_val)
        benchmark = benchmarks.get(key)
        actual = (value * 100) if (value is not None and is_percent) else value
        status, target_str = evaluate_benchmark(actual, benchmark)
        color = status_colors[status]
        target_line = f"Target: {target_str}" if target_str else "No target set"
        st.markdown(f"<span style='color:{color}; font-weight:600; font-size:13px;'>{status}</span>"
                    f"<br><span style='color:#848688; font-size:12px;'>{target_line}</span>", unsafe_allow_html=True)

r1, r2, r3, r4, r5 = st.columns(5)
_ratio_card(r1, "Submission Per Req", "submission per req", submission_per_req, is_percent=False)
_ratio_card(r2, "Submission-to-Interview", "submission to interview", sub_to_int)
_ratio_card(r3, "Interview-to-Hire", "interview to hire", int_to_hire)
_ratio_card(r4, "Close Rate", "close rate", close_rate)
_ratio_card(r5, "Back Out", "back out", back_out)

active["submissions_per_req"] = (active["submissions"] / active["new_reqs"]).round(2)
active["sub_to_int"] = (active["interviews"] / active["submissions"]).round(3)
active["int_to_hire"] = (active["hires"] / active["interviews"]).round(3)
active["close_rate"] = (active["starts"] / active["new_reqs"]).round(3)
active["bad_delivery"] = (active["not_hires"] / active["hires"].replace(0, pd.NA)).round(3)

st.divider()
st.subheader("Recruiter detail")
active_detail = active[~active["is_pooled_bucket"]]
st.dataframe(active_detail[["recruiter_name", "new_reqs", "worked_reqs", "submissions", "interviews", "hires",
                      "starts", "not_hires", "submissions_per_req", "sub_to_int", "int_to_hire",
                      "close_rate", "bad_delivery"]], use_container_width=True)

st.subheader("Pre-ID / Left Recruiters (reconciliation buckets, not scored)")
st.dataframe(pooled[["recruiter_name", "new_reqs", "worked_reqs", "submissions", "interviews", "hires", "starts", "not_hires"]],
             use_container_width=True)

st.caption(f"Reconciliation: recruiter-table total hires = {int(rp['hires'].sum())} "
           f"(should match Overall Performance total hires for the same period).")
