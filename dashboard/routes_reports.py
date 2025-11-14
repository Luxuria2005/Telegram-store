# dashboard/routes_reports.py - Reports and analytics routes
from flask import render_template, request, jsonify, redirect, url_for, flash, session, send_file
import io
import pandas as pd
from datetime import datetime
from . import dashboard_bp
from .utils import (
    login_required, permission_required, get_accessible_sidebar_items, 
    ARABIC_TEXTS, get_sales_analytics, get_inventory_analytics
)
from database import db

# Enhanced Reports Routes
@dashboard_bp.route('/reports')
@login_required
@permission_required('view_reports')
def reports_page():
    """Enhanced reports dashboard - UPDATED TO INCLUDE SOLD-OUT PRODUCTS"""
    try:
        # Get sales analytics - FIXED: Now properly calculates 30-day orders
        sales_analytics = get_sales_analytics()
        inventory_analytics = get_inventory_analytics()
        
        # Calculate product performance - USING UPDATED DATABASE METHOD
        product_performance = db.get_products_performance()
        
        # Sort by revenue (descending)
        product_performance.sort(key=lambda x: x['total_revenue'], reverse=True)
        
        # Get accessible sidebar items
        sidebar_items = get_accessible_sidebar_items()
        
        # ✅ ADDED: Pass user permissions to template
        user_permissions = session.get('permissions', {})
        
        return render_template('reports.html',
                             sales_analytics=sales_analytics,
                             inventory_analytics=inventory_analytics,
                             product_performance=product_performance,
                             sidebar_items=sidebar_items,
                             user_role=session.get('role'),
                             user_permissions=user_permissions,  # ✅ ADD THIS
                             user_full_name=session.get('full_name'),
                             texts=ARABIC_TEXTS)
        
    except Exception as e:
        print(f"❌ Error loading reports: {e}")
        flash('حدث خطأ في تحميل التقارير', 'error')
        return redirect(url_for('dashboard.index'))

@dashboard_bp.route('/export/product_reports/excel')
@login_required
@permission_required('view_reports')
def export_product_reports_excel():
    """Export product performance reports to Excel - FIXED TO INCLUDE SOLD-OUT PRODUCTS"""
    try:
        # Use the database method that includes sold-out products
        product_performance = db.get_products_performance()
        
        # Prepare comprehensive product data - INCLUDING SOLD-OUT PRODUCTS
        data = []
        for product in product_performance:
            # Calculate sell-through rate
            initial_quantity = product.get('initial_quantity', 0)
            sold_quantity = product.get('sold_quantity', 0)
            remaining_quantity = product.get('remaining_quantity', 0)
            
            sell_through_rate = (sold_quantity / initial_quantity * 100) if initial_quantity > 0 else 0
            
            data.append({
                'الفئة': product.get('category', ''),
                'اسم المنتج': product.get('name', ''),
                'رقم الموديل': product.get('model_number', 'غير متوفر'),
                'السعر': product.get('price', 0),
                'الكمية الأولية': initial_quantity,
                'الكمية المباعة': sold_quantity,
                'الكمية المتبقية': remaining_quantity,
                'إجمالي الإيرادات': product.get('total_revenue', 0),
                'معدل البيع': f"{sell_through_rate:.1f}%" if initial_quantity > 0 else "0%",
                'الحالة': 'تم البيع بالكامل ✅' if remaining_quantity == 0 and sold_quantity > 0 else 'متوفر' if remaining_quantity > 0 else 'غير متوفر'
            })
        
        df = pd.DataFrame(data)
        
        # Create Excel file in memory
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='تقارير المنتجات', index=False)
            
            # Auto-adjust column widths
            worksheet = writer.sheets['تقارير المنتجات']
            for idx, col in enumerate(df.columns):
                max_len = max(df[col].astype(str).str.len().max(), len(col)) + 2
                worksheet.column_dimensions[chr(65 + idx)].width = max_len
        
        output.seek(0)
        
        timestamp = datetime.now().strftime("%Y%m%d")
        filename = f"product_reports_{timestamp}.xlsx"
        
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=filename
        )
        
    except Exception as e:
        print(f"❌ Error exporting product reports: {e}")
        flash('حدث خطأ أثناء تصدير تقارير المنتجات', 'error')
        return redirect(url_for('dashboard.reports_page'))