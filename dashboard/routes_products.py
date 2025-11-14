# dashboard/routes_products.py - Product management routes (FIXED)
from flask import render_template, request, jsonify, redirect, url_for, flash, session, send_file
import io
import pandas as pd
import csv
from datetime import datetime
import os
from werkzeug.utils import secure_filename
from . import dashboard_bp
from .utils import (
    login_required, permission_required, get_accessible_sidebar_items, 
    has_permission, ARABIC_TEXTS, load_products, get_filtered_inventory,
    allowed_file
)
from database import db

@dashboard_bp.route('/products')
@login_required
@permission_required('view_products')
def products_page():
    # Load products with filtering for out-of-stock items
    products_data = get_filtered_inventory()  # This now only returns products with available variants
    
    # Debug: Print image paths and product counts
    total_products = 0
    for category, products in products_data.items():
        total_products += len(products)
        print(f"📦 Category: {category} - {len(products)} products")
        for product in products:
            print(f"   ✅ Available Product: {product['name']} - Model: {product.get('model_number', 'N/A')}")
            for variant in product.get('variants', []):
                print(f"      🎨 {variant['color']} - {variant['size']}: {variant.get('quantity', 0)} - {variant.get('image_path', 'No image')}")
    
    print(f"🎯 Total available products: {total_products}")
    
    # Get accessible sidebar items
    sidebar_items = get_accessible_sidebar_items()
    
    # ✅ ADDED: Pass user permissions to template
    user_permissions = session.get('permissions', {})
    
    return render_template('products.html', 
                         products=products_data,
                         categories=products_data.keys(),
                         sidebar_items=sidebar_items,
                         user_role=session.get('role'),
                         user_permissions=user_permissions,  # ✅ ADD THIS
                         user_full_name=session.get('full_name'),
                         texts=ARABIC_TEXTS)

# ✅ NEW: Bulk Prices Management Route
@dashboard_bp.route('/bulk-prices')
@login_required
@permission_required('manage_products')
def bulk_prices_page():
    """Bulk price management page"""
    try:
        products_data = load_products()
        
        # Get accessible sidebar items
        sidebar_items = get_accessible_sidebar_items()
        
        # ✅ ADDED: Pass user permissions to template
        user_permissions = session.get('permissions', {})
        
        # Prepare products data for the template
        products_by_category = {}
        for category, products in products_data.get('products', {}).items():
            products_by_category[category] = []
            for product in products:
                products_by_category[category].append({
                    'id': product['id'],
                    'name': product['name'],
                    'price': product['price'],
                    'model_number': product.get('model_number', '')
                })
        
        return render_template('bulk_prices.html', 
                             products=products_by_category,
                             categories=products_data.get('categories', []),
                             sidebar_items=sidebar_items,
                             user_role=session.get('role'),
                             user_permissions=user_permissions,
                             user_full_name=session.get('full_name'),
                             texts=ARABIC_TEXTS)
        
    except Exception as e:
        print(f"❌ Error loading bulk prices page: {e}")
        flash('حدث خطأ في تحميل صفحة إدارة الأسعار', 'error')
        return redirect(url_for('dashboard.products_page'))

# ✅ NEW: API Endpoint for Products by Category
@dashboard_bp.route('/api/products/by_category/<category>')
@login_required
@permission_required('view_products')
def get_products_by_category(category):
    """API endpoint to get products by category"""
    try:
        products_data = load_products()
        category_products = products_data.get('products', {}).get(category, [])
        
        # Format products for the API response
        formatted_products = []
        for product in category_products:
            formatted_products.append({
                'id': product['id'],
                'name': product['name'],
                'price': product['price'],
                'model_number': product.get('model_number', ''),
                'description': product.get('description', '')
            })
        
        return jsonify({
            'success': True,
            'products': formatted_products
        })
        
    except Exception as e:
        print(f"❌ Error getting products by category: {e}")
        return jsonify({
            'success': False,
            'message': 'حدث خطأ في جلب المنتجات'
        })

# ✅ NEW: API Endpoint for Bulk Price Updates
@dashboard_bp.route('/api/update_bulk_prices', methods=['POST'])
@login_required
@permission_required('manage_products')
def update_bulk_prices():
    """API endpoint to update prices in bulk"""
    try:
        data = request.get_json()
        product_ids = data.get('product_ids', [])
        operation = data.get('operation')
        value = data.get('value', 0)
        currency_rate = data.get('currency_rate', 1)
        
        print(f"🔄 Bulk price update: {len(product_ids)} products, operation: {operation}, value: {value}")
        
        if not product_ids:
            return jsonify({
                'success': False,
                'message': 'لم يتم اختيار أي منتجات'
            })
        
        success_count = 0
        errors = []
        
        for product_id in product_ids:
            try:
                # Get current product
                product = db.get_product_by_id(product_id)
                if not product:
                    errors.append(f"المنتج {product_id} غير موجود")
                    continue
                
                current_price = product['price']
                new_price = current_price
                
                # Calculate new price based on operation
                if operation == 'percentage_increase':
                    new_price = current_price * (1 + value/100)
                elif operation == 'percentage_decrease':
                    new_price = current_price * (1 - value/100)
                elif operation == 'set':
                    new_price = value
                elif operation == 'currency_conversion':
                    new_price = current_price * currency_rate
                
                # Round to 2 decimal places
                new_price = round(new_price, 2)
                
                # Update product price in database
                success = db.update_product_price(product_id, new_price)
                if success:
                    success_count += 1
                    print(f"✅ Updated product {product_id}: {current_price} → {new_price}")
                else:
                    errors.append(f"فشل في تحديث سعر المنتج {product_id}")
                    
            except Exception as e:
                errors.append(f"خطأ في المنتج {product_id}: {str(e)}")
                print(f"❌ Error updating product {product_id}: {e}")
        
        message = f"تم تحديث أسعار {success_count} منتج بنجاح"
        if errors:
            message += f" مع {len(errors)} أخطاء"
        
        return jsonify({
            'success': True,
            'message': message,
            'updated_count': success_count,
            'errors': errors
        })
        
    except Exception as e:
        print(f"❌ Error in bulk price update: {e}")
        return jsonify({
            'success': False,
            'message': f'حدث خطأ في تحديث الأسعار: {str(e)}'
        })

# ✅ UPDATED: Add product route - Only for users with manage_products permission
@dashboard_bp.route('/add-product')
@login_required
@permission_required('manage_products')
def add_product_page():
    products_data = load_products()
    
    # Get accessible sidebar items
    sidebar_items = get_accessible_sidebar_items()
    
    # ✅ ADDED: Pass user permissions to template
    user_permissions = session.get('permissions', {})
    
    return render_template('add_product.html', 
                         categories=products_data.get('categories', []),
                         sidebar_items=sidebar_items,
                         user_role=session.get('role'),
                         user_permissions=user_permissions,  # ✅ ADD THIS
                         user_full_name=session.get('full_name'),
                         texts=ARABIC_TEXTS)

# FIXED: Add product route with proper image path handling
@dashboard_bp.route('/add_product', methods=['POST'])
@login_required
@permission_required('manage_products')
def add_product_route():
    try:
        category = request.form.get('category', '').strip()
        name = request.form.get('name', '').strip()
        price = float(request.form.get('price', 0))
        description = request.form.get('description', '').strip()
        model_number = request.form.get('model_number', '').strip()
        
        # Validate required fields
        if not category or not name or price <= 0:
            flash('يرجى ملء جميع الحقول المطلوبة بشكل صحيح', 'error')
            return redirect(url_for('dashboard.add_product_page'))
        
        # Add product to database
        product_id = db.add_product(category, name, price, description, model_number)
        
        if not product_id:
            flash('فشل في إضافة المنتج', 'error')
            return redirect(url_for('dashboard.add_product_page'))
        
        # Add variants - FIXED IMAGE PATH HANDLING
        variant_count = int(request.form.get('variant_count', 0))
        variants_added = 0
        
        for i in range(variant_count):
            color = request.form.get(f'color_{i}', '').strip()
            
            if not color:  # Skip if no color name
                continue
                
            # Handle image uploads - FIXED PATH HANDLING
            image_path = None
            image_files = request.files.getlist(f'variant_images_{i}')
            
            # Take only the first image for this color
            for image_file in image_files:
                if image_file and allowed_file(image_file.filename):
                    # Create proper directory structure
                    safe_category = secure_filename(category)
                    safe_product = secure_filename(name)
                    safe_color = secure_filename(color)
                    
                    # Create directories
                    variant_folder = os.path.join('products', safe_category, safe_product, safe_color)
                    os.makedirs(variant_folder, exist_ok=True)
                    
                    # Generate unique filename
                    timestamp = datetime.now().strftime("%Y%m%d")
                    file_extension = image_file.filename.rsplit('.', 1)[1].lower() if '.' in image_file.filename else 'jpg'
                    filename = f"{safe_product}_{safe_color}_{timestamp}.{file_extension}"
                    filepath = os.path.join(variant_folder, filename)
                    
                    image_file.save(filepath)
                    
                    # FIX: Store relative path for web access - CORRECT FORMAT
                    image_path = f"{safe_category}/{safe_product}/{safe_color}/{filename}"
                    print(f"🖼️ Saved image to: {image_path}")
                    break  # Only save one image per color
            
            # Add all sizes for this color
            for j, size in enumerate(['S', 'M', 'L', 'XL', 'XXL', 'XXXL']):
                quantity_str = request.form.get(f'quantity_{i}_{j}', '0')
                
                try:
                    quantity = int(quantity_str) if quantity_str else 0
                except ValueError:
                    quantity = 0
                
                # Add variant to database with ONE IMAGE PER COLOR
                variant_id = db.add_product_variant(product_id, color, size, quantity, image_path=image_path)
                
                if variant_id:
                    variants_added += 1
                    print(f"✅ Added variant: {color} - {size} - Qty: {quantity} - Image: {image_path}")
        
        if variants_added > 0:
            # ✅ NEW: Log staff activity
            db.log_staff_activity(
                user_id=session.get('user_id'),
                action_type='product_add',
                action_description=f'إضافة منتج جديد: {name}',
                target_type='product',
                target_id=product_id,
                target_name=name,
                ip_address=request.remote_addr,
                user_agent=request.headers.get('User-Agent', '')
            )
            flash(f'تم إضافة المنتج بنجاح مع {variants_added} متغير', 'success')
        else:
            # If no variants were added, delete the product
            db.delete_product(product_id)
            flash('يجب إضافة至少 متغير واحد للمنتج', 'error')
        
    except Exception as e:
        print(f"❌ Error adding product: {e}")
        flash(f'حدث خطأ أثناء إضافة المنتج: {str(e)}', 'error')
    
    return redirect(url_for('dashboard.products_page'))

# Edit Product Route
@dashboard_bp.route('/edit_product/<category>/<int:product_id>')
@login_required
@permission_required('manage_products')
def edit_product_page(category, product_id):
    try:
        # Get product from database
        product = db.get_product_by_id(product_id)
        
        if not product:
            flash('المنتج غير موجود', 'error')
            return redirect(url_for('dashboard.products_page'))
        
        products_data = load_products()
        
        # Get accessible sidebar items
        sidebar_items = get_accessible_sidebar_items()
        
        # ✅ ADDED: Pass user permissions to template
        user_permissions = session.get('permissions', {})
        
        return render_template('edit_product.html', 
                             product=product,
                             category=category,
                             categories=products_data.get('categories', []),
                             sidebar_items=sidebar_items,
                             user_role=session.get('role'),
                             user_permissions=user_permissions,  # ✅ ADD THIS
                             user_full_name=session.get('full_name'),
                             texts=ARABIC_TEXTS)
        
    except Exception as e:
        print(f"❌ Error loading product for editing: {e}")
        flash('حدث خطأ في تحميل بيانات المنتج', 'error')
        return redirect(url_for('dashboard.products_page'))

# FIXED: Update Product Route - ONLY ONE DEFINITION
# FIXED: Update Product Route - Preserve existing images
@dashboard_bp.route('/update_product', methods=['POST'])
@login_required
@permission_required('manage_products')
def update_product_route():
    try:
        category = request.form.get('category', '')
        product_id = int(request.form.get('product_id', 0))
        name = request.form.get('name', '')
        price = float(request.form.get('price', 0))
        description = request.form.get('description', '')
        model_number = request.form.get('model_number', '')
        
        print(f"🔄 Updating product {product_id}: {name}")
        
        # Update product basic info
        success = db.update_product(
            product_id=product_id,
            name=name,
            price=price,
            description=description,
            model_number=model_number
        )
        
        if not success:
            flash('فشل في تحديث المنتج', 'error')
            return redirect(url_for('dashboard.products_page'))
        
        # Handle variants update - PRESERVE EXISTING IMAGES
        variant_count = int(request.form.get('variant_count', 0))
        print(f"🔄 Processing {variant_count} variants")
        
        # Get current product data to preserve existing images
        current_product = db.get_product_by_id(product_id)
        existing_variants = current_product.get('variants', [])
        
        # Create a mapping of existing images by color
        existing_images = {}
        for variant in existing_variants:
            if variant.get('image_path') and variant['image_path'] not in ['None', 'null', '']:
                existing_images[variant['color']] = variant['image_path']
        
        # Delete all existing variants first
        for variant in existing_variants:
            db.delete_product_variant(product_id, variant['color'], variant['size'])
        
        # Add new variants - PRESERVE EXISTING IMAGES IF NO NEW IMAGE UPLOADED
        variants_added = 0
        for i in range(variant_count):
            color = request.form.get(f'color_{i}', '').strip()
            
            if not color:  # Skip if no color name
                continue
                
            # Handle image uploads - PRESERVE EXISTING IF NO NEW UPLOAD
            image_path = None
            image_files = request.files.getlist(f'variant_images_{i}')
            
            # Check if new image was uploaded
            new_image_uploaded = False
            for image_file in image_files:
                if image_file and allowed_file(image_file.filename):
                    try:
                        # Create proper directory structure
                        safe_category = secure_filename(category)
                        safe_product = secure_filename(name)
                        safe_color = secure_filename(color)
                        
                        # Create directories
                        variant_folder = os.path.join('products', safe_category, safe_product, safe_color)
                        os.makedirs(variant_folder, exist_ok=True)
                        
                        # Generate unique filename
                        timestamp = datetime.now().strftime("%Y%m%d")
                        file_extension = image_file.filename.rsplit('.', 1)[1].lower() if '.' in image_file.filename else 'jpg'
                        filename = f"{safe_product}_{safe_color}_{timestamp}.{file_extension}"
                        filepath = os.path.join(variant_folder, filename)
                        
                        image_file.save(filepath)
                        
                        # Store relative path for web access
                        image_path = f"{safe_category}/{safe_product}/{safe_color}/{filename}"
                        print(f"🖼️ Saved NEW image to: {image_path}")
                        new_image_uploaded = True
                        break  # Only save one image per color
                    except Exception as e:
                        print(f"❌ Error saving new image: {e}")
                        continue
            
            # If no new image uploaded, use existing image for this color
            if not new_image_uploaded and color in existing_images:
                image_path = existing_images[color]
                print(f"🖼️ Preserving existing image for {color}: {image_path}")
            
            # Add all sizes for this color
            for j, size in enumerate(['S', 'M', 'L', 'XL', 'XXL', 'XXXL']):
                quantity_str = request.form.get(f'quantity_{i}_{j}', '0')
                
                try:
                    quantity = int(quantity_str) if quantity_str else 0
                except ValueError:
                    quantity = 0
                
                # Add variant to database with preserved or new image
                variant_id = db.add_product_variant(product_id, color, size, quantity, image_path=image_path)
                
                if variant_id:
                    variants_added += 1
                    print(f"✅ Added variant: {color} - {size} - Qty: {quantity} - Image: {image_path}")
        
        # ✅ ENHANCED: Log staff activity with detailed field changes
        if success:
            old_product = current_product
            changes = []
            
            # Track individual field changes
            if old_product.get('name', '') != name:
                changes.append(f"الاسم: '{old_product.get('name', '')}' → '{name}'")
            if float(old_product.get('price', 0)) != float(price):
                changes.append(f"السعر: {old_product.get('price', 0)} → {price}")
            if old_product.get('description', '') != description:
                changes.append(f"الوصف: تم التعديل")
            if old_product.get('model_number', '') != model_number:
                changes.append(f"رقم الموديل: '{old_product.get('model_number', '')}' → '{model_number}'")
            
            # Track variant changes
            old_variants_count = len(existing_variants)
            if old_variants_count != variants_added:
                changes.append(f"المتغيرات: {old_variants_count} → {variants_added}")
            
            detailed_description = f"تحديث منتج: {name}"
            if changes:
                detailed_description += f" | التغييرات: {', '.join(changes)}"
            
            old_value = f"Name: {old_product.get('name', '')}, Price: {old_product.get('price', 0)}, Variants: {old_variants_count}"
            new_value = f"Name: {name}, Price: {price}, Variants: {variants_added}"
            
            db.log_staff_activity(
                user_id=session.get('user_id'),
                action_type='product_update',
                action_description=detailed_description,
                target_type='product',
                target_id=product_id,
                target_name=name,
                old_value=old_value,
                new_value=new_value,
                ip_address=request.remote_addr,
                user_agent=request.headers.get('User-Agent', '')
            )
        
        flash(f'تم تحديث المنتج بنجاح مع {variants_added} متغير', 'success')
        print(f"✅ Product {product_id} updated successfully with {variants_added} variants")
        
    except Exception as e:
        print(f"❌ Error updating product: {e}")
        flash(f'حدث خطأ: {str(e)}', 'error')
    
    return redirect(url_for('dashboard.products_page'))

# Delete Product Route
@dashboard_bp.route('/delete_product/<category>/<int:product_id>')
@login_required
@permission_required('manage_products')
def delete_product(category, product_id):
    try:
        # ✅ NEW: Get product info before deleting for logging
        product = db.get_product_by_id(product_id)
        product_name = product.get('name', 'Unknown') if product else 'Unknown'
        
        success = db.delete_product(product_id)
        
        if success:
            # ✅ NEW: Log staff activity
            db.log_staff_activity(
                user_id=session.get('user_id'),
                action_type='product_delete',
                action_description=f'حذف منتج: {product_name}',
                target_type='product',
                target_id=product_id,
                target_name=product_name,
                ip_address=request.remote_addr,
                user_agent=request.headers.get('User-Agent', '')
            )
            flash('تم حذف المنتج بنجاح', 'success')
        else:
            flash('فشل في حذف المنتج', 'error')
            
    except Exception as e:
        print(f"❌ Error deleting product: {e}")
        flash('حدث خطأ أثناء حذف المنتج', 'error')
    
    return redirect(url_for('dashboard.products_page'))

# Delete Variant Route
@dashboard_bp.route('/delete_variant', methods=['POST'])
@login_required
@permission_required('manage_products')
def delete_variant():
    try:
        product_id = int(request.form.get('product_id', 0))
        color = request.form.get('color', '')
        size = request.form.get('size', '')
        
        success = db.delete_product_variant(product_id, color, size)
        
        if success:
            return jsonify({"success": True, "message": "تم حذف المتغير بنجاح"})
        else:
            return jsonify({"success": False, "message": "فشل في حذف المتغير"})
            
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

# Delete variant image route
@dashboard_bp.route('/delete_variant_image', methods=['POST'])
@login_required
@permission_required('manage_products')
def delete_variant_image():
    try:
        category = request.form.get('category', '')
        product_id = int(request.form.get('product_id', 0))
        color = request.form.get('color', '')
        size = request.form.get('size', '')
        image_path = request.form.get('image_path', '')
        
        # Get variant ID
        variant_id = db.get_variant_id(product_id, color, size)
        
        if variant_id:
            # Delete the specific image
            success = db.delete_variant_images(variant_id)
            
            if success:
                # Also delete the physical file
                if os.path.exists(image_path):
                    os.remove(image_path)
                
                return jsonify({"success": True, "message": "تم حذف الصورة بنجاح"})
        
        return jsonify({"success": False, "message": "فشل في حذف الصورة"})
        
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

# Category Management Route
@dashboard_bp.route('/add_category', methods=['POST'])
@login_required
@permission_required('manage_products')
def add_category():
    try:
        category_name = request.form.get('category', '').strip().lower()
        
        if not category_name:
            flash('يرجى إدخال اسم الفئة', 'error')
            return redirect(url_for('dashboard.add_product_page'))
        
        # Add category to database
        category_id = db.add_category(category_name)
        
        if category_id:
            flash('تم إضافة الفئة بنجاح', 'success')
        else:
            flash('الفئة موجودة مسبقاً', 'info')
            
    except Exception as e:
        print(f"❌ Error adding category: {e}")
        flash(f'حدث خطأ أثناء إضافة الفئة: {str(e)}', 'error')
    
    return redirect(url_for('dashboard.add_product_page'))

# Search and Filter Routes
@dashboard_bp.route('/search_products')
@login_required
@permission_required('view_products')
def search_products():
    try:
        query = request.args.get('q', '').strip()
        category_filter = request.args.get('category', 'all')
        
        products_data = load_products()
        filtered_products = {}
        
        for category, products in products_data.get('products', {}).items():
            if category_filter != 'all' and category != category_filter:
                continue
                
            category_products = []
            for product in products:
                # Search in product name, description, and model number
                if (query.lower() in product.get('name', '').lower() or 
                    query.lower() in product.get('description', '').lower() or 
                    query.lower() in product.get('model_number', '').lower()):
                    category_products.append(product)
            
            if category_products:
                filtered_products[category] = category_products
        
        # Get accessible sidebar items
        sidebar_items = get_accessible_sidebar_items()
        
        # ✅ ADDED: Pass user permissions to template
        user_permissions = session.get('permissions', {})
        
        return render_template('products.html', 
                             products=filtered_products,
                             categories=products_data.get('categories', []),
                             search_query=query,
                             selected_category=category_filter,
                             sidebar_items=sidebar_items,
                             user_role=session.get('role'),
                             user_permissions=user_permissions,  # ✅ ADD THIS
                             user_full_name=session.get('full_name'),
                             texts=ARABIC_TEXTS)
        
    except Exception as e:
        print(f"❌ Error searching products: {e}")
        flash('حدث خطأ أثناء البحث', 'error')
        return redirect(url_for('dashboard.products_page'))

# Export Data Routes
@dashboard_bp.route('/export_products')
@login_required
@permission_required('manage_products')
def export_products():
    try:
        products_data = load_products()
        
        # Create DataFrame for export
        data = []
        for category, products in products_data.get('products', {}).items():
            for product in products:
                for variant in product.get('variants', []):
                    data.append({
                        'Category': category,
                        'Product Name': product.get('name', ''),
                        'Model Number': product.get('model_number', ''),
                        'Price': product.get('price', 0),
                        'Description': product.get('description', ''),
                        'Color': variant.get('color', ''),
                        'Size': variant.get('size', ''),
                        'Quantity': variant.get('quantity', 0),
                        'Image Path': variant.get('image_path', '')
                    })
        
        df = pd.DataFrame(data)
        
        # Create Excel file in memory
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Products', index=False)
        
        output.seek(0)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"products_export_{timestamp}.xlsx"
        
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=filename
        )
        
    except Exception as e:
        print(f"❌ Error exporting products: {e}")
        flash('حدث خطأ أثناء تصدير البيانات', 'error')
        return redirect(url_for('dashboard.products_page'))