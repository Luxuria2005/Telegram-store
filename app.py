# app.py - Updated main application file (REPLACES dashboard.py)
from flask import Flask, send_from_directory
import os
from dashboard import dashboard_bp
from database import db

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'products'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
app.secret_key = 'your-secret-key-here-change-in-production'

# Register the dashboard blueprint
app.register_blueprint(dashboard_bp)
askaks

# Serve product images
@app.route('/products/<path:filename>')
def serve_product_image(filename):
    """Serve product images"""
    try:
        return send_from_directory('products', filename)
    except:
        return send_from_directory('static', 'placeholder.jpg')

# Create necessary directories
def create_directories():
    """Create necessary directories for the application"""
    directories = [
        'products',
        'static',
        'temp'
    ]
    
    for directory in directories:
        os.makedirs(directory, exist_ok=True)
        print(f"✅ Created directory: {directory}")

if __name__ == '__main__':
    # Create upload directory if it doesn't exist
    create_directories()
    
    print("🚀 Starting Fashion Store Management System...")
    print("📊 Dashboard: http://localhost:5000")
    print("📦 Products: http://localhost:5000/products")
    print("📋 Orders: http://localhost:5000/all-orders")
    print("📈 Inventory: http://localhost:5000/inventory")
    print("📢 Broadcast: http://localhost:5000/broadcast")
    
    app.run(debug=True, host='0.0.0.0', port=5000)