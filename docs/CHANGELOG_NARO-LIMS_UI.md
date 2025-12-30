## Next actions checklist (UI landing + auth + routing)

**Objective:** deliver a clean public landing page, and a separate authenticated workspace home, with correct logout behavior and zero 500s.

### 1) Decide the URL contract (recommended)
- **Public landing:** `/` (or `/lims/` if your project root is shared)
- **Authenticated workspace home:** `/lims/ui/`
- **Operational modules:** remain under `/lims/ui/samples/`, `/lims/ui/workflow-demo/`, etc.
- **Logout endpoint:** `/lims/ui/logout/` (GET-safe)

**Why this helps**
- Users can understand the system before login.
- The workspace becomes consistent and protected.
- You avoid mixing DRF browsable auth UX with your UI.

### 2) Implement a true landing page (public, no login required)
**Deliverables**
- `lims_core/templates/lims_core/landing.html` (public marketing-style landing page)
- `lims_core/views_ui.py` add a view like `landing(request)` (no `@login_required`)
- `lims_core/urls.py` add a route like:
  - `path("landing/", landing, name="ui-landing")` under the UI section
  - or map project root to landing in the project-level `urls.py` if preferred

**Acceptance criteria**
- Loads for anonymous users.
- Has a clear “Login” button.
- Has a short system description, capabilities, and module tiles.
- Does not touch DB (no risk of 500).

### 3) Make `/lims/ui/` the authenticated workspace home (not a “demo”)
**Deliverables**
- Keep `home()` as the authenticated workspace page.
- Ensure `base.html` brand link points to `/lims/ui/` (workspace home).
- Ensure `home.html` focuses on operations:
  - quick actions
  - stats (via `/lims/ui/stats/`)
  - module shortcuts

**Acceptance criteria**
- No duplicate logout buttons.
- Looks like a system workspace, not a sample list.
- Page loads without DB queries that can crash initial render.

### 4) Fix logout cleanly (one place only)
**Rules**
- Logout link should exist in **one place only**: `base.html` userbox.
- Remove any additional logout links from `home.html` or other pages unless special case.

**Recommended behavior**
- `base.html` uses: `/lims/ui/logout/?next=/lims/landing/` (or `/`)

**Acceptance criteria**
- Logout works via a normal anchor click (no 405).
- After logout, user lands on public landing page.
- No duplicate “logout” in the header.

### 5) Eliminate the remaining 500 cause (if any)
**Checklist**
- Confirm homepage template does not reference missing context keys.
- Confirm `home()` does not query models.
- Confirm `ui_stats()` handles missing optional models safely (already defensive).

**Debug command**
- `sudo journalctl -u narolims -n 200 --no-pager -l | tail -n 80`
Look for the Python traceback lines around the GET `/lims/ui/` request.

**Acceptance criteria**
- `/lims/ui/` returns 200 consistently.
- `/lims/ui/stats/` always returns JSON with `ok: true|false` but never 500.

### 6) Polish the nav for a real system feel
**Add (recommended)**
- “Home” (workspace)
- “Samples”
- “Workflows”
- “Experiments”
- “Inventory”
- “Reports”
- “API Docs”
- “System Health”
- “Admin” (only for staff/superusers)

**Acceptance criteria**
- A normal user sees only what they need.
- Admin-only links do not clutter non-admin UX.

### 7) Small ops rule to keep it stable
- Any time you add a UI page, add:
  - route in `lims_core/urls.py`
  - template under `lims_core/templates/lims_core/...`
  - keep DB calls out of initial render; use JSON endpoints where possible
- After changes:
  - `python manage.py check`
  - `python manage.py test` (or at least run targeted tests)
  - `sudo systemctl restart narolims`
  - verify: `/lims/ui/`, `/lims/ui/samples/`, `/lims/ui/logout/`

---
### Minimal “done” definition for this phase
- A public landing exists and looks intentional.
- Authenticated workspace home exists and looks like a LIMS dashboard.
- Logout works, once, and never 405.
- Home never 500s.

# Next Actions: NARO-LIMS UI

## Current UI Entry Points
- Public landing: `/lims/`
- Workspace dashboard: `/lims/ui/`
- Samples UI: `/lims/ui/samples/`
- Workflow demo: `/lims/ui/workflow-demo/`
- Stats endpoint: `/lims/ui/stats/`
- Logout: `/lims/ui/logout/`

## Immediate Next Steps (UI)
1. Convert landing page to wide-layout mode (Omics-style)
   - Full-width hero band
   - Multi-column feature blocks
   - Screenshots or diagram placeholder section
   - Clear “Enter workspace” CTA with role-based messaging

2. Workspace usability upgrades
   - Add lab switcher on the workspace home (if user has multiple labs)
   - Show “active lab” selector that reloads `/lims/ui/stats/?lab=<id>`
   - Add recent samples list with deep links to sample detail pages

3. Navigation cleanup
   - Add “Experiments” link once list view exists
   - Add “Inventory” link once UI exists
   - Add “Reports” link once stub view exists

4. UI consistency and layout framework
   - Move inline styles into a shared CSS file (or a dedicated UI stylesheet)
   - Adopt a consistent card system and spacing scale across pages

5. Expand module coverage
   - Experiments list page (`/lims/ui/experiments/`) and detail linking
   - Inventory list page (read-only first, then stock movements)
   - Alerts page (even if alerts model is optional)

6. Hardening
   - Ensure every UI view is login-protected (except `/lims/`)
   - Ensure stats endpoint never 500 even during schema changes
   - Add a simple 404/500 friendly template later

## Verification Checklist After Each UI Change
- `/lims/` loads for anonymous users
- `/lims/` redirects to `/lims/ui/` for authenticated users
- `/lims/ui/` requires login
- Logout works and returns to `/lims/` without 405
- Samples UI still loads and workflow JS still loads


## 2025-12-27

### Added
- Public landing section under `/lims/` with top menu: Features, Updates, Docs, System Status.
- Feature pages:
  - `/lims/features/` (feature overview)
  - `/lims/features/<slug>/` (module detail pages)
- Updates page `/lims/updates/` that renders `docs/CHANGELOG_NARO-LIMS_UI.md`.
- Docs hub `/lims/docs/` with links to API docs, health, identity, and workspace.

### Fixed
- Logout 405: replaced DRF logout usage with GET-safe UI logout at `/lims/ui/logout/`.
- Duplicate logout buttons: standardized logout to appear once in the authenticated topbar.

### Changed
- Navigation now separates public landing pages from authenticated workspace pages.
- UI base template menu now includes Landing, Workspace, Features, Updates, Docs.
