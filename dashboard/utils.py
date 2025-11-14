# dashboard/utils.py - Shared utility functions and helpers (FIXED)
from flask import session, redirect, url_for, flash
from functools import wraps
from datetime import datetime, timedelta
import os
from werkzeug.utils import secure_filename
import barcode
from barcode.writer import ImageWriter
import io
import base64
import qrcode
import requests
import pandas as pd
from database import db
from config import get_role_permissions, TELEGRAM_BOT_TOKEN, CURRENCY

# Arabic text constants
ARABIC_TEXTS = {
    "dashboard_title": "لوحة تحكم LUXURIA FASHION",
    "total_orders": "إجمالي الطلبات",
    "pending_orders": "طلبات معلقة", 
    "completed_orders": "طلبات مكتملة",
    "total_revenue": "إجمالي الإيرادات",
    "add_category": "إضافة فئة جديدة",
    "add_product": "إضافة منتج جديد",
    "current_products": "المنتجات الحالية",
    "recent_orders": "الطلبات الحديثة",
    "view_all_orders": "عرض جميع الطلبات",
    "category_name": "اسم الفئة",
    "product_name": "اسم المنتج",
    "price": "السعر",
    "size": "المقاس",
    "color": "اللون", 
    "quantity": "الكمية",
    "stock": "المخزون",
    "description": "الوصف",
    "add": "إضافة",
    "upload": "رفع",
    "delete": "حذف",
    "edit": "تعديل",
    "status": "الحالة",
    "add_variant": "إضافة مقاس ولون",
    "remove": "إزالة",
    "upload_images": "رفع صور اللون",
    "current_images": "الصور الحالية",
    "edit_product": "تعديل المنتج",
    "update_product": "تحديث المنتج",
    "save_changes": "حفظ التغييرات",
    "bulk_operations": "العمليات الجماعية",
    "select_all": "تحديد الكل",
    "deselect_all": "إلغاء الكل",
    "bulk_inventory": "تحديث المخزون",
    "bulk_prices": "تحديث الأسعار",
    "bulk_delete": "حذف جماعي",
    "apply_to_selected": "طبيق على المحدد",
    "model_number": "رقم الموديل",
    "enter_model_number": "أدخل رقم الموديل"
}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'png', 'jpg', 'jpeg', 'gif'}

def safe_get(obj, key, default=None):
    try:
        return obj.get(key, default)
    except:
        return default

# Authentication and Permission Decorators
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('dashboard.login_page'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('dashboard.login_page'))
        if session.get('role') != 'admin':
            flash('❌ غير مصرح بالوصول. تحتاج صلاحيات المدير.', 'error')
            return redirect(url_for('dashboard.index'))
        return f(*args, **kwargs)
    return decorated_function

def permission_required(permission):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                print(f"🔐 Permission DENIED: User not logged in for {permission}")
                return redirect(url_for('dashboard.login_page'))
            
            user_role = session.get('role')
            user_permissions = session.get('permissions', {})
            
            print(f"🔐 Permission Check: {permission}")
            print(f"🔐 User: {session.get('username')}, Role: {user_role}")
            print(f"🔐 Session Permissions: {user_permissions}")
            print(f"🔐 Required Permission '{permission}': {user_permissions.get(permission, 'NOT FOUND')}")
            
            # Admin has all permissions
            if user_role == 'admin':
                print(f"🔐 Permission GRANTED: Admin bypass for {permission}")
                return f(*args, **kwargs)
            
            # Check specific permission
            if not user_permissions.get(permission, False):
                print(f"🔐 Permission DENIED: User lacks {permission}")
                flash(f'❌ غير مصرح بالوصول. تحتاج صلاحية: {permission}', 'error')
                return redirect(url_for('dashboard.index'))
            
            print(f"🔐 Permission GRANTED: User has {permission}")
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# ✅ FIXED: Get permissions from config.py
def get_user_permissions(role):
    """Get permissions for user role from config"""
    role_config = get_role_permissions(role)
    return role_config.get('permissions', {})

# ✅ Check if user has permission
def has_permission(permission):
    if session.get('role') == 'admin':
        return True
    user_permissions = session.get('permissions', {})
    return user_permissions.get(permission, False)

# ✅ UPDATED: Get accessible sidebar items based on ACTUAL permissions
def get_accessible_sidebar_items():
    user_role = session.get('role')
    user_permissions = session.get('permissions', {})
    
    # Base items for all users
    sidebar_items = [
        {'url': '/', 'icon': 'fas fa-tachometer-alt', 'text': 'الرئيسية'},
        {'url': '/all-orders', 'icon': 'fas fa-shopping-bag', 'text': 'جميع الطلبات'}
    ]
    
    # Add items based on permissions
    if user_permissions.get('view_products') or user_role == 'admin':
        sidebar_items.append({'url': '/products', 'icon': 'fas fa-tshirt', 'text': 'إدارة المنتجات'})
    
    # ✅ FIXED: Only show "Add Product" if user has manage_products permission
    if user_permissions.get('manage_products') or user_role == 'admin':
        sidebar_items.append({'url': '/add-product', 'icon': 'fas fa-plus-circle', 'text': 'إضافة منتج جديد'})
    
    # ✅ FIXED: Only show inventory management if user has manage_inventory permission
    if user_permissions.get('manage_inventory') or user_role == 'admin':
        sidebar_items.append({'url': '/inventory', 'icon': 'fas fa-boxes', 'text': 'إدارة المخزون المتقدمة'})
    elif user_permissions.get('view_inventory'):
        # Order managers can view inventory but not manage it
        sidebar_items.append({'url': '/inventory', 'icon': 'fas fa-boxes', 'text': 'عرض المخزون'})
    
    if user_permissions.get('view_customers') or user_role == 'admin':
        sidebar_items.append({'url': '/customers', 'icon': 'fas fa-users', 'text': 'إدارة العملاء'})
    
    # ✅ FIXED: Only show bulk prices if user has bulk_prices permission
    if user_permissions.get('bulk_prices') or user_role == 'admin':
        sidebar_items.append({'url': '/bulk-prices', 'icon': 'fas fa-money-bill-wave', 'text': 'إدارة الأسعار'})
    
    if user_permissions.get('view_reports') or user_role == 'admin':
        sidebar_items.append({'url': '/reports', 'icon': 'fas fa-chart-bar', 'text': 'التقارير المتقدمة'})
    
    # ✅ NEW: Add Broadcast System to sidebar for users with notification permissions
    if user_permissions.get('send_notifications') or user_role == 'admin':
        sidebar_items.append({'url': '/broadcast', 'icon': 'fas fa-bullhorn', 'text': 'نظام البث'})
    
    if user_permissions.get('manage_users') or user_role == 'admin':
        sidebar_items.append({'url': '/users', 'icon': 'fas fa-user-cog', 'text': 'إدارة المستخدمين'})
    
    return sidebar_items

# Database functions to replace JSON
def load_products():
    """Load products from database"""
    try:
        categories = db.get_categories()
        products = db.get_all_products()
        return {
            "categories": [category['name'] for category in categories],
            "products": products
        }
    except Exception as e:
        print(f"❌ Error loading products from database: {e}")
        return {"categories": [], "products": {}}

def load_orders():
    """Load orders from database"""
    try:
        orders = db.get_orders()
        return {"orders": orders}
    except Exception as e:
        print(f"❌ Error loading orders from database: {e}")
        return {"orders": []}

# Analytics Functions
def get_inventory_analytics():
    """Get comprehensive inventory analytics - FIXED: Correct calculation of total/available/unavailable products"""
    try:
        products_data = load_products()
        
        # Initialize counters
        total_products_count = 0
        available_products_count = 0
        unavailable_products_count = 0
        low_stock_items_count = 0
        total_variants_count = 0
        out_of_stock_variants_count = 0
        category_stats = {}
        
        for category, products in products_data.get('products', {}).items():
            category_stats[category] = {
                'total_products': 0,
                'total_variants': 0,
                'low_stock': 0,
                'out_of_stock': 0,
                'available_products': 0,
                'unavailable_products': 0
            }
            
            for product in products:
                # Count this product
                total_products_count += 1
                category_stats[category]['total_products'] += 1
                
                product_has_stock = False
                product_variants = product.get('variants', [])
                
                for variant in product_variants:
                    total_variants_count += 1
                    category_stats[category]['total_variants'] += 1
                    
                    current_stock = variant.get('quantity', 0)
                    
                    if current_stock > 0:
                        product_has_stock = True
                        # Check for low stock (1-4 items)
                        if current_stock < 5:
                            low_stock_items_count += 1
                            category_stats[category]['low_stock'] += 1
                    else:
                        out_of_stock_variants_count += 1
                        category_stats[category]['out_of_stock'] += 1
                
                # Determine if product is available or unavailable
                if product_has_stock:
                    available_products_count += 1
                    category_stats[category]['available_products'] += 1
                else:
                    unavailable_products_count += 1
                    category_stats[category]['unavailable_products'] += 1
        
        print(f"📊 Fixed Inventory Analytics:")
        print(f"   Total Products: {total_products_count}")
        print(f"   Available Products: {available_products_count}") 
        print(f"   Unavailable Products: {unavailable_products_count}")
        print(f"   Low Stock Items: {low_stock_items_count}")
        print(f"   Total Variants: {total_variants_count}")
        print(f"   Out of Stock Variants: {out_of_stock_variants_count}")
        
        return {
            'total_products': total_products_count,
            'total_variants': total_variants_count,
            'low_stock_items': low_stock_items_count,
            'out_of_stock_items': out_of_stock_variants_count,
            'available_products': available_products_count,
            'unavailable_products': unavailable_products_count,
            'category_stats': category_stats
        }
    except Exception as e:
        print(f"❌ Error in inventory analytics: {e}")
        return {
            'total_products': 0,
            'total_variants': 0,
            'low_stock_items': 0,
            'out_of_stock_items': 0,
            'available_products': 0,
            'unavailable_products': 0,
            'category_stats': {}
        }

def get_sales_analytics():
    """Get sales analytics for inventory optimization - FIXED: Proper 30-day calculation"""
    try:
        orders_data = load_orders()
        orders = orders_data.get('orders', [])
        
        # Last 30 days sales - FIXED: Use proper date comparison
        thirty_days_ago = datetime.now() - timedelta(days=30)
        recent_orders = []
        
        for order in orders:
            try:
                # Handle different date formats
                order_date_str = order.get('order_date', '')
                if not order_date_str:
                    continue
                    
                # Try different date formats
                for date_format in ['%Y-%m-%d', '%Y-%m-%d', '%d/%m/%Y']:
                    try:
                        order_date = datetime.strptime(order_date_str, date_format)
                        break
                    except ValueError:
                        continue
                else:
                    # If no format works, skip this order
                    continue
                
                if order_date > thirty_days_ago:
                    recent_orders.append(order)
            except Exception as e:
                print(f"⚠️ Error processing order date: {e}")
                continue
        
        print(f"📊 Found {len(recent_orders)} orders in last 30 days")
        
        # Product sales analysis
        product_sales = {}
        for order in recent_orders:
            for item in order.get('items', []):
                product_key = f"{item.get('name')}_{item.get('color', '')}_{item.get('size', '')}"
                if product_key not in product_sales:
                    product_sales[product_key] = {
                        'name': item.get('name'),
                        'color': item.get('color', ''),
                        'size': item.get('size', ''),
                        'total_sold': 0,
                        'revenue': 0
                    }
                product_sales[product_key]['total_sold'] += item.get('quantity', 0)
                product_sales[product_key]['revenue'] += item.get('price', 0) * item.get('quantity', 0)
        
        # Sort by most sold
        top_selling = sorted(product_sales.values(), key=lambda x: x['total_sold'], reverse=True)[:10]
        
        return {
            'total_recent_orders': len(recent_orders),
            'top_selling_products': top_selling,
            'product_sales': product_sales
        }
    except Exception as e:
        print(f"❌ Error in sales analytics: {e}")
        return {
            'total_recent_orders': 0,
            'top_selling_products': [],
            'product_sales': {}
        }

def generate_stock_alerts():
    """Generate stock alerts and recommendations - MODIFIED: Only show items with quantity > 0 and stock < 5, INCLUDES MODEL NUMBER"""
    try:
        products_data = load_products()
        sales_analytics = get_sales_analytics()
        
        alerts = []
        recommendations = []
        
        for category, products in products_data.get('products', {}).items():
            for product in products:
                for variant in product.get('variants', []):
                    product_key = f"{product['name']}_{variant.get('color', '')}_{variant.get('size', '')}"
                    current_stock = variant.get('quantity', 0)
                    
                    # Only show alerts for items with quantity > 0 and stock < 5
                    if current_stock > 0 and current_stock < 5:
                        alerts.append({
                            'type': 'critical',
                            'message': f"منخفض جداً: {product['name']} - {variant.get('color')} - {variant.get('size')} ({current_stock} متبقي)",
                            'product': product['name'],
                            'model_number': product.get('model_number', 'غير متوفر'),  # ✅ ADDED MODEL NUMBER
                            'color': variant.get('color'),
                            'size': variant.get('size'),
                            'current_stock': current_stock,
                            'category': category
                        })
                    # REMOVED: The warning for stock < 15 since we only want alerts for stock < 5
        
        return {
            'alerts': alerts,
            'recommendations': recommendations
        }
    except Exception as e:
        print(f"❌ Error generating stock alerts: {e}")
        return {
            'alerts': [],
            'recommendations': []
        }

def get_filtered_inventory():
    """Get inventory data filtered to exclude zero/null quantities"""
    try:
        products_data = load_products()
        filtered_products = {}
        
        for category, products in products_data.get('products', {}).items():
            filtered_products[category] = []
            
            for product in products:
                # Filter variants to exclude zero/null quantities
                filtered_variants = []
                for variant in product.get('variants', []):
                    if variant.get('quantity', 0) > 0:
                        filtered_variants.append(variant)
                
                # Only include products that have variants with quantity > 0
                if filtered_variants:
                    product_copy = product.copy()
                    product_copy['variants'] = filtered_variants
                    filtered_products[category].append(product_copy)
        
        return filtered_products
    except Exception as e:
        print(f"❌ Error getting filtered inventory: {e}")
        return {}

def generate_barcode(data):
    """Generate barcode image as base64 string - WITHOUT TEXT"""
    try:
        # ✅ Convert Arabic letters to English codes
        def arabic_to_english_code(text):
            arabic_to_english_map = {
                'أ': 'A', 'ا': 'A',  # Alif variations
                'ب': 'B', 'ت': 'T', 'ث': 'TH', 'ج': 'J',
                'ح': 'H', 'خ': 'KH', 'د': 'D', 'ذ': 'DH',
                'ر': 'R', 'ز': 'Z', 'س': 'S', 'ش': 'SH',
                'ص': 'S2', 'ض': 'D2', 'ط': 'T2', 'ظ': 'Z2',
                'ع': 'A2', 'غ': 'GH', 'ف': 'F', 'ق': 'Q',
                'ك': 'K', 'ل': 'L', 'م': 'M', 'ن': 'N',
                'ه': 'H2', 'و': 'W', 'ي': 'Y', 'ى': 'A3'
            }
            
            result = ""
            for char in text:
                if char in arabic_to_english_map:
                    result += arabic_to_english_map[char]
                else:
                    result += char
            return result
        
        # ✅ Convert any Arabic letters in the barcode data
        clean_data = arabic_to_english_code(str(data))
        
        # Use Code128 format
        code128 = barcode.get_barcode_class('code128')
        barcode_instance = code128(clean_data, writer=ImageWriter())
        
        # Save to bytes buffer - WITHOUT TEXT
        buffer = io.BytesIO()
        barcode_instance.write(buffer, options={
            'module_height': 18.0,
            'module_width': 0.35,
            'quiet_zone': 10.0,
            'font_size': 0,           # ✅ Set to 0 to hide text
            'text_distance': 0,       # ✅ Set to 0
            'write_text': False,      # ✅ Set to False - NO TEXT IN BARCODE
            'dpi': 300
        })
        
        buffer.seek(0)
        barcode_base64 = base64.b64encode(buffer.getvalue()).decode()
        return f"data:image/png;base64,{barcode_base64}"
        
    except Exception as e:
        print(f"❌ Error generating barcode: {e}")
        return ""

def generate_qr_code(data):
    """Generate QR code image as base64 string"""
    try:
        # Create QR code instance
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=6,  # Smaller size for compact display
            border=2,
        )
        
        # Add data to QR code
        qr.add_data(str(data))
        qr.make(fit=True)
        
        # Create QR code image
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Convert to base64
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)
        qr_base64 = base64.b64encode(buffer.getvalue()).decode()
        
        return f"data:image/png;base64,{qr_base64}"
        
    except Exception as e:
        print(f"❌ Error generating QR code: {e}")
        # Return empty string if QR generation fails
        return ""

def get_color_code(color_name):
    """Get color code for color badges in inventory"""
    color_map = {
        'أحمر': '#dc3545',
        'أزرق': '#0d6efd', 
        'أخضر': '#198754',
        'أسود': '#000000',
        'أبيض': '#f8f9fa',
        'أصفر': '#ffc107',
        'وردي': '#e83e8c',
        'بنفسجي': '#6f42c1',
        'رمادي': '#6c757d',
        'بني': '#795548',
        'Red': '#dc3545',
        'Blue': '#0d6efd',
        'Green': '#198754',
        'Black': '#000000',
        'White': '#f8f9fa',
        'Yellow': '#ffc107',
        'Pink': '#e83e8c',
        'Purple': '#6f42c1',
        'Gray': '#6c757d',
        'Brown': '#795548'
    }
    return color_map.get(color_name, '#6c757d')  # Default gray

 # ✅ NEW: Excel Export Functions
def generate_client_logs_excel(logs, filters=None):
    """Generate Excel file for client logs with Arabic support"""
    try:
        # Prepare data for Excel
        data = []
        for log in logs:
            row = {
                'التاريخ والوقت': log.get('created_at', ''),
                'معرف التليجرام': log.get('telegram_id', ''),
                'الاسم الأول': log.get('first_name', ''),
                'الاسم الأخير': log.get('last_name', ''),
                'اسم المستخدم': f"@{log.get('username', '')}" if log.get('username') else '',
                'نوع النشاط': log.get('activity_type', ''),
                'وصف النشاط': log.get('activity_description', ''),
                'نوع الهدف': log.get('target_type', ''),
                'اسم الهدف': log.get('target_name', ''),
                'معرف الهدف': log.get('target_id', ''),
                'معلومات إضافية': log.get('metadata', '')
            }
            data.append(row)
        
        # Create DataFrame
        df = pd.DataFrame(data)
        
        # Create Excel file in memory
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='سجلات العملاء', index=False, startrow=1)
            
            # Get workbook and worksheet
            workbook = writer.book
            worksheet = writer.sheets['سجلات العملاء']
            
            # Add title and filters info
            title = "سجلات نشاط العملاء - LUXURIA FASHION"
            worksheet.cell(row=1, column=1, value=title)
            
            if filters:
                filters_text = f"الفلاتر المطبقة: {filters}"
                worksheet.cell(row=2, column=1, value=filters_text)
            
            # Auto-adjust columns width
            for column in worksheet.columns:
                max_length = 0
                column_letter = column[0].column_letter
                for cell in column:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                adjusted_width = min(max_length + 2, 50)
                worksheet.column_dimensions[column_letter].width = adjusted_width
        
        output.seek(0)
        return output
        
    except Exception as e:
        print(f"❌ Error generating client logs Excel: {e}")
        return None

def generate_staff_logs_excel(logs, filters=None):
    """Generate Excel file for staff logs with Arabic support"""
    try:
        # Prepare data for Excel
        data = []
        for log in logs:
            row = {
                'التاريخ والوقت': log.get('created_at', ''),
                'المستخدم': log.get('full_name') or log.get('username', ''),
                'اسم المستخدم': log.get('username', ''),
                'نوع النشاط': log.get('action_type', ''),
                'وصف النشاط': log.get('action_description', ''),
                'نوع الهدف': log.get('target_type', ''),
                'اسم الهدف': log.get('target_name', ''),
                'معرف الهدف': log.get('target_id', ''),
                'القيمة القديمة': log.get('old_value', ''),
                'القيمة الجديدة': log.get('new_value', ''),
                'عنوان IP': log.get('ip_address', '')
            }
            data.append(row)
        
        # Create DataFrame
        df = pd.DataFrame(data)
        
        # Create Excel file in memory
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='سجلات الموظفين', index=False, startrow=1)
            
            # Get workbook and worksheet
            workbook = writer.book
            worksheet = writer.sheets['سجلات الموظفين']
            
            # Add title and filters info
            title = "سجلات نشاط الموظفين - LUXURIA FASHION"
            worksheet.cell(row=1, column=1, value=title)
            
            if filters:
                filters_text = f"الفلاتر المطبقة: {filters}"
                worksheet.cell(row=2, column=1, value=filters_text)
            
            # Auto-adjust columns width
            for column in worksheet.columns:
                max_length = 0
                column_letter = column[0].column_letter
                for cell in column:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                adjusted_width = min(max_length + 2, 50)
                worksheet.column_dimensions[column_letter].width = adjusted_width
        
        output.seek(0)
        return output
        
    except Exception as e:
        print(f"❌ Error generating staff logs Excel: {e}")
        return None

def get_filters_description(args):
    """Generate human-readable description of applied filters"""
    filters = []
    
    if args.get('telegram_id'):
        filters.append(f"عميل: {args.get('telegram_id')}")
    
    if args.get('user_id'):
        filters.append(f"مستخدم: {args.get('user_id')}")
    
    if args.get('activity_type'):
        filters.append(f"نوع النشاط: {args.get('activity_type')}")
    
    if args.get('action_type'):
        filters.append(f"نوع الإجراء: {args.get('action_type')}")
    
    if args.get('start_date'):
        filters.append(f"من: {args.get('start_date')}")
    
    if args.get('end_date'):
        filters.append(f"إلى: {args.get('end_date')}")
    
    return " | ".join(filters) if filters else "جميع السجلات"   

# ✅ NEW: Send order status notification via Telegram
def send_order_status_notification(order_id, old_status, new_status):
    """Send order status update notification to customer via Telegram"""
    try:
        # Get order details
        order = db.get_order_by_id(order_id)
        if not order:
            print(f"❌ Order {order_id} not found for notification")
            return False
        
        user_id = order.get('user_id')
        if not user_id:
            print(f"❌ No user_id found for order {order_id}")
            return False
        
        # Status messages in Arabic
        status_messages = {
            'confirmed': {
                'title': '✅ تم تأكيد طلبك',
                'message': f'تم تأكيد طلبك #{order_id} وسيتم تجهيزه قريباً.'
            },
            'shipped': {
                'title': '🚚 تم شحن طلبك',
                'message': f'طلبك #{order_id} تم شحنه وهو في الطريق إليك.'
            },
            'delivered': {
                'title': '🎉 تم توصيل طلبك',
                'message': f'تهانينا! تم توصيل طلبك #{order_id} بنجاح.'
            }
        }
        
        # Get message for the new status
        status_key = new_status.lower()
        if status_key in ['مؤكد', 'confirmed']:
            message_info = status_messages['confirmed']
        elif status_key in ['تم الشحن', 'shipped']:
            message_info = status_messages['shipped']
        elif status_key in ['تم التوصيل', 'delivered']:
            message_info = status_messages['delivered']
        else:
            # No notification for other status changes
            return True
        
        # Prepare notification text
        notification_text = f"""
{message_info['title']}

{message_info['message']}

**تفاصيل الطلب:**
📦 رقم الطلب: #{order_id}
👤 العميل: {order.get('user_name', '')}
📞 الهاتف: {order.get('user_phone', '')}
🏠 العنوان: {order.get('user_address', '')}
💰 المبلغ: {CURRENCY}{order.get('total_amount', 0):,.0f}

شكراً لثقتك بنا! 🤝
"""
        
        # Send via Telegram API
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        data = {
            'chat_id': user_id,
            'text': notification_text,
            'parse_mode': 'Markdown'
        }
        
        response = requests.post(url, data=data)
        
        if response.status_code == 200:
            print(f"✅ Sent status notification for order #{order_id} to user {user_id}")
            return True
        else:
            print(f"❌ Failed to send notification: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error sending order status notification: {e}")
        return False