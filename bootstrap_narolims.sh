#!/usr/bin/env bash
set -euo pipefail

### --- CONFIG --- ###
APP_DIR="/home/shaykins/Projects/narolims"
VENV_DIR="${APP_DIR}/.venv"
SERVICE_NAME="narolims.service"
DOMAIN="https://narolims.reslab.dev"

ADMIN_USER="admin"
ADMIN_EMAIL="admin@example.com"
ADMIN_PASSWORD='suse10.2'   # <-- your temporary password

### --- HELPER FX --- ###
info(){ echo -e "\033[1;34m[INFO]\033[0m $*"; }
ok(){   echo -e "\033[1;32m[DONE]\033[0m $*"; }
err(){  echo -e "\033[1;31m[ERR]\033[0m $*"; }

### --- PRECHECKS --- ###
if [[ ! -d "$APP_DIR" ]]; then err "APP_DIR not found: $APP_DIR"; exit 1; fi
if [[ ! -d "$VENV_DIR" ]]; then err "VENV_DIR not found: $VENV_DIR"; exit 1; fi
if ! command -v python3 >/dev/null 2>&1; then err "python3 not found"; exit 1; fi
if ! command -v curl >/dev/null 2>&1; then err "curl not found"; exit 1; fi

### --- ACTIVATE VENV --- ###
info "Activating venv: ${VENV_DIR}"
# shellcheck source=/dev/null
source "${VENV_DIR}/bin/activate"

### --- ENSURE DEPENDENCIES (quiet) --- ###
info "Ensuring Python deps (DRF, SimpleJWT, Spectacular sidecar, django-filter)…"
python3 - <<'PY'
import importlib, sys
missing = []
for pkg in ["rest_framework","rest_framework_simplejwt","drf_spectacular","drf_spectacular_sidecar","django_filters"]:
    try:
        importlib.import_module(pkg.replace("-", "_"))
    except Exception:
        missing.append(pkg)
if missing:
    print(" ".join(missing))
else:
    print("")
PY
NEED=$(python3 - <<'PY'
import importlib, sys
missing = []
for pkg in ["djangorestframework","djangorestframework-simplejwt","drf-spectacular[sidecar]","django-filter"]:
    try:
        importlib.import_module(pkg.split("[")[0].replace("-", "_"))
    except Exception:
        missing.append(pkg)
print(" ".join(missing))
PY
)
if [[ -n "${NEED}" ]]; then
  info "Installing: ${NEED}"
  pip install -qU ${NEED}
else
  ok "Python deps already present"
fi

### --- MIGRATIONS --- ###
cd "${APP_DIR}"
info "Applying migrations…"
python manage.py migrate --noinput
ok "Migrations applied"

### --- CREATE/UPDATE SUPERUSER --- ###
info "Ensuring superuser '${ADMIN_USER}' exists (and setting password)…"
python manage.py shell <<PY
from django.contrib.auth import get_user_model
User = get_user_model()
u, created = User.objects.get_or_create(username="${ADMIN_USER}", defaults={"email":"${ADMIN_EMAIL}"})
u.is_superuser = True
u.is_staff = True
u.set_password("${ADMIN_PASSWORD}")
u.save()
print("created" if created else "updated")
PY
ok "Superuser ensured"

deactivate

### --- RESTART SERVICE --- ###
info "Restarting systemd service: ${SERVICE_NAME}"
sudo systemctl restart "${SERVICE_NAME}"
sudo systemctl status "${SERVICE_NAME}" --no-pager -l || true
ok "Service restarted"

### --- GET TOKENS --- ###
info "Fetching JWT tokens for ${ADMIN_USER}…"
TOKEN_JSON=$(curl -sS "${DOMAIN}/api/token/" \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"${ADMIN_USER}\",\"password\":\"${ADMIN_PASSWORD}\"}")

# Pretty print response for visibility
echo "${TOKEN_JSON}" | python3 -m json.tool || true

ACCESS_TOKEN=$(echo "${TOKEN_JSON}" | python3 -c 'import sys,json; d=json.load(sys.stdin); print(d.get("access",""))')
REFRESH_TOKEN=$(echo "${TOKEN_JSON}" | python3 -c 'import sys,json; d=json.load(sys.stdin); print(d.get("refresh",""))')

if [[ -z "${ACCESS_TOKEN}" ]]; then
  err "Could not obtain access token. Check credentials and server logs."
  exit 1
fi
ok "Access token acquired"

### --- SMOKE TESTS --- ###
info "Health check (public)…"
curl -sS "${DOMAIN}/lims/health/" | python3 -m json.tool || true

info "List projects (authorized)…"
curl -sS "${DOMAIN}/lims/projects/" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" | python3 -m json.tool || true

info "Create a sample project (authorized)…"
CREATE_PAYLOAD='{"name":"Banana Genotyping 2025","description":"Pilot project for LIMS"}'
curl -sS -X POST "${DOMAIN}/lims/projects/" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d "${CREATE_PAYLOAD}" | python3 -m json.tool || true

info "List projects again…"
curl -sS "${DOMAIN}/lims/projects/" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" | python3 -m json.tool || true

cat <<EOF

============================================================
DONE ✅

Useful values:
- DOMAIN:             ${DOMAIN}
- ADMIN_USER:         ${ADMIN_USER}
- ADMIN_PASSWORD:     (as set in this script)

Your access token is exported in shell variables ONLY within this script run.
To request a fresh access token later:

curl -s ${DOMAIN}/api/token/ \\
  -H "Content-Type: application/json" \\
  -d '{"username":"${ADMIN_USER}","password":"${ADMIN_PASSWORD}"}'

To use it:
curl -s ${DOMAIN}/lims/projects/ \\
  -H "Authorization: Bearer <ACCESS_TOKEN>"

To refresh:
curl -s ${DOMAIN}/api/token/refresh/ \\
  -H "Content-Type: application/json" \\
  -d '{"refresh":"<REFRESH_TOKEN>"}'
============================================================
EOF
