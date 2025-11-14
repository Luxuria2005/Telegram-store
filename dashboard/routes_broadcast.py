# dashboard/routes_broadcast.py - Broadcast system routes
import threading
import time
import requests
import os
from flask import render_template, request, jsonify, redirect, url_for, flash, session
from werkzeug.utils import secure_filename
from datetime import datetime
from . import dashboard_bp
from .utils import (
    login_required, permission_required, get_accessible_sidebar_items, 
    ARABIC_TEXTS, allowed_file, has_permission
)
from database import db
from config import TELEGRAM_BOT_TOKEN

# ✅ NEW: Broadcast System Routes
@dashboard_bp.route('/broadcast')
@login_required
@permission_required('send_notifications')
def broadcast_page():
    """Broadcast system dashboard - WITH FIXED USER COUNTS"""
    try:
        # ✅ FIXED: Count actual buyers based on orders
        all_users = db.get_all_bot_users()
        total_users = len(all_users) if all_users else 0
        
        # Get all orders to find actual buyers
        orders = db.get_orders()
        
        # Create set of unique user IDs who actually placed orders
        buyer_user_ids = set()
        for order in orders:
            user_id = order.get('user_id')
            if user_id:
                buyer_user_ids.add(user_id)
        
        buyers_count = len(buyer_user_ids)
        non_buyers_count = total_users - buyers_count
        
        print(f"📊 Fixed User Counts: Total={total_users}, Buyers={buyers_count}, Non-buyers={non_buyers_count}")
        
        # Get accessible sidebar items
        sidebar_items = get_accessible_sidebar_items()
        
        # Pass user permissions to template
        user_permissions = session.get('permissions', {})
        
        return render_template('broadcast.html',
                             all_users_count=total_users,
                             buyers_count=buyers_count,
                             non_buyers_count=non_buyers_count,
                             sidebar_items=sidebar_items,
                             user_role=session.get('role'),
                             user_permissions=user_permissions,
                             user_full_name=session.get('full_name'),
                             texts=ARABIC_TEXTS)
        
    except Exception as e:
        print(f"❌ Error loading broadcast page: {e}")
        flash('حدث خطأ في تحميل صفحة نظام البث', 'error')
        return redirect(url_for('dashboard.index'))

@dashboard_bp.route('/api/send_broadcast', methods=['POST'])
@login_required
@permission_required('send_notifications')
def api_send_broadcast():
    """Send broadcast message to users"""
    try:
        message = request.form.get('message', '').strip()
        audience = request.form.get('audience', 'all')
        image_file = request.files.get('image')
        
        if not message:
            return jsonify({"success": False, "message": "يرجى إدخال نص الرسالة"})
        
        # Get target users based on audience selection
        all_users = db.get_all_bot_users()
        
        if audience == 'buyers':
            target_users = [user for user in all_users if user.get('has_placed_order')]
        elif audience == 'non_buyers':
            target_users = [user for user in all_users if not user.get('has_placed_order')]
        else:  # 'all'
            target_users = all_users
        
        if not target_users:
            return jsonify({"success": False, "message": "لا يوجد مستخدمين مستهدفين"})
        
        # Prepare image for sending
        image_path = None
        if image_file and allowed_file(image_file.filename):
            # Save image temporarily
            filename = secure_filename(f"broadcast_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{image_file.filename}")
            image_path = os.path.join('temp', filename)
            os.makedirs('temp', exist_ok=True)
            image_file.save(image_path)
        
        # Start broadcast in background thread
        def run_broadcast():
            try:
                send_broadcast_message(target_users, message, image_path)
            except Exception as e:
                print(f"❌ Error in broadcast thread: {e}")
        
        thread = threading.Thread(target=run_broadcast)
        thread.daemon = True
        thread.start()
        
        audience_names = {
            'all': 'جميع المستخدمين',
            'buyers': 'العملاء الذين قاموا بالشراء',
            'non_buyers': 'المستخدمين الذين لم يشتروا بعد'
        }
        
        return jsonify({
            "success": True, 
            "message": f"✅ جاري إرسال الرسالة إلى {len(target_users)} مستخدم ({audience_names[audience]})",
            "sent_count": len(target_users),
            "audience": audience_names[audience]
        })
        
    except Exception as e:
        print(f"❌ Error in broadcast API: {e}")
        return jsonify({
            "success": False, 
            "message": f"❌ حدث خطأ: {str(e)}"
        })

def send_broadcast_message(users, message, image_path=None):
    """Send broadcast message to users via Telegram"""
    try:
        successful_sends = 0
        failed_sends = 0
        
        for user in users:
            try:
                telegram_id = user['telegram_id']
                
                if image_path and os.path.exists(image_path):
                    # Send photo with caption
                    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
                    
                    with open(image_path, 'rb') as photo_file:
                        files = {'photo': photo_file}
                        data = {
                            'chat_id': telegram_id,
                            'caption': message,
                            'parse_mode': 'Markdown'
                        }
                        response = requests.post(url, files=files, data=data)
                        
                else:
                    # Send text message
                    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
                    data = {
                        'chat_id': telegram_id,
                        'text': message,
                        'parse_mode': 'Markdown'
                    }
                    response = requests.post(url, data=data)
                
                if response.status_code == 200:
                    successful_sends += 1
                    print(f"✅ Broadcast sent to {telegram_id}")
                else:
                    failed_sends += 1
                    print(f"❌ Failed to send to {telegram_id}: {response.text}")
                
                # Small delay to prevent rate limiting
                time.sleep(0.2)
                
            except Exception as e:
                failed_sends += 1
                print(f"❌ Error sending to {user.get('telegram_id', 'unknown')}: {e}")
                continue
        
        # Clean up temporary image file
        if image_path and os.path.exists(image_path):
            try:
                os.remove(image_path)
            except:
                pass
        
        print(f"🎯 Broadcast completed: {successful_sends} successful, {failed_sends} failed")
        
    except Exception as e:
        print(f"💥 CRITICAL ERROR in broadcast: {e}")

# ✅ FIXED: API route to send REAL notifications - COMPLETELY REWRITTEN
@dashboard_bp.route('/api/send_notification/<int:product_id>', methods=['POST'])
@login_required
@permission_required('send_notifications')  # ✅ FIXED: Use the correct permission
def api_send_notification(product_id):
    """API endpoint to send REAL product notification - FIXED VERSION"""
    try:
        print(f"📢 [DASHBOARD API] Starting notification process for product {product_id}")
        
        # Check if user has permission to send notifications
        if not has_permission('send_notifications'):
            print(f"❌ [DASHBOARD API] User {session.get('username')} doesn't have notification permission")
            return jsonify({
                "success": False, 
                "message": "❌ غير مصرح بإرسال الإشعارات. تحتاج صلاحية إرسال الإشعارات."
            })
        
        # ✅ FIXED: Use the new sync notification function from store.py
        try:
            from store import send_product_notification_sync
            print(f"✅ [DASHBOARD API] Successfully imported sync notification function")
        except ImportError as e:
            print(f"❌ [DASHBOARD API] Failed to import notification function: {e}")
            return jsonify({
                "success": False, 
                "message": "❌ خطأ في نظام الإشعارات. يرجى التحقق من إعدادات البوت."
            })
        
        # Get product info for response
        from .utils import load_products
        products_data = load_products()
        product = None
        for category_products in products_data.get('products', {}).values():
            for prod in category_products:
                if prod['id'] == product_id:
                    product = prod
                    break
            if product:
                break
        
        if not product:
            print(f"❌ [DASHBOARD API] Product {product_id} not found")
            return jsonify({
                "success": False, 
                "message": "❌ المنتج غير موجود"
            })
        
        # Get user count for response
        users = db.get_all_notification_users()
        customer_count = len(users) if users else 0
        
        print(f"📢 [DASHBOARD API] Product: '{product['name']}', Users: {customer_count}")
        
        # ✅ FIXED: Run notification in background thread using the SYNC function
        def run_notification():
            try:
                print(f"🔄 [BACKGROUND] Starting background notification for product {product_id}")
                # Use the sync function that works without async issues
                result = send_product_notification_sync(product_id)
                if result:
                    print(f"✅ [BACKGROUND] Notification completed successfully for product {product_id}")
                else:
                    print(f"❌ [BACKGROUND] Notification failed for product {product_id}")
            except Exception as e:
                print(f"❌ [BACKGROUND] Error in notification thread: {e}")
                import traceback
                traceback.print_exc()
        
        # Start the background thread
        thread = threading.Thread(target=run_notification)
        thread.daemon = True
        thread.start()
        
        print(f"✅ [DASHBOARD API] Notification scheduled in background")
        
        return jsonify({
            "success": True, 
            "message": f"✅ جاري إرسال إشعار المنتج '{product['name']}' إلى {customer_count} عميل",
            "sent_count": customer_count,
            "product_name": product['name']
        })
        
    except Exception as e:
        print(f"❌ [DASHBOARD API] Error in api_send_notification: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "success": False, 
            "message": f"❌ حدث خطأ: {str(e)}"
        })