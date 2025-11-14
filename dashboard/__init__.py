# dashboard/__init__.py - Blueprint registration and imports
from flask import Blueprint

# Create the main dashboard blueprint
dashboard_bp = Blueprint('dashboard', __name__, template_folder='../templates', static_folder='../static')

print("✅ Dashboard blueprint initialized successfully!")

# Import all route modules AFTER blueprint creation to avoid circular imports
from . import routes_main
from . import routes_products
from . import routes_orders
from . import routes_inventory
from . import routes_users
from . import routes_reports
from . import routes_broadcast
from . import routes_accounting
from . import routes_logs
from . import error_handlers