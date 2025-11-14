# dashboard/routes_users.py - User management routes
from flask import render_template, request, jsonify, redirect, url_for, flash, session, send_file
import io
import pandas as pd
import csv
from datetime import datetime
from . import dashboard_bp
from .utils import (
    login_required, admin_required, get_accessible_sidebar_items, 
    ARABIC_TEXTS, load_orders
)
from database import db

# Users Management Route
@dashboard_bp.route('/users')
@login_required
@admin_required
def users_page():
    """User management dashboard - Only for admin users"""
    try:
        # Get all users from database
        users = db.get_all_users()
        
        # Get accessible sidebar items
        sidebar_items = get_accessible_sidebar_items()
        
        # Pass user permissions to template
        user_permissions = session.get('permissions', {})
        
        return render_template('users.html',
                             users=users,
                             sidebar_items=sidebar_items,
                             user_role=session.get('role'),
                             user_permissions=user_permissions,
                             user_full_name=session.get('full_name'),
                             texts=ARABIC_TEXTS)
        
    except Exception as e:
        print(f"❌ Error loading users page: {e}")
        flash('حدث خطأ في تحميل صفحة إدارة المستخدمين', 'error')
        return redirect(url_for('dashboard.index'))

# ✅ FIXED: API Routes for User Management - PROPERLY HANDLE FULL_NAME
@dashboard_bp.route('/api/users/create', methods=['POST'])
@login_required
@admin_required
def api_create_user():
    """Create new user - FIXED: Properly handle full_name"""
    try:
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        full_name = request.form.get('full_name', '').strip()
        role = request.form.get('role', 'user').strip()
        
        print(f"🔄 Creating user: {username}, Full Name: {full_name}, Role: {role}")
        
        if not username or not password:
            return jsonify({"success": False, "message": "يرجى إدخال اسم المستخدم وكلمة المرور"})
        
        # ✅ FIXED: Pass full_name to create_user method
        user_id = db.create_user(username, password, full_name, role)
        
        if user_id:
            print(f"✅ User created successfully: {username} with full name: {full_name}")
            return jsonify({"success": True, "message": "تم إنشاء المستخدم بنجاح"})
        else:
            return jsonify({"success": False, "message": "اسم المستخدم موجود مسبقاً"})
            
    except Exception as e:
        print(f"❌ Error creating user: {e}")
        return jsonify({"success": False, "message": f"حدث خطأ: {str(e)}"})

@dashboard_bp.route('/api/users/update', methods=['POST'])
@login_required
@admin_required
def api_update_user():
    """Update user information - FIXED: Properly handle full_name"""
    try:
        user_id = int(request.form.get('user_id', 0))
        username = request.form.get('username', '').strip()
        full_name = request.form.get('full_name', '').strip()
        role = request.form.get('role', 'user').strip()
        is_active = request.form.get('is_active') == 'true'
        
        print(f"🔄 Updating user {user_id}: {username}, Full Name: {full_name}")
        
        if not username:
            return jsonify({"success": False, "message": "يرجى إدخال اسم المستخدم"})
        
        # ✅ FIXED: Pass full_name to update_user method
        success = db.update_user(user_id, username, full_name, role, is_active)
        
        if success:
            print(f"✅ User updated successfully: {username} with full name: {full_name}")
            return jsonify({"success": True, "message": "تم تحديث بيانات المستخدم بنجاح"})
        else:
            return jsonify({"success": False, "message": "فشل في تحديث بيانات المستخدم"})
            
    except Exception as e:
        print(f"❌ Error updating user: {e}")
        return jsonify({"success": False, "message": f"حدث خطأ: {str(e)}"})

@dashboard_bp.route('/api/users/change-password', methods=['POST'])
@login_required
@admin_required
def api_change_user_password():
    """Change user password"""
    try:
        user_id = int(request.form.get('user_id', 0))
        new_password = request.form.get('new_password', '').strip()
        
        if not new_password:
            return jsonify({"success": False, "message": "يرجى إدخال كلمة المرور الجديدة"})
        
        # Change password in database
        success = db.change_user_password(user_id, new_password)
        
        if success:
            return jsonify({"success": True, "message": "تم تغيير كلمة المرور بنجاح"})
        else:
            return jsonify({"success": False, "message": "فشل في تغيير كلمة المرور"})
            
    except Exception as e:
        print(f"❌ Error changing user password: {e}")
        return jsonify({"success": False, "message": f"حدث خطأ: {str(e)}"})

@dashboard_bp.route('/api/users/delete', methods=['POST'])
@login_required
@admin_required
def api_delete_user():
    """Delete user"""
    try:
        user_id = int(request.form.get('user_id', 0))
        
        # Prevent user from deleting themselves
        if user_id == session.get('user_id'):
            return jsonify({"success": False, "message": "لا يمكن حذف حسابك الخاص"})
        
        # Delete user from database
        success = db.delete_user(user_id)
        
        if success:
            return jsonify({"success": True, "message": "تم حذف المستخدم بنجاح"})
        else:
            return jsonify({"success": False, "message": "فشل في حذف المستخدم"})
            
    except Exception as e:
        print(f"❌ Error deleting user: {e}")
        return jsonify({"success": False, "message": f"حدث خطأ: {str(e)}"})

# Customer Management Routes
@dashboard_bp.route('/customers')
@login_required
@admin_required
def customers_page():
    """Customer management dashboard"""
    try:
        # Get all customers and their order history
        customers = db.get_all_customers()
        orders = db.get_orders()
        
        # Enhance customer data with order information
        enhanced_customers = []
        for customer in customers:
            customer_orders = [order for order in orders if order.get('user_id') == customer['telegram_id']]
            total_orders = len(customer_orders)
            total_spent = sum(order.get('total_amount', 0) for order in customer_orders)
            last_order_date = max([order.get('order_date', '') for order in customer_orders]) if customer_orders else 'لا توجد طلبات'
            
            enhanced_customers.append({
                'telegram_id': customer['telegram_id'],
                'username': customer.get('username', 'غير متوفر'),
                'first_name': customer.get('first_name', ''),
                'last_name': customer.get('last_name', ''),
                'phone': customer.get('phone', 'غير متوفر'),
                'total_orders': total_orders,
                'total_spent': total_spent,
                'last_order_date': last_order_date,
                'created_at': customer.get('created_at', '')
            })
        
        # Sort by total spent (descending)
        enhanced_customers.sort(key=lambda x: x['total_spent'], reverse=True)
        
        # Get accessible sidebar items
        sidebar_items = get_accessible_sidebar_items()
        
        # ✅ ADDED: Pass user permissions to template
        user_permissions = session.get('permissions', {})
        
        return render_template('customers.html',
                             customers=enhanced_customers,
                             sidebar_items=sidebar_items,
                             user_role=session.get('role'),
                             user_permissions=user_permissions,  # ✅ ADD THIS
                             user_full_name=session.get('full_name'),
                             texts=ARABIC_TEXTS)
        
    except Exception as e:
        print(f"❌ Error loading customers: {e}")
        flash('حدث خطأ في تحميل بيانات العملاء', 'error')
        return redirect(url_for('dashboard.index'))

@dashboard_bp.route('/export/customers/excel')
@login_required
@admin_required
def export_customers_excel():
    """Export customers to Excel - UPDATED TO INCLUDE PHONE NUMBERS"""
    try:
        customers = db.get_all_customers()
        orders = db.get_orders()
        
        # Prepare data for export - INCLUDING PHONE NUMBERS
        data = []
        for customer in customers:
            customer_orders = [order for order in orders if order.get('user_id') == customer['telegram_id']]
            total_orders = len(customer_orders)
            total_spent = sum(order.get('total_amount', 0) for order in customer_orders)
            
            data.append({
                'معرف التليجرام': customer['telegram_id'],
                'اسم المستخدم': customer.get('username', 'غير متوفر'),
                'الاسم الأول': customer.get('first_name', ''),
                'الاسم الأخير': customer.get('last_name', ''),
                'رقم الهاتف': customer.get('phone', 'غير متوفر'),  # ✅ ADDED PHONE NUMBER
                'إجمالي الطلبات': total_orders,
                'إجمالي الإنفاق': total_spent,
                'تاريخ التسجيل': customer.get('created_at', '')
            })
        
        df = pd.DataFrame(data)
        
        # Create Excel file in memory
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='العملاء', index=False)
            
            # Auto-adjust column widths
            worksheet = writer.sheets['العملاء']
            for idx, col in enumerate(df.columns):
                max_len = max(df[col].astype(str).str.len().max(), len(col)) + 2
                worksheet.column_dimensions[chr(65 + idx)].width = max_len
        
        output.seek(0)
        
        timestamp = datetime.now().strftime("%Y%m%d")
        filename = f"customers_report_{timestamp}.xlsx"
        
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=filename
        )
        
    except Exception as e:
        print(f"❌ Error exporting customers: {e}")
        flash('حدث خطأ أثناء تصدير بيانات العملاء', 'error')
        return redirect(url_for('dashboard.customers_page'))

@dashboard_bp.route('/export/customers/csv')
@login_required
@admin_required
def export_customers_csv():
    """Export customers to CSV - UPDATED TO INCLUDE PHONE NUMBERS"""
    try:
        customers = db.get_all_customers()
        orders = db.get_orders()
        
        # Create CSV in memory
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header - INCLUDING PHONE NUMBER
        writer.writerow(['معرف التليجرام', 'اسم المستخدم', 'الاسم الأول', 'الاسم الأخير', 'رقم الهاتف', 'إجمالي الطلبات', 'إجمالي الإنفاق', 'تاريخ التسجيل'])
        
        # Write data - INCLUDING PHONE NUMBERS
        for customer in customers:
            customer_orders = [order for order in orders if order.get('user_id') == customer['telegram_id']]
            total_orders = len(customer_orders)
            total_spent = sum(order.get('total_amount', 0) for order in customer_orders)
            
            writer.writerow([
                customer['telegram_id'],
                customer.get('username', 'غير متوفر'),
                customer.get('first_name', ''),
                customer.get('last_name', ''),
                customer.get('phone', 'غير متوفر'),  # ✅ ADDED PHONE NUMBER
                total_orders,
                total_spent,
                customer.get('created_at', '')
            ])
        
        output.seek(0)
        
        timestamp = datetime.now().strftime("%Y%m%d")
        filename = f"customers_report_{timestamp}.csv"
        
        return send_file(
            io.BytesIO(output.getvalue().encode('utf-8-sig')),
            mimetype='text/csv; charset=utf-8-sig',
            as_attachment=True,
            download_name=filename
        )
        
    except Exception as e:
        print(f"❌ Error exporting customers CSV: {e}")
        flash('حدث خطأ أثناء تصدير بيانات العملاء', 'error')
        return redirect(url_for('dashboard.customers_page'))