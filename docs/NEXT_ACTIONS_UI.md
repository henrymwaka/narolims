# NEXT_ACTIONS_UI.md

## Purpose
This file is the operational checklist for completing the NARO-LIMS UI landing experience, session authentication UX, and routing cleanup without reintroducing 500 errors or confusing navigation.

## Target UX (final state)
### Public side
- Public landing page: `/` (or `/lims/` depending on your project root)
- Landing template: `lims_core/templates/lims_core/landing.html`
- Primary actions:
  - Login
  - View system modules (read-only descriptions)
  - Contact or support link (optional)

### Authenticated workspace
- Workspace home: `/lims/ui/`
- Workspace pages:
  - Samples: `/lims/ui/samples/`
  - Workflow demo: `/lims/ui/workflow-demo/`
  - Stats API: `/lims/ui/stats/`
  - Logout: `/lims/ui/logout/`

## Rules to prevent regressions
1. Never do database queries inside the initial render of `home()` or `landing()`.
   - Any dynamic counts or lists must come from JSON endpoints like `/lims/ui/stats/`.
2. Logout must appear only once in the UI.
   - The only global logout button should be in `base.html`.
3. Any page that requires authentication must use `@login_required`.
4. Public landing must not require authentication.
5. Always restart Gunicorn after template or view changes in production, then verify key URLs.

## Work plan (do these in order)

### Step 1: Create the public landing page
**Files**
- `lims_core/templates/lims_core/landing.html`
- `lims_core/views_ui.py` add `landing(request)` (no login_required)

**Requirements**
- Must load for anonymous users
- Must explain what NARO-LIMS is in plain, professional language
- Must show module tiles (Samples, Workflows, Experiments, Inventory, Reports)
- Must have a clear Login button

**Suggested buttons**
- Login: `/api/auth/login/?next=/lims/ui/`
- Go to workspace (optional for logged-in users): `/lims/ui/`

### Step 2: Wire landing page into URL routing
**Where**
- Prefer project-level `urls.py` to map `/` to landing.
- If you cannot touch project-level routing yet, expose:
  - `/lims/landing/` or `/lims/ui/landing/` as an interim path.

**Acceptance checks**
- Anonymous user can open landing without redirect loops
- Auth user can still open `/lims/ui/`

### Step 3: Make `/lims/ui/` a real workspace home
**Where**
- `lims_core/views_ui.py` `home()` stays protected with `@login_required`
- `lims_core/templates/lims_core/home.html` becomes the operational dashboard

**What home must contain**
- Quick actions: browse samples, bulk status update, workflow demo
- KPI tiles (populated via `/lims/ui/stats/`)
- Recent activity and open alerts (populated via `/lims/ui/stats/`)
- Lab context hint (active lab id if available)

### Step 4: Fix logout correctly and remove duplicates
**Goal**
- A single logout button in `base.html`
- Logout should not return 405

**Implementation**
- Keep `ui_logout(request)` as GET-safe:
  - calls `auth_logout(request)`
  - redirects to `next` parameter or landing

**Recommended redirect**
- `/lims/ui/logout/?next=/` (or `/lims/landing/` if you keep landing there)

**Cleanup**
- Remove any additional Logout buttons from `home.html` and other templates.

### Step 5: Clean up navigation to look like a real system
**In `base.html`**
Show:
- Home
- Samples
- Workflows (optional placeholder for now)
- Experiments (optional placeholder for now)
- Inventory (optional placeholder for now)
- Reports (optional placeholder for now)
- API Docs
- System Health
- Admin only if staff/superuser
- Login/Logout depending on auth status

### Step 6: Verification routine after each change
Run these every time:
1. Django sanity:
   - `python manage.py check`
2. Restart service:
   - `sudo systemctl restart narolims`
3. Confirm key endpoints:
   - `/` (landing)
   - `/lims/ui/` (workspace home)
   - `/lims/ui/stats/` (must never 500)
   - `/lims/ui/samples/`
   - `/lims/ui/logout/?next=/` (must log out and redirect)
4. Logs if anything breaks:
   - `sudo journalctl -u narolims -n 200 --no-pager -l`

## Definition of done (this phase)
- Public landing exists and looks intentional.
- Workspace home exists and feels like a LIMS dashboard.
- Logout works and appears once.
- Home never returns 500.
- Stats endpoint never returns 500.

## Notes and decisions
- Landing path chosen: ________________________
- Workspace path chosen: `/lims/ui/`
- Post-logout redirect: ________________________
- Owner: ________________________
- Date: ________________________
# Next Actions: NARO LIMS UI

## Objective
Move from functional internal pages to a product-grade LIMS experience with a consistent wide layout and a clear separation of public pages vs authenticated workspace UI.

## Immediate priorities (today)
1. Validate routing
   - Confirm `/lims/` loads landing page
   - Confirm `/lims/features/`, `/lims/updates/`, `/lims/docs/` load without authentication
   - Confirm `/lims/ui/` requires login and loads workspace
2. Confirm logout flow
   - `/lims/ui/logout/?next=/lims/` logs out and returns to landing
   - No 405 responses
   - Logout appears once in topbar
3. Confirm nav integrity
   - Landing menu works
   - Workspace menu works
   - Admin button shown only for staff

## Short term UI upgrades (next 48 hours)
1. Replace inline CSS blocks in templates with a shared CSS file
   - Create `lims_core/static/lims_core/css/public.css` for public pages
   - Create `lims_core/static/lims_core/css/app.css` for workspace UI
2. Add “Updates” parsing
   - Convert markdown sections into styled HTML blocks (optional)
   - Add “Latest changes” snippet on landing page
3. Add a “System status widget” to landing
   - Fetch `/lims/health/` and display status badge
4. Add “Feature availability status”
   - Active, Beta, Admin-first, Next
   - Keep in a single feature registry dict to avoid template drift

## Medium term (wide layout like omics.reslab.dev)
1. Create a layout contract
   - Fixed max width for content sections
   - Wide hero, readable typography
   - Consistent card and grid spacing
2. Split base templates explicitly
   - Keep `base_public.html` as public theme
   - Keep `base.html` as workspace theme
3. Build a workspace home that feels like a control room
   - Lab selection drop-down (if multiple labs)
   - KPI panels
   - Recent events and alerts feed
   - Quick actions aligned to real lab tasks

## Risks and checks
- Avoid DB queries in public views to prevent accidental 500s during migrations or first-run states.
- Avoid hardcoding DRF logout links; keep logout routed through `/lims/ui/logout/`.
- Keep navigation paths canonical and consistent to prevent duplicate menu entries.
