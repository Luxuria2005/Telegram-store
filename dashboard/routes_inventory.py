# dashboard/routes_inventory.py - Inventory management routes
from flask import render_template, request, jsonify, redirect, url_for, flash, session, send_file
import io
import pandas as pd
import csv
from datetime import datetime
from . import dashboard_bp
from .utils import (
    login_required, permission_required, get_accessible_sidebar_items, 
    has_permission, ARABIC_TEXTS, get_inventory_analytics, generate_stock_alerts,
    get_sales_analytics, get_filtered_inventory, get_color_code
)
from database import db

# ✅ UPDATED: Inventory route - Different permissions for view vs manage
@dashboard_bp.route('/inventory')
@login_required
def inventory_page():
    """Enhanced inventory management page - Accessible to all logged-in users with appropriate permissions"""
    inventory_analytics = get_inventory_analytics()
    stock_alerts = generate_stock_alerts()
    sales_analytics = get_sales_analytics()
    filtered_inventory = get_filtered_inventory()
    
    # Get accessible sidebar items
    sidebar_items = get_accessible_sidebar_items()
    
    # ✅ ADDED: Pass user permissions to template
    user_permissions = session.get('permissions', {})
    
    return render_template('inventory.html',
                         inventory_analytics=inventory_analytics,
                         stock_alerts=stock_alerts,
                         sales_analytics=sales_analytics,
                         filtered_inventory=filtered_inventory,
                         get_color_code=get_color_code,  # Add this line
                         sidebar_items=sidebar_items,
                         user_role=session.get('role'),
                         user_permissions=user_permissions,  # ✅ ADD THIS
                         user_full_name=session.get('full_name'),
                         texts=ARABIC_TEXTS)

# Inventory Management Route
@dashboard_bp.route('/update_inventory', methods=['POST'])
@login_required
@permission_required('manage_products')
def update_inventory():
    try:
        category = request.form.get('category', '')
        product_id = int(request.form.get('product_id', 0))
        color = request.form.get('color', '')
        size = request.form.get('size', '')
        quantity_change = int(request.form.get('quantity_change', 0))
        
        # Get current quantity
        product = db.get_product_by_id(product_id)
        if not product:
            return jsonify({"success": False, "message": "لم يتم العثور على المنتج"})
        
        # Find the variant and calculate new quantity
        current_quantity = 0
        for variant in product.get('variants', []):
            if variant['color'] == color and variant['size'] == size:
                current_quantity = variant['quantity']
                break
        
        new_quantity = current_quantity + quantity_change
        
        if new_quantity < 0:
            return jsonify({"success": False, "message": "الكمية غير كافية"})
        
        # Update in database
        success = db.update_variant_quantity(product_id, color, size, new_quantity, reason=f"Manual update by {session.get('username', 'unknown')}")
        
        if success:
            # ✅ ENHANCED: Log detailed inventory change
            product = db.get_product_by_id(product_id)
            product_name = product.get('name', 'Unknown') if product else 'Unknown'
            
            db.log_staff_activity(
                user_id=session.get('user_id'),
                action_type='inventory_update',
                action_description=f'تحديث مخزون: {product_name} ({color}, {size}) من {current_quantity} إلى {new_quantity} (تغيير: {quantity_change:+d})',
                target_type='product_variant',
                target_id=product_id,
                target_name=f"{product_name} - {color} - {size}",
                old_value=f"Quantity: {current_quantity}",
                new_value=f"Quantity: {new_quantity} (Change: {quantity_change:+d})",
                ip_address=request.remote_addr,
                user_agent=request.headers.get('User-Agent', '')
            )
            
            return jsonify({
                "success": True, 
                "message": f"تم تحديث المخزون إلى {new_quantity}",
                "new_quantity": new_quantity
            })
        else:
            return jsonify({"success": False, "message": "فشل في تحديث المخزون"})
        
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

# NEW: Export inventory to Excel
@dashboard_bp.route('/export/inventory/excel')
@login_required
@permission_required('manage_products')
def export_inventory_excel():
    try:
        filtered_inventory = get_filtered_inventory()
        
        # Create DataFrame for export
        data = []
        for category, products in filtered_inventory.items():
            for product in products:
                for variant in product.get('variants', []):
                    data.append({
                        'الفئة': category,
                        'اسم المنتج': product.get('name', ''),
                        'رقم الموديل': product.get('model_number', ''),
                        'السعر': product.get('price', 0),
                        'الوصف': product.get('description', ''),
                        'اللون': variant.get('color', ''),
                        'المقاس': variant.get('size', ''),
                        'الكمية': variant.get('quantity', 0),
                        'مسار الصورة': variant.get('image_path', '')
                    })
        
        df = pd.DataFrame(data)
        
        # Create Excel file in memory
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='المخزون', index=False)
            
            # Auto-adjust column widths
            worksheet = writer.sheets['المخزون']
            for idx, col in enumerate(df.columns):
                max_len = max(df[col].astype(str).str.len().max(), len(col)) + 2
                worksheet.column_dimensions[chr(65 + idx)].width = max_len
        
        output.seek(0)
        
        timestamp = datetime.now().strftime("%Y%m%d")
        filename = f"inventory_report_{timestamp}.xlsx"
        
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=filename
        )
        
    except Exception as e:
        print(f"❌ Error exporting inventory: {e}")
        flash('حدث خطأ أثناء تصدير البيانات', 'error')
        return redirect(url_for('dashboard.inventory_page'))

# NEW: Export inventory to CSV
@dashboard_bp.route('/export/inventory/csv')
@login_required
@permission_required('manage_products')
def export_inventory_csv():
    try:
        filtered_inventory = get_filtered_inventory()
        
        # Create CSV in memory
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow(['الفئة', 'اسم المنتج', 'رقم الموديل', 'السعر', 'الوصف', 'اللون', 'المقاس', 'الكمية'])
        
        # Write data
        for category, products in filtered_inventory.items():
            for product in products:
                for variant in product.get('variants', []):
                    writer.writerow([
                        category,
                        product.get('name', ''),
                        product.get('model_number', ''),
                        product.get('price', 0),
                        product.get('description', ''),
                        variant.get('color', ''),
                        variant.get('size', ''),
                        variant.get('quantity', 0)
                    ])
        
        output.seek(0)
        
        timestamp = datetime.now().strftime("%Y%m%d")
        filename = f"inventory_report_{timestamp}.csv"
        
        return send_file(
            io.BytesIO(output.getvalue().encode('utf-8-sig')),
            mimetype='text/csv; charset=utf-8-sig',
            as_attachment=True,
            download_name=filename
        )
        
    except Exception as e:
        print(f"❌ Error exporting inventory CSV: {e}")
        flash('حدث خطأ أثناء تصدير البيانات', 'error')
        return redirect(url_for('dashboard.inventory_page'))

# NEW: API for low stock items
@dashboard_bp.route('/api/inventory/low_stock')
@login_required
@permission_required('manage_products')
def api_low_stock():
    try:
        threshold = int(request.args.get('threshold', 10))
        products_data = get_filtered_inventory()
        
        low_stock_items = []
        for category, products in products_data.items():
            for product in products:
                for variant in product.get('variants', []):
                    if 0 < variant.get('quantity', 0) <= threshold:
                        low_stock_items.append({
                            'product_name': product['name'],
                            'model_number': product.get('model_number', ''),
                            'category': category,
                            'color': variant.get('color', ''),
                            'size': variant.get('size', ''),
                            'current_stock': variant.get('quantity', 0)
                        })
        
        return jsonify({
            'success': True,
            'low_stock_items': low_stock_items
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        })

# Bulk Operations Routes
@dashboard_bp.route('/bulk_update_inventory', methods=['POST'])
@login_required
@permission_required('manage_products')
def bulk_update_inventory():
    try:
        selected_products = request.form.getlist('selected_products')
        operation = request.form.get('operation', 'set')
        value = int(request.form.get('value', 0))
        
        updated_count = 0
        
        for product_str in selected_products:
            try:
                # Format: "product_id:color:size"
                parts = product_str.split(':')
                if len(parts) == 3:
                    product_id = int(parts[0])
                    color = parts[1]
                    size = parts[2]
                    
                    # Get current quantity
                    product = db.get_product_by_id(product_id)
                    if product:
                        for variant in product.get('variants', []):
                            if variant['color'] == color and variant['size'] == size:
                                current_quantity = variant['quantity']
                                
                                if operation == 'set':
                                    new_quantity = value
                                elif operation == 'add':
                                    new_quantity = current_quantity + value
                                elif operation == 'subtract':
                                    new_quantity = max(0, current_quantity - value)
                                else:
                                    new_quantity = current_quantity
                                
                                # Update in database
                                product_name = product.get('name', 'Unknown')
                                if db.update_variant_quantity(product_id, color, size, new_quantity, reason=f"Bulk {operation} by {session.get('username', 'unknown')}"):
                                    # ✅ ENHANCED: Log bulk inventory update
                                    db.log_staff_activity(
                                        user_id=session.get('user_id'),
                                        action_type='inventory_bulk_update',
                                        action_description=f'تحديث جماعي للمخزون: {product_name} ({color}, {size}) - العملية: {operation} - من {current_quantity} إلى {new_quantity}',
                                        target_type='product_variant',
                                        target_id=product_id,
                                        target_name=f"{product_name} - {color} - {size}",
                                        old_value=f"Quantity: {current_quantity}, Operation: {operation}",
                                        new_value=f"Quantity: {new_quantity}, Value: {value}",
                                        ip_address=request.remote_addr,
                                        user_agent=request.headers.get('User-Agent', '')
                                    )
                                    updated_count += 1
            except Exception as e:
                print(f"❌ Error updating product {product_str}: {e}")
                continue
        
        flash(f'تم تحديث {updated_count} منتج بنجاح', 'success')
        
    except Exception as e:
        print(f"❌ Error in bulk update: {e}")
        flash('حدث خطأ أثناء التحديث الجماعي', 'error')
    
    return redirect(url_for('dashboard.products_page'))