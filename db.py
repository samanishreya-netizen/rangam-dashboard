"""
Shared Supabase connection + query helpers for the Rangam Staffing BI Dashboard.
Uses the service_role key (server-side only) since RLS is enabled with no
policies — this is the only key that can read/write.
"""

import streamlit as st
import pandas as pd
from supabase import create_client


@st.cache_resource
def get_client():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_SERVICE_ROLE_KEY"]
    return create_client(url, key)


def clean_row(d):
    """Converts a dict (typically from a pandas row.to_dict()) into plain
    Python types before sending to Supabase. Pandas/numpy scalar types
    (numpy.float64, numpy.int64, etc.) can otherwise get serialized as
    strings like "2.0" instead of numbers, which Postgres then rejects
    for integer columns with 'invalid input syntax for type integer'.
    NaN/NaT/None all become None."""
    out = {}
    for k, v in d.items():
        try:
            is_na = pd.isna(v)
        except (TypeError, ValueError):
            is_na = False
        if is_na:
            out[k] = None
        elif hasattr(v, "item"):
            out[k] = v.item()
        else:
            out[k] = v
    return out


def df(table, select="*", **filters):
    """Fetch a table (with optional eq filters) as a DataFrame."""
    sb = get_client()
    q = sb.table(table).select(select)
    for k, v in filters.items():
        q = q.eq(k, v)
    res = q.execute()
    return pd.DataFrame(res.data)


@st.cache_data(ttl=60)
def get_monthly_performance(fy_code=None):
    sb = get_client()
    q = sb.table("fact_monthly_performance").select("*").order("month")
    if fy_code:
        q = q.eq("fy_code", fy_code)
    return pd.DataFrame(q.execute().data)


@st.cache_data(ttl=60)
def get_client_monthly_performance(fy_code=None):
    sb = get_client()
    q = sb.table("fact_client_monthly_performance").select(
        "*, dim_client(client_name), dim_msp(msp_name)"
    ).order("month")
    if fy_code:
        q = q.eq("fy_code", fy_code)
    data = q.execute().data
    rows = []
    for r in data:
        r = dict(r)
        r["client_name"] = (r.pop("dim_client") or {}).get("client_name")
        r["msp_name"] = (r.pop("dim_msp") or {}).get("msp_name")
        rows.append(r)
    return pd.DataFrame(rows)


@st.cache_data(ttl=60)
def get_recruiter_performance(fy_code=None):
    sb = get_client()
    q = sb.table("fact_recruiter_period_performance").select(
        "*, dim_recruiter(recruiter_name, is_pooled_bucket)"
    ).order("period_start")
    if fy_code:
        q = q.eq("fy_code", fy_code)
    data = q.execute().data
    rows = []
    for r in data:
        r = dict(r)
        rec = r.pop("dim_recruiter") or {}
        r["recruiter_name"] = rec.get("recruiter_name")
        r["is_pooled_bucket"] = rec.get("is_pooled_bucket")
        rows.append(r)
    return pd.DataFrame(rows)


@st.cache_data(ttl=60)
def get_onboarding_performance(fy_code=None):
    sb = get_client()
    q = sb.table("fact_onboarding_period_performance").select(
        "*, dim_onboarding_specialist(name)"
    ).order("period_start")
    if fy_code:
        q = q.eq("fy_code", fy_code)
    data = q.execute().data
    rows = []
    for r in data:
        r = dict(r)
        r["specialist_name"] = (r.pop("dim_onboarding_specialist") or {}).get("name")
        rows.append(r)
    return pd.DataFrame(rows)


@st.cache_data(ttl=60)
def get_business_target(fy_code):
    sb = get_client()
    res = sb.table("config_business_target").select("*").eq("fy_code", fy_code).eq("is_active", True).execute()
    return res.data[0] if res.data else None


@st.cache_data(ttl=300)
def get_dim(table):
    sb = get_client()
    return pd.DataFrame(sb.table(table).select("*").execute().data)


@st.cache_data(ttl=60)
def get_benchmarks(fy_code, level):
    """Returns {kpi_name_lowercase: benchmark_row} for the given FY and level."""
    sb = get_client()
    res = sb.table("config_kpi_benchmark").select("*").eq("fy_code", fy_code).eq(
        "applies_to_level", level).eq("is_active", True).execute()
    return {b["kpi_name"].strip().lower(): b for b in res.data}


def evaluate_benchmark(actual, benchmark):
    """Returns (status, target_display_string). status is one of:
    'Meeting', 'Not Meeting', 'No live data', 'No target set'."""
    if benchmark is None:
        return "No target set", None
    unit = benchmark.get("unit") or ""
    ct = benchmark.get("comparison_type")
    if ct == "between":
        target_str = f"{benchmark['min_value']}–{benchmark['max_value']}{unit}"
    else:
        target_str = f"{ct} {benchmark['target_value']}{unit}"
    if actual is None:
        return "No live data", target_str
    if ct == ">=":
        met = actual >= benchmark["target_value"]
    elif ct == "<=":
        met = actual <= benchmark["target_value"]
    elif ct == "between":
        met = (benchmark["min_value"] or 0) <= actual <= (benchmark["max_value"] or 1e12)
    else:
        return "No target set", target_str
    return ("Meeting" if met else "Not Meeting"), target_str


def clear_caches():
    get_monthly_performance.clear()
    get_client_monthly_performance.clear()
    get_recruiter_performance.clear()
    get_onboarding_performance.clear()
    get_business_target.clear()
    get_dim.clear()
    get_benchmarks.clear()


def months_already_in_db():
    sb = get_client()
    res = sb.table("fact_monthly_performance").select("month").execute()
    return {r["month"] for r in res.data}


def is_admin():
    return st.session_state.get("is_admin", False)


def require_admin_gate():
    """Call at the top of admin-only pages. Renders a password box and
    stops the page until the correct password is entered."""
    if is_admin():
        return True
    st.info("This page is admin-only.")
    pw = st.text_input("Admin password", type="password")
    if st.button("Unlock"):
        if pw == st.secrets.get("ADMIN_PASSWORD"):
            st.session_state["is_admin"] = True
            st.rerun()
        else:
            st.error("Incorrect password.")
    st.stop()
