"""
WSGI config for naro_lims project.
"""

import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'naro_lims.settings')
application = get_wsgi_application()
