# dashboard/routes_accounting.py - Accounting and financial routes (FIXED)
from flask import render_template, request, jsonify, redirect, url_for, flash, session
from datetime import datetime
from . import dashboard_bp
from .utils import (
    login_required, permission_required, get_accessible_sidebar_items, 
    ARABIC_TEXTS
)
from database import db

# Accounting Route
@dashboard_bp.route('/accounting')
@login_required
@permission_required('view_accounting')
def accounting_page():
    """Accounting dashboard - only delivered orders"""
    try:
        # Get date range from request or default to current month
        start_date = request.args.get('start_date', datetime.now().replace(day=1).strftime('%Y-%m-%d'))
        end_date = request.args.get('end_date', datetime.now().strftime('%Y-%m-%d'))
        
        # Get delivered orders for the date range
        delivered_orders = db.get_delivered_orders_by_date_range(start_date, end_date)
        total_revenue = db.get_delivered_revenue_by_date_range(start_date, end_date)
        
        # Calculate additional stats
        total_orders = len(delivered_orders)
        average_order_value = total_revenue / total_orders if total_orders > 0 else 0
        
        # Get accessible sidebar items
        sidebar_items = get_accessible_sidebar_items()
        
        # Pass user permissions to template
        user_permissions = session.get('permissions', {})
        
        return render_template('accounting.html',
                             delivered_orders=delivered_orders,
                             total_revenue=total_revenue,
                             total_orders=total_orders,
                             average_order_value=average_order_value,
                             start_date=start_date,
                             end_date=end_date,
                             sidebar_items=sidebar_items,
                             user_role=session.get('role'),
                             user_permissions=user_permissions,
                             user_full_name=session.get('full_name'),
                             texts=ARABIC_TEXTS)
        
    except Exception as e:
        print(f"❌ Error loading accounting page: {e}")
        flash('حدث خطأ في تحميل صفحة المحاسبة', 'error')
        return redirect(url_for('dashboard.index'))