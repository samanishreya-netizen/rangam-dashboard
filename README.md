# Rangam Staffing BI Dashboard

## What's in this folder
- `app.py` — main entry point / landing page
- `db.py` — Supabase connection + query helpers (shared by all pages)
- `etl_parser.py` — parses the monthly Excel template (tested against real data)
- `pages/` — all 10 dashboard pages
- `.streamlit/config.toml` — Rangam-branded theme (already set, no action needed)
- `.streamlit/secrets.toml.example` — copy this, fill in real values (see below)

The database is **already live** — schema deployed, June 2026 data loaded,
FY2026-27 target (₹20 Cr) configured. This package is the application layer
that connects to it.

## One-time setup (15 minutes)

### 1. Get your Supabase service_role key
1. Go to https://supabase.com/dashboard/project/cldeynpwcejvbmmkckgt/settings/api
2. Log in with `shreya@rangam.com`
3. Under "Project API keys," copy the **`service_role`** key (NOT `anon`/`publishable` —
   RLS is enabled with no policies on every table, so only `service_role` can
   read or write). Keep this secret; never share it or commit it to a public repo.

### 2. Push this folder to a GitHub repo
- Create a new repo (can be private) and push everything in this folder to it.

### 3. Deploy on Streamlit Community Cloud (free)
1. Go to https://share.streamlit.io and sign in (GitHub login works)
2. "New app" → pick your repo → main file path: `app.py`
3. Before it launches, open **Advanced settings → Secrets** and paste:
   ```
   SUPABASE_URL = "https://cldeynpwcejvbmmkckgt.supabase.co"
   SUPABASE_SERVICE_ROLE_KEY = "paste-the-service_role-key-from-step-1"
   ADMIN_PASSWORD = "pick-something-only-you-know"
   ```
4. Deploy. You'll get a URL like `https://rangam-staffing-bi.streamlit.app` —
   that's your live dashboard link.

### 4. Monthly workflow going forward
1. Open the app link
2. Go to **Data Management** in the sidebar, enter the admin password
3. Upload that month's Excel file (same template every time)
4. Review the preview (new months vs. already-imported months)
5. Click Import — done. Nothing existing is ever touched.

## What's fully built vs. what's a starting point
- **Fully working**: all 10 pages querying live data, Executive Overview,
  Revenue Performance, Business Performance, Client/MSP drill-down,
  Recruiter productivity/quality matrix, Recruitment Funnel, Onboarding,
  Target admin with version history, CXO auto-insights, and the core
  upload → validate → preview → append-only import flow.
- **Stubbed and needs finishing**: the "Replace a month's data" correction
  flow in Data Management currently shows a preview placeholder rather than
  a full old-vs-new diff and confirmed overwrite. This is the one piece
  I'd recommend finishing next, once you've used the normal import flow
  for a month or two.

## Local testing (optional, before deploying)
```bash
cd rangam_dashboard
pip install -r requirements.txt
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# edit .streamlit/secrets.toml with your real service_role key
streamlit run app.py
```
