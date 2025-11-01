#!/bin/bash
# ===============================================================
# NaroLIMS Diagnostic Script
# Author: Henry Mwaka
# Location: /home/shaykins/Projects/narolims/
# ===============================================================

PROJECT_ROOT="/home/shaykins/Projects/narolims"
SOCKET_PATH="/run/gunicorn/narolims.sock"
SERVICE_NAME="narolims.service"
DOMAIN="narolims.reslab.dev"

# --- Color codes ---
RED="\033[0;31m"
GREEN="\033[0;32m"
YELLOW="\033[1;33m"
NC="\033[0m" # No Color

echo -e "\n============================="
echo -e "🔍 NaroLIMS Diagnostic Report"
echo -e "=============================\n"

# 1️⃣ Check Gunicorn Service
echo -e "1️⃣ Checking Gunicorn service..."
if systemctl is-active --quiet $SERVICE_NAME; then
    echo -e "✅ ${GREEN}Gunicorn is running${NC}"
else
    echo -e "❌ ${RED}Gunicorn is NOT running${NC}"
    echo -e "   Try: sudo systemctl restart $SERVICE_NAME"
fi
echo ""

# 2️⃣ Check Gunicorn socket
echo -e "2️⃣ Checking Gunicorn socket..."
if [ -S "$SOCKET_PATH" ]; then
    echo -e "✅ ${GREEN}Socket exists:${NC} $SOCKET_PATH"
    ls -l "$SOCKET_PATH"
else
    echo -e "❌ ${RED}Socket missing:${NC} $SOCKET_PATH"
    echo -e "   Check your ExecStart in /etc/systemd/system/$SERVICE_NAME"
fi
echo ""

# 3️⃣ Nginx Configuration
echo -e "3️⃣ Testing Nginx configuration..."
if sudo nginx -t 2>&1 | grep -q "successful"; then
    echo -e "✅ ${GREEN}Nginx configuration is valid${NC}"
else
    echo -e "❌ ${RED}Nginx configuration errors found${NC}"
fi
echo ""

# 4️⃣ Nginx service
echo -e "4️⃣ Checking Nginx service..."
if systemctl is-active --quiet nginx; then
    echo -e "✅ ${GREEN}Nginx is running${NC}"
else
    echo -e "❌ ${RED}Nginx is NOT running${NC}"
fi
echo ""

# 5️⃣ File permissions
echo -e "5️⃣ Checking file and directory permissions..."
if [ -d "$PROJECT_ROOT" ]; then
    OWNER=$(stat -c "%U:%G" "$PROJECT_ROOT")
    echo -e "📁 Project owner: ${YELLOW}$OWNER${NC}"
    echo "   Reset (if wrong): sudo chown -R shaykins:www-data $PROJECT_ROOT"
else
    echo -e "❌ ${RED}Project folder not found${NC}: $PROJECT_ROOT"
fi
echo ""

# 6️⃣ SSL certificates
echo -e "6️⃣ Checking SSL certificates..."
if [ -f "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" ]; then
    echo -e "✅ ${GREEN}SSL certificate found${NC}"
else
    echo -e "❌ ${RED}SSL certificate missing${NC}"
    echo "   Try: sudo certbot certonly --nginx -d $DOMAIN"
fi
echo ""

# 7️⃣ Django health check
echo -e "7️⃣ Checking Django integrity..."
cd "$PROJECT_ROOT" || exit
source venv/bin/activate
if python manage.py check > /dev/null 2>&1; then
    echo -e "✅ ${GREEN}Django project passes system checks${NC}"
else
    echo -e "❌ ${RED}Django check failed${NC}"
fi
deactivate
echo ""

# 8️⃣ Nginx Error Log (last 10 lines)
echo -e "8️⃣ Nginx recent errors (if any):"
sudo tail -n 10 /var/log/nginx/error.log
echo ""

# 9️⃣ Gunicorn Logs (last 10 lines)
echo -e "9️⃣ Gunicorn recent logs:"
sudo journalctl -u $SERVICE_NAME -n 10 --no-pager
echo ""

echo -e "============================="
echo -e "🏁 ${GREEN}Diagnostic completed${NC}"
echo -e "=============================\n"
