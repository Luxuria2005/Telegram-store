# config.py - Central Configuration File
# Enhanced with Role-Based Access Control

# Bot Configuration
TELEGRAM_BOT_TOKEN = "7739570245:AAFJ-q_dUDWwz4NiEra5Ytv6ow2gBsv3AKE"
BOT_USERNAME = "@LuxuriaLingerieBot"
ADMIN_USER_IDS = [1691722957]  # Replace 123456789 with your actual Telegram ID
SEND_NEW_PRODUCT_NOTIFICATIONS = True  # Enable automatic notifications
ENABLE_DASHBOARD_NOTIFICATIONS = True

# Your existing config.py content...
TELEGRAM_BOT_TOKEN = "7739570245:AAFJ-q_dUDWwz4NiEra5Ytv6ow2gBsv3AKE"
BOT_USERNAME = "@LuxuriaLingerieBot"
COMPANY_NAME = "LUXURIA FASHION"
# ... your existing content ...

# ✅ ADD THESE NEW LINES AFTER YOUR EXISTING CONTENT:
SEND_NEW_PRODUCT_NOTIFICATIONS = True
SEND_PROMOTIONAL_NOTIFICATIONS = True 
ENABLE_DASHBOARD_NOTIFICATIONS = True
ADMIN_USER_IDS = [1691722957]  # ⚠️ REPLACE WITH YOUR ACTUAL ID

# Your existing content continues...
CURRENCY = "SYP "
# ... etc

# Company Information
COMPANY_NAME = "LUXURIA FASHION"
COMPANY_ARABIC_NAME = "LUXURIA FASHION"
SUPPORT_EMAIL = "mkhalifeh2005@gmail.com"
SUPPORT_PHONE = "963944232394+"
BUSINESS_HOURS = "10:00 صباحاً - 6:00 مساءً"

# config.py - ADD THESE LINES

# Location Configuration - States and Regions
STATES_AND_REGIONS = {
    "دمشق": ["مركز المدينة", "المزة","الميدان","ركن الدين","المهاجرين", "كفر سوسة", "المالكي", "أبو رمانة", "قصاع", "تجارة", "برزة", "القابون"],
    "ريف دمشق": ["دوما", "حرستا", "داريا", "معضمية الشام", "الصبورة"],
    #"حمص": ["مركز المدينة", "الخالدية", "القدم", "الوعر", "الكرامة"],
    #"اللاذقية": ["مركز المدينة", "الشنغار", "السبيل", "الأسد", "الحفة"],
    #"حماة": ["مركز المدينة", "الحاضر", "المشرفة", "الكرامة", "الميدان"],
    #"طرطوس": ["مركز المدينة", "أرزنة", "الدريكيش", "بانياس", "صافيتا"],
    #"دير الزور": ["مركز المدينة", "الحويقة", "الجزيرة", "الميادين", "البوليل"],
    #"الحسكة": ["مركز المدينة", "الرقة", "المالكية", "القامشلي", "رأس العين"],
    #"الرقة": ["مركز المدينة", "التبني", "الكرم", "المسلمية", "الصويدرة"]
}

# Arabic text constants - UPDATE ARABIC_TEXTS
ARABIC_TEXTS = {
    # ... your existing texts ...
    "select_state": "🏙️ **اختر المحافظة:**\n\nالرجاء اختيار المحافظة التي تقيم فيها:",
    "select_region": "📍 **اختر المنطقة:**\n\nالرجاء اختيار منطقتك داخل المحافظة:",
    "state": "المحافظة",
    "region": "المنطقة"
}

# Store Settings
CURRENCY = "SYP "
LOW_STOCK_THRESHOLD = 5
CRITICAL_STOCK_THRESHOLD = 2

# Database Configuration
DATABASE_PATH = "store.db"

# Notification Settings
SEND_NEW_PRODUCT_NOTIFICATIONS = True
SEND_PROMOTIONAL_NOTIFICATIONS = True

# Shipping & Delivery
SHIPPING_COST = 5.00
FREE_SHIPPING_THRESHOLD = 50.00

# Feature Toggles
ENABLE_CUSTOMER_NOTIFICATIONS = True
ENABLE_INVENTORY_ALERTS = True
ENABLE_SALES_ANALYTICS = True

# ✅ UPDATED Permissions Configuration - FIXED NOTIFICATION PERMISSIONS FOR ORDER MANAGER
ROLE_PERMISSIONS = {
    'admin': {
        'name': 'مدير النظام',
        'description': 'صلاحيات كاملة على النظام',
        'permissions': {
            'all_permissions': True,
            
            # Orders Permissions
            'view_orders': True,
            'print_orders': True,
            'print_invoices': True,
            'change_order_status': True,
            'delete_orders': True,
            
            # Products Permissions
            'view_products': True,
            'manage_products': True,
            'add_products': True,
            'edit_products': True,
            'delete_products': True,
            
            # Inventory Permissions
            'view_inventory': True,
            'manage_inventory': True,
            'update_inventory': True,
            
            # Customers Permissions
            'view_customers': True,
            'manage_customers': True,
            'export_customers': True,
            
            # Reports Permissions
            'view_reports': True,
            'manage_reports': True,
            'export_reports': True,
            
            # ✅ ADD THIS LINE - Accounting Permission
            'view_accounting': True,
            
            # System Permissions
            'manage_users': True,
            'system_settings': True,
            'send_notifications': True,
            
            # Bulk Operations
            'bulk_operations': True,
            'bulk_prices': True,
            'bulk_inventory': True
        }
    },
    'order_manager': {
        'name': 'مدير الطلبات',
        'description': 'إدارة الطلبات والمخزون - عرض المنتجات فقط',
        'permissions': {
            'all_permissions': False,
            
            # Orders Permissions
            'view_orders': True,
            'print_orders': True,
            'print_invoices': True,
            'change_order_status': True,
            'delete_orders': False,
            
            # Products Permissions
            'view_products': True,
            'manage_products': False,
            'add_products': True,
            'edit_products': True,
            'delete_products': False,
            
            # Inventory Permissions
            'view_inventory': True,
            'manage_inventory': True,
            'update_inventory': True,
            
            # Customers Permissions
            'view_customers': False,
            'manage_customers': False,
            'export_customers': False,
            
            # Reports Permissions
            'view_reports': False,
            'manage_reports': False,
            'export_reports': False,
            
            # ✅ ADD THIS LINE - Accounting Permission
            'view_accounting': True,
            
            # System Permissions
            'manage_users': False,
            'system_settings': False,
            'send_notifications': True,
            
            # Bulk Operations
            'bulk_operations': False,
            'bulk_prices': False,
            'bulk_inventory': False
        }
    },
    'user': {
        'name': 'مستخدم عادي',
        'description': 'عرض الطلبات والطباعة فقط',
        'permissions': {
            'all_permissions': False,
            
            # Orders Permissions
            'view_orders': True,
            'print_orders': True,
            'print_invoices': True,
            'change_order_status': True,
            'delete_orders': False,
            
            # Products Permissions
            'view_products': False,
            'manage_products': False,
            'add_products': False,
            'edit_products': False,
            'delete_products': False,
            
            # Inventory Permissions
            'view_inventory': False,
            'manage_inventory': False,
            'update_inventory': False,
            
            # Customers Permissions
            'view_customers': False,
            'manage_customers': False,
            'export_customers': False,
            
            # Reports Permissions
            'view_reports': False,
            'manage_reports': False,
            'export_reports': False,
            
            # ✅ ADD THIS LINE - Accounting Permission (set to False for regular users)
            'view_accounting': False,
            
            # System Permissions
            'manage_users': False,
            'system_settings': False,
            'send_notifications': False,
            
            # Bulk Operations
            'bulk_operations': False,
            'bulk_prices': False,
            'bulk_inventory': False
        }
    }
}

# Session Configuration
SESSION_TIMEOUT_MINUTES = 30
SESSION_WARNING_MINUTES = 25

# Security Settings
PASSWORD_MIN_LENGTH = 6
ALLOWED_LOGIN_ATTEMPTS = 5
LOGIN_LOCKOUT_MINUTES = 15

# Arabic Text Constants
ARABIC_TEXTS = {
    "welcome": "مرحباً بك في {company_name}! 🛍️",
    "order_placed": "تم وضع الطلب بنجاح! 🎉",
    "out_of_stock": "❌ المنتج غير متوفر حالياً",
    "insufficient_stock": "❌ الكمية المطلوبة تتجاوز المخزون المتاح",
    "order_cannot_delete": "❌ لا يمكن حذف طلب تم توصيله",
    "inventory_restored": "✅ تم استعادة المخزون بعد إلغاء الطلب"
}

def get_company_info():
    """Get complete company information"""
    return {
        'name': COMPANY_NAME,
        'arabic_name': COMPANY_ARABIC_NAME,
        'support_email': SUPPORT_EMAIL,
        'support_phone': SUPPORT_PHONE,
        'business_hours': BUSINESS_HOURS
    }

def get_role_permissions(role):
    """Get permissions for a specific role"""
    return ROLE_PERMISSIONS.get(role, ROLE_PERMISSIONS['user'])

def get_all_roles():
    """Get all available roles"""
    return ROLE_PERMISSIONS