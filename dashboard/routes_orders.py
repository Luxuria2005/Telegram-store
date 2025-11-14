# dashboard/routes_orders.py - Order management routes (FIXED)
from flask import render_template, request, jsonify, redirect, url_for, flash, session, send_file
import io
import pandas as pd
from datetime import datetime
from . import dashboard_bp
from .utils import (
    login_required, permission_required, get_accessible_sidebar_items, 
    has_permission, ARABIC_TEXTS, load_orders, safe_get,
    generate_barcode, generate_qr_code, send_order_status_notification
)
from database import db

# ✅ UPDATED: All orders route to pass permissions
@dashboard_bp.route('/all-orders')
@login_required
@permission_required('view_orders')
def all_orders_page():
    orders_data = load_orders()
    orders_list = orders_data.get('orders', [])
    
    # Filter orders by all criteria
    status_filter = request.args.get('status', 'all')
    state_filter = request.args.get('state', 'all')
    region_filter = request.args.get('region', 'all')
    order_number_filter = request.args.get('order_number', '')  # ✅ NEW: Order number filter
    
    safe_orders = []
    for order in orders_list:  # This now shows newest orders first
        safe_order = {
            'id': safe_get(order, 'id', 0),
            'user_name': safe_get(order, 'user_name', 'غير معروف'),
            'user_phone': safe_get(order, 'user_phone', ''),
            'user_address': safe_get(order, 'user_address', ''),
            'user_state': safe_get(order, 'user_state', ''),
            'user_region': safe_get(order, 'user_region', ''),
            'order_date': safe_get(order, 'order_date', 'تاريخ غير معروف'),
            'status': safe_get(order, 'status', 'معلق'),
            'total_amount': safe_get(order, 'total_amount', 0),
            'items': safe_get(order, 'items', [])
        }
        safe_orders.append(safe_order)
    
    # ✅ ENHANCED: Apply all filters
    filtered_orders = safe_orders
    
    # Apply order number filter
    if order_number_filter:
        try:
            order_id = int(order_number_filter)
            filtered_orders = [order for order in filtered_orders if order['id'] == order_id]
        except ValueError:
            # If order number is not valid, show no results
            filtered_orders = []
    
    # Apply status filter
    if status_filter != 'all':
        filtered_orders = [order for order in filtered_orders if order['status'].lower() == status_filter.lower()]
    
    # Apply state filter
    if state_filter != 'all':
        filtered_orders = [order for order in filtered_orders if order['user_state'] and order['user_state'].lower() == state_filter.lower()]
    
    # Apply region filter
    if region_filter != 'all':
        filtered_orders = [order for order in filtered_orders if order['user_region'] and order['user_region'].lower() == region_filter.lower()]
    
    # Calculate stats for all orders page
    total_orders = len(filtered_orders)
    pending_orders = len([o for o in filtered_orders if str(o.get('status', '')).lower() in ['معلق', 'pending']])
    completed_orders = len([o for o in filtered_orders if str(o.get('status', '')).lower() in ['مكتمل', 'completed', 'delivered', 'تم التوصيل', 'تم الشحن', 'shipped']])
    total_revenue = sum(order['total_amount'] for order in filtered_orders)
    
    # Get unique states and regions for filters
    states = sorted(list(set([order['user_state'] for order in safe_orders if order['user_state']])))
    regions = sorted(list(set([order['user_region'] for order in safe_orders if order['user_region']])))
    
    # Get accessible sidebar items
    sidebar_items = get_accessible_sidebar_items()
    
    # ✅ ADDED: Pass user permissions to template
    user_permissions = session.get('permissions', {})
    
    return render_template('all_orders.html', 
                         orders=filtered_orders, 
                         stats={
                             'total_orders': total_orders,
                             'pending_orders': pending_orders,
                             'completed_orders': completed_orders,
                             'total_revenue': total_revenue
                         },
                         current_filter=status_filter,
                         current_state=state_filter,
                         current_region=region_filter,
                         states=states,
                         regions=regions,
                         sidebar_items=sidebar_items,
                         user_role=session.get('role'),
                         user_permissions=user_permissions,
                         user_full_name=session.get('full_name'),
                         can_change_status=has_permission('change_order_status'),
                         can_delete_orders=(session.get('role') == 'admin'),
                         texts=ARABIC_TEXTS)

# ✅ ENHANCED: Update Order Status Route - WITH TELEGRAM NOTIFICATIONS
@dashboard_bp.route('/update_order_status', methods=['POST'])
@login_required
@permission_required('change_order_status')
def update_order_status():
    try:
        order_id = int(request.form.get('order_id', 0))
        new_status = request.form.get('status', 'معلق')
        
        # Get order details before updating
        order = db.get_order_by_id(order_id)
        if not order:
            return jsonify({"success": False, "message": "لم يتم العثور على الطلب"})
        
        old_status = order.get('status', 'معلق')
        
        # Update order status in database
        success = db.update_order_status(order_id, new_status)
        
        if success:
            # ✅ NEW: Log staff activity
            db.log_staff_activity(
                user_id=session.get('user_id'),
                action_type='order_status_update',
                action_description=f'تحديث حالة الطلب #{order_id} من {old_status} إلى {new_status}',
                target_type='order',
                target_id=order_id,
                target_name=f'Order #{order_id}',
                old_value=old_status,
                new_value=new_status,
                ip_address=request.remote_addr,
                user_agent=request.headers.get('User-Agent', '')
            )
            
            # ✅ NEW: Send Telegram notification to customer
            try:
                send_order_status_notification(order_id, old_status, new_status)
            except Exception as e:
                print(f"⚠️ Failed to send notification: {e}")
            
            return jsonify({"success": True, "message": f"تم تحديث الطلب #{order_id} إلى {new_status}"})
        else:
            return jsonify({"success": False, "message": "لم يتم العثور على الطلب"})
            
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

# ✅ FIXED: Delete Order Route - WITH STATUS VALIDATION AND INVENTORY RESTORATION
@dashboard_bp.route('/delete_order/<int:order_id>')
@login_required
@permission_required('delete_orders')
def delete_order(order_id):
    """Delete an order with proper error handling"""
    try:
        print(f"🔄 Starting delete process for order #{order_id}")
        
        # ✅ NEW: Get order info before deleting for logging
        order = db.get_order_by_id(order_id)
        order_info = f"Order #{order_id}" if order else f"Order #{order_id}"
        
        # Call the database method
        result = db.delete_order(order_id)
        
        # Handle the result
        if result.get('success'):
            # ✅ NEW: Log staff activity
            db.log_staff_activity(
                user_id=session.get('user_id'),
                action_type='order_delete',
                action_description=f'حذف الطلب #{order_id}',
                target_type='order',
                target_id=order_id,
                target_name=order_info,
                ip_address=request.remote_addr,
                user_agent=request.headers.get('User-Agent', '')
            )
            flash(f'✅ {result.get("message", "تم حذف الطلب بنجاح")}', 'success')
        else:
            # Check if it's a status-based rejection
            if result.get('can_delete') is False:
                flash(f'⚠️ {result.get("message", "لا يمكن حذف هذا الطلب")}', 'warning')
            else:
                flash(f'❌ {result.get("message", "حدث خطأ أثناء حذف الطلب")}', 'error')
                
    except Exception as e:
        print(f"💥 CRITICAL ERROR in delete_order route: {e}")
        import traceback
        traceback.print_exc()
        flash('حدث خطأ غير متوقع أثناء حذف الطلب', 'error')
    
    return redirect(url_for('dashboard.all_orders_page'))

# FIXED: Print Invoice Route - WITH ENHANCED BARCODE GENERATION
@dashboard_bp.route('/print_invoice/<int:order_id>')
@login_required
@permission_required('print_invoices')
def print_invoice(order_id):
    try:
        order = db.get_order_by_id(order_id)
        if not order:
            flash('الطلب غير موجود', 'error')
            return redirect(url_for('dashboard.all_orders_page'))
        
        print(f"🔄 Processing invoice for order #{order_id}")
        print(f"📦 Order items: {order.get('items', [])}")
        
        # FIXED: Get product details for each item in the order
        order_items_with_details = []
        for item in order.get('items', []):
            print(f"🔍 Processing item: {item}")
            
            # Get product from database - FIXED: Use correct product ID
            product_id = item.get('product_id')
            print(f"📊 Looking for product ID: {product_id}")
            
            product = db.get_product_by_id(product_id)
            print(f"📊 Product from DB: {product}")
            
            item_with_details = item.copy()
            
            # FIX: Use the product name from the ITEM first (from order), then from product DB
            # The item should already have the product name stored when the order was created
            product_name = item.get('name')
            if not product_name and product:
                product_name = product.get('name', 'غير معروف')
            elif not product_name:
                product_name = 'غير معروف'
                
            item_with_details['product_name'] = product_name
            
            # Get model number from product database
            if product:
                model_number = product.get('model_number', 'غير متوفر')
                description = product.get('description', '')
                category = product.get('category', 'غير معروف')
            else:
                model_number = 'غير متوفر'
                description = ''
                category = 'غير معروف'
            
            item_with_details['model_number'] = model_number
            item_with_details['description'] = description
            item_with_details['category'] = category
            
            # ✅ ENHANCED: Generate barcode data for this item with ARABIC HANDLING
            color = item.get('color', '')
            size = item.get('size', '')

            # Get first letter of color (Arabic or English) - CONVERT TO ENGLISH CODE
            color_first_letter = ''
            if color:
                # Remove any spaces and get first character
                clean_color = color.replace(' ', '').replace('_', '')
                if clean_color:
                    color_first_letter = clean_color[0]
                    
                    # ✅ Convert Arabic color first letter to English code
                    arabic_to_english_colors = {
                        'أ': 'A', 'ا': 'A',  # Alif variations
                        'ب': 'B', 'ت': 'T', 'ث': 'TH', 'ج': 'J',
                        'ح': 'H', 'خ': 'KH', 'د': 'D', 'ذ': 'DH',
                        'ر': 'R', 'ز': 'Z', 'س': 'S', 'ش': 'SH',
                        'ص': 'S2', 'ض': 'D2', 'ط': 'T2', 'ظ': 'Z2',
                        'ع': 'A2', 'غ': 'GH', 'ف': 'F', 'ق': 'Q',
                        'ك': 'K', 'ل': 'L', 'م': 'M', 'ن': 'N',
                        'ه': 'H2', 'و': 'W', 'ي': 'Y', 'ى': 'A3',
                        'أسود': 'BLA', 'أبيض': 'WHI', 'أحمر': 'RED',
                        'أزرق': 'BLU', 'أخضر': 'GRE', 'أصفر': 'YEL',
                        'وردي': 'PIN', 'بنفسجي': 'PUR', 'رمادي': 'GRA',
                        'بني': 'BRO'
                    }
                    
                    if color_first_letter in arabic_to_english_colors:
                        color_first_letter = arabic_to_english_colors[color_first_letter]
                    elif clean_color in arabic_to_english_colors:
                        color_first_letter = arabic_to_english_colors[clean_color]

            # Get first letter of size
            size_first_letter = ''
            if size:
                clean_size = size.replace(' ', '').replace('_', '')
                if clean_size:
                    size_first_letter = clean_size[0]

            # Create barcode data - NOW WITH ENGLISH CODES ONLY
            barcode_data = f"{order_id}{model_number}{color_first_letter}{size_first_letter}"

            # Generate barcode
            barcode_image = generate_barcode(barcode_data)

            # ✅ NEW: Generate QR code with complete order information
            qr_content = f"""=== ORDER DETAILS ===
            Order #: {order_id}
            Customer: {order['user_name']}
            Phone: {order['user_phone']}
            Date: {order['order_date'][:10]}
            Status: {order['status']}

            === PRODUCT INFO ===
            Product: {item_with_details['product_name']}
            Model: {model_number}
            Color: {color}, Size: {size}
            Quantity: {item['quantity']}
            Price: {item['price']:,.0f} SYP
            Subtotal: {item['price'] * item['quantity']:,.0f} SYP

            === DELIVERY INFO ===
            Address: {order['user_address']}
            State: {order.get('user_state', 'N/A')}
            Region: {order.get('user_region', 'N/A')}

            === ORDER SUMMARY ===
            Total Items: {len(order['items'])}
            Total Amount: {order['total_amount']:,.0f} SYP
            """

            qr_code_image = generate_qr_code(qr_content)

            item_with_details['barcode_data'] = barcode_data
            item_with_details['barcode_image'] = barcode_image
            item_with_details['qr_code_image'] = qr_code_image
            
            order_items_with_details.append(item_with_details)
            print(f"✅ Processed item: {item_with_details['product_name']} - Model: {item_with_details['model_number']} - Barcode: {barcode_data}")
        
        order['items_with_details'] = order_items_with_details
        
        print(f"🎯 Rendering invoice template with {len(order_items_with_details)} items and ENHANCED barcodes")
        
        return render_template('invoice.html', 
                             order=order, 
                             db=db, 
                             now=datetime.now())
        
    except Exception as e:
        print(f"❌ Error generating invoice: {e}")
        import traceback
        traceback.print_exc()
        flash('حدث خطأ في إنشاء الفاتورة', 'error')
        return redirect(url_for('dashboard.all_orders_page'))

# Print Orders by Status Route
@dashboard_bp.route('/print_orders')
@login_required
@permission_required('print_orders')
def print_orders():
    try:
        status_filter = request.args.get('status', 'all')
        state_filter = request.args.get('state', 'all')
        region_filter = request.args.get('region', 'all')
        
        orders_data = load_orders()
        orders_list = orders_data.get('orders', [])
        
        # Apply status filter
        if status_filter != 'all':
            orders_list = [order for order in orders_list if order.get('status', '').lower() == status_filter.lower()]
        
        # Apply state filter
        if state_filter != 'all':
            orders_list = [order for order in orders_list if order.get('user_state') and order.get('user_state').lower() == state_filter.lower()]
        
        # Apply region filter
        if region_filter != 'all':
            orders_list = [order for order in orders_list if order.get('user_region') and order.get('user_region').lower() == region_filter.lower()]
        
        # ✅ ENHANCED: Get product details for each order WITH BARCODES AND QR CODES
        for order in orders_list:
            order_items_with_details = []
            for item in order.get('items', []):
                product_id = item.get('product_id')
                product = db.get_product_by_id(product_id)
                
                item_with_details = item.copy()
                
                # FIX: Use item name first, then product name
                product_name = item.get('name')
                if not product_name and product:
                    product_name = product.get('name', 'غير معروف')
                elif not product_name:
                    product_name = 'غير معروف'
                    
                item_with_details['product_name'] = product_name
                item_with_details['model_number'] = product.get('model_number', 'غير متوفر') if product else 'غير متوفر'
                item_with_details['description'] = product.get('description', '') if product else ''
                item_with_details['category'] = product.get('category', 'غير معروف') if product else 'غير معروف'
                
                # ✅ NEW: Generate barcode data for this item (SAME AS INVOICE)
                color = item.get('color', '')
                size = item.get('size', '')

                # Get first letter of color (Arabic or English) - CONVERT TO ENGLISH CODE
                color_first_letter = ''
                if color:
                    # Remove any spaces and get first character
                    clean_color = color.replace(' ', '').replace('_', '')
                    if clean_color:
                        color_first_letter = clean_color[0]
                        
                        # ✅ Convert Arabic color first letter to English code
                        arabic_to_english_colors = {
                            'أ': 'A', 'ا': 'A',  # Alif variations
                            'ب': 'B', 'ت': 'T', 'ث': 'TH', 'ج': 'J',
                            'ح': 'H', 'خ': 'KH', 'د': 'D', 'ذ': 'DH',
                            'ر': 'R', 'ز': 'Z', 'س': 'S', 'ش': 'SH',
                            'ص': 'S2', 'ض': 'D2', 'ط': 'T2', 'ظ': 'Z2',
                            'ع': 'A2', 'غ': 'GH', 'ف': 'F', 'ق': 'Q',
                            'ك': 'K', 'ل': 'L', 'م': 'M', 'ن': 'N',
                            'ه': 'H2', 'و': 'W', 'ي': 'Y', 'ى': 'A3',
                            'أسود': 'BLA', 'أبيض': 'WHI', 'أحمر': 'RED',
                            'أزرق': 'BLU', 'أخضر': 'GRE', 'أصفر': 'YEL',
                            'وردي': 'PIN', 'بنفسجي': 'PUR', 'رمادي': 'GRA',
                            'بني': 'BRO'
                        }
                        
                        if color_first_letter in arabic_to_english_colors:
                            color_first_letter = arabic_to_english_colors[color_first_letter]
                        elif clean_color in arabic_to_english_colors:
                            color_first_letter = arabic_to_english_colors[clean_color]

                # Get first letter of size
                size_first_letter = ''
                if size:
                    clean_size = size.replace(' ', '').replace('_', '')
                    if clean_size:
                        size_first_letter = clean_size[0]

                # Create barcode data - NOW WITH ENGLISH CODES ONLY
                barcode_data = f"{order['id']}{item_with_details['model_number']}{color_first_letter}{size_first_letter}"
                
                # Generate barcode
                barcode_image = generate_barcode(barcode_data)

                # ✅ NEW: Generate QR code with complete order information (SAME AS INVOICE)
                qr_content = f"""=== ORDER DETAILS ===
        Order #: {order['id']}
        Customer: {order['user_name']}
        Phone: {order['user_phone']}
        Date: {order['order_date'][:10]}
        Status: {order['status']}

        === PRODUCT INFO ===
        Product: {item_with_details['product_name']}
        Model: {item_with_details['model_number']}
        Color: {color}, Size: {size}
        Quantity: {item['quantity']}
        Price: {item['price']:,.0f} SYP
        Subtotal: {item['price'] * item['quantity']:,.0f} SYP

        === DELIVERY INFO ===
        Address: {order['user_address']}
        State: {order.get('user_state', 'N/A')}
        Region: {order.get('user_region', 'N/A')}

        === ORDER SUMMARY ===
        Total Items: {len(order['items'])}
        Total Amount: {order['total_amount']:,.0f} SYP
        """

                qr_code_image = generate_qr_code(qr_content)
                
                item_with_details['barcode_data'] = barcode_data
                item_with_details['barcode_image'] = barcode_image
                item_with_details['qr_code_image'] = qr_code_image
                
                order_items_with_details.append(item_with_details)
                print(f"✅ Generated barcode and QR for order #{order['id']}: {barcode_data}")
            
            order['items_with_details'] = order_items_with_details
        
        status_name = {
            'all': 'جميع الطلبات',
            'pending': 'الطلبات المعلقة',
            'confirmed': 'الطلبات المؤكدة',
            'shipped': 'الطلبات المشحونة',
            'delivered': 'الطلبات المكتملة',
            'cancelled': 'الطلبات الملغية'
        }.get(status_filter, 'جميع الطلبات')
        
        # Build filter description
        filter_description = status_name
        if state_filter != 'all':
            filter_description += f" - المحافظة: {state_filter}"
        if region_filter != 'all':
            filter_description += f" - المنطقة: {region_filter}"
        
        print(f"🎯 Rendering print_orders with {len(orders_list)} orders and barcodes")
        
        return render_template('print_orders.html', 
                             orders=orders_list, 
                             status_filter=status_filter,
                             state_filter=state_filter,
                             region_filter=region_filter,
                             status_name=filter_description,
                             now=datetime.now())
        
    except Exception as e:
        print(f"❌ Error generating orders print: {e}")
        flash('حدث خطأ في إنشاء صفحة الطباعة', 'error')
        return redirect(url_for('dashboard.all_orders_page'))

# FIXED: API Order Details with Product Info
@dashboard_bp.route('/api/order/<int:order_id>')
@login_required
@permission_required('view_orders')
def get_order_details(order_id):
    try:
        order = db.get_order_by_id(order_id)
        
        if order:
            # FIXED: Add product details to items for the preview
            items_with_details = []
            for item in order.get('items', []):
                product_id = item.get('product_id')
                product = db.get_product_by_id(product_id)
                
                item_with_details = item.copy()
                
                # FIX: Use item name first, then product name
                product_name = item.get('name')
                if not product_name and product:
                    product_name = product.get('name', 'غير معروف')
                elif not product_name:
                    product_name = 'غير معروف'
                    
                item_with_details['product_name'] = product_name
                item_with_details['model_number'] = product.get('model_number', 'غير متوفر') if product else 'غير متوفر'
                
                items_with_details.append(item_with_details)
            
            return jsonify({
                "success": True,
                "order": {
                    'order_id': safe_get(order, 'id'),
                    'user_name': safe_get(order, 'user_name', 'غير معروف'),
                    'user_phone': safe_get(order, 'user_phone', ''),
                    'user_address': safe_get(order, 'user_address', ''),
                    'user_state': safe_get(order, 'user_state', ''),
                    'user_region': safe_get(order, 'user_region', ''),
                    'order_date': safe_get(order, 'order_date', ''),
                    'status': safe_get(order, 'status', 'معلق'),
                    'total_amount': safe_get(order, 'total_amount', 0),
                    'items': items_with_details  # Use the fixed items with product names
                }
            })
        else:
            return jsonify({"success": False, "message": "لم يتم العثور على الطلب"})
            
    except Exception as e:
        print(f"❌ Error in API order details: {e}")
        return jsonify({"success": False, "message": str(e)})

# API Routes
@dashboard_bp.route('/api/orders')
@login_required
@permission_required('view_orders')
def api_orders():
    return jsonify(load_orders())

@dashboard_bp.route('/api/stats')
@login_required
def api_stats():
    orders_data = load_orders()
    products_data = load_products()
    
    orders_list = orders_data.get('orders', [])
    
    total_revenue = 0
    for order in orders_list:
        order_status = str(safe_get(order, 'status', '')).lower()
        if order_status in ['مكتمل', 'completed', 'delivered', 'تم التوصيل', 'تم الشحن', 'shipped']:
            total_revenue += float(safe_get(order, 'total_amount', 0))
    
    stats = {
        "total_orders": len(orders_list),
        "pending_orders": len([o for o in orders_list if str(safe_get(o, 'status', '')).lower() in ['معلق', 'pending']]),
        "completed_orders": len([o for o in orders_list if str(safe_get(o, 'status', '')).lower() in ['مكتمل', 'completed', 'delivered', 'تم التوصيل', 'تم الشحن', 'shipped']]),
        "total_revenue": total_revenue,
        "total_products": sum(len(products) for products in products_data.get('products', {}).values()),
        "total_categories": len(products_data.get('categories', []))
    }
    
    return jsonify(stats)

@dashboard_bp.route('/export_orders')
@login_required
@permission_required('view_orders')
def export_orders():
    try:
        orders_data = load_orders()
        orders_list = orders_data.get('orders', [])
        
        # Create DataFrame for export
        data = []
        for order in orders_list:
            for item in order.get('items', []):
                data.append({
                    'Order ID': order.get('id', ''),
                    'Order Date': order.get('order_date', ''),
                    'Customer Name': order.get('user_name', ''),
                    'Customer Phone': order.get('user_phone', ''),
                    'Customer Address': order.get('user_address', ''),
                    'Customer State': order.get('user_state', ''),
                    'Customer Region': order.get('user_region', ''),
                    'Status': order.get('status', ''),
                    'Product Name': item.get('name', ''),
                    'Color': item.get('color', ''),
                    'Size': item.get('size', ''),
                    'Quantity': item.get('quantity', 0),
                    'Price': item.get('price', 0),
                    'Subtotal': item.get('price', 0) * item.get('quantity', 0),
                    'Total Amount': order.get('total_amount', 0)
                })
        
        df = pd.DataFrame(data)
        
        # Create Excel file in memory
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Orders', index=False)
        
        output.seek(0)
        
        timestamp = datetime.now().strftime("%Y%m%d")
        filename = f"orders_export_{timestamp}.xlsx"
        
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=filename
        )
        
    except Exception as e:
        print(f"❌ Error exporting orders: {e}")
        flash('حدث خطأ أثناء تصدير البيانات', 'error')
        return redirect(url_for('dashboard.all_orders_page'))