import streamlit as st

st.set_page_config(
    page_title="Rangam Staffing BI Dashboard",
    page_icon="🔥",
    layout="wide",
)

st.markdown("""
<style>
    [data-testid="stSidebar"] { background-color: #28425B; }
    [data-testid="stSidebar"] * { color: #F4F5F7 !important; }
    .rangam-header {
        background: #28425B; padding: 14px 20px; border-radius: 10px;
        display:flex; align-items:center; gap:12px; margin-bottom: 18px;
    }
    .rangam-header h1 { color: white; font-size: 20px; margin: 0; font-weight: 500; }
    .rangam-header span { color: #c7d0da; font-size: 13px; }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="rangam-header">
    <div>
        <h1>Rangam Infotech &middot; Domestic Staffing BI Dashboard</h1>
        <span>Empathy Drives Innovation</span>
    </div>
</div>
""", unsafe_allow_html=True)

st.markdown("""
Use the pages in the sidebar to navigate:

- **Executive Overview** — top-line KPIs for CXO review
- **Business Performance** — funnel trends over time
- **Revenue Performance** — revenue vs. target, projections
- **Client & MSP Performance** — drill-down by client/MSP
- **Recruiter Performance** — productivity/quality matrix
- **Recruitment Funnel** — stage-by-stage conversion
- **Onboarding Performance** — onboarding team KPIs
- **Target & Benchmark Admin** — set FY targets (admin)
- **Data Management** — upload monthly files (admin)
- **CXO Insights** — auto-generated commentary

Data is live from Supabase and updates immediately after each monthly upload.
""")

try:
    from db import get_monthly_performance
    mp = get_monthly_performance()
    if len(mp):
        months = sorted(mp["month"].unique())
        st.success(f"Connected. Data available for {len(months)} month(s): {months[0]} to {months[-1]}")
    else:
        st.warning("Connected to the database, but no monthly data found yet. Use Data Management to upload a file.")
except Exception as e:
    st.error(f"Could not connect to the database. Check .streamlit/secrets.toml. ({e})")
