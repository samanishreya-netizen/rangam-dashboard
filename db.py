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


def clear_caches():
    get_monthly_performance.clear()
    get_client_monthly_performance.clear()
    get_recruiter_performance.clear()
    get_onboarding_performance.clear()
    get_business_target.clear()
    get_dim.clear()


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
