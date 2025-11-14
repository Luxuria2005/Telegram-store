# database.py - FIXED NOTIFICATION SYSTEM WITH BACKWARD COMPATIBILITY
import sqlite3
import json
import os
from datetime import datetime
from typing import List, Dict, Any, Optional
from config import LOW_STOCK_THRESHOLD, CRITICAL_STOCK_THRESHOLD
import hashlib
import secrets

class Database:
    def __init__(self, db_path='store.db'):
        self.db_path = db_path
        self._ensure_db_file()
        self.init_db()
        self.update_schema()  # ADD THIS LINE
    
    def _ensure_db_file(self):
        """Ensure the database file exists"""
        if not os.path.exists(self.db_path):
            print(f"📄 Creating new database file: {self.db_path}")
            open(self.db_path, 'a').close()
        else:
            print(f"✅ Database file exists: {self.db_path}")
    
    def update_schema(self):
        """Update database schema to add location fields and bot_users table"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                # Check if user_state column exists
                cursor.execute("PRAGMA table_info(orders)")
                columns = [column[1] for column in cursor.fetchall()]
                
                if 'user_state' not in columns:
                    print("🔄 Adding user_state column to orders table...")
                    cursor.execute('ALTER TABLE orders ADD COLUMN user_state TEXT')
                
                if 'user_region' not in columns:
                    print("🔄 Adding user_region column to orders table...")
                    cursor.execute('ALTER TABLE orders ADD COLUMN user_region TEXT')
                
                # ✅ NEW: Create bot_users table for tracking ALL users
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS bot_users (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        telegram_id INTEGER UNIQUE NOT NULL,
                        username TEXT,
                        first_name TEXT,
                        last_name TEXT,
                        phone TEXT,
                        total_interactions INTEGER DEFAULT 0,
                        has_placed_order BOOLEAN DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # ✅ NEW: Create dashboard_users table for admin/user access
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS dashboard_users (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        username TEXT UNIQUE NOT NULL,
                        password_hash TEXT NOT NULL,
                        role TEXT NOT NULL DEFAULT "user",
                        permissions TEXT,
                        is_active BOOLEAN DEFAULT 1,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        last_login TIMESTAMP,
                        full_name TEXT
                    )
                ''')
                
                # ✅ MIGRATE EXISTING CUSTOMERS TO BOT_USERS
                print("🔄 Migrating existing customers to bot_users table...")
                cursor.execute('''
                    INSERT OR IGNORE INTO bot_users (telegram_id, username, first_name, last_name, has_placed_order)
                    SELECT telegram_id, username, first_name, last_name, 1 
                    FROM customers 
                    WHERE telegram_id NOT IN (SELECT telegram_id FROM bot_users)
                ''')
                
                migrated_count = cursor.rowcount
                if migrated_count > 0:
                    print(f"✅ Migrated {migrated_count} existing customers to bot_users")
                
                # ✅ CREATE DEFAULT ADMIN USER if no users exist
                cursor.execute('SELECT COUNT(*) FROM dashboard_users')
                if cursor.fetchone()[0] == 0:
                    self._create_default_admin(cursor)
                
                # ✅ NEW: Create staff_activity_logs table for tracking staff activities
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS staff_activity_logs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        username TEXT,
                        full_name TEXT,
                        action_type TEXT NOT NULL,
                        action_description TEXT NOT NULL,
                        target_type TEXT,
                        target_id INTEGER,
                        target_name TEXT,
                        old_value TEXT,
                        new_value TEXT,
                        ip_address TEXT,
                        user_agent TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (user_id) REFERENCES dashboard_users (id)
                    )
                ''')
                
                # ✅ NEW: Create client_activity_logs table for tracking client/bot user activities
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS client_activity_logs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        telegram_id INTEGER NOT NULL,
                        username TEXT,
                        first_name TEXT,
                        last_name TEXT,
                        activity_type TEXT NOT NULL,
                        activity_description TEXT NOT NULL,
                        target_type TEXT,
                        target_id INTEGER,
                        target_name TEXT,
                        metadata TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (telegram_id) REFERENCES bot_users (telegram_id)
                    )
                ''')
                
                # Create indexes for better query performance
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_staff_logs_user_id ON staff_activity_logs(user_id)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_staff_logs_created_at ON staff_activity_logs(created_at)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_staff_logs_action_type ON staff_activity_logs(action_type)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_client_logs_telegram_id ON client_activity_logs(telegram_id)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_client_logs_created_at ON client_activity_logs(created_at)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_client_logs_activity_type ON client_activity_logs(activity_type)')
                
                conn.commit()
                print("✅ Database schema updated successfully!")
                
            except Exception as e:
                print(f"❌ Error updating schema: {e}")

    def _create_default_admin(self, cursor):
        """Create default admin user"""
        try:
            # Default admin credentials
            admin_username = "admin"
            admin_password = "admin123"  # User should change this
            admin_full_name = "مدير النظام"
            
            password_hash = self._hash_password(admin_password)
            
            cursor.execute('''
                INSERT INTO dashboard_users (username, password_hash, role, permissions, full_name)
                VALUES (?, ?, ?, ?, ?)
            ''', (admin_username, password_hash, "admin", "all", admin_full_name))
            
            print("✅ Created default admin user:")
            print(f"   👤 Username: {admin_username}")
            print(f"   🔑 Password: {admin_password}")
            print(f"   ⚠️  Please change the default password immediately!")
            
        except Exception as e:
            print(f"❌ Error creating default admin: {e}")

    def _hash_password(self, password):
        """Hash a password for storing"""
        salt = secrets.token_hex(16)
        return f"{salt}${hashlib.sha256((salt + password).encode()).hexdigest()}"

    def verify_password(self, stored_hash, provided_password):
        """Verify a stored password against one provided by user"""
        try:
            salt, stored_digest = stored_hash.split('$')
            computed_digest = hashlib.sha256((salt + provided_password).encode()).hexdigest()
            return secrets.compare_digest(stored_digest, computed_digest)
        except:
            return False

    def init_db(self):
        """Initialize database with enhanced inventory tracking AND LOCATION FIELDS"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Enable foreign keys and WAL mode for better performance
                cursor.execute('PRAGMA foreign_keys = ON')
                cursor.execute('PRAGMA journal_mode = WAL')
                
                # Categories table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS categories (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT UNIQUE NOT NULL,
                        arabic_name TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # Products table with enhanced fields
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS products (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        category_id INTEGER NOT NULL,
                        name TEXT NOT NULL,
                        arabic_name TEXT,
                        price REAL NOT NULL,
                        description TEXT,
                        arabic_description TEXT,
                        model_number TEXT UNIQUE,
                        barcode_data TEXT,
                        is_active BOOLEAN DEFAULT 1,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (category_id) REFERENCES categories (id)
                    )
                ''')
                
                # Product variants with inventory tracking
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS product_variants (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        product_id INTEGER NOT NULL,
                        color TEXT NOT NULL,
                        color_arabic TEXT,
                        size TEXT NOT NULL,
                        size_arabic TEXT,
                        quantity INTEGER DEFAULT 0,
                        min_stock_alert INTEGER DEFAULT 5,
                        image_path TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (product_id) REFERENCES products (id),
                        UNIQUE(product_id, color, size)
                    )
                ''')
                
                # Orders table with enhanced status tracking AND LOCATION FIELDS
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS orders (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        user_name TEXT NOT NULL,
                        user_phone TEXT NOT NULL,
                        user_address TEXT NOT NULL,
                        user_state TEXT,           -- NEW: State field
                        user_region TEXT,          -- NEW: Region field
                        username TEXT,
                        total_amount REAL NOT NULL,
                        status TEXT DEFAULT 'pending',
                        order_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        status_update TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        notes TEXT,
                        shipping_method TEXT
                    )
                ''')
                
                # Order items table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS order_items (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        order_id INTEGER NOT NULL,
                        product_id INTEGER NOT NULL,
                        variant_id INTEGER,
                        product_name TEXT NOT NULL,
                        price REAL NOT NULL,
                        quantity INTEGER NOT NULL,
                        color TEXT,
                        size TEXT,
                        FOREIGN KEY (order_id) REFERENCES orders (id),
                        FOREIGN KEY (product_id) REFERENCES products (id),
                        FOREIGN KEY (variant_id) REFERENCES product_variants (id)
                    )
                ''')
                
                # Inventory history for tracking changes
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS inventory_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        product_id INTEGER NOT NULL,
                        variant_id INTEGER,
                        change_type TEXT NOT NULL, -- 'sale', 'restock', 'adjustment'
                        old_quantity INTEGER,
                        new_quantity INTEGER,
                        change_amount INTEGER,
                        reason TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (product_id) REFERENCES products (id),
                        FOREIGN KEY (variant_id) REFERENCES product_variants (id)
                    )
                ''')
                
                # Customers table for notifications (existing - for buyers)
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS customers (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        telegram_id INTEGER UNIQUE NOT NULL,
                        username TEXT,
                        first_name TEXT,
                        last_name TEXT,
                        phone TEXT,
                        total_orders INTEGER DEFAULT 0,
                        total_spent REAL DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # ✅ NEW: Bot users table for ALL users (including non-buyers)
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS bot_users (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        telegram_id INTEGER UNIQUE NOT NULL,
                        username TEXT,
                        first_name TEXT,
                        last_name TEXT,
                        phone TEXT,
                        total_interactions INTEGER DEFAULT 0,
                        has_placed_order BOOLEAN DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # ✅ NEW: Dashboard users table for admin/user access
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS dashboard_users (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        username TEXT UNIQUE NOT NULL,
                        password_hash TEXT NOT NULL,
                        role TEXT NOT NULL DEFAULT "user",
                        permissions TEXT,
                        is_active BOOLEAN DEFAULT 1,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        last_login TIMESTAMP,
                        full_name TEXT
                    )
                ''')
                
                # Predefined sizes and colors for consistency
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS size_options (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        size_code TEXT UNIQUE NOT NULL,
                        arabic_name TEXT,
                        display_order INTEGER DEFAULT 0
                    )
                ''')
                
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS color_options (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        color_code TEXT UNIQUE NOT NULL,
                        arabic_name TEXT,
                        display_order INTEGER DEFAULT 0
                    )
                ''')
                
                # Insert default sizes and colors
                self._insert_default_options(cursor)
                
                # Create default admin user
                self._create_default_admin(cursor)
                
                conn.commit()
                print("✅ Enhanced database with inventory and location tracking created successfully!")
                
        except Exception as e:
            print(f"❌ Error creating database tables: {e}")
    
    def _insert_default_options(self, cursor):
        """Insert default size and color options"""
        # Default sizes
        sizes = [
            ('S', 'صغير', 1),
            ('M', 'متوسط', 2),
            ('L', 'كبير', 3),
            ('XL', 'كبير جداً', 4),
            ('XXL', 'مقاس إضافي', 5),
            ('XXXL', 'مقاس إضافي كبير', 6)
        ]
        
        cursor.executemany('''
            INSERT OR IGNORE INTO size_options (size_code, arabic_name, display_order)
            VALUES (?, ?, ?)
        ''', sizes)
        
        # Default colors
        colors = [
            ('Red', 'أحمر', 1),
            ('Blue', 'أزرق', 2),
            ('Black', 'أسود', 3),
            ('White', 'أبيض', 4),
            ('Green', 'أخضر', 5),
            ('Yellow', 'أصفر', 6),
            ('Pink', 'وردي', 7),
            ('Purple', 'بنفسجي', 8),
            ('Gray', 'رمادي', 9),
            ('Brown', 'بني', 10)
        ]
        
        cursor.executemany('''
            INSERT OR IGNORE INTO color_options (color_code, arabic_name, display_order)
            VALUES (?, ?, ?)
        ''', colors)
    
    def get_connection(self):
        """Get database connection"""
        return sqlite3.connect(self.db_path)

    # ✅ NEW: User Authentication Methods
    def authenticate_user(self, username, password):
        """Authenticate user credentials"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, username, password_hash, role, permissions, full_name, is_active
                FROM dashboard_users 
                WHERE username = ? AND is_active = 1
            ''', (username,))
            
            user = cursor.fetchone()
            if user and self.verify_password(user[2], password):
                # Update last login
                cursor.execute('''
                    UPDATE dashboard_users 
                    SET last_login = CURRENT_TIMESTAMP 
                    WHERE id = ?
                ''', (user[0],))
                conn.commit()
                
                return {
                    'id': user[0],
                    'username': user[1],
                    'role': user[3],
                    'permissions': user[4],
                    'full_name': user[5],
                    'is_active': user[6]
                }
            return None

    # ✅ FIXED: Create user method - PROPERLY HANDLE FULL_NAME
    def create_user(self, username, password, full_name=None, role="user", permissions=None):
        """Create a new dashboard user - FIXED: Properly handle full_name"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                password_hash = self._hash_password(password)
                permissions_json = json.dumps(permissions) if permissions else "{}"
                
                print(f"🔄 Creating user in database: {username}, Full Name: {full_name}, Role: {role}")
                
                cursor.execute('''
                    INSERT INTO dashboard_users (username, password_hash, role, permissions, full_name)
                    VALUES (?, ?, ?, ?, ?)
                ''', (username, password_hash, role, permissions_json, full_name))
                
                conn.commit()
                print(f"✅ Created user: {username} with full name: {full_name}, role: {role}")
                return cursor.lastrowid
            except sqlite3.IntegrityError:
                print(f"❌ Username {username} already exists")
                return None
            except Exception as e:
                print(f"❌ Error creating user: {e}")
                return None

    def get_all_users(self):
        """Get all dashboard users"""
        with self.get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, username, role, permissions, is_active, created_at, last_login, full_name
                FROM dashboard_users 
                ORDER BY created_at DESC
            ''')
            return [dict(row) for row in cursor.fetchall()]

    # ✅ FIXED: Update user method - PROPERLY HANDLE FULL_NAME
    def update_user(self, user_id, username=None, full_name=None, role=None, permissions=None, is_active=None):
        """Update user information - FIXED: Properly handle full_name"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                updates = []
                params = []
                
                if username is not None:
                    updates.append("username = ?")
                    params.append(username)
                if full_name is not None:
                    updates.append("full_name = ?")
                    params.append(full_name)
                if role is not None:
                    updates.append("role = ?")
                    params.append(role)
                if permissions is not None:
                    updates.append("permissions = ?")
                    params.append(json.dumps(permissions))
                if is_active is not None:
                    updates.append("is_active = ?")
                    params.append(is_active)
                
                if not updates:
                    return False
                    
                params.append(user_id)
                query = f"UPDATE dashboard_users SET {', '.join(updates)} WHERE id = ?"
                cursor.execute(query, params)
                
                conn.commit()
                print(f"✅ Updated user {user_id}: username={username}, full_name={full_name}")
                return True
            except Exception as e:
                print(f"❌ Error updating user: {e}")
                return False

    def change_user_password(self, user_id, new_password):
        """Change user password"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                password_hash = self._hash_password(new_password)
                cursor.execute('''
                    UPDATE dashboard_users 
                    SET password_hash = ? 
                    WHERE id = ?
                ''', (password_hash, user_id))
                
                conn.commit()
                print(f"✅ Changed password for user {user_id}")
                return True
            except Exception as e:
                print(f"❌ Error changing password: {e}")
                return False

    def delete_user(self, user_id):
        """Delete a user (cannot delete yourself)"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute('DELETE FROM dashboard_users WHERE id = ?', (user_id,))
                conn.commit()
                print(f"✅ Deleted user {user_id}")
                return True
            except Exception as e:
                print(f"❌ Error deleting user: {e}")
                return False

    def get_user_by_id(self, user_id):
        """Get user by ID"""
        with self.get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, username, role, permissions, is_active, created_at, last_login, full_name
                FROM dashboard_users 
                WHERE id = ?
            ''', (user_id,))
            
            user = cursor.fetchone()
            return dict(user) if user else None

    # ✅ FIXED: Bot Users Management Methods with proper migration
    def add_bot_user(self, telegram_id: int, username: str = None, first_name: str = None, last_name: str = None):
        """Add or update bot user (ALL users who interact with bot)"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute('''
                    INSERT OR REPLACE INTO bot_users 
                    (telegram_id, username, first_name, last_name, last_active, total_interactions)
                    VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, COALESCE((SELECT total_interactions + 1 FROM bot_users WHERE telegram_id = ?), 1))
                ''', (telegram_id, username, first_name, last_name, telegram_id))
                conn.commit()
                print(f"✅ Registered bot user: {first_name} ({telegram_id})")
                return True
            except Exception as e:
                print(f"❌ Error adding bot user: {e}")
                return False

    def mark_user_as_buyer(self, telegram_id: int):
        """Mark user as someone who placed an order"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute('''
                    UPDATE bot_users 
                    SET has_placed_order = 1 
                    WHERE telegram_id = ?
                ''', (telegram_id,))
                conn.commit()
                print(f"✅ Marked user {telegram_id} as buyer")
                return True
            except Exception as e:
                print(f"❌ Error marking user as buyer: {e}")
                return False

    def get_all_bot_users(self):
        """Get ALL bot users (including non-buyers)"""
        with self.get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM bot_users ORDER BY created_at DESC')
            return [dict(row) for row in cursor.fetchall()]

    def get_bot_users_count(self):
        """Get count of all bot users"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM bot_users')
            return cursor.fetchone()[0]

    def get_buyers_count(self):
        """Get count of users who placed orders"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM bot_users WHERE has_placed_order = 1')
            return cursor.fetchone()[0]

    # ✅ FIXED: Customer management - now updates both tables properly
    def add_customer(self, telegram_id: int, username: str = None, first_name: str = None, last_name: str = None, phone: str = None):
        """Add or update customer (for buyers) - NOW ALSO UPDATES BOT_USERS WITH PHONE"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                # Add to customers table (existing functionality)
                cursor.execute('''
                    INSERT OR REPLACE INTO customers 
                    (telegram_id, username, first_name, last_name, phone, last_active)
                    VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ''', (telegram_id, username, first_name, last_name, phone))
                
                # ✅ NEW: Also mark as buyer in bot_users table with phone
                cursor.execute('''
                    INSERT OR REPLACE INTO bot_users 
                    (telegram_id, username, first_name, last_name, phone, has_placed_order, last_active)
                    VALUES (?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP)
                ''', (telegram_id, username, first_name, last_name, phone))
                
                conn.commit()
                print(f"✅ Updated customer and marked as buyer: {first_name} ({telegram_id}) - Phone: {phone}")
                return True
            except Exception as e:
                print(f"❌ Error adding customer: {e}")
                return False

    # ✅ FIXED: Get all users for notifications (BACKWARD COMPATIBLE - uses customers table)
    def get_all_notification_users(self):
        """Get combined list of all users for notifications - FIXED VERSION"""
        with self.get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # ✅ FIXED: Get ALL users from bot_users table (including non-buyers)
            cursor.execute('''
                SELECT telegram_id, username, first_name, last_name 
                FROM bot_users 
                WHERE telegram_id IS NOT NULL
            ''')
            all_users = [dict(row) for row in cursor.fetchall()]
            
            print(f"📢 Found {len(all_users)} total users for notifications")
            return all_users

    # ✅ ADDED: Backward compatible method using only customers table
    def get_all_customers(self):
        """Get all customers from customers table (original method) - FIXED TO GET PHONE FROM ORDERS"""
        with self.get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # ✅ FIXED: Get customers with their latest phone number from orders
            cursor.execute('''
                SELECT 
                    c.*,
                    (SELECT o.user_phone 
                     FROM orders o 
                     WHERE o.user_id = c.telegram_id 
                     ORDER BY o.order_date DESC 
                     LIMIT 1) as latest_phone
                FROM customers c
                ORDER BY c.created_at DESC
            ''')
            
            customers = []
            for row in cursor.fetchall():
                customer = dict(row)
                # Use latest phone from orders if available, otherwise use customer phone
                if customer.get('latest_phone'):
                    customer['phone'] = customer['latest_phone']
                customers.append(customer)
            
            return customers

    # Category methods
    def add_category(self, name: str, arabic_name: str = None) -> int:
        """Add a new category with Arabic name"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute('''
                    INSERT OR IGNORE INTO categories (name, arabic_name) 
                    VALUES (?, ?)
                ''', (name, arabic_name or name))
                conn.commit()
                
                if cursor.rowcount > 0:
                    print(f"✅ Added new category: {name}")
                    return cursor.lastrowid
                else:
                    cursor.execute('SELECT id FROM categories WHERE name = ?', (name,))
                    result = cursor.fetchone()
                    return result[0] if result else 0
                    
            except Exception as e:
                print(f"❌ Error adding category {name}: {e}")
                return 0
    
    def get_categories(self) -> List[Dict]:
        """Get all categories"""
        with self.get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM categories ORDER BY name')
            return [dict(row) for row in cursor.fetchall()]

    # Product methods
    def add_product(self, category_name: str, name: str, price: float, 
                   description: str = "", model_number: str = "",
                   arabic_name: str = None, arabic_description: str = None) -> int:
        """Add a new product with Arabic support"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            try:
                # Ensure category exists
                category_id = self.add_category(category_name)
                
                if not category_id:
                    raise Exception(f"Failed to create or find category: {category_name}")
                
                cursor.execute('''
                    INSERT INTO products 
                    (category_id, name, arabic_name, price, description, arabic_description, model_number)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (category_id, name, arabic_name or name, price, 
                      description, arabic_description or description, model_number))
                
                conn.commit()
                product_id = cursor.lastrowid
                print(f"✅ Added product: {name} (ID: {product_id})")
                return product_id
                
            except Exception as e:
                print(f"❌ Error adding product {name}: {e}")
                return 0
    
    def add_product_variant(self, product_id: int, color: str, size: str, 
                           quantity: int = 0, color_arabic: str = None, 
                           size_arabic: str = None, image_path: str = None) -> int:
        """Add a variant to a product"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute('''
                    INSERT OR REPLACE INTO product_variants 
                    (product_id, color, color_arabic, size, size_arabic, quantity, image_path, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ''', (product_id, color, color_arabic or color, size, 
                      size_arabic or size, quantity, image_path))
                
                conn.commit()
                variant_id = cursor.lastrowid
                print(f"✅ Added variant: Product {product_id}, {color} {size}, Qty: {quantity}")
                return variant_id
                
            except Exception as e:
                print(f"❌ Error adding variant for product {product_id}: {e}")
                return 0

    def update_product(self, product_id: int, name: str = None, price: float = None, 
                      description: str = None, model_number: str = None) -> bool:
        """Update product basic information"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                # Build dynamic update query
                updates = []
                params = []
                
                if name is not None:
                    updates.append("name = ?")
                    params.append(name)
                if price is not None:
                    updates.append("price = ?")
                    params.append(price)
                if description is not None:
                    updates.append("description = ?")
                    params.append(description)
                if model_number is not None:
                    updates.append("model_number = ?")
                    params.append(model_number)
                
                if not updates:
                    return False
                    
                updates.append("updated_at = CURRENT_TIMESTAMP")
                params.append(product_id)
                
                query = f"UPDATE products SET {', '.join(updates)} WHERE id = ?"
                cursor.execute(query, params)
                
                conn.commit()
                print(f"✅ Updated product {product_id}")
                return True
                
            except Exception as e:
                print(f"❌ Error updating product: {e}")
                return False

    def delete_product_variant(self, product_id: int, color: str, size: str) -> bool:
        """Delete a specific product variant"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute('''
                    DELETE FROM product_variants 
                    WHERE product_id = ? AND color = ? AND size = ?
                ''', (product_id, color, size))
                
                conn.commit()
                print(f"✅ Deleted variant: {product_id}, {color} {size}")
                return True
                
            except Exception as e:
                print(f"❌ Error deleting variant: {e}")
                return False

    def update_product_price(self, product_id: int, new_price: float) -> bool:
        """Update product price"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute('''
                    UPDATE products 
                    SET price = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (new_price, product_id))
                
                conn.commit()
                print(f"✅ Updated price for product {product_id}: {new_price}")
                return True
                
            except Exception as e:
                print(f"❌ Error updating product price: {e}")
                return False

    def delete_product(self, product_id: int) -> bool:
        """Delete a product and its variants"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                # Delete variants first
                cursor.execute('DELETE FROM product_variants WHERE product_id = ?', (product_id,))
                # Delete product
                cursor.execute('DELETE FROM products WHERE id = ?', (product_id,))
                
                conn.commit()
                print(f"✅ Deleted product {product_id} and its variants")
                return True
                
            except Exception as e:
                print(f"❌ Error deleting product: {e}")
                return False

    def get_order_by_id(self, order_id: int) -> Dict:
        """Get order by ID"""
        with self.get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('SELECT * FROM orders WHERE id = ?', (order_id,))
            order = cursor.fetchone()
            
            if not order:
                return None
            
            order_dict = dict(order)
            
            # Get order items
            cursor.execute('SELECT * FROM order_items WHERE order_id = ?', (order_id,))
            order_dict['items'] = [dict(row) for row in cursor.fetchall()]
            
            return order_dict
    
    def get_size_options(self) -> List[Dict]:
        """Get all available size options"""
        with self.get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM size_options ORDER BY display_order')
            return [dict(row) for row in cursor.fetchall()]
    
    def get_color_options(self) -> List[Dict]:
        """Get all available color options"""
        with self.get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM color_options ORDER BY display_order')
            return [dict(row) for row in cursor.fetchall()]

    # Product retrieval methods - ENHANCED WITH OUT-OF-STOCK FILTERING
    def get_all_products(self) -> Dict[str, List[Dict]]:
        """Get all products organized by category - ONLY AVAILABLE VARIANTS"""
        with self.get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT 
                    c.name as category_name,
                    c.arabic_name as category_arabic,
                    p.id as product_id,
                    p.name as product_name,
                    p.arabic_name as product_arabic,
                    p.price,
                    p.description,
                    p.arabic_description,
                    p.model_number,
                    pv.id as variant_id,
                    pv.color,
                    pv.color_arabic,
                    pv.size,
                    pv.size_arabic,
                    pv.quantity,
                    pv.image_path
                FROM products p
                JOIN categories c ON p.category_id = c.id
                LEFT JOIN product_variants pv ON p.id = pv.product_id
                WHERE p.is_active = 1
                ORDER BY c.name, p.id, pv.color, pv.size
            ''')
            
            results = cursor.fetchall()
            products_by_category = {}
            
            for row in results:
                category = row['category_name']
                product_id = row['product_id']
                
                if category not in products_by_category:
                    products_by_category[category] = []
                
                # Find or create product
                product = None
                for p in products_by_category[category]:
                    if p['id'] == product_id:
                        product = p
                        break
                
                if not product:
                    product = {
                        'id': product_id,
                        'name': row['product_name'],
                        'arabic_name': row['product_arabic'],
                        'price': row['price'],
                        'description': row['description'] or '',
                        'arabic_description': row['arabic_description'] or '',
                        'model_number': row['model_number'] or '',
                        'category_arabic': row['category_arabic'],
                        'variants': []
                    }
                    products_by_category[category].append(product)
                
                # ✅ FIXED: Only add variants with quantity > 0
                if row['variant_id'] and row['quantity'] > 0:
                    variant = {
                        'id': row['variant_id'],
                        'color': row['color'],
                        'color_arabic': row['color_arabic'],
                        'size': row['size'],
                        'size_arabic': row['size_arabic'],
                        'quantity': row['quantity'],
                        'image_path': row['image_path']
                    }
                    product['variants'].append(variant)
            
            # ✅ FIXED: Remove products that have no available variants (completely out of stock)
            for category in list(products_by_category.keys()):
                products_by_category[category] = [
                    product for product in products_by_category[category] 
                    if product.get('variants') and len(product['variants']) > 0
                ]
                # Remove empty categories
                if len(products_by_category[category]) == 0:
                    del products_by_category[category]
            
            return products_by_category

    def get_product_by_id(self, product_id: int) -> Dict:
        """Get single product by ID with variants - ONLY AVAILABLE VARIANTS"""
        with self.get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT 
                    p.*,
                    pv.id as variant_id,
                    pv.color,
                    pv.color_arabic,
                    pv.size,
                    pv.size_arabic,
                    pv.quantity,
                    pv.image_path,
                    c.name as category_name,
                    c.arabic_name as category_arabic
                FROM products p
                LEFT JOIN product_variants pv ON p.id = pv.product_id
                LEFT JOIN categories c ON p.category_id = c.id
                WHERE p.id = ? AND p.is_active = 1
            ''', (product_id,))
            
            results = cursor.fetchall()
            if not results:
                return None
            
            product = None
            variants = []
            
            for row in results:
                if not product:
                    product = {
                        'id': row['id'],
                        'name': row['name'],
                        'arabic_name': row['arabic_name'],
                        'price': row['price'],
                        'description': row['description'],
                        'arabic_description': row['arabic_description'],
                        'model_number': row['model_number'],
                        'category': row['category_name'],
                        'category_arabic': row['category_arabic'],
                        'variants': variants
                    }
                
                # ✅ FIXED: Only add variants with quantity > 0
                if row['variant_id'] and row['quantity'] > 0:
                    variant = {
                        'id': row['variant_id'],
                        'color': row['color'],
                        'color_arabic': row['color_arabic'],
                        'size': row['size'],
                        'size_arabic': row['size_arabic'],
                        'quantity': row['quantity'],
                        'image_path': row['image_path']
                    }
                    variants.append(variant)
            
            return product

    def get_color_image(self, product_id: int, color: str) -> str:
        """Get the image path for a specific color"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT image_path FROM product_variants 
                WHERE product_id = ? AND color = ? AND image_path IS NOT NULL
                LIMIT 1
            ''', (product_id, color))
            
            result = cursor.fetchone()
            return result[0] if result else None

    # ✅ FIXED: Enhanced inventory validation
    def check_inventory(self, product_id: int, color: str, size: str, quantity: int = 1) -> Dict:
        """Check if requested inventory is available with detailed validation"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT quantity FROM product_variants 
                WHERE product_id = ? AND color = ? AND size = ?
            ''', (product_id, color, size))
            
            result = cursor.fetchone()
            
            if not result:
                return {
                    'available': False,
                    'message': f'المنتج غير متوفر باللون {color} والمقاس {size}',
                    'current_stock': 0,
                    'requested': quantity
                }
            
            current_stock = result[0]
            
            if current_stock <= 0:
                return {
                    'available': False,
                    'message': f'المنتج غير متوفر حالياً باللون {color} والمقاس {size}',
                    'current_stock': current_stock,
                    'requested': quantity
                }
            
            if current_stock < quantity:
                return {
                    'available': False,
                    'message': f'الكمية المطلوبة ({quantity}) تتجاوز المخزون المتاح ({current_stock}) للون {color} والمقاس {size}',
                    'current_stock': current_stock,
                    'requested': quantity
                }
            
            return {
                'available': True,
                'message': 'الكمية متاحة',
                'current_stock': current_stock,
                'requested': quantity
            }

    def get_variant_id(self, product_id: int, color: str, size: str) -> int:
        """Get variant ID for given product, color and size"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id FROM product_variants 
                WHERE product_id = ? AND color = ? AND size = ?
            ''', (product_id, color, size))
            
            result = cursor.fetchone()
            return result[0] if result else None

    def update_variant_quantity(self, product_id: int, color: str, size: str, 
                               new_quantity: int, reason: str = "manual_update") -> bool:
        """Update quantity for a specific variant with history tracking"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                # Get current quantity
                cursor.execute('''
                    SELECT quantity FROM product_variants 
                    WHERE product_id = ? AND color = ? AND size = ?
                ''', (product_id, color, size))
                
                result = cursor.fetchone()
                if not result:
                    return False
                
                old_quantity = result[0]
                change_amount = new_quantity - old_quantity
                
                # Update quantity
                cursor.execute('''
                    UPDATE product_variants 
                    SET quantity = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE product_id = ? AND color = ? AND size = ?
                ''', (new_quantity, product_id, color, size))
                
                # Get variant ID for history
                variant_id = self.get_variant_id(product_id, color, size)
                
                # Record inventory history
                cursor.execute('''
                    INSERT INTO inventory_history 
                    (product_id, variant_id, change_type, old_quantity, new_quantity, change_amount, reason)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (product_id, variant_id, 'adjustment', old_quantity, new_quantity, change_amount, reason))
                
                conn.commit()
                print(f"✅ Updated quantity for product {product_id}, {color} {size}: {old_quantity} → {new_quantity}")
                return True
                
            except Exception as e:
                print(f"❌ Error updating variant quantity: {e}")
                return False

    # ✅ FIXED: Order creation with enhanced inventory validation AND LOCATION
    def create_order(self, user_id: int, user_name: str, user_phone: str, 
                    user_address: str, user_state: str, user_region: str,
                    username: str, items: List[Dict], 
                    total_amount: float, notes: str = None) -> Dict:
        """Create a new order with comprehensive inventory validation AND LOCATION"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            try:
                print(f"🔄 Creating order for user: {user_name}, State: {user_state}, Region: {user_region}")
                
                # ✅ Validate inventory for ALL items before processing
                inventory_errors = []
                for item in items:
                    product_id = item['product_id']
                    color = item.get('color')
                    size = item.get('size')
                    quantity = item['quantity']
                    
                    if color and size:  # Only validate variants with color/size
                        inventory_check = self.check_inventory(product_id, color, size, quantity)
                        if not inventory_check['available']:
                            inventory_errors.append({
                                'product': item['name'],
                                'color': color,
                                'size': size,
                                'message': inventory_check['message']
                            })
                
                # If any inventory errors, return them without creating order
                if inventory_errors:
                    return {
                        'success': False,
                        'order_id': None,
                        'errors': inventory_errors
                    }
                
                # Create order WITH LOCATION FIELDS - FIXED QUERY
                cursor.execute('''
                    INSERT INTO orders 
                    (user_id, user_name, user_phone, user_address, user_state, user_region, username, total_amount, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (user_id, user_name, user_phone, user_address, user_state, user_region, username, total_amount, notes))
                
                order_id = cursor.lastrowid
                
                # Add order items and update inventory
                for item in items:
                    variant_id = None
                    if item.get('color') and item.get('size'):
                        variant_id = self.get_variant_id(item['product_id'], item.get('color'), item.get('size'))
                    
                    cursor.execute('''
                        INSERT INTO order_items 
                        (order_id, product_id, variant_id, product_name, price, quantity, color, size)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (order_id, item['product_id'], variant_id, item['name'], 
                          item['price'], item['quantity'], item.get('color'), item.get('size')))
                    
                    # Update inventory and record history
                    if variant_id:
                        # Get current quantity
                        cursor.execute('SELECT quantity FROM product_variants WHERE id = ?', (variant_id,))
                        result = cursor.fetchone()
                        if result:
                            current_qty = result[0]
                            new_qty = current_qty - item['quantity']
                            
                            cursor.execute('''
                                UPDATE product_variants 
                                SET quantity = ?, updated_at = CURRENT_TIMESTAMP
                                WHERE id = ? AND quantity >= ?
                            ''', (new_qty, variant_id, item['quantity']))
                            
                            # Record inventory history for sale
                            cursor.execute('''
                                INSERT INTO inventory_history 
                                (product_id, variant_id, change_type, old_quantity, new_quantity, change_amount, reason)
                                VALUES (?, ?, 'sale', ?, ?, ?, ?)
                            ''', (item['product_id'], variant_id, current_qty, new_qty, -item['quantity'], f'Order #{order_id}'))
                
                # ✅ NEW: Mark user as buyer in bot_users table with phone number
                cursor.execute('''
                    INSERT OR REPLACE INTO bot_users 
                    (telegram_id, username, first_name, last_name, phone, has_placed_order, last_active)
                    VALUES (?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP)
                ''', (user_id, username, user_name.split(' ')[0] if user_name else '', 
                      ' '.join(user_name.split(' ')[1:]) if user_name and ' ' in user_name else '', 
                      user_phone))
                
                # ✅ NEW: Also update customers table with phone number
                cursor.execute('''
                    INSERT OR REPLACE INTO customers 
                    (telegram_id, username, first_name, last_name, phone, last_active)
                    VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ''', (user_id, username, user_name.split(' ')[0] if user_name else '', 
                      ' '.join(user_name.split(' ')[1:]) if user_name and ' ' in user_name else '', 
                      user_phone))
                
                conn.commit()
                print(f"✅ Created order: #{order_id} for user {user_name} in {user_state}, {user_region}")
                return {
                    'success': True,
                    'order_id': order_id,
                    'errors': []
                }
                
            except Exception as e:
                conn.rollback()
                print(f"❌ Error creating order: {e}")
                import traceback
                traceback.print_exc()  # This will show the full error trace
                return {
                    'success': False,
                    'order_id': None,
                    'errors': [{'message': f'خطأ في النظام: {str(e)}'}]
                }

    def cancel_order(self, order_id: int) -> bool:
        """Cancel an order and RESTORE inventory quantities"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            try:
                # Get all items from the order
                cursor.execute('SELECT * FROM order_items WHERE order_id = ?', (order_id,))
                order_items = [dict(row) for row in cursor.fetchall()]
                
                if not order_items:
                    print(f"❌ No items found for order #{order_id}")
                    return False
                
                # ✅ RESTORE INVENTORY: INCREASE quantities
                for item in order_items:
                    product_id = item['product_id']
                    color = item['color']
                    size = item['size']
                    quantity = item['quantity']
                    
                    if color and size:  # Only for variants with color/size
                        variant_id = self.get_variant_id(product_id, color, size)
                        
                        if variant_id:
                            # Get current quantity
                            cursor.execute('SELECT quantity FROM product_variants WHERE id = ?', (variant_id,))
                            result = cursor.fetchone()
                            current_qty = result[0] if result else 0
                            new_qty = current_qty + quantity  # ⬆️ INCREASE inventory
                            
                            # Update inventory
                            cursor.execute('''
                                UPDATE product_variants 
                                SET quantity = ?, updated_at = CURRENT_TIMESTAMP
                                WHERE id = ?
                            ''', (new_qty, variant_id))
                            
                            # Record inventory history for cancellation
                            cursor.execute('''
                                INSERT INTO inventory_history 
                                (product_id, variant_id, change_type, old_quantity, new_quantity, change_amount, reason)
                                VALUES (?, ?, 'restock', ?, ?, ?, ?)
                            ''', (product_id, variant_id, current_qty, new_qty, quantity, f'Order #{order_id} cancellation'))
                            
                            print(f"✅ Restored {quantity} items for {color} {size}")
                
                # Update order status to cancelled
                cursor.execute('''
                    UPDATE orders 
                    SET status = 'cancelled', status_update = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (order_id,))
                
                conn.commit()
                print(f"✅ Cancelled order #{order_id} and restored inventory")
                return True
                
            except Exception as e:
                conn.rollback()
                print(f"❌ Error cancelling order: {e}")
                return False

    def get_orders(self) -> List[Dict]:
        """Get all orders with items - FIXED: Sort by ID DESC (newest first)"""
        with self.get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # FIXED: Changed from order_date DESC to id DESC for proper newest-first sorting
            cursor.execute('SELECT * FROM orders ORDER BY id DESC')
            orders = [dict(row) for row in cursor.fetchall()]
            
            # Get order items for each order
            for order in orders:
                cursor.execute('''
                    SELECT * FROM order_items WHERE order_id = ?
                ''', (order['id'],))
                order['items'] = [dict(row) for row in cursor.fetchall()]
            
            return orders

    def get_order_status(self, order_id: int) -> str:
        """Get current status of an order"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT status FROM orders WHERE id = ?', (order_id,))
            result = cursor.fetchone()
            return result[0] if result else None

    def update_order_status(self, order_id: int, new_status: str) -> bool:
        """Update order status (pending → confirmed → shipped → completed)"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute('''
                    UPDATE orders 
                    SET status = ?, status_update = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (new_status, order_id))
                
                conn.commit()
                print(f"✅ Updated order #{order_id} status to: {new_status}")
                return True
            except Exception as e:
                print(f"❌ Error updating order status: {e}")
                return False

    # ✅ FIXED: Get available variants only (hide zero quantities)
    def get_available_variants(self, product_id: int) -> List[Dict]:
        """Get only variants with quantity > 0"""
        with self.get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT * FROM product_variants 
                WHERE product_id = ? AND quantity > 0
                ORDER BY color, size
            ''', (product_id,))
            
            return [dict(row) for row in cursor.fetchall()]

    # Analytics methods
    def get_inventory_analytics(self) -> Dict:
        """Get comprehensive inventory analytics"""
        with self.get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Basic inventory stats
            cursor.execute('''
                SELECT 
                    COUNT(DISTINCT p.id) as total_products,
                    COUNT(pv.id) as total_variants,
                    SUM(CASE WHEN pv.quantity = 0 THEN 1 ELSE 0 END) as out_of_stock,
                    SUM(CASE WHEN pv.quantity > 0 AND pv.quantity <= pv.min_stock_alert THEN 1 ELSE 0 END) as low_stock,
                    SUM(pv.quantity) as total_inventory_value
                FROM products p
                LEFT JOIN product_variants pv ON p.id = pv.product_id
                WHERE p.is_active = 1
            ''')
            
            stats = dict(cursor.fetchone())
            
            # Category-wise breakdown
            cursor.execute('''
                SELECT 
                    c.name as category,
                    c.arabic_name as category_arabic,
                    COUNT(DISTINCT p.id) as product_count,
                    COUNT(pv.id) as variant_count,
                    SUM(CASE WHEN pv.quantity = 0 THEN 1 ELSE 0 END) as out_of_stock,
                    SUM(CASE WHEN pv.quantity > 0 AND pv.quantity <= pv.min_stock_alert THEN 1 ELSE 0 END) as low_stock
                FROM categories c
                LEFT JOIN products p ON c.id = p.category_id
                LEFT JOIN product_variants pv ON p.id = pv.product_id
                WHERE p.is_active = 1
                GROUP BY c.id, c.name
                ORDER BY c.name
            ''')
            
            stats['category_breakdown'] = [dict(row) for row in cursor.fetchall()]
            
            return stats
        
    # ✅ FIXED: Delete order with PROPER status checking and inventory restoration
    def delete_order(self, order_id: int) -> Dict:
        """Delete an order with status validation and inventory restoration"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                print(f"🔍 Checking order #{order_id} for deletion...")
                
                # Get order status first
                cursor.execute('SELECT id, status FROM orders WHERE id = ?', (order_id,))
                order_row = cursor.fetchone()
                
                if not order_row:
                    return {
                        'success': False,
                        'message': f'الطلب #{order_id} غير موجود',
                        'can_delete': False
                    }
                
                # Convert to dictionary properly
                order_id = order_row[0]
                current_status = str(order_row[1]).lower() if order_row[1] else ''
                
                print(f"📋 Order #{order_id} status: {current_status}")
                
                # Define deletable and non-deletable statuses
                deletable_statuses = ['pending', 'confirmed', 'shipped', 'معلق', 'مؤكد', 'مشحون']
                non_deletable_statuses = ['delivered', 'completed', 'تم التوصيل', 'مكتمل']
                
                # Check if order can be deleted based on status
                can_delete = any(status in current_status for status in deletable_statuses)
                cannot_delete = any(status in current_status for status in non_deletable_statuses)
                
                if cannot_delete:
                    return {
                        'success': False,
                        'message': f'لا يمكن حذف الطلب #{order_id} لأن حالته "{order_row[1]}" - الطلبات المكتملة أو المسلمة لا يمكن حذفها',
                        'can_delete': False
                    }
                
                if not can_delete:
                    return {
                        'success': False,
                        'message': f'لا يمكن حذف الطلب #{order_id} بسبب حالته "{order_row[1]}"',
                        'can_delete': False
                    }
                
                print(f"🗑️ Proceeding with deletion of order #{order_id}")
                
                # Get all items from the order
                cursor.execute('SELECT * FROM order_items WHERE order_id = ?', (order_id,))
                order_items_rows = cursor.fetchall()
                
                if not order_items_rows:
                    print(f"❌ No items found for order #{order_id}")
                    # Still delete the order even if no items found
                    cursor.execute('DELETE FROM orders WHERE id = ?', (order_id,))
                    conn.commit()
                    return {
                        'success': True,
                        'message': f'تم حذف الطلب #{order_id} (لم يكن يحتوي على عناصر)',
                        'can_delete': True,
                        'restored_items': 0
                    }
                
                # Convert rows to dictionaries
                order_items = []
                for row in order_items_rows:
                    order_items.append(dict(zip([col[0] for col in cursor.description], row)))
                
                # ✅ RESTORE INVENTORY for all items
                restored_items = 0
                for item in order_items:
                    product_id = item.get('product_id')
                    color = item.get('color')
                    size = item.get('size')
                    quantity = item.get('quantity', 0)
                    
                    if color and size and product_id:  # Only for variants with color/size
                        try:
                            # Get current quantity
                            cursor.execute('''
                                SELECT quantity FROM product_variants 
                                WHERE product_id = ? AND color = ? AND size = ?
                            ''', (product_id, color, size))
                            
                            result = cursor.fetchone()
                            if result:
                                current_qty = result[0] if result[0] is not None else 0
                                new_qty = current_qty + quantity
                                
                                # Update inventory
                                cursor.execute('''
                                    UPDATE product_variants 
                                    SET quantity = ?, updated_at = CURRENT_TIMESTAMP
                                    WHERE product_id = ? AND color = ? AND size = ?
                                ''', (new_qty, product_id, color, size))
                                
                                print(f"✅ Restored {quantity} items for product {product_id}, {color} {size}")
                                restored_items += 1
                                
                        except Exception as inv_error:
                            print(f"⚠️ Error restoring inventory for item: {inv_error}")
                            continue
                
                # Delete order items and order
                cursor.execute('DELETE FROM order_items WHERE order_id = ?', (order_id,))
                cursor.execute('DELETE FROM orders WHERE id = ?', (order_id,))
                
                conn.commit()
                print(f"✅ Successfully deleted order #{order_id} and restored {restored_items} inventory items")
                
                return {
                    'success': True,
                    'message': f'تم حذف الطلب #{order_id} بنجاح واستعادة {restored_items} عنصر من المخزون',
                    'can_delete': True,
                    'restored_items': restored_items
                }
                
            except Exception as e:
                conn.rollback()
                print(f"❌ Error deleting order #{order_id}: {e}")
                import traceback
                traceback.print_exc()
                return {
                    'success': False,
                    'message': f'حدث خطأ أثناء حذف الطلب: {str(e)}',
                    'can_delete': False
                }

    def get_sales_analytics(self, days: int = 30) -> Dict:
        """Get sales analytics for the specified period"""
        with self.get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT 
                    COUNT(*) as total_orders,
                    SUM(total_amount) as total_revenue,
                    AVG(total_amount) as average_order_value
                FROM orders 
                WHERE order_date >= datetime('now', ?)
            ''', (f'-{days} days',))
            
            sales_stats = dict(cursor.fetchone())
            
            # Top selling products
            cursor.execute('''
                SELECT 
                    p.name,
                    p.arabic_name,
                    p.model_number,
                    SUM(oi.quantity) as total_sold,
                    SUM(oi.quantity * oi.price) as total_revenue
                FROM order_items oi
                JOIN products p ON oi.product_id = p.id
                JOIN orders o ON oi.order_id = o.id
                WHERE o.order_date >= datetime('now', ?)
                GROUP BY p.id, p.name
                ORDER BY total_sold DESC
                LIMIT 10
            ''', (f'-{days} days',))
            
            sales_stats['top_products'] = [dict(row) for row in cursor.fetchall()]
            
            return sales_stats

    def get_customer_orders_summary(self, telegram_id: int) -> Dict:
        """Get customer orders summary"""
        with self.get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT 
                    COUNT(*) as total_orders,
                    SUM(total_amount) as total_spent,
                    MAX(order_date) as last_order_date
                FROM orders 
                WHERE user_id = ?
            ''', (telegram_id,))
            
            result = cursor.fetchone()
            return dict(result) if result else {
                'total_orders': 0,
                'total_spent': 0,
                'last_order_date': None
            }

    def get_product_sales_data(self, product_id: int) -> Dict:
        """Get product sales data for reporting"""
        with self.get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Get total sold quantity and revenue
            cursor.execute('''
                SELECT 
                    SUM(oi.quantity) as total_sold,
                    SUM(oi.quantity * oi.price) as total_revenue
                FROM order_items oi
                JOIN orders o ON oi.order_id = o.id
                WHERE oi.product_id = ?
            ''', (product_id,))
            
            sales_data = cursor.fetchone()
            
            # Get current inventory
            cursor.execute('''
                SELECT SUM(quantity) as current_stock
                FROM product_variants
                WHERE product_id = ?
            ''', (product_id,))
            
            inventory_data = cursor.fetchone()
            
            return {
                'total_sold': sales_data['total_sold'] or 0,
                'total_revenue': sales_data['total_revenue'] or 0,
                'current_stock': inventory_data['current_stock'] or 0
            }

    def get_all_customers_with_orders(self) -> List[Dict]:
        """Get all customers with their order statistics"""
        with self.get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT 
                    c.*,
                    COUNT(o.id) as total_orders,
                    SUM(o.total_amount) as total_spent,
                    MAX(o.order_date) as last_order_date
                FROM customers c
                LEFT JOIN orders o ON c.telegram_id = o.user_id
                GROUP BY c.telegram_id
                ORDER BY total_spent DESC
            ''')
            
            return [dict(row) for row in cursor.fetchall()]

    def get_products_performance(self) -> List[Dict]:
        """Get products performance data for reports - INCLUDING SOLD-OUT PRODUCTS"""
        with self.get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT 
                    p.id,
                    p.name,
                    p.model_number,
                    p.price,
                    c.name as category,
                    SUM(pv.quantity) as current_stock,
                    (SELECT SUM(oi.quantity) 
                    FROM order_items oi 
                    JOIN orders o ON oi.order_id = o.id 
                    WHERE oi.product_id = p.id) as total_sold,
                    (SELECT SUM(oi.quantity * oi.price) 
                    FROM order_items oi 
                    JOIN orders o ON oi.order_id = o.id 
                    WHERE oi.product_id = p.id) as total_revenue
                FROM products p
                JOIN categories c ON p.category_id = c.id
                LEFT JOIN product_variants pv ON p.id = pv.product_id
                WHERE p.is_active = 1
                GROUP BY p.id
                ORDER BY total_revenue DESC
            ''')
            
            results = []
            for row in cursor.fetchall():
                row_dict = dict(row)
                # Calculate initial quantity (current stock + total sold)
                current_stock = row_dict['current_stock'] or 0
                total_sold = row_dict['total_sold'] or 0
                row_dict['initial_quantity'] = current_stock + total_sold
                row_dict['remaining_quantity'] = current_stock
                row_dict['sold_quantity'] = total_sold
                
                # ✅ FIXED: Include ALL products (even sold-out ones with 0 remaining quantity)
                # Only exclude products that have never been sold AND have no current stock
                if total_sold > 0 or current_stock > 0:
                    results.append(row_dict)
            
            return results
        

    #Add Delivered Orders Methods    
    def get_delivered_orders_by_date_range(self, start_date, end_date):
        """Get delivered orders between two dates - ONLY delivered status"""
        with self.get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Define delivered statuses in both Arabic and English
            delivered_statuses = ['تم التوصيل', 'delivered', 'مكتمل', 'completed']
            
            # Build status condition
            status_conditions = " OR ".join([f"status LIKE '%{status}%'" for status in delivered_statuses])
            
            cursor.execute(f'''
                SELECT * FROM orders 
                WHERE ({status_conditions}) 
                AND date(order_date) BETWEEN date(?) AND date(?)
                ORDER BY order_date DESC
            ''', (start_date, end_date))
            
            orders = [dict(row) for row in cursor.fetchall()]
            
            # Get order items for each order
            for order in orders:
                cursor.execute('SELECT * FROM order_items WHERE order_id = ?', (order['id'],))
                order['items'] = [dict(row) for row in cursor.fetchall()]
            
            return orders

    def get_delivered_revenue_by_date_range(self, start_date, end_date):
        """Calculate total revenue from delivered orders in date range"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Define delivered statuses
            delivered_statuses = ['تم التوصيل', 'delivered', 'مكتمل', 'completed']
            status_conditions = " OR ".join([f"status LIKE '%{status}%'" for status in delivered_statuses])
            
            cursor.execute(f'''
                SELECT SUM(total_amount) as total_revenue 
                FROM orders 
                WHERE ({status_conditions}) 
                AND date(order_date) BETWEEN date(?) AND date(?)
            ''', (start_date, end_date))
            
            result = cursor.fetchone()
            return result[0] if result and result[0] else 0

    # ✅ NEW: Staff Activity Logging Methods
    def log_staff_activity(self, user_id: int, action_type: str, action_description: str,
                          target_type: str = None, target_id: int = None, target_name: str = None,
                          old_value: str = None, new_value: str = None, ip_address: str = None,
                          user_agent: str = None):
        """Log staff activity in the dashboard"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                # Get user info
                user = self.get_user_by_id(user_id)
                username = user.get('username', '') if user else ''
                full_name = user.get('full_name', '') if user else ''
                
                cursor.execute('''
                    INSERT INTO staff_activity_logs 
                    (user_id, username, full_name, action_type, action_description, 
                     target_type, target_id, target_name, old_value, new_value, 
                     ip_address, user_agent)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (user_id, username, full_name, action_type, action_description,
                      target_type, target_id, target_name, old_value, new_value,
                      ip_address, user_agent))
                
                conn.commit()
                print(f"✅ Logged staff activity: {action_type} by {username}")
                return True
            except Exception as e:
                print(f"❌ Error logging staff activity: {e}")
                return False

    def get_staff_activity_logs(self, user_id: int = None, action_type: str = None, 
                               limit: int = 100, offset: int = 0, 
                               start_date: str = None, end_date: str = None):
        """Get staff activity logs with optional filters"""
        with self.get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            query = 'SELECT * FROM staff_activity_logs WHERE 1=1'
            params = []
            
            if user_id:
                query += ' AND user_id = ?'
                params.append(user_id)
            
            if action_type:
                query += ' AND action_type = ?'
                params.append(action_type)
            
            if start_date:
                query += ' AND date(created_at) >= date(?)'
                params.append(start_date)
            
            if end_date:
                query += ' AND date(created_at) <= date(?)'
                params.append(end_date)
            
            query += ' ORDER BY created_at DESC LIMIT ? OFFSET ?'
            params.extend([limit, offset])
            
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    def get_staff_activity_stats(self, days: int = 30):
        """Get statistics about staff activities"""
        with self.get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Total activities
            cursor.execute('''
                SELECT COUNT(*) as total_activities
                FROM staff_activity_logs
                WHERE created_at >= datetime('now', ?)
            ''', (f'-{days} days',))
            total = dict(cursor.fetchone())
            
            # Activities by type
            cursor.execute('''
                SELECT action_type, COUNT(*) as count
                FROM staff_activity_logs
                WHERE created_at >= datetime('now', ?)
                GROUP BY action_type
                ORDER BY count DESC
            ''', (f'-{days} days',))
            by_type = [dict(row) for row in cursor.fetchall()]
            
            # Activities by user
            cursor.execute('''
                SELECT user_id, username, full_name, COUNT(*) as count
                FROM staff_activity_logs
                WHERE created_at >= datetime('now', ?)
                GROUP BY user_id, username, full_name
                ORDER BY count DESC
                LIMIT 10
            ''', (f'-{days} days',))
            by_user = [dict(row) for row in cursor.fetchall()]
            
            return {
                'total_activities': total.get('total_activities', 0),
                'by_type': by_type,
                'by_user': by_user
            }

    # ✅ NEW: Client Activity Logging Methods
    def log_client_activity(self, telegram_id: int, activity_type: str, activity_description: str,
                           target_type: str = None, target_id: int = None, target_name: str = None,
                           metadata: str = None):
        """Log client/bot user activity"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                # Get user info from bot_users
                cursor.execute('''
                    SELECT username, first_name, last_name 
                    FROM bot_users 
                    WHERE telegram_id = ?
                ''', (telegram_id,))
                user_info = cursor.fetchone()
                
                username = user_info[0] if user_info and user_info[0] else None
                first_name = user_info[1] if user_info and user_info[1] else None
                last_name = user_info[2] if user_info and user_info[2] else None
                
                # Convert metadata dict to JSON string if needed
                if metadata and isinstance(metadata, dict):
                    metadata = json.dumps(metadata)
                
                cursor.execute('''
                    INSERT INTO client_activity_logs 
                    (telegram_id, username, first_name, last_name, activity_type, 
                     activity_description, target_type, target_id, target_name, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (telegram_id, username, first_name, last_name, activity_type,
                      activity_description, target_type, target_id, target_name, metadata))
                
                conn.commit()
                print(f"✅ Logged client activity: {activity_type} by user {telegram_id}")
                return True
            except Exception as e:
                print(f"❌ Error logging client activity: {e}")
                return False

    def get_client_activity_logs(self, telegram_id: int = None, activity_type: str = None,
                                limit: int = 100, offset: int = 0,
                                start_date: str = None, end_date: str = None):
        """Get client activity logs with optional filters"""
        with self.get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            query = 'SELECT * FROM client_activity_logs WHERE 1=1'
            params = []
            
            if telegram_id:
                query += ' AND telegram_id = ?'
                params.append(telegram_id)
            
            if activity_type:
                query += ' AND activity_type = ?'
                params.append(activity_type)
            
            if start_date:
                query += ' AND date(created_at) >= date(?)'
                params.append(start_date)
            
            if end_date:
                query += ' AND date(created_at) <= date(?)'
                params.append(end_date)
            
            query += ' ORDER BY created_at DESC LIMIT ? OFFSET ?'
            params.extend([limit, offset])
            
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    def get_client_activity_stats(self, days: int = 30):
        """Get statistics about client activities"""
        with self.get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Total activities
            cursor.execute('''
                SELECT COUNT(*) as total_activities
                FROM client_activity_logs
                WHERE created_at >= datetime('now', ?)
            ''', (f'-{days} days',))
            total = dict(cursor.fetchone())
            
            # Activities by type
            cursor.execute('''
                SELECT activity_type, COUNT(*) as count
                FROM client_activity_logs
                WHERE created_at >= datetime('now', ?)
                GROUP BY activity_type
                ORDER BY count DESC
            ''', (f'-{days} days',))
            by_type = [dict(row) for row in cursor.fetchall()]
            
            # Most active users
            cursor.execute('''
                SELECT telegram_id, username, first_name, last_name, COUNT(*) as count
                FROM client_activity_logs
                WHERE created_at >= datetime('now', ?)
                GROUP BY telegram_id, username, first_name, last_name
                ORDER BY count DESC
                LIMIT 10
            ''', (f'-{days} days',))
            by_user = [dict(row) for row in cursor.fetchall()]
            
            return {
                'total_activities': total.get('total_activities', 0),
                'by_type': by_type,
                'by_user': by_user
            }

    def get_client_interests(self, telegram_id: int, days: int = 30):
        """Get detailed client interests and behavior patterns"""
        with self.get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Get all activities for this client
            cursor.execute('''
                SELECT activity_type, activity_description, target_type, target_id, target_name, metadata, created_at
                FROM client_activity_logs
                WHERE telegram_id = ? AND created_at >= datetime('now', ?)
                ORDER BY created_at DESC
            ''', (telegram_id, f'-{days} days'))
            
            activities = [dict(row) for row in cursor.fetchall()]
            
            # Analyze interests
            interests = {
                'browsed_categories': {},
                'viewed_products': {},
                'cart_additions': {},
                'purchased_products': {},
                'favorite_colors': {},
                'favorite_sizes': {},
                'activity_timeline': [],
                'shopping_behavior': {
                    'total_browses': 0,
                    'total_cart_adds': 0,
                    'total_orders': 0,
                    'cart_abandonment_rate': 0,
                    'average_order_value': 0,
                    'most_active_day': None,
                    'most_active_hour': None
                }
            }
            
            # Parse activities
            cart_adds = 0
            orders = 0
            total_order_value = 0
            day_counts = {}
            hour_counts = {}
            
            for activity in activities:
                activity_type = activity.get('activity_type', '')
                metadata_str = activity.get('metadata', '')
                created_at = activity.get('created_at', '')
                
                # Track timeline
                interests['activity_timeline'].append({
                    'type': activity_type,
                    'description': activity.get('activity_description', ''),
                    'timestamp': created_at
                })
                
                # Parse metadata
                try:
                    if metadata_str:
                        metadata = json.loads(metadata_str)
                    else:
                        metadata = {}
                except:
                    metadata = {}
                
                # Analyze by activity type
                if activity_type == 'browse_products':
                    interests['shopping_behavior']['total_browses'] += 1
                elif activity_type == 'add_to_cart':
                    cart_adds += 1
                    interests['shopping_behavior']['total_cart_adds'] += 1
                    
                    # Track product interests
                    target_name = activity.get('target_name', '')
                    if target_name:
                        if target_name not in interests['cart_additions']:
                            interests['cart_additions'][target_name] = 0
                        interests['cart_additions'][target_name] += 1
                    
                    # Track color preferences
                    if 'color' in metadata:
                        color = metadata['color']
                        if color not in interests['favorite_colors']:
                            interests['favorite_colors'][color] = 0
                        interests['favorite_colors'][color] += 1
                    
                    # Track size preferences
                    if 'size' in metadata:
                        size = metadata['size']
                        if size not in interests['favorite_sizes']:
                            interests['favorite_sizes'][size] = 0
                        interests['favorite_sizes'][size] += 1
                
                elif activity_type == 'order_placed':
                    orders += 1
                    interests['shopping_behavior']['total_orders'] += 1
                    
                    if 'total_amount' in metadata:
                        total_order_value += float(metadata['total_amount'])
                
                # Track time patterns
                if created_at:
                    try:
                        from datetime import datetime
                        dt = datetime.strptime(created_at.split('.')[0], '%Y-%m-%d %H:%M:%S')
                        day_name = dt.strftime('%A')
                        hour = dt.hour
                        
                        if day_name not in day_counts:
                            day_counts[day_name] = 0
                        day_counts[day_name] += 1
                        
                        if hour not in hour_counts:
                            hour_counts[hour] = 0
                        hour_counts[hour] += 1
                    except:
                        pass
            
            # Calculate shopping behavior metrics
            if cart_adds > 0:
                interests['shopping_behavior']['cart_abandonment_rate'] = round((1 - (orders / cart_adds)) * 100, 2) if cart_adds > 0 else 0
            
            if orders > 0:
                interests['shopping_behavior']['average_order_value'] = round(total_order_value / orders, 2)
            
            if day_counts:
                interests['shopping_behavior']['most_active_day'] = max(day_counts, key=day_counts.get)
            
            if hour_counts:
                interests['shopping_behavior']['most_active_hour'] = max(hour_counts, key=hour_counts.get)
            
            # Sort by frequency
            interests['cart_additions'] = dict(sorted(interests['cart_additions'].items(), key=lambda x: x[1], reverse=True)[:10])
            interests['favorite_colors'] = dict(sorted(interests['favorite_colors'].items(), key=lambda x: x[1], reverse=True)[:5])
            interests['favorite_sizes'] = dict(sorted(interests['favorite_sizes'].items(), key=lambda x: x[1], reverse=True)[:5])
            
            return interests

    def get_client_interest_summary(self, telegram_id: int):
        """Get quick summary of client interests"""
        interests = self.get_client_interests(telegram_id, days=90)
        
        summary = {
            'top_products': list(interests['cart_additions'].keys())[:5],
            'favorite_colors': list(interests['favorite_colors'].keys())[:3],
            'favorite_sizes': list(interests['favorite_sizes'].keys())[:3],
            'shopping_behavior': interests['shopping_behavior'],
            'activity_level': 'high' if interests['shopping_behavior']['total_browses'] > 20 else 'medium' if interests['shopping_behavior']['total_browses'] > 10 else 'low'
        }
        
        return summary

# Global database instance
db = Database()