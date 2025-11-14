# dashboard/routes_main.py - Main dashboard routes
from flask import render_template, request, jsonify, redirect, url_for, session, flash
from datetime import datetime
from . import dashboard_bp
from .utils import (
    login_required, admin_required, permission_required, 
    get_accessible_sidebar_items, has_permission, ARABIC_TEXTS,
    load_products, load_orders, safe_get, get_inventory_analytics,
    generate_stock_alerts, get_user_permissions
)
from database import db

# ✅ UPDATED: Index route - ORDERS REMOVED FROM DASHBOARD
@dashboard_bp.route('/')
@login_required
def index():
    products_data = load_products()
    orders_data = load_orders()
    
    orders_list = orders_data.get('orders', [])
    if not isinstance(orders_list, list):
        orders_list = []
    
    # Calculate stats (still needed for the stats cards)
    total_orders = len(orders_list)
    pending_orders = len([o for o in orders_list if str(safe_get(o, 'status', '')).lower() in ['معلق', 'pending']])
    completed_orders = len([o for o in orders_list if str(safe_get(o, 'status', '')).lower() in ['مكتمل', 'completed', 'delivered', 'تم التوصيل', 'تم الشحن', 'shipped']])
    
    total_revenue = 0
    for order in orders_list:
        order_status = str(safe_get(order, 'status', '')).lower()
        if order_status in ['مكتمل', 'completed', 'delivered', 'تم التوصيل', 'تم الشحن', 'shipped']:
            total_revenue += float(safe_get(order, 'total_amount', 0))
    
    # Inventory stats - UPDATED: Include new analytics
    inventory_analytics = get_inventory_analytics()
    stock_alerts = generate_stock_alerts()
    
    # ✅ REMOVED: Recent orders processing - orders are no longer displayed on dashboard
    
    # Get accessible sidebar items based on user role
    sidebar_items = get_accessible_sidebar_items()
    
    # ✅ ADDED: Pass user permissions to template
    user_permissions = session.get('permissions', {})
    
    return render_template('dashboard.html', 
                         products=products_data.get('products', {}),
                         categories=products_data.get('categories', []),
                         # ✅ REMOVED: orders parameter - no longer passing orders to template
                         stats={
                             'total_orders': total_orders,
                             'pending_orders': pending_orders,
                             'completed_orders': completed_orders,
                             'total_revenue': total_revenue,
                             'total_products': inventory_analytics['total_products'],
                             'total_variants': inventory_analytics['total_variants'],
                             'low_stock_items': inventory_analytics['low_stock_items'],
                             'out_of_stock_items': inventory_analytics['out_of_stock_items'],
                             'available_products': inventory_analytics['available_products'],
                             'unavailable_products': inventory_analytics['unavailable_products']
                         },
                         stock_alerts=stock_alerts,
                         sidebar_items=sidebar_items,
                         user_role=session.get('role'),
                         user_permissions=user_permissions,  # ✅ ADD THIS
                         user_full_name=session.get('full_name'),
                         texts=ARABIC_TEXTS)

# ✅ UPDATED: Login route to set proper permissions from config
@dashboard_bp.route('/login', methods=['GET', 'POST'])
def login_page():
    """User login page"""
    # If already logged in, redirect to dashboard
    if 'user_id' in session:
        return redirect(url_for('dashboard.index'))
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        
        if not username or not password:
            flash('❌ يرجى إدخال اسم المستخدم وكلمة المرور', 'error')
            return render_template('login.html')
        
        # Authenticate user
        user = db.authenticate_user(username, password)
        
        if user:
            # Set session variables
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            session['full_name'] = user['full_name']
            
            # ✅ FIXED: Get permissions from utils.py function
            permissions = get_user_permissions(user['role'])
            session['permissions'] = permissions
            
            # ✅ NEW: Log staff login activity
            db.log_staff_activity(
                user_id=user['id'],
                action_type='login',
                action_description=f'تسجيل دخول المستخدم {user["username"]}',
                ip_address=request.remote_addr,
                user_agent=request.headers.get('User-Agent', '')
            )
            
            print(f"🔐 User {user['username']} logged in with role: {user['role']}")
            print(f"🔐 Permissions set: {permissions}")
            
            flash(f'✅ تم تسجيل الدخول بنجاح. مرحباً {user["full_name"] or user["username"]}!', 'success')
            return redirect(url_for('dashboard.index'))
        else:
            flash('❌ اسم المستخدم أو كلمة المرور غير صحيحة', 'error')
    
    return render_template('login.html')

@dashboard_bp.route('/logout')
def logout():
    """User logout"""
    # ✅ NEW: Log staff logout activity before clearing session
    if 'user_id' in session:
        db.log_staff_activity(
            user_id=session['user_id'],
            action_type='logout',
            action_description=f'تسجيل خروج المستخدم {session.get("username", "unknown")}',
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent', '')
        )
    
    session.clear()
    flash('✅ تم تسجيل الخروج بنجاح', 'success')
    return redirect(url_for('dashboard.login_page'))

@dashboard_bp.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    """Change user password - FIXED: Added missing template variables"""
    if request.method == 'POST':
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        
        if not current_password or not new_password or not confirm_password:
            flash('❌ يرجى ملء جميع الحقول', 'error')
            return redirect(url_for('dashboard.change_password'))
        
        if new_password != confirm_password:
            flash('❌ كلمة المرور الجديدة غير متطابقة', 'error')
            return redirect(url_for('dashboard.change_password'))
        
        # Verify current password
        user = db.get_user_by_id(session['user_id'])
        if not user or not db.verify_password(user['password_hash'], current_password):
            flash('❌ كلمة المرور الحالية غير صحيحة', 'error')
            return redirect(url_for('dashboard.change_password'))
        
        # Update password
        if db.change_user_password(session['user_id'], new_password):
            flash('✅ تم تغيير كلمة المرور بنجاح', 'success')
            return redirect(url_for('dashboard.index'))
        else:
            flash('❌ حدث خطأ أثناء تغيير كلمة المرور', 'error')
    
    # ✅ FIXED: Add all required template variables for sidebar
    sidebar_items = get_accessible_sidebar_items()
    user_permissions = session.get('permissions', {})
    
    return render_template('change_password.html',
                         sidebar_items=sidebar_items,
                         user_role=session.get('role'),
                         user_permissions=user_permissions,
                         user_full_name=session.get('full_name'),
                         texts=ARABIC_TEXTS)

# Health check route
@dashboard_bp.route('/health')
def health_check():
    return jsonify({"status": "healthy", "timestamp": datetime.now().isoformat()})