# store.py - COMPLETE FIXED CODE WITH ENHANCED NOTIFICATIONS & UPDATED ORDER FLOW
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters, CallbackQueryHandler, ConversationHandler
import os
import json
from datetime import datetime
import re
import asyncio
from database import db
from config import (
    TELEGRAM_BOT_TOKEN, COMPANY_NAME, SUPPORT_EMAIL, SUPPORT_PHONE, 
    BUSINESS_HOURS, CURRENCY, ARABIC_TEXTS, SEND_NEW_PRODUCT_NOTIFICATIONS,
    STATES_AND_REGIONS
)

# ✅ UPDATED: Conversation states - NEW ORDER FLOW: 1.NAME → 2.PHONE → 3.STATE → 4.REGION → 5.ADDRESS
NAME, PHONE, SELECT_STATE, SELECT_REGION, ADDRESS, CONFIRM_ORDER = range(6)

# ✅ ADDED: Product selection conversation states
SELECT_SIZE, SELECT_COLOR, SELECT_QUANTITY = range(3)

# Arabic text constants with company info
BOT_TEXTS = {
    "welcome": f"""
👕 **مرحباً بك في {COMPANY_NAME}!** 👖

أنا مساعدك الشخصي للتسوق! هذا ما يمكنني فعله:

**🛍️ ميزات التسوق:**
• تصفح فئاتنا المتعددة
• أضف العناصر إلى سلة التسوق مع اختيار المقاس واللون  
• اطلب مباشرة
• تتبع طلباتك

**📋 الفئات المتاحة:**
{{categories}}

**إجراءات سريعة:**
• استخدم الأزرار أدناه للتسوق
• اكتب "طلب" لوضع طلب
• قل "سلة" لعرض سلة التسوق

**📞 الدعم:**
• البريد: {SUPPORT_EMAIL}
• الهاتف: {SUPPORT_PHONE}
• ساعات العمل: {BUSINESS_HOURS}

تسوق سعيد! 🛍️
    """,
    
    "order_placed": """
🎉 **تم وضع الطلب بنجاح!** 🎉

**تفاصيل الطلب:**
📦 رقم الطلب: #{order_id}
💰 المبلغ الإجمالي: {currency}{total_amount:,.0f}
📋 العناصر: {items_count}
📅 تاريخ الطلب: {order_date}

**الخطوات التالية:**
1. سنتصل بك قريباً لتأكيد التفاصيل
2. ستتلقى تأكيد الطلب
3. تتبع طلبك مع /myorders

شكراً لتسوقك معنا! 💝
    """,
    "select_size": "📏 **اختر المقاس:**\n\nالرجاء اختيار المقاس المناسب:",
    "select_color": "🎨 **اختر اللون:**\n\nالرجاء اختيار اللون المفضل:",
    "select_quantity": "📦 **اختر الكمية:**\n\nكم قطعة تريد إضافة إلى السلة؟",
    "enter_name": "📝 **معلومات العميل**\n\nالرجاء إدخال اسمك الكامل:",
    "enter_phone": "📱 **رقم الهاتف**\n\nالرجاء إدخال رقم هاتفك:",
    "enter_address": "🏠 **عنوان التوصيل**\n\nالرجاء إدخال عنوان التوصيل بالتفصيل:",
    "select_state": "🏙️ **اختر المحافظة:**\n\nالرجاء اختيار المحافظة التي تقيم فيها:",
    "select_region": "📍 **اختر المنطقة:**\n\nالرجاء اختيار منطقتك داخل المحافظة:",
    "confirm_order": """
✅ **تأكيد الطلب**

**معلومات العميل:**
👤 الاسم: {name}
📱 الهاتف: {phone}
🏠 العنوان: {address}
🏙️ المحافظة: {state}
📍 المنطقة: {region}

**محتويات الطلب:**
{items_summary}

**المبلغ الإجمالي: {currency}{total_amount:,.0f}**

هل تريد تأكيد الطلب؟
    """,
    "order_cancelled": "❌ تم إلغاء الطلب.",
    "invalid_phone": "❌ رقم هاتف غير صحيح. الرجاء إدخال رقم هاتف صحيح:",
    "thank_you": "شكراً لك! سنتصل بك قريباً لتأكيد طلبك. 📞",
    "added_to_cart": "✅ **تمت الإضافة إلى السلة!**\n\n{product_name}\n📏 المقاس: {size}\n🎨 اللون: {color}\n📦 الكمية: {quantity}\n💰 السعر: {currency}{total_price:,.0f}",
    "out_of_stock": "❌ **غير متوفر**\n\n{product_name}\n📏 المقاس: {size}\n🎨 اللون: {color}\n\nهذا المنتج غير متوفر حالياً",
    "color_images": "🎨 **صور اللون: {color}**\n📏 **المقاس: {size}**",
    "insufficient_stock": "❌ **الكمية غير متوفرة**\n\n{product_name}\n📏 المقاس: {size}\n🎨 اللون: {color}\n\nالمخزون المتاح: {available_quantity}\nالكمية المطلوبة: {requested_quantity}",
    "inventory_warning": "⚠️ **تنبيه المخزون**\n\n{message}",
    "new_product_notification": """
🆕 **منتج جديد!** 🛍️

{product_name}
💰 السعر: {currency}{price}
📝 {description}

{model_text}
🎨 الألوان المتاحة: {available_colors}

**للطلب:** استخدم زر '🛒 أضف إلى السلة' أدناه!
    """
}

# Arabic category mapping
ARABIC_CATEGORIES = {
    'men': 'رجالي',
    'women': 'نسائي', 
    'kids': 'أطفال',
    't-shirts': 'تيشيرتات',
    'jeans': 'جينز',
    'dresses': 'فساتين', 
    'jackets': 'جاكيتات'
}

# Global variables
user_carts = {}
user_order_data = {}
user_temp_selection = {}

# ✅ ADD TO store.py - Order Status Notification Function
def send_order_status_notification_sync(order_id, old_status, new_status):
    """Synchronous function to send order status notifications"""
    import requests
    from database import db
    from config import TELEGRAM_BOT_TOKEN, CURRENCY
    
    try:
        print(f"📢 [ORDER NOTIFICATION] Starting notification for order {order_id}")
        
        # Get order details
        order = db.get_order_by_id(order_id)
        if not order:
            print(f"❌ [ORDER NOTIFICATION] Order {order_id} not found")
            return False
        
        user_id = order.get('user_id')
        if not user_id:
            print(f"❌ [ORDER NOTIFICATION] No user_id found for order {order_id}")
            return False
        
        # Status messages in Arabic
        status_messages = {
            'confirmed': {
                'title': '✅ تم تأكيد طلبك',
                'message': f'تم تأكيد طلبك #{order_id} وسيتم تجهيزه قريباً.'
            },
            'shipped': {
                'title': '🚚 تم شحن طلبك',
                'message': f'طلبك #{order_id} تم شحنه وهو في الطريق إليك.'
            },
            'delivered': {
                'title': '🎉 تم توصيل طلبك',
                'message': f'تهانينا! تم توصيل طلبك #{order_id} بنجاح.'
            }
        }
        
        # Get message for the new status
        status_key = new_status.lower()
        if status_key in ['مؤكد', 'confirmed']:
            message_info = status_messages['confirmed']
        elif status_key in ['تم الشحن', 'shipped']:
            message_info = status_messages['shipped']
        elif status_key in ['تم التوصيل', 'delivered']:
            message_info = status_messages['delivered']
        else:
            # No notification for other status changes
            print(f"ℹ️ [ORDER NOTIFICATION] No notification for status change: {old_status} → {new_status}")
            return True
        
        # Prepare notification text
        notification_text = f"""
{message_info['title']}

{message_info['message']}

**تفاصيل الطلب:**
📦 رقم الطلب: #{order_id}
👤 العميل: {order.get('user_name', '')}
📞 الهاتف: {order.get('user_phone', '')}
🏠 العنوان: {order.get('user_address', '')}
💰 المبلغ: {CURRENCY}{order.get('total_amount', 0):,.0f}

شكراً لثقتك بنا! 🤝
"""
        
        # Send via Telegram API
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        data = {
            'chat_id': user_id,
            'text': notification_text,
            'parse_mode': 'Markdown'
        }
        
        response = requests.post(url, data=data)
        
        if response.status_code == 200:
            print(f"✅ [ORDER NOTIFICATION] Sent status notification for order #{order_id} to user {user_id}")
            return True
        else:
            print(f"❌ [ORDER NOTIFICATION] Failed to send notification: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ [ORDER NOTIFICATION] Error sending order status notification: {e}")
        return False

# Database functions
def load_products():
    """Load products from database"""
    try:
        products_data = db.get_all_products()
        categories = db.get_categories()
        category_names = [cat['name'] for cat in categories]
        
        print(f"🤖 Loaded {len(category_names)} categories: {category_names}")
        print(f"🤖 Loaded products for: {list(products_data.keys())}")
        
        return products_data, category_names
    except Exception as e:
        print(f"❌ Error loading products from database: {e}")
        return {}, []

def get_arabic_category_name(category_key):
    """Get Arabic name for category"""
    return ARABIC_CATEGORIES.get(category_key, category_key.title())

def create_category_keyboard(categories):
    """Dynamically create category keyboard based on available categories"""
    if not categories:
        return [['🏠 الرئيسية', '🛒 سلة التسوق']]
    
    arabic_categories = [get_arabic_category_name(cat) for cat in categories]
    
    keyboard = []
    row = []
    
    for i, category in enumerate(arabic_categories):
        row.append(category)
        if len(row) == 2 or i == len(arabic_categories) - 1:
            keyboard.append(row)
            row = []
    
    keyboard.append(['🏠 الرئيسية', '🛒 سلة التسوق'])
    keyboard.append(['📋 جميع المنتجات'])  # Added All Products button
    
    return keyboard

# Load initial data
PRODUCT_CATALOG, CATEGORIES = load_products()
CATEGORY_KEYBOARD = create_category_keyboard(CATEGORIES)

# Create keyboards with ALL PRODUCTS button
MAIN_KEYBOARD = ReplyKeyboardMarkup([
    ['🛍️ تصفح المنتجات', '📦 طلباتي'],
    ['🛒 سلة التسوق', '📞 الدعم الفني'],
    ['🏠 الرئيسية', 'ℹ️ المساعدة'],
    ['📋 جميع المنتجات']  # All products button
], resize_keyboard=True)

CATEGORY_KEYBOARD_MARKUP = ReplyKeyboardMarkup(CATEGORY_KEYBOARD, resize_keyboard=True)

# Location keyboard functions
def create_state_keyboard():
    """Create keyboard for state selection"""
    keyboard = []
    row = []
    
    states = list(STATES_AND_REGIONS.keys())
    
    for i, state in enumerate(states):
        row.append(InlineKeyboardButton(state, callback_data=f"state_{state}"))
        if len(row) == 2 or i == len(states) - 1:
            keyboard.append(row)
            row = []
    
    keyboard.append([InlineKeyboardButton("❌ إلغاء", callback_data="cancel_selection")])
    
    return InlineKeyboardMarkup(keyboard)

def create_region_keyboard(state):
    """Create keyboard for region selection based on state"""
    keyboard = []
    row = []
    
    regions = STATES_AND_REGIONS.get(state, [])
    
    for i, region in enumerate(regions):
        row.append(InlineKeyboardButton(region, callback_data=f"region_{region}"))
        if len(row) == 2 or i == len(regions) - 1:
            keyboard.append(row)
            row = []
    
    keyboard.append([InlineKeyboardButton("↩️ العودة للمحافظات", callback_data="back_to_states")])
    keyboard.append([InlineKeyboardButton("❌ إلغاء", callback_data="cancel_selection")])
    
    return InlineKeyboardMarkup(keyboard)

# FIXED: Image path handling function
def get_variant_images(product_id, category, color):
    """Get images for specific color variant"""
    try:
        image_path = db.get_color_image(product_id, color)
        
        if image_path and image_path != 'None' and image_path.strip():
            possible_paths = [
                image_path,
                os.path.join('products', image_path),
                os.path.join('images', image_path),
                os.path.join('.', 'products', image_path),
                os.path.join('.', 'images', image_path)
            ]
            
            for path in possible_paths:
                if os.path.exists(path):
                    return [path]
            
        return []
        
    except Exception as e:
        print(f"❌ Error in get_variant_images: {e}")
        return []

# Cart management functions
def get_user_cart(user_id):
    """Get or create cart for user"""
    if user_id not in user_carts:
        user_carts[user_id] = []
        print(f"🛒 Created new cart for user {user_id}")
    return user_carts[user_id]

def add_to_cart(user_id, product, category, size=None, color=None, quantity=1):
    """Add product to user's cart with size and color - WITH INVENTORY VALIDATION"""
    cart = get_user_cart(user_id)
    
    # ✅ Check inventory before adding to cart
    if color and size:
        inventory_check = db.check_inventory(product['id'], color, size, quantity)
        if not inventory_check['available']:
            return {
                'success': False,
                'message': BOT_TEXTS["insufficient_stock"].format(
                    product_name=product['name'],
                    size=size,
                    color=color,
                    available_quantity=inventory_check['current_stock'],
                    requested_quantity=quantity,
                    currency=CURRENCY
                )
            }
    
    for item in cart:
        if (item['product_id'] == product['id'] and 
            item['category'] == category and 
            item.get('size') == size and 
            item.get('color') == color):
            # ✅ Check if updated quantity is available
            new_quantity = item['quantity'] + quantity
            if color and size:
                inventory_check = db.check_inventory(product['id'], color, size, new_quantity)
                if not inventory_check['available']:
                    return {
                        'success': False,
                        'message': BOT_TEXTS["insufficient_stock"].format(
                            product_name=product['name'],
                            size=size,
                            color=color,
                            available_quantity=inventory_check['current_stock'],
                            requested_quantity=new_quantity,
                            currency=CURRENCY
                        )
                    }
            
            item['quantity'] = new_quantity
            print(f"🛒 Updated quantity for {product['name']} in cart")
            return {'success': True, 'cart': cart}
    
    cart_item = {
        'product_id': product['id'],
        'name': product['name'],
        'category': category,
        'price': product['price'],
        'size': size,
        'color': color,
        'quantity': quantity,
        'images': get_variant_images(product['id'], category, color) if color else []
    }
    cart.append(cart_item)
    print(f"🛒 Added {product['name']} to cart (Size: {size}, Color: {color}, Qty: {quantity})")
    
    # ✅ NEW: Log client activity
    db.log_client_activity(
        telegram_id=user_id,
        activity_type='add_to_cart',
        activity_description=f'إضافة منتج إلى السلة: {product["name"]}',
        target_type='product',
        target_id=product['id'],
        target_name=product['name'],
        metadata=json.dumps({
            'size': size,
            'color': color,
            'quantity': quantity,
            'category': category
        })
    )
    
    return {'success': True, 'cart': cart}

def clear_cart(user_id):
    """Clear user's cart"""
    if user_id in user_carts:
        user_carts[user_id] = []
        print(f"🛒 Cleared cart for user {user_id}")
        return True
    return False

def get_cart_total(user_id):
    """Calculate total price of items in cart"""
    cart = get_user_cart(user_id)
    total = sum(item['price'] * item['quantity'] for item in cart)
    return total

def get_cart_summary(user_id):
    """Get formatted cart summary"""
    cart = get_user_cart(user_id)
    if not cart:
        return ""
    
    summary = ""
    for i, item in enumerate(cart, 1):
        item_total = item['price'] * item['quantity']
        summary += f"{i}. **{item['name']}**\n"
        summary += f"   💰 {CURRENCY}{item['price']:,.0f} × {item['quantity']} = {CURRENCY}{item_total:,.0f}\n"
        if item.get('size'):
            summary += f"   📏 المقاس: {item['size']}\n"
        if item.get('color'):
            summary += f"   🎨 اللون: {item['color']}\n"
        summary += "\n"
    
    total = get_cart_total(user_id)
    summary += f"**💰 الإجمالي: {CURRENCY}{total:,.0f}**"
    return summary

def create_size_keyboard(sizes):
    """Create inline keyboard for size selection - ONLY AVAILABLE SIZES"""
    if not sizes:
        return None
    
    keyboard = []
    row = []
    
    for i, size in enumerate(sizes):
        row.append(InlineKeyboardButton(size, callback_data=f"size_{size}"))
        if len(row) == 3 or i == len(sizes) - 1:
            keyboard.append(row)
            row = []
    
    keyboard.append([InlineKeyboardButton("❌ إلغاء", callback_data="cancel_selection")])
    
    return InlineKeyboardMarkup(keyboard)

def create_color_keyboard(colors):
    """Create inline keyboard for color selection - ONLY AVAILABLE COLORS"""
    if not colors:
        return None
    
    keyboard = []
    row = []
    
    for i, color in enumerate(colors):
        row.append(InlineKeyboardButton(color, callback_data=f"color_{color}"))
        if len(row) == 3 or i == len(colors) - 1:
            keyboard.append(row)
            row = []
    
    keyboard.append([InlineKeyboardButton("❌ إلغاء", callback_data="cancel_selection")])
    
    return InlineKeyboardMarkup(keyboard)

def create_quantity_keyboard(max_quantity=10):
    """Create inline keyboard for quantity selection"""
    keyboard = []
    row = []
    
    for i in range(1, max_quantity + 1):
        row.append(InlineKeyboardButton(str(i), callback_data=f"qty_{i}"))
        if len(row) == 3:
            keyboard.append(row)
            row = []
    
    if row:
        keyboard.append(row)
    
    keyboard.append([InlineKeyboardButton("❌ إلغاء", callback_data="cancel_selection")])
    
    return InlineKeyboardMarkup(keyboard)

def create_order_keyboard():
    """Create keyboard for order confirmation"""
    keyboard = [
        [InlineKeyboardButton("✅ نعم، تأكيد الطلب", callback_data="confirm_order")],
        [InlineKeyboardButton("❌ إلغاء الطلب", callback_data="cancel_order")]
    ]
    return InlineKeyboardMarkup(keyboard)

# ✅ FIXED: Enhanced product display functions - HIDE ZERO QUANTITIES
def generate_product_caption_with_colors(product):
    """Generate product caption without showing quantities to customers - HIDE UNAVAILABLE SIZES"""
    caption = f"✨ **{product['name']}** ✨\n\n"
    caption += f"💰 **السعر:** {CURRENCY}{product['price']:,.0f}\n"
    
    if product.get('model_number'):
        caption += f"🔢 **رقم الموديل:** {product['model_number']}\n"
    
    if product.get('description'):
        caption += f"📝 {product['description']}\n"
    
    variants = product.get('variants', [])
    if variants:
        # ✅ ONLY SHOW VARIANTS WITH QUANTITY > 0
        available_variants = [v for v in variants if v.get('quantity', 0) > 0]
        
        if available_variants:
            caption += f"🎨 **الألوان والمقاسات المتاحة:**\n"
            
            color_size_combinations = {}
            for variant in available_variants:
                color = variant.get('color', 'واحد')
                size = variant.get('size', 'واحد')
                has_image = variant.get('image_path') is not None
                
                if color not in color_size_combinations:
                    color_size_combinations[color] = {
                        'sizes': [],
                        'has_image': has_image
                    }
                
                if size not in color_size_combinations[color]['sizes']:
                    color_size_combinations[color]['sizes'].append(size)
            
            for color, info in color_size_combinations.items():
                sizes_text = "، ".join(info['sizes'])
                caption += f"   • {color} - {sizes_text}"
                if info['has_image']:
                    caption += " 📷"
                caption += f" - ✅ متوفر\n"
        else:
            caption += "❌ **غير متوفر حالياً**\n"
    else:
        caption += "⚠️ **لا توجد تفاصيل متاحة**\n"
    
    caption += f"\n🛍️ **رقم المنتج:** #{product['id']}"
    caption += f"\n\n**للطلب:** اختر '🛒 أضف إلى السلة' ثم اختر اللون والمقاس"
    
    return caption

# ✅ FIXED: STANDALONE NOTIFICATION FUNCTION - CAN BE CALLED FROM DASHBOARD
def send_product_notification_sync(product_id):
    """
    Synchronous function to send product notifications
    Can be called from dashboard without async issues
    """
    import requests
    import json
    from database import db
    from config import TELEGRAM_BOT_TOKEN, CURRENCY
    
    try:
        print(f"📢 [SYNC NOTIFICATION] Starting notification for product {product_id}")
        
        # Load products to find the product
        products_data, _ = load_products()
        product = None
        category = None
        
        # Find the product
        for cat, products in products_data.items():
            for prod in products:
                if prod['id'] == product_id:
                    product = prod
                    category = cat
                    break
            if product:
                break
        
        if not product:
            print(f"❌ [SYNC NOTIFICATION] Product {product_id} not found")
            return False
        
        print(f"✅ [SYNC NOTIFICATION] Found product: {product['name']}")
        
        # Get ALL users for notification
        users = db.get_all_notification_users()
        if not users:
            print("❌ [SYNC NOTIFICATION] No users found for notifications")
            return False
        
        print(f"📢 [SYNC NOTIFICATION] Sending to {len(users)} users")
        
        # Prepare product information
        available_colors = set()
        for variant in product.get('variants', []):
            if variant.get('quantity', 0) > 0:
                available_colors.add(variant.get('color', ''))
        
        available_colors_text = "، ".join(available_colors) if available_colors else "واحد"
        model_text = f"🔢 **رقم الموديل:** {product['model_number']}\n" if product.get('model_number') else ""
        
        notification_text = f"""
🆕 **منتج جديد!** 🛍️

{product['name']}
💰 السعر: {CURRENCY}{product['price']:,.0f}
📝 {product.get('description', '')}

{model_text}
🎨 الألوان المتاحة: {available_colors_text}

**للطلب:** استخدم زر '🛒 أضف إلى السلة' أدناه!
        """.strip()
        
        # Get first available image
        first_image = None
        for variant in product.get('variants', []):
            if variant.get('quantity', 0) > 0 and variant.get('image_path'):
                images = get_variant_images(product['id'], category, variant['color'])
                if images and os.path.exists(images[0]):
                    first_image = images[0]
                    break
        
        # Create inline keyboard markup
        keyboard = {
            "inline_keyboard": [
                [{"text": "🛒 أضف إلى السلة", "callback_data": f"select_{category}_{product['id']}"}],
                [{"text": "🛍️ تصفح المزيد", "callback_data": "browse_products"}]
            ]
        }
        
        # Send to all users
        successful_sends = 0
        failed_sends = 0
        
        for user in users:
            try:
                telegram_id = user['telegram_id']
                
                if first_image and os.path.exists(first_image):
                    # Send photo with caption
                    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
                    
                    with open(first_image, 'rb') as photo_file:
                        files = {'photo': photo_file}
                        data = {
                            'chat_id': telegram_id,
                            'caption': notification_text,
                            'parse_mode': 'Markdown',
                            'reply_markup': json.dumps(keyboard)
                        }
                        response = requests.post(url, files=files, data=data)
                        
                else:
                    # Send text message
                    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
                    data = {
                        'chat_id': telegram_id,
                        'text': notification_text,
                        'parse_mode': 'Markdown',
                        'reply_markup': json.dumps(keyboard)
                    }
                    response = requests.post(url, data=data)
                
                if response.status_code == 200:
                    successful_sends += 1
                    print(f"✅ [SYNC NOTIFICATION] Successfully sent to {telegram_id}")
                else:
                    failed_sends += 1
                    print(f"❌ [SYNC NOTIFICATION] Failed to send to {telegram_id}: {response.text}")
                
                # Small delay to prevent rate limiting
                import time
                time.sleep(0.2)
                
            except Exception as e:
                failed_sends += 1
                print(f"❌ [SYNC NOTIFICATION] Error sending to {user.get('telegram_id', 'unknown')}: {e}")
                continue
        
        print(f"🎯 [SYNC NOTIFICATION] COMPLETED: {successful_sends} successful, {failed_sends} failed")
        return successful_sends > 0
        
    except Exception as e:
        print(f"💥 [SYNC NOTIFICATION] CRITICAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

# ✅ FIXED: Enhanced product notification function for dashboard
async def send_product_notification(context: ContextTypes.DEFAULT_TYPE, product, category):
    """Send new product notification to ALL users - FIXED FOR DASHBOARD"""
    from config import SEND_NEW_PRODUCT_NOTIFICATIONS
    
    if not SEND_NEW_PRODUCT_NOTIFICATIONS:
        print("🔕 [NOTIFICATION] Notifications are disabled in config")
        return
    
    try:
        # ✅ Get ALL users (not just buyers)
        users = db.get_all_notification_users()
        if not users:
            print("❌ [NOTIFICATION] No users found for notifications")
            return
        
        print(f"📢 [NOTIFICATION] Sending product notification to {len(users)} users")
        
        # Prepare product information
        available_colors = set()
        for variant in product.get('variants', []):
            if variant.get('quantity', 0) > 0:
                available_colors.add(variant.get('color', ''))
        
        available_colors_text = "، ".join(available_colors) if available_colors else "واحد"
        model_text = f"🔢 **رقم الموديل:** {product['model_number']}\n" if product.get('model_number') else ""
        
        notification_text = f"""
🆕 **منتج جديد!** 🛍️

{product['name']}
💰 السعر: {CURRENCY}{product['price']:,.0f}
📝 {product.get('description', '')}

{model_text}
🎨 الألوان المتاحة: {available_colors_text}

**للطلب:** استخدم زر '🛒 أضف إلى السلة' أدناه!
        """.strip()
        
        # Get first available image
        first_image = None
        for variant in product.get('variants', []):
            if variant.get('quantity', 0) > 0 and variant.get('image_path'):
                images = get_variant_images(product['id'], category, variant['color'])
                if images and os.path.exists(images[0]):
                    first_image = images[0]
                    break
        
        # Create order button
        keyboard = [
            [InlineKeyboardButton("🛒 أضف إلى السلة", callback_data=f"select_{category}_{product['id']}")],
            [InlineKeyboardButton("🛍️ تصفح المزيد", callback_data="browse_products")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Send to all users
        successful_sends = 0
        for user in users:
            try:
                if first_image and os.path.exists(first_image):
                    with open(first_image, 'rb') as photo:
                        await context.bot.send_photo(
                            chat_id=user['telegram_id'],
                            photo=photo,
                            caption=notification_text,
                            reply_markup=reply_markup,
                            parse_mode='Markdown'
                        )
                else:
                    await context.bot.send_message(
                        chat_id=user['telegram_id'],
                        text=notification_text,
                        reply_markup=reply_markup,
                        parse_mode='Markdown'
                    )
                successful_sends += 1
                await asyncio.sleep(0.2)  # Prevent rate limiting
            except Exception as e:
                error_msg = str(e)
                print(f"❌ [NOTIFICATION] Failed to send to {user['telegram_id']}: {error_msg}")
                continue
        
        print(f"✅ [NOTIFICATION] Successfully sent product notification to {successful_sends} users")
        
    except Exception as e:
        print(f"❌ [NOTIFICATION] Error in product notification system: {e}")

# Command Handlers
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    print(f"🚀 Start command from user {user_id}")
    
    # ✅ ENHANCED: Register user in bot_users table (ALL users)
    db.add_bot_user(
        telegram_id=user_id,
        username=update.message.from_user.username,
        first_name=update.message.from_user.first_name,
        last_name=update.message.from_user.last_name
    )
    
    # ✅ KEEP EXISTING: Also register in customers table for backward compatibility
    db.add_customer(
        telegram_id=user_id,
        username=update.message.from_user.username,
        first_name=update.message.from_user.first_name,
        last_name=update.message.from_user.last_name
    )
    
    # ✅ NEW: Log client activity
    db.log_client_activity(
        telegram_id=user_id,
        activity_type='bot_start',
        activity_description='بدء استخدام البوت',
        metadata=json.dumps({
            'username': update.message.from_user.username,
            'first_name': update.message.from_user.first_name
        })
    )
    
    global PRODUCT_CATALOG, CATEGORIES, CATEGORY_KEYBOARD_MARKUP
    PRODUCT_CATALOG, CATEGORIES = load_products()
    CATEGORY_KEYBOARD = create_category_keyboard(CATEGORIES)
    CATEGORY_KEYBOARD_MARKUP = ReplyKeyboardMarkup(CATEGORY_KEYBOARD, resize_keyboard=True)
    
    categories_text = "\n".join([f"• {get_arabic_category_name(cat)}" for cat in CATEGORIES])
    welcome_text = BOT_TEXTS["welcome"].format(categories=categories_text)
    
    await update.message.reply_text(welcome_text, reply_markup=MAIN_KEYBOARD, parse_mode='Markdown')

async def browse_products(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    print(f"🛍️ Browse products from user {user_id}")
    
    # ✅ NEW: Log client activity
    db.log_client_activity(
        telegram_id=user_id,
        activity_type='browse_products',
        activity_description='تصفح المنتجات'
    )
    
    await update.message.reply_text("🎯 **تصفح فئاتنا:**\n\nاختر فئة لبدء التسوق!", reply_markup=CATEGORY_KEYBOARD_MARKUP, parse_mode='Markdown')

async def view_cart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    cart = get_user_cart(user_id)
    
    print(f"🛒 Displaying cart for user {user_id} with {len(cart)} items")
    
    # ✅ NEW: Log client activity
    db.log_client_activity(
        telegram_id=user_id,
        activity_type='view_cart',
        activity_description=f'عرض السلة ({len(cart)} عنصر)',
        metadata=json.dumps({'cart_items_count': len(cart)})
    )
    
    if not cart:
        await update.message.reply_text("🛒 **سلة التسوق فارغة!**\n\nتصفح الفئات وأضف بعض العناصر الأنيقة! 👕", reply_markup=MAIN_KEYBOARD, parse_mode='Markdown')
        return
    
    cart_text = "🛒 **سلة التسوق**\n\n"
    cart_text += get_cart_summary(user_id)
    cart_text += f"\n\n**الخيارات:**\n• انقر '✅ تأكيد الطلب' للشراء\n• انقر '🗑️ مسح السلة' لتفريغ السلة"
    
    keyboard = [
        [InlineKeyboardButton("✅ تأكيد الطلب", callback_data="start_order")],
        [InlineKeyboardButton("🗑️ مسح السلة", callback_data="clear_cart")],
        [InlineKeyboardButton("🛍️ متابعة التسوق", callback_data="continue_shopping")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(cart_text, reply_markup=reply_markup, parse_mode='Markdown')

# ✅ UPDATED: Order conversation handlers - NEW FLOW: NAME → PHONE → STATE → REGION → ADDRESS
async def start_order_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start the order conversation"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    cart = get_user_cart(user_id)
    
    print(f"🛒 Starting order process for user {user_id} with {len(cart)} items")
    
    if not cart:
        await query.edit_message_text("سلة التسوق فارغة! أضف عناصر أولاً.")
        return ConversationHandler.END
    
    # Store cart in context for the conversation
    context.user_data['cart'] = cart
    context.user_data['user_id'] = user_id
    
    # ✅ STEP 1: Start with NAME (new first step)
    await query.edit_message_text(BOT_TEXTS["enter_name"])
    return NAME

async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """STEP 1: Get customer name"""
    user_id = update.message.from_user.id
    context.user_data['name'] = update.message.text
    
    # ✅ STEP 2: Proceed to PHONE
    await update.message.reply_text(BOT_TEXTS["enter_phone"])
    return PHONE

async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """STEP 2: Get customer phone"""
    user_id = update.message.from_user.id
    phone = update.message.text
    
    # Simple phone validation
    if not re.match(r'^[\+]?[0-9\s\-\(\)]{8,}$', phone):
        await update.message.reply_text(BOT_TEXTS["invalid_phone"])
        return PHONE
    
    context.user_data['phone'] = phone
    
    # ✅ STEP 3: Proceed to STATE selection
    await update.message.reply_text(
        BOT_TEXTS["select_state"],
        reply_markup=create_state_keyboard()
    )
    return SELECT_STATE

async def select_state(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """STEP 3: Select state"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    if query.data == "cancel_selection":
        await query.edit_message_text(BOT_TEXTS["order_cancelled"])
        return ConversationHandler.END
    
    if query.data.startswith("state_"):
        state = query.data.replace("state_", "")
        context.user_data['state'] = state
        
        # ✅ STEP 4: Proceed to REGION selection for the selected state
        await query.edit_message_text(
            BOT_TEXTS["select_region"],
            reply_markup=create_region_keyboard(state)
        )
        return SELECT_REGION
    
    return SELECT_STATE

async def select_region(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """STEP 4: Select region"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    if query.data == "cancel_selection":
        await query.edit_message_text(BOT_TEXTS["order_cancelled"])
        return ConversationHandler.END
    
    if query.data == "back_to_states":
        await query.edit_message_text(
            BOT_TEXTS["select_state"],
            reply_markup=create_state_keyboard()
        )
        return SELECT_STATE
    
    if query.data.startswith("region_"):
        region = query.data.replace("region_", "")
        context.user_data['region'] = region
        
        # ✅ STEP 5: Proceed to ADDRESS
        await query.edit_message_text(BOT_TEXTS["enter_address"])
        return ADDRESS
    
    return SELECT_REGION

async def get_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """STEP 5: Get customer address"""
    user_id = update.message.from_user.id
    context.user_data['address'] = update.message.text
    
    # ✅ FINAL STEP: Show order confirmation with all details
    cart = context.user_data['cart']
    items_summary = ""
    for item in cart:
        items_summary += f"• {item['name']} - {CURRENCY}{item['price']:,.0f} × {item['quantity']}\n"
        if item.get('size'):
            items_summary += f"  📏 المقاس: {item['size']}\n"
        if item.get('color'):
            items_summary += f"  🎨 اللون: {item['color']}\n"
        items_summary += "\n"
    
    total_amount = sum(item['price'] * item['quantity'] for item in cart)
    
    confirm_text = BOT_TEXTS["confirm_order"].format(
        name=context.user_data['name'],
        phone=context.user_data['phone'],
        address=context.user_data['address'],
        state=context.user_data['state'],
        region=context.user_data['region'],
        items_summary=items_summary,
        total_amount=total_amount,
        currency=CURRENCY
    )
    
    reply_markup = create_order_keyboard()
    
    await update.message.reply_text(confirm_text, reply_markup=reply_markup, parse_mode='Markdown')
    return CONFIRM_ORDER

# FIXED: Add the missing cancel_order_conversation function
async def cancel_order_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel the order conversation"""
    user_id = update.message.from_user.id if update.message else update.callback_query.from_user.id
    
    # Clean up
    cleanup_keys = ['cart', 'name', 'phone', 'address', 'state', 'region', 'user_id']
    for key in cleanup_keys:
        if key in context.user_data:
            del context.user_data[key]
    
    if update.message:
        await update.message.reply_text(BOT_TEXTS["order_cancelled"], reply_markup=MAIN_KEYBOARD)
    else:
        await update.callback_query.edit_message_text(BOT_TEXTS["order_cancelled"])
    
    return ConversationHandler.END

async def confirm_order_final(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Finalize the order - WITH INVENTORY VALIDATION AND LOCATION"""
    query = update.callback_query
    await query.answer()
    
    user_id = context.user_data['user_id']
    
    if query.data == "confirm_order":
        cart = context.user_data['cart']
        
        try:
            # Debug: Print what we're sending to the database
            print(f"🔍 Order data: Name: {context.user_data['name']}, Phone: {context.user_data['phone']}")
            print(f"🔍 Address: {context.user_data['address']}, State: {context.user_data['state']}, Region: {context.user_data['region']}")
            print(f"🔍 Cart items: {len(cart)} items, Total: {sum(item['price'] * item['quantity'] for item in cart)}")
            
            # ✅ Create the order with inventory validation AND LOCATION DATA
            order_result = db.create_order(
                user_id=user_id,
                user_name=context.user_data['name'],
                user_phone=context.user_data['phone'],
                user_address=context.user_data['address'],
                user_state=context.user_data.get('state', 'غير محدد'),  # Use .get() with default
                user_region=context.user_data.get('region', 'غير محدد'), # Use .get() with default
                username=query.from_user.username,
                items=cart,
                total_amount=sum(item['price'] * item['quantity'] for item in cart)
            )
            
            if order_result['success'] and order_result['order_id']:
                # ✅ NEW: Log client activity
                db.log_client_activity(
                    telegram_id=user_id,
                    activity_type='order_placed',
                    activity_description=f'إنشاء طلب جديد #{order_result["order_id"]}',
                    target_type='order',
                    target_id=order_result['order_id'],
                    target_name=f'Order #{order_result["order_id"]}',
                    metadata=json.dumps({
                        'total_amount': sum(item['price'] * item['quantity'] for item in cart),
                        'items_count': len(cart),
                        'state': context.user_data.get('state', 'غير محدد'),
                        'region': context.user_data.get('region', 'غير محدد')
                    })
                )
                
                # Clear cart after successful order
                clear_cart(user_id)
                
                order_text = BOT_TEXTS["order_placed"].format(
                    order_id=order_result['order_id'],
                    total_amount=sum(item['price'] * item['quantity'] for item in cart),
                    items_count=len(cart),
                    order_date=datetime.now().strftime("%Y-%m-%d %H:%M"),
                    currency=CURRENCY
                )
                
                await query.edit_message_text(order_text, parse_mode='Markdown')
                
                # Send thank you message
                await context.bot.send_message(
                    chat_id=user_id,
                    text=BOT_TEXTS["thank_you"],
                    reply_markup=MAIN_KEYBOARD
                )
            else:
                # ✅ Show inventory errors to user
                if order_result.get('errors'):
                    error_messages = "\n".join([error['message'] for error in order_result['errors']])
                    await query.edit_message_text(
                        f"❌ **تعذر إكمال الطلب:**\n\n{error_messages}\n\nيرجى تعديل سلة التسوق والمحاولة مرة أخرى.",
                        parse_mode='Markdown'
                    )
                else:
                    await query.edit_message_text(
                        "❌ **حدث خطأ غير متوقع في حفظ الطلب.**\n\nيرجى المحاولة مرة أخرى أو التواصل مع الدعم.",
                        parse_mode='Markdown'
                    )
            
        except Exception as e:
            print(f"❌ Error in confirm_order_final: {e}")
            import traceback
            traceback.print_exc()
            await query.edit_message_text("❌ حدث خطأ في حفظ الطلب. يرجى المحاولة مرة أخرى.")
        
    else:
        await query.edit_message_text(BOT_TEXTS["order_cancelled"])
    
    # Clean up
    cleanup_keys = ['cart', 'name', 'phone', 'address', 'state', 'region', 'user_id']
    for key in cleanup_keys:
        if key in context.user_data:
            del context.user_data[key]
    
    return ConversationHandler.END

# ✅ FIXED: Product display with images - ONLY AVAILABLE PRODUCTS
async def show_products(update: Update, category_input: str):
    user_id = update.message.from_user.id
    print(f"🛍️ Showing products for category: '{category_input}' from user {user_id}")
    
    category_en = None
    for eng_cat, arabic_cat in ARABIC_CATEGORIES.items():
        if arabic_cat == category_input:
            category_en = eng_cat
            break
    
    if not category_en:
        category_en = category_input.lower()
    
    if category_en in PRODUCT_CATALOG and PRODUCT_CATALOG[category_en]:
        products = PRODUCT_CATALOG[category_en]
        arabic_category_name = get_arabic_category_name(category_en)
        
        # ✅ FILTER: Only show products with available variants
        available_products = []
        for product in products:
            # Check if product has any variants with quantity > 0
            has_available_variants = any(
                variant.get('quantity', 0) > 0 
                for variant in product.get('variants', [])
            )
            if has_available_variants:
                available_products.append(product)
        
        print(f"✅ Found {len(available_products)} available products in category '{category_en}'")
        
        if not available_products:
            await update.message.reply_text(
                f"❌ **لا توجد منتجات متاحة حالياً في '{arabic_category_name}'**\n\nيرجى التحقق لاحقاً أو تصفح فئة أخرى.",
                reply_markup=CATEGORY_KEYBOARD_MARKUP
            )
            return
        
        await update.message.reply_text(
            f"👕 **مجموعة {arabic_category_name}** 👕\n\n"
            f"وجدنا {len(available_products)} منتج(منتجات) رائعة لك!",
            reply_markup=CATEGORY_KEYBOARD_MARKUP,
            parse_mode='Markdown'
        )
        
        # ✅ NEW: Log category browsing
        db.log_client_activity(
            telegram_id=user_id,
            activity_type='view_category',
            activity_description=f'عرض فئة: {arabic_category_name}',
            target_type='category',
            target_name=category_en,
            metadata=json.dumps({
                'category_arabic': arabic_category_name,
                'products_count': len(available_products)
            })
        )
        
        for product in available_products:
            try:
                first_image = None
                for variant in product.get('variants', []):
                    if variant.get('image_path') and variant.get('quantity', 0) > 0:
                        images = get_variant_images(product['id'], category_en, variant['color'])
                        if images:
                            first_image = images[0]
                            break
                
                caption = generate_product_caption_with_colors(product)
                
                if first_image and os.path.exists(first_image):
                    keyboard = [
                        [InlineKeyboardButton("🛒 أضف إلى السلة", callback_data=f"select_{category_en}_{product['id']}")],
                        [InlineKeyboardButton("🎨 عرض الألوان", callback_data=f"view_colors_{category_en}_{product['id']}")]
                    ]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    
                    with open(first_image, 'rb') as photo:
                        await update.message.reply_photo(
                            photo=photo, 
                            caption=caption,
                            reply_markup=reply_markup,
                            parse_mode='Markdown'
                        )
                else:
                    keyboard = [
                        [InlineKeyboardButton("🛒 أضف إلى السلة", callback_data=f"select_{category_en}_{product['id']}")],
                        [InlineKeyboardButton("🎨 عرض الألوان", callback_data=f"view_colors_{category_en}_{product['id']}")]
                    ]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    
                    await update.message.reply_text(
                        f"📦 {caption}",
                        reply_markup=reply_markup,
                        parse_mode='Markdown'
                    )
                    
            except Exception as e:
                print(f"❌ Error showing product {product['name']}: {e}")
        
        await update.message.reply_text(
            f"**لطلب أي عنصر:**\n"
            f"• استخدم زر '🛒 أضف إلى السلة'\n"
            f"• أو '🎨 عرض الألوان' لرؤية جميع الصور\n"
            f"• ثم اذهب إلى '🛒 سلة التسوق' لوضع الطلب",
            reply_markup=CATEGORY_KEYBOARD_MARKUP
        )
    else:
        arabic_category_name = get_arabic_category_name(category_en)
        await update.message.reply_text(
            f"❌ لم يتم العثور على منتجات في '{arabic_category_name}'",
            reply_markup=CATEGORY_KEYBOARD_MARKUP
        )

# ✅ FIXED: Show all products without category dependency
async def show_all_products(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show all available products across all categories"""
    user_id = update.message.from_user.id
    print(f"🛍️ Showing ALL products for user {user_id}")
    
    # Collect all available products from all categories
    all_available_products = []
    
    for category_en, products in PRODUCT_CATALOG.items():
        for product in products:
            # Check if product has any variants with quantity > 0
            has_available_variants = any(
                variant.get('quantity', 0) > 0 
                for variant in product.get('variants', [])
            )
            if has_available_variants:
                product_with_category = product.copy()
                product_with_category['category'] = category_en
                all_available_products.append(product_with_category)
    
    if not all_available_products:
        await update.message.reply_text(
            "❌ **لا توجد منتجات متاحة حالياً**\n\nيرجى التحقق لاحقاً.",
            reply_markup=MAIN_KEYBOARD
        )
        return
    
    await update.message.reply_text(
        f"🛍️ **جميع المنتجات المتاحة** 🛍️\n\n"
        f"عرض {len(all_available_products)} منتج متاح من جميع الفئات:",
        reply_markup=MAIN_KEYBOARD,
        parse_mode='Markdown'
    )
    
    products_displayed = 0
    for product in all_available_products:
        try:
            if products_displayed >= 20:  # Limit to prevent spam
                await update.message.reply_text(
                    "📋 **عرض أول 20 منتج متاح**\n\nاستخدم البحث بالفئات لعرض المزيد من المنتجات.",
                    reply_markup=MAIN_KEYBOARD
                )
                break
                
            first_image = None
            for variant in product.get('variants', []):
                if variant.get('image_path') and variant.get('quantity', 0) > 0:
                    images = get_variant_images(product['id'], product['category'], variant['color'])
                    if images:
                        first_image = images[0]
                        break
            
            category_arabic = get_arabic_category_name(product['category'])
            caption = f"**{product['name']}**\n📂 الفئة: {category_arabic}\n\n"
            caption += generate_product_caption_with_colors(product)
            
            if first_image and os.path.exists(first_image):
                keyboard = [
                    [InlineKeyboardButton("🛒 أضف إلى السلة", callback_data=f"select_{product['category']}_{product['id']}")],
                    [InlineKeyboardButton("🎨 عرض الألوان", callback_data=f"view_colors_{product['category']}_{product['id']}")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                with open(first_image, 'rb') as photo:
                    await update.message.reply_photo(
                        photo=photo, 
                        caption=caption,
                        reply_markup=reply_markup,
                        parse_mode='Markdown'
                    )
            else:
                keyboard = [
                    [InlineKeyboardButton("🛒 أضف إلى السلة", callback_data=f"select_{product['category']}_{product['id']}")],
                    [InlineKeyboardButton("🎨 عرض الألوان", callback_data=f"view_colors_{product['category']}_{product['id']}")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await update.message.reply_text(
                    caption,
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
            
            products_displayed += 1
            await asyncio.sleep(0.5)  # Small delay to prevent rate limiting
                
        except Exception as e:
            print(f"❌ Error showing product {product['name']}: {e}")
            continue

# FIXED: Color images display - ONLY AVAILABLE VARIANTS
async def show_color_images(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    user_id = query.from_user.id
    
    parts = data.split("_")
    if len(parts) < 4:
        await query.message.reply_text("❌ خطأ في بيانات المنتج")
        return
    
    category = parts[2]
    product_id = int(parts[3])
    
    product = None
    for category_products in PRODUCT_CATALOG.values():
        for prod in category_products:
            if prod['id'] == product_id:
                product = prod
                break
        if product:
            break
    
    if not product:
        await query.message.reply_text("❌ تعذر العثور على المنتج")
        return
    
    # ✅ NEW: Log product view
    db.log_client_activity(
        telegram_id=user_id,
        activity_type='view_product',
        activity_description=f'عرض تفاصيل المنتج: {product["name"]}',
        target_type='product',
        target_id=product_id,
        target_name=product['name'],
        metadata=json.dumps({
            'category': category,
            'product_name': product['name']
        })
    )
    
    color_images = {}
    for variant in product.get('variants', []):
        color = variant.get('color')
        
        # ✅ ONLY SHOW IMAGES FOR AVAILABLE VARIANTS
        if color and variant.get('quantity', 0) > 0:
            images = get_variant_images(product_id, category, color)
            if images:
                color_images[color] = images[0]
    
    if not color_images:
        await query.message.reply_text("❌ لا توجد صور متاحة لهذا المنتج")
        return
    
    await query.message.reply_text(f"🎨 **صور ألوان {product['name']}**\n\nاختر اللون الذي يعجبك:")
    
    images_sent = 0
    for color, image_path in color_images.items():
        try:
            caption = BOT_TEXTS["color_images"].format(
                color=color,
                size="جميع المقاسات"
            )
            
            with open(image_path, 'rb') as photo:
                await context.bot.send_photo(
                    chat_id=user_id,
                    photo=photo,
                    caption=caption,
                    parse_mode='Markdown'
                )
            images_sent += 1
                
        except Exception as e:
            print(f"❌ Error sending color image for {color}: {e}")
    
    if images_sent == 0:
        await query.message.reply_text("❌ لم يتم العثور على أي صور متاحة لهذا المنتج")
        return
    
    keyboard = [[InlineKeyboardButton("🛒 أضف إلى السلة", callback_data=f"select_{category}_{product_id}")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await context.bot.send_message(
        chat_id=user_id,
        text="**لإضافة المنتج إلى السلة:** استخدم الزر أدناه واختر اللون والمقاس المناسب",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

# ✅ FIXED: Product selection handlers - ONLY AVAILABLE SIZES/COLORS
async def start_product_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    data = query.data
    
    parts = data.split("_")
    if len(parts) < 3:
        await query.message.reply_text("❌ خطأ في بيانات المنتج")
        return ConversationHandler.END
    
    category = parts[1]
    product_id = int(parts[2])
    
    product = None
    for category_products in PRODUCT_CATALOG.values():
        for prod in category_products:
            if prod['id'] == product_id:
                product = prod
                break
        if product:
            break
    
    if not product:
        await query.message.reply_text("❌ تعذر العثور على المنتج")
        return ConversationHandler.END
    
    # ✅ ONLY SHOW AVAILABLE SIZES AND COLORS
    available_sizes = []
    available_colors = []
    
    for variant in product.get('variants', []):
        if variant.get('quantity', 0) > 0:  # Only variants with stock
            size = variant.get('size')
            color = variant.get('color')
            
            if size and size not in available_sizes:
                available_sizes.append(size)
            if color and color not in available_colors:
                available_colors.append(color)
    
    if not available_sizes and not available_colors:
        await query.message.reply_text("❌ المنتج غير متوفر حالياً")
        return ConversationHandler.END
    
    user_temp_selection[user_id] = {
        'product': product,
        'category': category,
        'product_id': product_id,
        'size': None,
        'color': None,
        'quantity': 1
    }
    
    if available_sizes:
        size_keyboard = create_size_keyboard(available_sizes)
        await query.message.reply_text(
            BOT_TEXTS["select_size"],
            reply_markup=size_keyboard
        )
        return SELECT_SIZE
    elif available_colors:
        color_keyboard = create_color_keyboard(available_colors)
        await query.message.reply_text(
            BOT_TEXTS["select_color"],
            reply_markup=color_keyboard
        )
        return SELECT_COLOR
    else:
        await query.message.reply_text(
            BOT_TEXTS["select_quantity"],
            reply_markup=create_quantity_keyboard()
        )
        return SELECT_QUANTITY

async def select_size(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    if query.data == "cancel_selection":
        await query.edit_message_text("❌ تم إلغاء عملية الإضافة")
        if user_id in user_temp_selection:
            del user_temp_selection[user_id]
        return ConversationHandler.END
    
    if query.data.startswith("size_"):
        size = query.data.replace("size_", "")
        user_temp_selection[user_id]['size'] = size
        
        product = user_temp_selection[user_id]['product']
        product_id = user_temp_selection[user_id]['product_id']
        category = user_temp_selection[user_id]['category']
        
        # ✅ ONLY SHOW AVAILABLE COLORS FOR SELECTED SIZE
        available_colors = []
        for variant in product.get('variants', []):
            if (variant.get('size') == size and 
                variant.get('quantity', 0) > 0 and 
                variant.get('color') not in available_colors):
                available_colors.append(variant.get('color'))
        
        if available_colors:
            color_keyboard = create_color_keyboard(available_colors)
            await query.edit_message_text(
                BOT_TEXTS["select_color"],
                reply_markup=color_keyboard
            )
            return SELECT_COLOR
        else:
            await query.edit_message_text("❌ لا توجد ألوان متاحة لهذا المقاس")
            del user_temp_selection[user_id]
            return ConversationHandler.END
    
    return SELECT_SIZE

async def select_color(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    if query.data == "cancel_selection":
        await query.edit_message_text("❌ تم إلغاء عملية الإضافة")
        if user_id in user_temp_selection:
            del user_temp_selection[user_id]
        return ConversationHandler.END
    
    if query.data.startswith("color_"):
        color = query.data.replace("color_", "")
        user_temp_selection[user_id]['color'] = color
        
        await query.edit_message_text(
            BOT_TEXTS["select_quantity"],
            reply_markup=create_quantity_keyboard(10)
        )
        return SELECT_QUANTITY
    
    return SELECT_COLOR

async def select_quantity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    if query.data == "cancel_selection":
        await query.edit_message_text("❌ تم إلغاء عملية الإضافة")
        if user_id in user_temp_selection:
            del user_temp_selection[user_id]
        return ConversationHandler.END
    
    if query.data.startswith("qty_"):
        quantity = int(query.data.replace("qty_", ""))
        
        if user_id not in user_temp_selection:
            await query.edit_message_text("❌ انتهت صلاحية الجلسة، يرجى المحاولة مرة أخرى")
            return ConversationHandler.END
        
        selection = user_temp_selection[user_id]
        product = selection['product']
        category = selection['category']
        product_id = selection['product_id']
        size = selection.get('size')
        color = selection.get('color')
        
        # ✅ Add to cart with inventory validation
        result = add_to_cart(user_id, product, category, size, color, quantity)
        
        if result['success']:
            cart = result['cart']
            total_price = product['price'] * quantity
            
            confirmation_text = BOT_TEXTS["added_to_cart"].format(
                product_name=product['name'],
                size=size if size else "غير محدد",
                color=color if color else "غير محدد",
                quantity=quantity,
                total_price=total_price,
                currency=CURRENCY
            )
            
            await query.edit_message_text(
                confirmation_text + f"\n\n🛒 السلة تحتوي الآن على {len(cart)} عنصر",
                parse_mode='Markdown'
            )
        else:
            # Show inventory error
            await query.edit_message_text(
                result['message'],
                parse_mode='Markdown'
            )
        
        del user_temp_selection[user_id]
        
        return ConversationHandler.END
    
    return SELECT_QUANTITY

# NEW: My Orders Handler
async def show_my_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user's orders"""
    user_id = update.message.from_user.id
    
    try:
        # Get orders from database
        orders = db.get_orders()
        user_orders = [order for order in orders if order.get('user_id') == user_id]
        
        if not user_orders:
            await update.message.reply_text(
                "📦 **لا توجد طلبات سابقة**\n\n"
                "لم تقم بوضع أي طلبات حتى الآن. ابدأ التسوق الآن! 🛍️",
                reply_markup=MAIN_KEYBOARD,
                parse_mode='Markdown'
            )
            return
        
        # Show recent orders (last 5)
        recent_orders = user_orders[:5]
        orders_text = "📦 **طلباتي السابقة**\n\n"
        
        for i, order in enumerate(recent_orders, 1):
            order_date = order.get('order_date', 'غير معروف')
            status = order.get('status', 'معلق')
            total = order.get('total_amount', 0)
            
            orders_text += f"**الطلب #{order['id']}**\n"
            orders_text += f"📅 {order_date}\n"
            orders_text += f"💰 {CURRENCY}{total:,.0f}\n"
            orders_text += f"📊 الحالة: {status}\n"
            orders_text += "─" * 20 + "\n\n"
        
        if len(user_orders) > 5:
            orders_text += f"*عرض {len(recent_orders)} من أصل {len(user_orders)} طلب*\n"
        
        orders_text += "\n**للتتبع الكامل:** تفضل بزيارة لوحة التحكم"
        
        await update.message.reply_text(
            orders_text,
            reply_markup=MAIN_KEYBOARD,
            parse_mode='Markdown'
        )
        
    except Exception as e:
        print(f"❌ Error showing orders: {e}")
        await update.message.reply_text(
            "❌ حدث خطأ في تحميل الطلبات. يرجى المحاولة مرة أخرى.",
            reply_markup=MAIN_KEYBOARD
        )

# NEW: Support Handler
async def show_support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show support information"""
    support_text = f"""
📞 **الدعم الفني**

**للتواصل مع الدعم:**
• 📧 البريد الإلكتروني: {SUPPORT_EMAIL}
• 📱 الهاتف: {SUPPORT_PHONE}
• 🕒 ساعات العمل: {BUSINESS_HOURS}

**للمساعدة الفورية:**
• استخدم زر 'ℹ️ المساعدة' للحصول على إرشادات الاستخدام
• تواصل معنا عبر البريد الإلكتروني للاستفسارات الفنية

**لشكاوى المنتجات:**
• نضمن لكم جودة المنتجات وسرعة التوصيل
• في حال وجود أي مشكلة، سنقوم بحلها في أقرب وقت ممكن

شكراً لثقتكم بنا! 🤝
"""
    
    await update.message.reply_text(
        support_text,
        reply_markup=MAIN_KEYBOARD,
        parse_mode='Markdown'
    )

# NEW: Help Handler
async def show_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show help information"""
    help_text = """
ℹ️ **دليل استخدام البوت**

**كيفية التسوق:**
1. اختر '🛍️ تصفح المنتجات' لرؤية الفئات
2. اختر الفئة التي تريدها
3. اختر المنتج الذي يعجبك
4. اضغط '🛒 أضف إلى السلة'
5. اختر المقاس واللون والكمية
6. انتقل إلى '🛒 سلة التسوق' لتأكيد الطلب

**إدارة الطلبات:**
• '📦 طلباتي': لعرض طلباتك السابقة
• '🛒 سلة التسوق': لعرض ومتابعة مشترياتك
• '✅ تأكيد الطلب': لإتمام عملية الشراء

**الدعم:**
• '📞 الدعم الفني': للتواصل مع فريق الدعم
• '🏠 الرئيسية': للعودة للقائمة الرئيسية

**نصائح سريعة:**
• يمكنك استخدام الأزرار أو كتابة الأوامر مباشرة
• تأكد من اختيار المقاس واللون المناسبين
• يمكنك تعديل السلة قبل تأكيد الطلب

للاستفسارات، لا تتردد في التواصل مع الدعم الفني! 📞
"""
    
    await update.message.reply_text(
        help_text,
        reply_markup=MAIN_KEYBOARD,
        parse_mode='Markdown'
    )

# ✅ FIXED: Message handler - UPDATED TO HANDLE ALL BUTTONS + ALL PRODUCTS
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text
    user_id = update.message.from_user.id
    
    print(f"📱 Received message from user {user_id}: '{user_message}'")
    
    # Handle main menu buttons
    if user_message in ['🛍️ تصفح المنتجات', 'تصفح', 'منتجات', 'تسوق', 'browse']:
        await browse_products(update, context)
        return
    elif user_message in ['🛒 سلة التسوق', 'سلة', 'عربة', 'cart']:
        await view_cart(update, context)
        return
    elif user_message in ['📦 طلباتي', 'طلباتي', 'طلبات', 'orders', 'myorders']:
        await show_my_orders(update, context)
        return
    elif user_message in ['📞 الدعم الفني', 'دعم', 'support', 'مساعدة']:
        await show_support(update, context)
        return
    elif user_message in ['ℹ️ المساعدة', 'مساعدة', 'help', 'info']:
        await show_help(update, context)
        return
    elif user_message in ['🏠 الرئيسية', 'رئيس', 'الرئيس', 'start', 'home']:
        await start_command(update, context)
        return
    # ✅ FIXED: Handle "جميع المنتجات" button
    elif user_message in ['📋 جميع المنتجات', 'جميع المنتجات', 'كل المنتجات', 'all products']:
        await show_all_products(update, context)
        return
    
    # Handle category selection
    for category_en in CATEGORIES:
        arabic_name = get_arabic_category_name(category_en)
        if user_message == arabic_name:
            await show_products(update, arabic_name)
            return
    
    # If no match found
    await update.message.reply_text(
        "🤔 **لم أفهم طلبك**\n\n"
        "يمكنك:\n"
        "• استخدام الأزرار أدناه\n"
        "• تصفح المنتجات 🛍️\n"
        "• عرض جميع المنتجات 📋\n"
        "• عرض السلة 🛒\n"
        "• وضع طلب 📦\n\n"
        "اختر أحد الخيارات:",
        reply_markup=MAIN_KEYBOARD,
        parse_mode='Markdown'
    )

# Callback query handler
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    user_id = query.from_user.id
    
    if data == "clear_cart":
        if clear_cart(user_id):
            await query.edit_message_text("🗑️ تم مسح السلة! ابدأ التسوق مرة أخرى! 🛍️")
        else:
            await query.edit_message_text("❌ لم يتم العثور على سلة للمسح")
    elif data == "continue_shopping":
        await query.edit_message_text("🛍️ تابع التسوق! اختر فئة:", reply_markup=CATEGORY_KEYBOARD_MARKUP)
    elif data.startswith("view_colors_"):
        await show_color_images(update, context)
    elif data.startswith("select_"):
        await start_product_selection(update, context)
    elif data == "browse_products":
        await browse_products(update, context)
    else:
        print(f"🔘 Unhandled callback: {data}")

# In store.py - UPDATE THE ADMIN COMMAND
async def send_product_notification_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin command to send product notifications"""
    user_id = update.message.from_user.id
    
    # ✅ FIXED: Proper admin check
    from config import ADMIN_USER_IDS
    
    if user_id not in ADMIN_USER_IDS:
        await update.message.reply_text("❌ هذا الأمر للمسؤول فقط")
        return
    
    if not context.args:
        await update.message.reply_text("❌ يرجى تحديد معرف المنتج\n\nاستخدم: /notify_product <product_id>")
        return
    
    try:
        product_id = int(context.args[0])
        
        # Find product
        product = None
        category = None
        for cat, products in PRODUCT_CATALOG.items():
            for prod in products:
                if prod['id'] == product_id:
                    product = prod
                    category = cat
                    break
            if product:
                break
        
        if not product:
            await update.message.reply_text("❌ المنتج غير موجود")
            return
        
        # Send notification
        await send_product_notification(context, product, category)
        await update.message.reply_text(f"✅ تم إرسال إشعار المنتج '{product['name']}' إلى جميع العملاء")
        
    except ValueError:
        await update.message.reply_text("❌ معرف المنتج يجب أن يكون رقماً")
    except Exception as e:
        await update.message.reply_text(f"❌ حدث خطأ: {e}")

# ✅ FIXED: Global app instance for notification system
app = None

# ✅ FIXED: Enhanced Notification System - COMPLETELY REWRITTEN
async def send_telegram_notification(product_id):
    """Send product notification to ALL users - COMPLETELY FIXED VERSION"""
    try:
        print(f"📢 [NOTIFICATION] Starting notification process for product {product_id}")
        
        # Load products to find the product
        products_data, _ = load_products()
        product = None
        category = None
        
        # Find the product
        for cat, products in products_data.items():
            for prod in products:
                if prod['id'] == product_id:
                    product = prod
                    category = cat
                    break
            if product:
                break
        
        if not product:
            print(f"❌ [NOTIFICATION] Product {product_id} not found")
            return
        
        print(f"✅ [NOTIFICATION] Found product: {product['name']} in category: {category}")
        
        # Get ALL users for notification
        users = db.get_all_notification_users()
        if not users:
            print("❌ [NOTIFICATION] No users found for notifications")
            return
        
        print(f"📢 [NOTIFICATION] Sending to {len(users)} users")
        
        # Prepare product information
        available_colors = set()
        for variant in product.get('variants', []):
            if variant.get('quantity', 0) > 0:
                available_colors.add(variant.get('color', ''))
        
        available_colors_text = "، ".join(available_colors) if available_colors else "واحد"
        model_text = f"🔢 **رقم الموديل:** {product['model_number']}\n" if product.get('model_number') else ""
        
        notification_text = f"""
🆕 **منتج جديد!** 🛍️

{product['name']}
💰 السعر: {CURRENCY}{product['price']:,.0f}
📝 {product.get('description', '')}

{model_text}
🎨 الألوان المتاحة: {available_colors_text}

**للطلب:** استخدم زر '🛒 أضف إلى السلة' أدناه!
        """.strip()
        
        # Get first available image
        first_image = None
        for variant in product.get('variants', []):
            if variant.get('quantity', 0) > 0 and variant.get('image_path'):
                images = get_variant_images(product['id'], category, variant['color'])
                if images and os.path.exists(images[0]):
                    first_image = images[0]
                    break
        
        print(f"🖼️ [NOTIFICATION] Using image: {first_image}")
        
        # Create order button
        keyboard = [
            [InlineKeyboardButton("🛒 أضف إلى السلة", callback_data=f"select_{category}_{product['id']}")],
            [InlineKeyboardButton("🛍️ تصفح المزيد", callback_data="browse_products")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Send to all users
        successful_sends = 0
        failed_sends = 0
        
        for user in users:
            try:
                telegram_id = user['telegram_id']
                print(f"📤 [NOTIFICATION] Sending to user {telegram_id}")
                
                if first_image and os.path.exists(first_image):
                    with open(first_image, 'rb') as photo:
                        await app.bot.send_photo(
                            chat_id=telegram_id,
                            photo=photo,
                            caption=notification_text,
                            reply_markup=reply_markup,
                            parse_mode='Markdown'
                        )
                else:
                    await app.bot.send_message(
                        chat_id=telegram_id,
                        text=notification_text,
                        reply_markup=reply_markup,
                        parse_mode='Markdown'
                    )
                successful_sends += 1
                print(f"✅ [NOTIFICATION] Successfully sent to {telegram_id}")
                
                # Small delay to prevent rate limiting
                await asyncio.sleep(0.2)
                
            except Exception as e:
                failed_sends += 1
                error_msg = str(e)
                print(f"❌ [NOTIFICATION] Failed to send to {user.get('telegram_id', 'unknown')}: {error_msg}")
                
                # If it's a blocking error (user blocked the bot), skip quickly
                if "bot was blocked" in error_msg.lower() or "chat not found" in error_msg.lower():
                    continue
                
        print(f"🎯 [NOTIFICATION] COMPLETED: {successful_sends} successful, {failed_sends} failed")
        
    except Exception as e:
        print(f"💥 [NOTIFICATION] CRITICAL ERROR: {e}")
        import traceback
        traceback.print_exc()

# Main function
def main():
    global app
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    try:
        print("🔗 Testing database connection...")
        categories = db.get_categories()
        print(f"✅ Database connected successfully! Found {len(categories)} categories.")
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return

    # ✅ UPDATED: Order conversation handler WITH NEW FLOW
    order_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_order_conversation, pattern='^start_order$')],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_phone)],
            SELECT_STATE: [CallbackQueryHandler(select_state, pattern='^(state_|cancel_selection)')],
            SELECT_REGION: [CallbackQueryHandler(select_region, pattern='^(region_|back_to_states|cancel_selection)')],
            ADDRESS: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_address)],
            CONFIRM_ORDER: [CallbackQueryHandler(confirm_order_final, pattern='^(confirm_order|cancel_order)$')]
        },
        fallbacks=[CommandHandler('cancel', cancel_order_conversation), MessageHandler(filters.TEXT, cancel_order_conversation)]
    )

    # ✅ FIXED: Product selection handler with correct states
    product_selection_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_product_selection, pattern='^select_')],
        states={
            SELECT_SIZE: [CallbackQueryHandler(select_size, pattern='^(size_|cancel_selection)')],
            SELECT_COLOR: [CallbackQueryHandler(select_color, pattern='^(color_|cancel_selection)')],
            SELECT_QUANTITY: [CallbackQueryHandler(select_quantity, pattern='^(qty_|cancel_selection)')],
        },
        fallbacks=[]
    )

    # Add handlers
    app.add_handler(CommandHandler('start', start_command))
    app.add_handler(CommandHandler('browse', browse_products))
    app.add_handler(CommandHandler('cart', view_cart))
    app.add_handler(CommandHandler('orders', show_my_orders))
    app.add_handler(CommandHandler('support', show_support))
    app.add_handler(CommandHandler('help', show_help))
    app.add_handler(CommandHandler('all_products', show_all_products))
    app.add_handler(CommandHandler('notify_product', send_product_notification_command))
    
    # Add conversation handlers
    app.add_handler(order_handler)
    app.add_handler(product_selection_handler)
    
    # Add other handlers
    app.add_handler(CallbackQueryHandler(show_color_images, pattern='^view_colors_'))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print('=' * 60)
    print(f'🛍️  {COMPANY_NAME} - بوت المتجر العربي')
    print('=' * 60)
    
    global PRODUCT_CATALOG, CATEGORIES
    PRODUCT_CATALOG, CATEGORIES = load_products()
    
    if PRODUCT_CATALOG and CATEGORIES:
        total_products = sum(len(products) for products in PRODUCT_CATALOG.values())
        print(f'✅ تم تحميل {len(CATEGORIES)} فئات مع {total_products} منتج')
    else:
        print('❌ لم يتم تحميل أي فئات أو منتجات')
    
    orders = db.get_orders()
    customers = db.get_all_customers()
    print(f'📦 إجمالي الطلبات في النظام: {len(orders)}')
    print(f'👥 إجمالي العملاء المسجلين: {len(customers)}')
    print(f'🔔 نظام الإشعارات: {"مفعل" if SEND_NEW_PRODUCT_NOTIFICATIONS else "معطل"}')
    print('🤖 البوت يعمل...')
    print('=' * 60)
    
    app.run_polling(poll_interval=3)


if __name__ == '__main__':
    import asyncio
    main()