# dashboard/error_handlers.py - Error handling routes
from flask import render_template, send_from_directory
import os
from . import dashboard_bp

# FIXED: Image serving route for Windows paths
@dashboard_bp.route('/products/<path:filename>')
def serve_product_image(filename):
    """Serve product images - IMPROVED VERSION"""
    try:
        print(f"🖼️ Requested image: {filename}")
        
        # Normalize path
        clean_path = filename.replace('\\', '/').strip()
        
        # Try multiple locations
        locations = [
            clean_path,
            os.path.join('products', clean_path),
            os.path.join('products', clean_path),
            os.path.join('.', clean_path),
        ]
        
        for location in locations:
            print(f"🔍 Checking: {location}")
            if os.path.exists(location) and os.path.isfile(location):
                print(f"✅ Found at: {location}")
                return send_from_directory(os.path.dirname(location), os.path.basename(location))
        
        print(f"❌ Image not found: {clean_path}")
        return send_from_directory('static', 'placeholder.jpg')
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return send_from_directory('static', 'placeholder.jpg')

@dashboard_bp.route('/debug_images')
def debug_images():
    """Debug route to check image paths"""
    from .utils import load_products
    products_data = load_products()
    image_info = []
    
    for category, products in products_data.get('products', {}).items():
        for product in products:
            product_info = {
                'product': product['name'],
                'category': category,
                'variants': []
            }
            for variant in product.get('variants', []):
                product_info['variants'].append({
                    'color': variant['color'],
                    'size': variant['size'],
                    'image_path': variant.get('image_path', 'No image'),
                    'quantity': variant.get('quantity', 0),
                    'image_exists': False
                })
            image_info.append(product_info)
    
    # Check if files actually exist
    for product in image_info:
        for variant in product['variants']:
            if variant['image_path'] and variant['image_path'] not in ['None', 'null', '']:
                # Try multiple possible locations
                possible_paths = [
                    os.path.join('products', variant['image_path']),
                    os.path.join('images', variant['image_path']),
                    variant['image_path'],
                    os.path.join('.', variant['image_path'])
                ]
                
                for path in possible_paths:
                    if os.path.exists(path):
                        variant['image_exists'] = True
                        variant['found_at'] = path
                        break
    
    return jsonify(image_info)

@dashboard_bp.errorhandler(404)
def not_found_error(error):
    return render_template('404.html'), 404

@dashboard_bp.errorhandler(500)
def internal_error(error):
    return render_template('500.html'), 500