import telebot
from telebot import types
import requests
import re
import random
import time
import sqlite3
import json
import socket
from datetime import datetime, timedelta
import threading
import hashlib
import traceback
import string
import os
import html
from concurrent.futures import ThreadPoolExecutor, as_completed

# =====================================================================
# 1. إعدادات البوت
# =====================================================================
API_TOKEN = "8764377158:AAG-tWBUPqi5CK6p76Hi0_7hTAoNoVi6iCc"
ADMIN_ID = 8633059017
DEVELOPER_USERNAME = "@XENYXr"
BOT_NAME = "بيت الخدمات"
BOT_USERNAME = "Rabih12bot"

bot = telebot.TeleBot(API_TOKEN)

# =====================================================================
# 2. قاعدة البيانات
# =====================================================================
class DB:
    def __init__(self):
        self.conn = sqlite3.connect("bot.db", check_same_thread=False)
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.execute("PRAGMA journal_mode = WAL")
        self.init_tables()
    
    def init_tables(self):
        cursor = self.conn.cursor()
        try:
            cursor.execute('''CREATE TABLE IF NOT EXISTS users 
                (id TEXT PRIMARY KEY, name TEXT, join_date TEXT, referred_by TEXT)''')
            cursor.execute("PRAGMA table_info(users)")
            columns = [col[1] for col in cursor.fetchall()]
            if 'name' not in columns:
                cursor.execute("ALTER TABLE users ADD COLUMN name TEXT")
                print("✅ تم إضافة عمود name إلى جدول users")
            
            cursor.execute('''CREATE TABLE IF NOT EXISTS user_stats 
                (user_id TEXT PRIMARY KEY, 
                 points INTEGER DEFAULT 0, 
                 invites INTEGER DEFAULT 0, 
                 last_daily TEXT, 
                 total_servers INTEGER DEFAULT 0)''')
            cursor.execute('''CREATE TABLE IF NOT EXISTS server_stats 
                (server_name TEXT PRIMARY KEY, uses INTEGER DEFAULT 0, last_use TEXT, 
                 avg_ping INTEGER DEFAULT 0, total_ping INTEGER DEFAULT 0, ping_count INTEGER DEFAULT 0)''')
            cursor.execute('''CREATE TABLE IF NOT EXISTS cooldown 
                (user_id TEXT, server TEXT, time REAL, PRIMARY KEY (user_id, server))''')
            cursor.execute('''CREATE TABLE IF NOT EXISTS announcements 
                (id INTEGER PRIMARY KEY AUTOINCREMENT, message TEXT, date TEXT)''')
            cursor.execute('''CREATE TABLE IF NOT EXISTS force_channels 
                (id INTEGER PRIMARY KEY AUTOINCREMENT, channel TEXT UNIQUE, 
                 type TEXT, added_date TEXT)''')
            cursor.execute('''CREATE TABLE IF NOT EXISTS store_items 
                (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                 seller_id TEXT, 
                 seller_username TEXT,
                 image_message_id TEXT,
                 description TEXT,
                 date_added TEXT)''')
            cursor.execute('''CREATE TABLE IF NOT EXISTS bot_settings 
                (key TEXT PRIMARY KEY, value TEXT)''')
            cursor.execute('''CREATE TABLE IF NOT EXISTS user_state 
                (user_id TEXT PRIMARY KEY, 
                 state TEXT, 
                 image_message_id TEXT, 
                 description TEXT,
                 temp_data TEXT)''')
            cursor.execute('''CREATE TABLE IF NOT EXISTS request_counter 
                (id INTEGER PRIMARY KEY, counter INTEGER)''')
            cursor.execute("INSERT OR IGNORE INTO request_counter (id, counter) VALUES (1, 0)")
            cursor.execute('''CREATE TABLE IF NOT EXISTS redeem_codes 
                (code TEXT PRIMARY KEY, 
                 points INTEGER, 
                 max_uses INTEGER, 
                 used INTEGER DEFAULT 0, 
                 created_by TEXT, 
                 created_date TEXT)''')
            cursor.execute('''CREATE TABLE IF NOT EXISTS redeem_usage 
                (code TEXT, user_id TEXT, used_date TEXT, PRIMARY KEY (code, user_id))''')
            cursor.execute('''CREATE TABLE IF NOT EXISTS sell_requests 
                (id INTEGER PRIMARY KEY AUTOINCREMENT,
                 user_id TEXT,
                 username TEXT,
                 phone TEXT,
                 points INTEGER,
                 status TEXT DEFAULT 'pending',
                 request_date TEXT,
                 completed_date TEXT)''')
            self.conn.commit()
            print("✅ تم إنشاء الجداول بنجاح")
            
            cursor.execute("PRAGMA table_info(user_state)")
            columns = [col[1] for col in cursor.fetchall()]
            if 'temp_data' not in columns:
                cursor.execute("ALTER TABLE user_state ADD COLUMN temp_data TEXT")
                self.conn.commit()
                print("✅ تم إضافة عمود temp_data")
        except Exception as e:
            print(f"❌ خطأ في إنشاء الجداول: {e}")
        finally:
            cursor.close()
    
    def add_user(self, user_id, name=None, referred_by=None):
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                "INSERT OR IGNORE INTO users (id, name, join_date, referred_by) VALUES (?, ?, ?, ?)",
                (str(user_id), name, datetime.now().strftime('%Y-%m-%d'), referred_by)
            )
            cursor.execute(
                "INSERT OR IGNORE INTO user_stats (user_id) VALUES (?)",
                (str(user_id),)
            )
            self.conn.commit()
            if referred_by:
                self.add_points(user_id, 1)
                self.add_points(referred_by, 2)
                self.add_invite(referred_by)
                try:
                    bot.send_message(
                        referred_by,
                        f"🎉 تم دعوة مستخدم جديد بواسطتك!\n\n"
                        f"👤 {name or 'مستخدم'}\n"
                        f"⭐ تم إضافة 2 نقطة لك!"
                    )
                except:
                    pass
            return True
        except Exception as e:
            print(f"❌ خطأ في add_user: {e}")
            self.conn.rollback()
            return False
        finally:
            cursor.close()
    
    def get_user_count(self):
        cursor = self.conn.cursor()
        try:
            cursor.execute("SELECT COUNT(*) FROM users")
            return cursor.fetchone()[0]
        except:
            return 0
        finally:
            cursor.close()
    
    def get_active_users(self, days=7):
        cursor = self.conn.cursor()
        try:
            date_limit = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
            cursor.execute("SELECT COUNT(*) FROM users WHERE join_date >= ?", (date_limit,))
            return cursor.fetchone()[0]
        except:
            return 0
        finally:
            cursor.close()
    
    def add_points(self, user_id, points):
        cursor = self.conn.cursor()
        try:
            cursor.execute("SELECT user_id FROM user_stats WHERE user_id = ?", (str(user_id),))
            if not cursor.fetchone():
                cursor.execute("INSERT INTO user_stats (user_id) VALUES (?)", (str(user_id),))
            cursor.execute(
                "UPDATE user_stats SET points = points + ? WHERE user_id = ?",
                (points, str(user_id))
            )
            self.conn.commit()
            cursor.execute("SELECT points FROM user_stats WHERE user_id = ?", (str(user_id),))
            new_points = cursor.fetchone()[0]
            return new_points
        except Exception as e:
            print(f"❌ خطأ في add_points: {e}")
            self.conn.rollback()
            return 0
        finally:
            cursor.close()
    
    def get_points(self, user_id):
        cursor = self.conn.cursor()
        try:
            cursor.execute("SELECT user_id FROM user_stats WHERE user_id = ?", (str(user_id),))
            if not cursor.fetchone():
                cursor.execute("INSERT INTO user_stats (user_id) VALUES (?)", (str(user_id),))
                self.conn.commit()
                return 0
            cursor.execute("SELECT points FROM user_stats WHERE user_id = ?", (str(user_id),))
            row = cursor.fetchone()
            return row[0] if row else 0
        except:
            return 0
        finally:
            cursor.close()
    
    def get_invites(self, user_id):
        cursor = self.conn.cursor()
        try:
            cursor.execute("SELECT invites FROM user_stats WHERE user_id = ?", (str(user_id),))
            row = cursor.fetchone()
            return row[0] if row else 0
        except:
            return 0
        finally:
            cursor.close()
    
    def add_invite(self, user_id):
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                "UPDATE user_stats SET invites = invites + 1 WHERE user_id = ?",
                (str(user_id),)
            )
            self.conn.commit()
        except:
            pass
        finally:
            cursor.close()
    
    def can_claim_daily(self, user_id):
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                "SELECT last_claim FROM daily_rewards WHERE user_id = ?",
                (str(user_id),)
            )
            row = cursor.fetchone()
            if not row or not row[0]:
                return True, 0
            last_claim = datetime.strptime(row[0], '%Y-%m-%d')
            diff = datetime.now() - last_claim
            if diff.days >= 1:
                return True, 0
            else:
                seconds_left = 86400 - diff.total_seconds()
                return False, int(seconds_left)
        except:
            return True, 0
        finally:
            cursor.close()
    
    def claim_daily(self, user_id):
        cursor = self.conn.cursor()
        try:
            today = datetime.now().strftime('%Y-%m-%d')
            cursor.execute(
                "INSERT OR REPLACE INTO daily_rewards (user_id, last_claim) VALUES (?, ?)",
                (str(user_id), today)
            )
            points = 1
            self.add_points(user_id, points)
            self.conn.commit()
            return points
        except:
            return 1
        finally:
            cursor.close()
    
    def create_redeem_code(self, points, max_uses, created_by):
        cursor = self.conn.cursor()
        try:
            code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))
            while True:
                cursor.execute("SELECT code FROM redeem_codes WHERE code = ?", (code,))
                if not cursor.fetchone():
                    break
                code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))
            cursor.execute(
                "INSERT INTO redeem_codes (code, points, max_uses, created_by, created_date) VALUES (?, ?, ?, ?, ?)",
                (code, points, max_uses, str(created_by), datetime.now().strftime('%Y-%m-%d %H:%M'))
            )
            self.conn.commit()
            return code
        except:
            return None
        finally:
            cursor.close()
    
    def use_redeem_code(self, code, user_id):
        cursor = self.conn.cursor()
        try:
            cursor.execute("SELECT points, max_uses, used FROM redeem_codes WHERE code = ?", (code,))
            row = cursor.fetchone()
            if not row:
                return None, "الكود غير صحيح", 0
            points, max_uses, used = row
            if used >= max_uses:
                return None, "هذا الكود انتهت صلاحيته (تم استخدامه من قبل كل المستخدمين المسموح لهم)", 0
            cursor.execute("SELECT 1 FROM redeem_usage WHERE code = ? AND user_id = ?", (code, str(user_id)))
            if cursor.fetchone():
                return None, "لقد استخدمت هذا الكود مسبقاً، لا يمكن استخدامه مرة أخرى", 0
            new_balance = self.add_points(user_id, points)
            cursor.execute(
                "INSERT INTO redeem_usage (code, user_id, used_date) VALUES (?, ?, ?)",
                (code, str(user_id), datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
            )
            cursor.execute(
                "UPDATE redeem_codes SET used = used + 1 WHERE code = ?",
                (code,)
            )
            self.conn.commit()
            return points, "تم إضافة النقاط بنجاح", new_balance
        except Exception as e:
            print(f"❌ خطأ في use_redeem_code: {e}")
            self.conn.rollback()
            return None, "حدث خطأ", 0
        finally:
            cursor.close()
    
    def get_redeem_codes(self, created_by=None):
        cursor = self.conn.cursor()
        try:
            if created_by:
                cursor.execute("SELECT code, points, max_uses, used, created_date FROM redeem_codes WHERE created_by = ? ORDER BY created_date DESC", (str(created_by),))
            else:
                cursor.execute("SELECT code, points, max_uses, used, created_date FROM redeem_codes ORDER BY created_date DESC")
            return cursor.fetchall()
        except:
            return []
        finally:
            cursor.close()
    
    def set_user_state(self, user_id, state, image_message_id=None, description=None, temp_data=None):
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                "INSERT OR REPLACE INTO user_state (user_id, state, image_message_id, description, temp_data) VALUES (?, ?, ?, ?, ?)",
                (str(user_id), state, image_message_id, description, temp_data)
            )
            self.conn.commit()
            return True
        except:
            return False
        finally:
            cursor.close()
    
    def get_user_state(self, user_id):
        cursor = self.conn.cursor()
        try:
            cursor.execute("SELECT state, image_message_id, description, temp_data FROM user_state WHERE user_id = ?", (str(user_id),))
            return cursor.fetchone()
        except:
            return None
        finally:
            cursor.close()
    
    def clear_user_state(self, user_id):
        cursor = self.conn.cursor()
        try:
            cursor.execute("DELETE FROM user_state WHERE user_id = ?", (str(user_id),))
            self.conn.commit()
            return True
        except:
            return False
        finally:
            cursor.close()
    
    def set_setting(self, key, value):
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                "INSERT OR REPLACE INTO bot_settings (key, value) VALUES (?, ?)",
                (key, value)
            )
            self.conn.commit()
            return True
        except:
            return False
        finally:
            cursor.close()
    
    def get_setting(self, key):
        cursor = self.conn.cursor()
        try:
            cursor.execute("SELECT value FROM bot_settings WHERE key = ?", (key,))
            row = cursor.fetchone()
            return row[0] if row else None
        except:
            return None
        finally:
            cursor.close()
    
    def delete_setting(self, key):
        cursor = self.conn.cursor()
        try:
            cursor.execute("DELETE FROM bot_settings WHERE key = ?", (key,))
            self.conn.commit()
            return cursor.rowcount > 0
        except:
            return False
        finally:
            cursor.close()
    
    def add_store_item(self, seller_id, seller_username, image_message_id, description=""):
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO store_items (seller_id, seller_username, image_message_id, description, date_added) VALUES (?, ?, ?, ?, ?)",
                (str(seller_id), seller_username, str(image_message_id), description, datetime.now().strftime('%Y-%m-%d %H:%M'))
            )
            self.conn.commit()
            item_id = cursor.lastrowid
            return item_id
        except:
            return None
        finally:
            cursor.close()
    
    def get_store_items(self):
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                "SELECT id, seller_id, seller_username, image_message_id, description, date_added FROM store_items ORDER BY id DESC"
            )
            return cursor.fetchall()
        except:
            return []
        finally:
            cursor.close()
    
    def get_store_item(self, item_id):
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                "SELECT id, seller_id, seller_username, image_message_id, description, date_added FROM store_items WHERE id = ?",
                (item_id,)
            )
            return cursor.fetchone()
        except:
            return None
        finally:
            cursor.close()
    
    def delete_store_item(self, item_id, seller_id):
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                "DELETE FROM store_items WHERE id = ? AND seller_id = ?",
                (item_id, str(seller_id))
            )
            self.conn.commit()
            return cursor.rowcount > 0
        except:
            return False
        finally:
            cursor.close()
    
    def add_force_channel(self, channel, channel_type='channel'):
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                "INSERT OR IGNORE INTO force_channels (channel, type, added_date) VALUES (?, ?, ?)",
                (channel, channel_type, datetime.now().strftime('%Y-%m-%d'))
            )
            self.conn.commit()
            return True
        except:
            return False
        finally:
            cursor.close()
    
    def remove_force_channel(self, channel):
        cursor = self.conn.cursor()
        try:
            cursor.execute("DELETE FROM force_channels WHERE channel = ?", (channel,))
            self.conn.commit()
            return cursor.rowcount > 0
        except:
            return False
        finally:
            cursor.close()
    
    def get_force_channels(self):
        cursor = self.conn.cursor()
        try:
            cursor.execute("SELECT channel, type FROM force_channels")
            return cursor.fetchall()
        except:
            return []
        finally:
            cursor.close()
    
    def get_force_channels_count(self):
        cursor = self.conn.cursor()
        try:
            cursor.execute("SELECT COUNT(*) FROM force_channels")
            return cursor.fetchone()[0]
        except:
            return 0
        finally:
            cursor.close()
    
    def log_server_use(self, server_name, ping=None):
        cursor = self.conn.cursor()
        try:
            today = datetime.now().strftime('%Y-%m-%d')
            cursor.execute(
                "UPDATE server_stats SET uses = uses + 1, last_use = ? WHERE server_name = ?",
                (today, server_name)
            )
            if cursor.rowcount == 0:
                cursor.execute(
                    "INSERT INTO server_stats (server_name, uses, last_use) VALUES (?, 1, ?)",
                    (server_name, today)
                )
            if ping:
                cursor.execute(
                    "UPDATE server_stats SET total_ping = total_ping + ?, ping_count = ping_count + 1 WHERE server_name = ?",
                    (ping, server_name)
                )
                cursor.execute(
                    "UPDATE server_stats SET avg_ping = total_ping / ping_count WHERE server_name = ?",
                    (server_name,)
                )
            self.conn.commit()
        except:
            pass
        finally:
            cursor.close()
    
    def check_cooldown(self, user_id, server):
        if str(user_id) == str(ADMIN_ID):
            return 0
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                "SELECT time FROM cooldown WHERE user_id=? AND server=?",
                (str(user_id), server)
            )
            row = cursor.fetchone()
            if row:
                elapsed = time.time() - row[0]
                if elapsed < 86400:
                    return int(86400 - elapsed)
            return 0
        except:
            return 0
        finally:
            cursor.close()
    
    def check_global_cooldown(self, user_id):
        if str(user_id) == str(ADMIN_ID):
            return 0
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                "SELECT time FROM cooldown WHERE user_id=? ORDER BY time DESC LIMIT 1",
                (str(user_id),)
            )
            row = cursor.fetchone()
            if row:
                elapsed = time.time() - row[0]
                if elapsed < 21600:
                    return int(21600 - elapsed)
            return 0
        except:
            return 0
        finally:
            cursor.close()
    
    def set_cooldown(self, user_id, server):
        if str(user_id) == str(ADMIN_ID):
            return
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                "INSERT OR REPLACE INTO cooldown (user_id, server, time) VALUES (?, ?, ?)",
                (str(user_id), server, time.time())
            )
            self.conn.commit()
        except:
            pass
        finally:
            cursor.close()
    
    def set_dark_file(self, file_id, description, expiry_timestamp):
        self.set_setting('dark_file_id', file_id)
        self.set_setting('dark_description', description)
        self.set_setting('dark_expiry', str(expiry_timestamp))
        return True

    def get_dark_file(self):
        file_id = self.get_setting('dark_file_id')
        description = self.get_setting('dark_description')
        expiry = self.get_setting('dark_expiry')
        if file_id and description and expiry:
            return file_id, description, int(expiry)
        return None, None, None

    def delete_dark_file(self):
        self.delete_setting('dark_file_id')
        self.delete_setting('dark_description')
        self.delete_setting('dark_expiry')
        return True

    def is_dark_file_expired(self):
        _, _, expiry = self.get_dark_file()
        if expiry:
            return int(time.time()) > expiry
        return True

    def add_sell_request(self, user_id, username, phone, points):
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO sell_requests (user_id, username, phone, points, request_date, status) VALUES (?, ?, ?, ?, ?, ?)",
                (str(user_id), username, phone, points, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'pending')
            )
            self.conn.commit()
            return cursor.lastrowid
        except Exception as e:
            print(f"❌ خطأ في add_sell_request: {e}")
            return None
        finally:
            cursor.close()
    
    def get_sell_requests(self, status='pending'):
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                "SELECT id, user_id, username, phone, points, request_date, status FROM sell_requests WHERE status = ? ORDER BY id DESC",
                (status,)
            )
            return cursor.fetchall()
        except:
            return []
        finally:
            cursor.close()
    
    def update_sell_request_status(self, request_id, status):
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                "UPDATE sell_requests SET status = ?, completed_date = ? WHERE id = ?",
                (status, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), request_id)
            )
            self.conn.commit()
            return cursor.rowcount > 0
        except:
            return False
        finally:
            cursor.close()
    
    def get_sell_request(self, request_id):
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                "SELECT id, user_id, username, phone, points, request_date, status FROM sell_requests WHERE id = ?",
                (request_id,)
            )
            return cursor.fetchone()
        except:
            return None
        finally:
            cursor.close()

db = DB()

# =====================================================================
# 3. السيرفرات (محفوظة لكن لن تُستخدم)
# =====================================================================
VLESS_SERVERS = {
    "fr2": {
        "vless": "vless://24680552-432b-4932-be4e-202175e3097c@149.202.56.74:443?path=/vless&security=tls&encryption=none&host=fr2.niekotin.de&type=ws&sni=fr2.niekotin.de#FR2",
        "ip": "149.202.56.74",
        "port": "443",
        "name": "France 2",
        "flag": "🇫🇷",
        "country": "فرنسا"
    },
}

def test_server_speed(ip, port=443):
    try:
        start = time.time()
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(3)
        result = sock.connect_ex((ip, port))
        end = time.time()
        sock.close()
        if result == 0:
            ping = round((end - start) * 1000)
            return True, ping
        return False, None
    except:
        return False, None

# =====================================================================
# 4. نظام الاشتراك الإجباري
# =====================================================================
def check_force_subscribe(user_id):
    channels = db.get_force_channels()
    if not channels:
        return True, None
    not_subscribed = []
    for channel, channel_type in channels:
        try:
            member = bot.get_chat_member(channel, user_id)
            if member.status in ['member', 'administrator', 'creator']:
                continue
            else:
                not_subscribed.append(channel)
        except:
            not_subscribed.append(channel)
    if not_subscribed:
        return False, not_subscribed
    return True, None

def get_force_subscribe_keyboard(not_subscribed):
    markup = types.InlineKeyboardMarkup(row_width=1)
    for channel in not_subscribed:
        clean_channel = channel.replace('@', '').strip()
        markup.add(
            types.InlineKeyboardButton(
                f"📢 اشترك في {channel}",
                url=f"https://t.me/{clean_channel}"
            )
        )
    markup.add(
        types.InlineKeyboardButton(
            "✅ تحقق من الاشتراك",
            callback_data="check_subscribe"
        )
    )
    return markup

# =====================================================================
# 5. دوال مجموعة الصور
# =====================================================================
def get_image_storage_group():
    return db.get_setting('image_storage_group')

def set_image_storage_group(group_id):
    return db.set_setting('image_storage_group', group_id)

def delete_image_storage_group():
    return db.delete_setting('image_storage_group')

# =====================================================================
# 6. دوال البحث عن بروكسيات يوتيوب
# =====================================================================
def fetch_proxies_from_url(url):
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            lines = response.text.splitlines()
            proxies = []
            for line in lines:
                line = line.strip()
                if ':' in line:
                    parts = line.split(':')
                    if len(parts) >= 2:
                        ip = parts[0].strip()
                        port = parts[1].strip()
                        if port == '443' and re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', ip):
                            proxies.append(f"{ip}:{port}")
                elif ' ' in line:
                    parts = line.split()
                    if len(parts) >= 2:
                        ip = parts[0].strip()
                        port = parts[1].strip()
                        if port == '443' and re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', ip):
                            proxies.append(f"{ip}:{port}")
            return proxies
    except:
        pass
    return []

def fetch_youtube_proxies():
    sources = [
        "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=https&timeout=10000&country=all&ssl=all&anonymity=all",
        "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
        "https://raw.githubusercontent.com/roosterkid/openproxylist/main/HTTPS_RAW.txt",
        "https://raw.githubusercontent.com/proxylist-to/proxylist/main/https.txt",
        "https://raw.githubusercontent.com/clarketm/proxy-list/master/proxy-list-raw.txt",
        "https://www.proxy-list.download/api/v1/get?type=https",
        "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/http.txt",
        "https://raw.githubusercontent.com/mmpx222/proxy-list/master/http.txt",
        "https://raw.githubusercontent.com/hookzof/socks5_list/master/proxy.txt",
    ]
    all_proxies = set()
    for url in sources:
        proxies = fetch_proxies_from_url(url)
        for p in proxies:
            all_proxies.add(p)
    proxy_list = list(all_proxies)
    if len(proxy_list) > 150:
        proxy_list = random.sample(proxy_list, 150)
    if not proxy_list:
        return []
    working = []
    with ThreadPoolExecutor(max_workers=100) as executor:
        futures = {executor.submit(test_proxy, proxy): proxy for proxy in proxy_list}
        for future in as_completed(futures, timeout=15):
            try:
                proxy, ping = future.result()
                if proxy:
                    working.append((proxy, ping))
            except:
                pass
    working.sort(key=lambda x: x[1])
    return working

def test_proxy(proxy_str):
    try:
        ip, port = proxy_str.split(':')
        port = int(port)
        if port != 443:
            return None, None
        start = time.time()
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1.5)
        result = sock.connect_ex((ip, port))
        end = time.time()
        sock.close()
        if result == 0:
            ping = round((end - start) * 1000)
            return proxy_str, ping
    except:
        pass
    return None, None

def display_proxies(proxies):
    if not proxies:
        return "❌ **لا توجد بروكسيات نشطة (HTTPS:443) حالياً.**"
    text = "🔍 **بروكسيات HTTPS النشطة (المنفذ 443):**\n\n"
    for idx, (proxy, ping) in enumerate(proxies[:30], 1):
        text += f"{idx}. `{proxy}`  ⚡ {ping}ms\n"
    text += f"\n📌 تم العثور على {len(proxies)} بروكسي نشط على المنفذ 443."
    return text

# =====================================================================
# 7. واجهات البوت
# =====================================================================
def get_main_keyboard(user_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    
    btn_dark = types.KeyboardButton("📁 ملف دارك")
    btn_update_dark = types.KeyboardButton("🔄 تحديث دارك") if str(user_id) == str(ADMIN_ID) else None
    
    if btn_update_dark:
        markup.row(btn_dark, btn_update_dark)
    else:
        markup.row(btn_dark)
    
    btn2 = types.KeyboardButton("📊 الإحصائيات")
    btn3 = types.KeyboardButton("⭐ مكافأة يومية")
    btn4 = types.KeyboardButton("💰 رصيدي")
    btn5 = types.KeyboardButton("📤 مشاركة البوت")
    btn6 = types.KeyboardButton("🔍 بحث بروكسيات يوتيوب")
    btn8 = types.KeyboardButton("🛒 المتجر")
    btn9 = types.KeyboardButton("🎫 إدخال كود نقاط")
    
    markup.row(btn2, btn3)
    markup.row(btn4, btn5)
    
    if str(user_id) != str(ADMIN_ID):
        btn7 = types.KeyboardButton("👨‍💻 المطور")
        markup.row(btn6, btn7)
    else:
        markup.row(btn6)
    
    markup.row(btn8, btn9)
    
    if str(user_id) != str(ADMIN_ID):
        btn10 = types.KeyboardButton("💰 شراء نقاط")
        markup.row(btn10)
    
    if str(user_id) == str(ADMIN_ID):
        btn11 = types.KeyboardButton("⚙️ لوحة التحكم")
        markup.row(btn11)
    
    return markup

def get_admin_panel():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("➕ إضافة قناة إجبارية", callback_data="add_channel"),
        types.InlineKeyboardButton("📋 عرض القنوات الإجبارية", callback_data="list_channels"),
        types.InlineKeyboardButton("❌ حذف قناة إجبارية", callback_data="remove_channel"),
        types.InlineKeyboardButton("📸 تعيين مجموعة الصور", callback_data="set_image_group"),
        types.InlineKeyboardButton("📋 عرض مجموعة الصور", callback_data="view_image_group"),
        types.InlineKeyboardButton("❌ حذف مجموعة الصور", callback_data="delete_image_group"),
        types.InlineKeyboardButton("📊 إحصائيات البوت", callback_data="admin_stats"),
        types.InlineKeyboardButton("📢 إرسال إعلان", callback_data="admin_announce"),
        types.InlineKeyboardButton("💰 إعدادات الدفع", callback_data="payment_settings"),
        types.InlineKeyboardButton("🎫 إنشاء كود نقاط", callback_data="create_code"),
        types.InlineKeyboardButton("📋 طلبات بيع النقاط", callback_data="view_sell_requests")
    )
    return markup

def get_store_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("📋 عرض السلع", callback_data="view_store"),
        types.InlineKeyboardButton("➕ إضافة سلعة للبيع", callback_data="add_item"),
        types.InlineKeyboardButton("💰 طلب بيع نقاط", callback_data="sell_points"),
        types.InlineKeyboardButton("🔙 رجوع", callback_data="back_main")
    )
    return markup

def get_buy_points_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("💳 شراء عبر فليكسي", callback_data="flexi_pay"),
        types.InlineKeyboardButton("🔙 رجوع", callback_data="back_main")
    )
    return markup

# =====================================================================
# 8. دالة مساعدة لتحليل وقت الانتهاء
# =====================================================================
def parse_expiry(text):
    text = text.strip()
    try:
        dt = datetime.strptime(text, '%Y-%m-%d %H:%M')
        return int(dt.timestamp())
    except:
        pass
    if text.startswith('+'):
        try:
            num = int(text[1:-1])
            unit = text[-1]
            if unit == 'd':
                delta = timedelta(days=num)
            elif unit == 'h':
                delta = timedelta(hours=num)
            elif unit == 'm':
                delta = timedelta(minutes=num)
            else:
                return None
            return int((datetime.now() + delta).timestamp())
        except:
            pass
    return None

# =====================================================================
# 9. دالة مساعدة للإرسال الآمن
# =====================================================================
def send_safe(chat_id, text, parse_mode='HTML', reply_markup=None):
    try:
        bot.send_message(chat_id, text, parse_mode=parse_mode, reply_markup=reply_markup)
    except:
        try:
            bot.send_message(chat_id, text, reply_markup=reply_markup)
        except:
            bot.send_message(chat_id, "حدث خطأ. حاول مرة أخرى.")

# =====================================================================
# 10. معالج الأوامر الرئيسي
# =====================================================================
@bot.message_handler(commands=['start'])
def start(message):
    try:
        user_id = message.from_user.id
        name = message.from_user.first_name
        referred_by = None
        if len(message.text.split()) > 1:
            param = message.text.split()[1]
            if param.startswith('ref_'):
                ref_id = param.replace('ref_', '')
                if ref_id.isdigit() and int(ref_id) != user_id:
                    referred_by = int(ref_id)
        db.add_user(user_id, name, referred_by)
        is_subscribed, not_subscribed = check_force_subscribe(user_id)
        if not is_subscribed:
            channels_text = "\n".join([f"• {ch}" for ch in not_subscribed])
            msg = (
                f"🔒 **اشتراك إجباري**\n\n"
                f"عذراً {name}، يجب الاشتراك في:\n\n"
                f"{channels_text}\n\n"
                f"📌 بعد الاشتراك، اضغط على زر التحقق."
            )
            send_safe(
                message.chat.id,
                msg,
                reply_markup=get_force_subscribe_keyboard(not_subscribed)
            )
            return
        welcome_msg = (
            f"👋 أهلاً بك {name} في {BOT_NAME}!\n\n"
            "🌟 **المميزات:**\n"
            "• 📁 ملف دارك (رابط تحميل)\n"
            "• ⭐ نقاط ومكافآت يومية\n"
            "• 🛒 متجر لعرض السلع (صور)\n"
            "• 💰 شراء نقاط عبر فليكسي\n"
            "• 💰 بيع نقاط (حد أدنى 150 نقطة)\n"
            "• 🎫 أكواد نقاط للهدايا (كل مستخدم يستخدم الكود مرة واحدة)\n"
            "• 🔍 بحث بروكسيات يوتيوب\n\n"
            "اختر الخدمة 👇"
        )
        send_safe(message.chat.id, welcome_msg, reply_markup=get_main_keyboard(user_id))
    except Exception as e:
        print(f"خطأ في start: {e}")

# =====================================================================
# 11. معالج النصوص (معدل)
# =====================================================================
@bot.message_handler(func=lambda m: True)
def handle_text(message):
    try:
        user_id = message.from_user.id
        text = message.text
        
        is_subscribed, not_subscribed = check_force_subscribe(user_id)
        if not is_subscribed:
            channels_text = "\n".join([f"• {ch}" for ch in not_subscribed])
            msg = (
                f"🔒 **اشتراك إجباري**\n\n"
                f"يجب الاشتراك في:\n\n"
                f"{channels_text}\n\n"
                f"📌 بعد الاشتراك، اضغط على زر التحقق."
            )
            send_safe(
                message.chat.id,
                msg,
                reply_markup=get_force_subscribe_keyboard(not_subscribed)
            )
            return
        
        state = db.get_user_state(user_id)
        if state:
            current_state = state[0]
            temp_data = state[3] if state[3] else '{}'
            try:
                temp = json.loads(temp_data)
            except:
                temp = {}
            
            # حالات إنشاء كود النقاط
            if current_state == 'admin_create_code_points':
                try:
                    points = int(text)
                    if points < 1:
                        bot.reply_to(message, "❌ عدد النقاط يجب أن يكون أكبر من 0.")
                        return
                    db.set_user_state(user_id, 'admin_create_code_uses', temp_data=json.dumps({'points': points}))
                    bot.reply_to(
                        message,
                        f"✅ تم حفظ عدد النقاط: {points}\n\n"
                        "📝 **الخطوة 2:** أرسل عدد المستخدمين الذين يمكنهم استخدام هذا الكود (كل مستخدم مرة واحدة)."
                    )
                except ValueError:
                    bot.reply_to(message, "❌ يرجى إدخال رقم صحيح.")
                return
            
            elif current_state == 'admin_create_code_uses':
                try:
                    uses = int(text)
                    if uses < 1:
                        bot.reply_to(message, "❌ عدد المستخدمين يجب أن يكون أكبر من 0.")
                        return
                    if temp_data:
                        temp = json.loads(temp_data)
                        points = temp['points']
                    else:
                        bot.reply_to(message, "❌ حدث خطأ في البيانات المؤقتة.")
                        db.clear_user_state(user_id)
                        return
                    code = db.create_redeem_code(points, uses, user_id)
                    if code:
                        bot.reply_to(
                            message,
                            f"✅ **تم إنشاء كود النقاط بنجاح!**\n\n"
                            f"🎫 **الكود:** `{code}`\n"
                            f"⭐ عدد النقاط: {points}\n"
                            f"👥 عدد المستخدمين المسموح لهم: {uses}\n\n"
                            f"📌 يمكن لـ {uses} مستخدم مختلف استخدام هذا الكود، كل منهم مرة واحدة."
                        )
                    else:
                        bot.reply_to(message, "❌ حدث خطأ أثناء إنشاء الكود.")
                    db.clear_user_state(user_id)
                except ValueError:
                    bot.reply_to(message, "❌ يرجى إدخال رقم صحيح.")
                except json.JSONDecodeError:
                    bot.reply_to(message, "❌ حدث خطأ.")
                    db.clear_user_state(user_id)
                return
            
            # حالات رفع الملف الدارك
            if current_state == 'admin_dark_file_waiting_description':
                description = message.text
                if not description.strip():
                    bot.reply_to(message, "❌ الوصف لا يمكن أن يكون فارغاً.")
                    return
                temp['description'] = description
                db.set_user_state(user_id, 'admin_dark_file_waiting_expiry', temp_data=json.dumps(temp))
                bot.reply_to(
                    message,
                    "✅ تم حفظ الوصف.\n\n⏳ الآن أرسل وقت انتهاء الصلاحية (مثال: `2026-07-20 15:30` أو `+1d`)."
                )
                return
            
            elif current_state == 'admin_dark_file_waiting_expiry':
                expiry_input = message.text.strip()
                expiry_timestamp = parse_expiry(expiry_input)
                if expiry_timestamp is None:
                    bot.reply_to(
                        message,
                        "❌ صيغة الوقت غير صحيحة.\nاستخدم:\n• `YYYY-MM-DD HH:MM`\n• `+1d` (يوم)\n• `+2h` (ساعة)"
                    )
                    return
                file_id = temp.get('file_id')
                description = temp.get('description')
                if not file_id or not description:
                    bot.reply_to(message, "❌ حدث خطأ في البيانات المؤقتة.")
                    db.clear_user_state(user_id)
                    return
                db.set_dark_file(file_id, description, expiry_timestamp)
                db.clear_user_state(user_id)
                expiry_str = datetime.fromtimestamp(expiry_timestamp).strftime('%Y-%m-%d %H:%M')
                escaped_desc = html.escape(description)
                formatted_desc = f"<pre>{escaped_desc}</pre>"
                bot.reply_to(
                    message,
                    f"✅ **تم تحديث ملف دارك بنجاح!**\n\n"
                    f"📝 **الوصف:**\n{formatted_desc}\n"
                    f"⏳ **ينتهي في:** `{expiry_str}`",
                    parse_mode='HTML'
                )
                return
            
            # ===== حالة طلب بيع النقاط - إدخال عدد النقاط (جديد) =====
            if current_state == 'sell_points_amount':
                try:
                    points = int(text)
                    if points < 150:
                        bot.reply_to(message, "❌ الحد الأدنى لبيع النقاط هو 150 نقطة.")
                        return
                    max_points = temp.get('max_points', 0)
                    if points > max_points:
                        bot.reply_to(
                            message,
                            f"❌ **رصيدك غير كافٍ!**\n⭐ رصيدك: {max_points} نقطة\n💡 لا يمكنك بيع أكثر من رصيدك."
                        )
                        return
                    db.set_user_state(user_id, 'sell_points_phone', temp_data=json.dumps({'points': points}))
                    bot.reply_to(
                        message,
                        f"✅ تم تحديد عدد النقاط: {points}\n\n"
                        f"📱 **الخطوة الأخيرة:** أرسل رقم هاتف فليكسي الذي تريد شحن الرصيد عليه.\n"
                        f"مثال: `0779429835`"
                    )
                except ValueError:
                    bot.reply_to(message, "❌ يرجى إدخال رقم صحيح.")
                return
            
            # ===== حالة طلب بيع النقاط - إدخال رقم الهاتف =====
            if current_state == 'sell_points_phone':
                phone = text.strip()
                if not phone:
                    bot.reply_to(message, "❌ الرقم لا يمكن أن يكون فارغاً. أرسل رقم الهاتف.")
                    return
                points = temp.get('points')
                if not points:
                    bot.reply_to(message, "❌ حدث خطأ، حاول مرة أخرى.")
                    db.clear_user_state(user_id)
                    return
                current_points = db.get_points(user_id)
                if current_points < points:
                    bot.reply_to(
                        message,
                        f"❌ **رصيدك غير كافٍ!**\n"
                        f"⭐ رصيدك: {current_points} نقطة\n"
                        f"💡 تحتاج {points} نقطة."
                    )
                    db.clear_user_state(user_id)
                    return
                new_balance = db.add_points(user_id, -points)
                username = message.from_user.username or "لا يوجد يوزر"
                request_id = db.add_sell_request(user_id, username, phone, points)
                if request_id:
                    admin_text = (
                        f"💰 **طلب بيع نقاط جديد**\n\n"
                        f"🆔 رقم الطلب: `{request_id}`\n"
                        f"👤 المستخدم: @{username}\n"
                        f"🆔 المعرف: `{user_id}`\n"
                        f"📱 رقم الهاتف: `{phone}`\n"
                        f"⭐ عدد النقاط المبيعة: `{points}`\n"
                        f"📅 التاريخ: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
                        f"⚠️ تم خصم النقاط من المستخدم.\n"
                        f"📌 قم بشحن الرصيد للمستخدم ثم اضغط على زر 'تم الشحن'."
                    )
                    markup = types.InlineKeyboardMarkup(row_width=1)
                    markup.add(
                        types.InlineKeyboardButton("✅ تم شحن الرصيد", callback_data=f"complete_sell_{request_id}")
                    )
                    bot.send_message(ADMIN_ID, admin_text, reply_markup=markup)
                    bot.reply_to(
                        message,
                        f"✅ **تم استلام طلب بيع النقاط!**\n\n"
                        f"⭐ تم خصم {points} نقطة من رصيدك.\n"
                        f"📊 رصيدك الجديد: {new_balance} نقطة\n"
                        f"📱 رقم الهاتف: `{phone}`\n\n"
                        f"📌 سيتم شحن رصيدك قريباً.\n"
                        f"سوف تتلقى رسالة تأكيد عند اكتمال العملية."
                    )
                else:
                    db.add_points(user_id, points)
                    bot.reply_to(message, "❌ حدث خطأ أثناء تسجيل الطلب. تم إعادة النقاط.")
                db.clear_user_state(user_id)
                return
        
        # ===== النصوص العادية =====
        if text == "📁 ملف دارك":
            file_id, description, expiry = db.get_dark_file()
            if file_id and not db.is_dark_file_expired():
                expiry_str = datetime.fromtimestamp(expiry).strftime('%Y-%m-%d %H:%M')
                escaped_desc = html.escape(description)
                caption = f"📁 **ملف دارك**\n\n📝 **الوصف:**\n<pre>{escaped_desc}</pre>\n⏳ **ينتهي في:** `{expiry_str}`"
                bot.send_document(
                    message.chat.id,
                    file_id,
                    caption=caption,
                    parse_mode='HTML'
                )
            else:
                bot.reply_to(message, "❌ **لا يوجد ملف دارك صالح حالياً.**")
            return
        
        elif text == "🔄 تحديث دارك":
            if str(user_id) != str(ADMIN_ID):
                bot.reply_to(message, "⛔ مخصص للإدمن فقط!")
                return
            db.set_user_state(user_id, 'admin_dark_file_waiting_file')
            bot.reply_to(message, "📤 **رفع ملف دارك جديد**\n\nأرسل الملف (صورة، فيديو، مستند، أو أي نوع).")
            return
        
        elif text == "💰 رصيدي":
            points = db.get_points(user_id)
            bot.send_message(
                message.chat.id,
                f"💰 **رصيد نقاطك**\n\n⭐ عدد النقاط: `{points}`"
            )
            return
        
        elif text == "💰 شراء نقاط":
            send_safe(
                message.chat.id,
                "💳 **شراء نقاط**\n\nاختر طريقة الشراء:",
                reply_markup=get_buy_points_keyboard()
            )
            return
        
        elif text == "🎫 إدخال كود نقاط":
            bot.send_message(
                message.chat.id,
                "🎫 **إدخال كود نقاط**\n\nأرسل الكود (يمكن لكل مستخدم استخدام الكود مرة واحدة فقط):"
            )
            db.set_user_state(user_id, 'waiting_code')
            bot.register_next_step_handler(message, process_redeem_code)
            return
        
        elif text == "🛒 المتجر":
            send_safe(
                message.chat.id,
                "🛒 **مرحباً بك في متجر السلع!**\n\nاختر الإجراء:",
                reply_markup=get_store_keyboard()
            )
        
        elif text == "📊 الإحصائيات":
            stats_text = (
                f"📊 **إحصائيات البوت**\n\n"
                f"👥 المستخدمين: `{db.get_user_count()}`\n"
                f"📅 نشطاء الأسبوع: `{db.get_active_users()}`\n"
                f"🛒 السلع المعروضة: `{len(db.get_store_items())}`\n"
                f"🔒 القنوات الإجبارية: `{db.get_force_channels_count()}`"
            )
            send_safe(message.chat.id, stats_text)
        
        elif text == "⭐ مكافأة يومية":
            can_claim, seconds_left = db.can_claim_daily(user_id)
            if can_claim:
                points = db.claim_daily(user_id)
                send_safe(
                    message.chat.id,
                    f"🎉 **مكافأة يومية!**\n\n⭐ +{points} نقطة\n📊 نقاطك: `{db.get_points(user_id)}`"
                )
            else:
                hours = seconds_left // 3600
                minutes = (seconds_left % 3600) // 60
                seconds = seconds_left % 60
                send_safe(
                    message.chat.id,
                    f"⏳ **متبقي للمكافأة القادمة:**\n`{hours:02d}:{minutes:02d}:{seconds:02d}`"
                )
        
        elif text == "📤 مشاركة البوت":
            invite_link = f"https://t.me/{BOT_USERNAME}?start=ref_{user_id}"
            markup = types.InlineKeyboardMarkup()
            markup.add(
                types.InlineKeyboardButton(
                    "📤 مشاركة البوت",
                    url=f"https://t.me/share/url?url=اشترك في {BOT_NAME} واحصل على نقاط! {invite_link}"
                )
            )
            send_safe(
                message.chat.id,
                f"📤 **شارك البوت مع أصدقائك!**\n\n"
                f"🔗 رابط دعوتك:\n`{invite_link}`\n\n"
                f"👥 مكافآت الدعوة: أنت +2 نقطة، الصديق +1 نقطة\n"
                f"📊 عدد دعواتك: `{db.get_invites(user_id)}`",
                reply_markup=markup
            )
        
        elif text == "🔍 بحث بروكسيات يوتيوب":
            points = db.get_points(user_id)
            if points < 5:
                bot.reply_to(
                    message,
                    f"❌ **رصيدك غير كافٍ للبحث!**\n\n"
                    f"⭐ رصيدك الحالي: {points} نقطة\n"
                    f"💡 تحتاج إلى 5 نقاط على الأقل."
                )
                return
            new_balance = db.add_points(user_id, -5)
            status_msg = bot.reply_to(
                message,
                f"⏳ جاري البحث عن بروكسيات HTTPS...\n⭐ تم خصم 5 نقاط. رصيدك: {new_balance} نقطة"
            )
            working = fetch_youtube_proxies()
            result_text = display_proxies(working)
            bot.edit_message_text(
                result_text,
                chat_id=message.chat.id,
                message_id=status_msg.message_id,
                parse_mode='HTML'
            )
            return
        
        elif text == "👨‍💻 المطور":
            developer_text = (
                f"👨‍💻 **المطور**\n\n"
                f"• الاسم: XENYX\n"
                f"• المعرف: {DEVELOPER_USERNAME}\n"
                f"• الإصدار: 2.0\n\n"
                f"📞 للتواصل: {DEVELOPER_USERNAME}"
            )
            markup = types.InlineKeyboardMarkup()
            markup.add(
                types.InlineKeyboardButton(
                    "📩 تواصل مع المطور",
                    url=f"https://t.me/XENYXr"
                )
            )
            send_safe(message.chat.id, developer_text, reply_markup=markup)
        
        elif text == "⚙️ لوحة التحكم":
            if str(user_id) != str(ADMIN_ID):
                send_safe(message.chat.id, "⛔ مخصص للإدمن فقط!")
                return
            admin_text = (
                f"⚙️ **لوحة التحكم**\n\n"
                f"📡 السيرفرات: {len(VLESS_SERVERS)}\n"
                f"🛒 السلع: {len(db.get_store_items())}\n"
                f"🔒 القنوات: {db.get_force_channels_count()}\n"
                f"👥 المستخدمين: {db.get_user_count()}\n"
                f"📸 مجموعة الصور: {get_image_storage_group() or '❌ غير محددة'}\n"
                f"💳 رقم فليكسي: {db.get_setting('flexi_number') or '❌ غير محدد'}\n"
                f"📁 ملف دارك: {'✅ موجود' if db.get_dark_file()[0] else '❌ لا يوجد'}\n"
                f"💰 طلبات بيع نقاط معلقة: {len(db.get_sell_requests('pending'))}"
            )
            send_safe(message.chat.id, admin_text, reply_markup=get_admin_panel())
        
        elif text.startswith('تم فليكسي'):
            admin_text = (
                f"💳 **طلب شراء عبر فليكسي**\n\n"
                f"👤 المستخدم: @{message.from_user.username or message.from_user.first_name}\n"
                f"🆔 المعرف: `{user_id}`\n"
                f"📝 الرسالة: `{text}`\n\n"
                f"📌 بعد التحقق، استخدم زر '🎫 إنشاء كود نقاط'."
            )
            markup = types.InlineKeyboardMarkup(row_width=1)
            markup.add(
                types.InlineKeyboardButton("🎫 إنشاء كود نقاط", callback_data="create_code")
            )
            bot.send_message(ADMIN_ID, admin_text, reply_markup=markup)
            bot.reply_to(
                message,
                "✅ **تم استلام طلبك!**\n\n"
                "📌 سيقوم الإدمن بالتحقق وإرسال كود نقاط لك قريباً."
            )
        else:
            pass
    
    except Exception as e:
        print(f"خطأ في handle_text: {e}")
        send_safe(message.chat.id, "❌ حدث خطأ، حاول مرة أخرى.")

# =====================================================================
# 12. معالج الملفات (لرفع ملف دارك)
# =====================================================================
@bot.message_handler(content_types=['document', 'photo', 'video', 'audio'])
def handle_files(message):
    try:
        user_id = message.from_user.id
        is_subscribed, not_subscribed = check_force_subscribe(user_id)
        if not is_subscribed:
            channels_text = "\n".join([f"• {ch}" for ch in not_subscribed])
            msg = (
                f"🔒 **اشتراك إجباري**\n\n"
                f"يجب الاشتراك في:\n\n"
                f"{channels_text}\n\n"
                f"📌 بعد الاشتراك، اضغط على زر التحقق."
            )
            send_safe(
                message.chat.id,
                msg,
                reply_markup=get_force_subscribe_keyboard(not_subscribed)
            )
            return
        state = db.get_user_state(user_id)
        if state and state[0] == 'admin_dark_file_waiting_file':
            if message.document:
                file_id = message.document.file_id
            elif message.photo:
                file_id = message.photo[-1].file_id
            elif message.video:
                file_id = message.video.file_id
            elif message.audio:
                file_id = message.audio.file_id
            else:
                bot.reply_to(message, "❌ نوع الملف غير مدعوم.")
                return
            temp_data = state[3] if state[3] else '{}'
            try:
                temp = json.loads(temp_data)
            except:
                temp = {}
            temp['file_id'] = file_id
            db.set_user_state(user_id, 'admin_dark_file_waiting_description', temp_data=json.dumps(temp))
            bot.reply_to(message, "✅ تم استلام الملف.\n\n📝 الآن أرسل وصفاً لهذا الملف:")
        else:
            bot.reply_to(message, "❌ لا توجد عملية نشطة لاستقبال الملفات.")
    except Exception as e:
        print(f"خطأ في handle_files: {e}")
        bot.reply_to(message, "❌ حدث خطأ.")

# =====================================================================
# 13. معالج إدخال الكود
# =====================================================================
def process_redeem_code(message):
    try:
        user_id = message.from_user.id
        code = message.text.strip().upper()
        if not code:
            bot.reply_to(message, "❌ الكود لا يمكن أن يكون فارغاً.")
            db.clear_user_state(user_id)
            return
        points, msg, new_balance = db.use_redeem_code(code, user_id)
        if points:
            bot.reply_to(
                message,
                f"✅ **تم إضافة النقاط بنجاح!**\n\n⭐ +{points} نقطة\n📊 نقاطك الحالية: `{new_balance}`\n\n⚠️ لا يمكنك استخدام هذا الكود مرة أخرى."
            )
        else:
            bot.reply_to(message, f"❌ {msg}")
        db.clear_user_state(user_id)
    except Exception as e:
        print(f"خطأ في process_redeem_code: {e}")
        bot.reply_to(message, "❌ حدث خطأ")

# =====================================================================
# 14. معالج الأزرار
# =====================================================================
@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    try:
        user_id = call.from_user.id
        data = call.data
        
        is_subscribed, not_subscribed = check_force_subscribe(user_id)
        if not is_subscribed and data != "check_subscribe":
            bot.answer_callback_query(
                call.id,
                "🔒 يجب الاشتراك في القنوات الإجبارية!",
                show_alert=True
            )
            return
        
        if data == "check_subscribe":
            is_subscribed, not_subscribed = check_force_subscribe(user_id)
            if is_subscribed:
                bot.answer_callback_query(call.id, "✅ تم التحقق!")
                send_safe(
                    call.message.chat.id,
                    "✅ **تم التحقق بنجاح!**",
                    reply_markup=get_main_keyboard(user_id)
                )
                try:
                    bot.delete_message(call.message.chat.id, call.message.message_id)
                except:
                    pass
            else:
                channels_text = "\n".join([f"• {ch}" for ch in not_subscribed])
                bot.answer_callback_query(call.id, "❌ لم تشترك بعد!", show_alert=True)
            return
        
        if str(user_id) != str(ADMIN_ID):
            if data in ['add_channel', 'list_channels', 'remove_channel', 'set_image_group', 
                        'view_image_group', 'delete_image_group', 'admin_stats', 
                        'admin_announce', 'payment_settings', 'create_code',
                        'del_channel_', 'cancel_delete', 'set_flexi', 'delete_flexi',
                        'view_sell_requests']:
                bot.answer_callback_query(call.id, "⛔ مخصص للإدمن!", show_alert=True)
                return
        
        if data == "back_main":
            send_safe(
                call.message.chat.id,
                "🔙 رجوع إلى القائمة الرئيسية",
                reply_markup=get_main_keyboard(user_id)
            )
            try:
                bot.delete_message(call.message.chat.id, call.message.message_id)
            except:
                pass
            bot.answer_callback_query(call.id, "✅")
            return
        
        # ===== طلب بيع نقاط =====
        if data == "sell_points":
            points = db.get_points(user_id)
            if points < 150:
                bot.answer_callback_query(
                    call.id,
                    f"❌ الحد الأدنى لبيع النقاط هو 150 نقطة.\nرصيدك الحالي: {points} نقطة",
                    show_alert=True
                )
                return
            bot.send_message(
                call.message.chat.id,
                f"💰 **بيع نقاط**\n\n"
                f"⭐ رصيدك الحالي: {points} نقطة\n"
                f"📝 أدخل عدد النقاط التي تريد بيعها (الحد الأدنى 150 نقطة):"
            )
            db.set_user_state(user_id, 'sell_points_amount', temp_data=json.dumps({'max_points': points}))
            bot.answer_callback_query(call.id, "✅")
            return
        
        # ===== إكمال طلب البيع (للمالك) =====
        if data.startswith('complete_sell_'):
            if str(user_id) != str(ADMIN_ID):
                bot.answer_callback_query(call.id, "⛔ مخصص للإدمن فقط!", show_alert=True)
                return
            request_id = int(data.split('_')[2])
            request = db.get_sell_request(request_id)
            if not request:
                bot.answer_callback_query(call.id, "❌ الطلب غير موجود!", show_alert=True)
                return
            if request[6] != 'pending':
                bot.answer_callback_query(call.id, "❌ هذا الطلب تم معالجته مسبقاً!", show_alert=True)
                return
            if db.update_sell_request_status(request_id, 'completed'):
                user_id_req = request[1]
                username = request[2]
                phone = request[3]
                points = request[4]
                try:
                    bot.send_message(
                        user_id_req,
                        f"✅ **تم شحن رصيد فليكسي بنجاح!**\n\n"
                        f"💰 عدد النقاط المباعة: `{points}`\n"
                        f"📱 رقم الهاتف: `{phone}`\n\n"
                        f"🎉 تم إيداع الرصيد في حسابك."
                    )
                except:
                    pass
                bot.answer_callback_query(call.id, "✅ تم شحن الرصيد وإعلام المستخدم.")
                bot.edit_message_text(
                    f"✅ **تم شحن الرصيد**\n\nطلب #{request_id}\nالمستخدم: @{username}\nالهاتف: {phone}\nالنقاط: {points}",
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    reply_markup=None
                )
            else:
                bot.answer_callback_query(call.id, "❌ فشل التحديث!", show_alert=True)
            return
        
        # ===== عرض طلبات بيع النقاط للمالك =====
        if data == "view_sell_requests":
            if str(user_id) != str(ADMIN_ID):
                bot.answer_callback_query(call.id, "⛔ مخصص للإدمن!", show_alert=True)
                return
            requests = db.get_sell_requests('pending')
            if not requests:
                send_safe(call.message.chat.id, "📋 **لا توجد طلبات بيع نقاط معلقة.**")
                bot.answer_callback_query(call.id, "✅")
                return
            text = "📋 **طلبات بيع النقاط المعلقة:**\n\n"
            for req in requests:
                text += f"🆔 #{req[0]}\n"
                text += f"👤 المستخدم: @{req[2] or 'لا يوجد يوزر'}\n"
                text += f"📱 الهاتف: `{req[3]}`\n"
                text += f"⭐ النقاط: `{req[4]}`\n"
                text += f"📅 التاريخ: {req[5]}\n"
                text += "─" * 20 + "\n"
            send_safe(call.message.chat.id, text)
            bot.answer_callback_query(call.id, "✅")
            return
        
        # ===== باقي الأزرار =====
        if data == "create_code":
            db.set_user_state(user_id, 'admin_create_code_points')
            bot.send_message(
                call.message.chat.id,
                "🎫 **إنشاء كود نقاط**\n\n📝 أرسل عدد النقاط:"
            )
            bot.answer_callback_query(call.id, "✅")
            return
        
        if data == "payment_settings":
            flexi = db.get_setting('flexi_number')
            text = f"💳 **إعدادات الدفع**\n\n📌 رقم فليكسي: `{flexi or '❌ غير محدد'}`"
            markup = types.InlineKeyboardMarkup(row_width=1)
            markup.add(
                types.InlineKeyboardButton("➕ تعيين رقم فليكسي", callback_data="set_flexi"),
                types.InlineKeyboardButton("❌ حذف رقم فليكسي", callback_data="delete_flexi")
            )
            send_safe(call.message.chat.id, text, reply_markup=markup)
            bot.answer_callback_query(call.id, "✅")
            return
        
        if data == "set_flexi":
            bot.send_message(
                call.message.chat.id,
                "📝 **تعيين رقم فليكسي**\n\nأرسل الرقم:"
            )
            bot.register_next_step_handler(call.message, set_flexi_handler)
            bot.answer_callback_query(call.id, "✅")
            return
        
        if data == "delete_flexi":
            db.delete_setting('flexi_number')
            send_safe(call.message.chat.id, "✅ **تم حذف رقم فليكسي**")
            bot.answer_callback_query(call.id, "✅")
            return
        
        if data == "set_image_group":
            bot.send_message(
                call.message.chat.id,
                "📸 **تعيين مجموعة تخزين الصور**\n\nأرسل معرف المجموعة:\nمثال: `@hsksbwvwwn`"
            )
            bot.register_next_step_handler(call.message, set_image_group_handler)
            bot.answer_callback_query(call.id, "✅")
            return
        
        elif data == "view_image_group":
            group = get_image_storage_group()
            if group:
                send_safe(
                    call.message.chat.id,
                    f"📸 **مجموعة تخزين الصور الحالية:**\n\n`{group}`"
                )
            else:
                send_safe(
                    call.message.chat.id,
                    "📸 **لا توجد مجموعة تخزين صور محددة.**"
                )
            bot.answer_callback_query(call.id, "✅")
            return
        
        elif data == "delete_image_group":
            group = get_image_storage_group()
            if not group:
                send_safe(call.message.chat.id, "📸 **لا توجد مجموعة لحذفها.**")
                bot.answer_callback_query(call.id, "❌")
                return
            if delete_image_storage_group():
                send_safe(call.message.chat.id, "✅ **تم حذف مجموعة الصور بنجاح!**")
                bot.answer_callback_query(call.id, "✅")
            else:
                send_safe(call.message.chat.id, "❌ فشل الحذف.")
                bot.answer_callback_query(call.id, "❌")
            return
        
        elif data == "add_channel":
            bot.send_message(
                call.message.chat.id,
                "📝 **إضافة قناة إجبارية**\n\nأرسل معرف القناة:\n`@hsjBwbxkw`"
            )
            bot.register_next_step_handler(call.message, add_channel_handler)
            bot.answer_callback_query(call.id, "✅")
        
        elif data == "list_channels":
            channels = db.get_force_channels()
            if channels:
                text = "📋 **القنوات الإجبارية:**\n\n"
                for i, (channel, ctype) in enumerate(channels, 1):
                    text += f"{i}. {channel} ({ctype})\n"
            else:
                text = "📋 لا توجد قنوات."
            send_safe(call.message.chat.id, text)
            bot.answer_callback_query(call.id, "✅")
        
        elif data == "remove_channel":
            channels = db.get_force_channels()
            if not channels:
                send_safe(call.message.chat.id, "📋 لا توجد قنوات.")
                bot.answer_callback_query(call.id, "❌")
                return
            markup = types.InlineKeyboardMarkup(row_width=1)
            for channel, ctype in channels:
                markup.add(
                    types.InlineKeyboardButton(
                        f"🗑️ حذف {channel}",
                        callback_data=f"del_channel_{channel}"
                    )
                )
            markup.add(types.InlineKeyboardButton("🔙 إلغاء", callback_data="cancel_delete"))
            send_safe(call.message.chat.id, "🗑️ **اختر القناة:**", reply_markup=markup)
            bot.answer_callback_query(call.id, "✅")
        
        elif data.startswith("del_channel_"):
            channel = data.replace("del_channel_", "")
            if db.remove_force_channel(channel):
                send_safe(call.message.chat.id, f"✅ **تم حذف {channel}**")
            bot.answer_callback_query(call.id, "✅")
        
        elif data == "cancel_delete":
            send_safe(call.message.chat.id, "🔙 تم الإلغاء.")
            bot.answer_callback_query(call.id, "✅")
        
        elif data == "admin_stats":
            stats_text = (
                f"📊 **إحصائيات البوت**\n\n"
                f"👥 المستخدمين: `{db.get_user_count()}`\n"
                f"🛒 السلع: `{len(db.get_store_items())}`\n"
                f"🔒 القنوات: `{db.get_force_channels_count()}`\n"
                f"📸 مجموعة الصور: `{get_image_storage_group() or 'غير محددة'}`\n"
                f"💳 رقم فليكسي: `{db.get_setting('flexi_number') or 'غير محدد'}`\n"
                f"📁 ملف دارك: {'✅ موجود' if db.get_dark_file()[0] else '❌ لا يوجد'}\n"
                f"💰 طلبات بيع نقاط معلقة: `{len(db.get_sell_requests('pending'))}`"
            )
            send_safe(call.message.chat.id, stats_text)
            bot.answer_callback_query(call.id, "✅")
        
        elif data == "admin_announce":
            bot.send_message(
                call.message.chat.id,
                "📢 **إرسال إعلان**\n\nأرسل النص:"
            )
            bot.register_next_step_handler(call.message, admin_announce_handler)
            bot.answer_callback_query(call.id, "✅")
        
        elif data == "flexi_pay":
            flexi = db.get_setting('flexi_number')
            if not flexi:
                send_safe(
                    call.message.chat.id,
                    "❌ **رقم فليكسي غير محدد حالياً.**\nيرجى التواصل مع الإدمن."
                )
                bot.answer_callback_query(call.id, "❌", show_alert=True)
                return
            text = (
                f"💳 **الشراء عبر فليكسي**\n\n"
                f"📌 رقم فليكسي: `{flexi}`\n\n"
                f"📝 **الخطوات:**\n"
                f"1. أرسل المبلغ إلى الرقم أعلاه.\n"
                f"2. أرسل رسالة `تم فليكسي` مع ذكر عدد النقاط.\n"
                f"3. سيقوم الإدمن بالتحقق وإرسال كود نقاط لك."
            )
            send_safe(call.message.chat.id, text)
            bot.answer_callback_query(call.id, "✅")
        
        elif data == "view_store":
            image_group = get_image_storage_group()
            if not image_group:
                send_safe(
                    call.message.chat.id,
                    "❌ **لم يتم تعيين مجموعة تخزين الصور!**\nيرجى من الإدمن تعيينها."
                )
                bot.answer_callback_query(call.id, "❌", show_alert=True)
                return
            try:
                chat = bot.get_chat(image_group)
                if chat.username:
                    group_link = f"https://t.me/{chat.username}"
                else:
                    group_link = f"المجموعة: {image_group}"
            except:
                group_link = f"المجموعة: {image_group}"
            send_safe(
                call.message.chat.id,
                f"🛒 **السلع المعروضة للبيع**\n\n📸 جميع الصور في:\n🔗 {group_link}\n\n📌 كل صورة تحمل اسم البائع."
            )
            bot.answer_callback_query(call.id, "✅")
        
        elif data == "add_item":
            if not get_image_storage_group():
                send_safe(
                    call.message.chat.id,
                    "❌ **لم يتم تعيين مجموعة تخزين الصور!**\nيرجى من الإدمن تعيينها أولاً."
                )
                bot.answer_callback_query(call.id, "❌", show_alert=True)
                return
            user_points = db.get_points(user_id)
            if user_points < 5:
                markup = types.InlineKeyboardMarkup(row_width=1)
                markup.add(
                    types.InlineKeyboardButton("💰 شراء نقاط", callback_data="flexi_pay"),
                    types.InlineKeyboardButton("📤 مشاركة البوت", callback_data="share_bot")
                )
                bot.send_message(
                    call.message.chat.id,
                    f"❌ **رصيدك غير كافٍ!**\n⭐ رصيدك: {user_points} نقطة\n💡 تحتاج 5 نقاط.",
                    reply_markup=markup
                )
                bot.answer_callback_query(call.id, "❌", show_alert=True)
                return
            bot.send_message(
                call.message.chat.id,
                "📸 **إضافة سلعة للبيع**\n\n⭐ سيتم خصم 5 نقاط.\nالخطوة 1: أرسل صورة السلعة 📸"
            )
            db.set_user_state(user_id, 'waiting_store_image')
            bot.register_next_step_handler(call.message, process_store_image)
            bot.answer_callback_query(call.id, "✅")
        
        elif data == "test_all":
            results = "📊 **نتائج اختبار جميع السيرفرات:**\n\n"
            for key, server in VLESS_SERVERS.items():
                is_online, ping = test_server_speed(server['ip'], int(server['port']))
                status = "🟢" if is_online else "🔴"
                ping_text = f"{ping}ms" if ping else "⏳"
                results += f"{status} {server['flag']} {server['name']}: `{ping_text}`\n"
            try:
                bot.edit_message_text(
                    results,
                    call.message.chat.id,
                    call.message.message_id,
                    reply_markup=None
                )
            except:
                send_safe(call.message.chat.id, results)
            bot.answer_callback_query(call.id, "✅")
    
    except Exception as e:
        print(f"خطأ في handle_callback: {e}")
        try:
            bot.answer_callback_query(call.id, "❌ حدث خطأ", show_alert=True)
        except:
            pass

# =====================================================================
# 15. معالج إضافة سلعة
# =====================================================================
def process_store_image(message):
    try:
        user_id = message.from_user.id
        state = db.get_user_state(user_id)
        if not state or state[0] != 'waiting_store_image':
            bot.reply_to(message, "❌ يرجى البدء من البداية.")
            return
        if not message.photo:
            bot.reply_to(message, "❌ **يرجى إرسال صورة.**")
            bot.register_next_step_handler(message, process_store_image)
            return
        image_group = get_image_storage_group()
        if not image_group:
            bot.reply_to(message, "❌ **لم يتم تعيين مجموعة الصور!**")
            db.clear_user_state(user_id)
            return
        username = message.from_user.username
        if not username:
            bot.reply_to(message, "❌ **ليس لديك يوزر!**\nيرجى تعيين يوزر.")
            db.clear_user_state(user_id)
            return
        try:
            bot.get_chat_member(image_group, bot.get_me().id)
        except:
            bot.reply_to(
                message,
                f"❌ **البوت ليس أدمن في مجموعة الصور!**\nالمجموعة: `{image_group}`"
            )
            db.clear_user_state(user_id)
            return
        user_points = db.get_points(user_id)
        if user_points < 5:
            bot.reply_to(
                message,
                f"❌ **رصيدك غير كافٍ!**\n⭐ رصيدك: {user_points} نقطة\n💡 تحتاج 5 نقاط."
            )
            db.clear_user_state(user_id)
            return
        try:
            sent_msg = bot.send_photo(
                image_group,
                message.photo[-1].file_id,
                caption=f"🛒 سلعة جديدة\n👤 البائع: @{username}\n📅 {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            )
            image_message_id = str(sent_msg.message_id)
            db.add_store_item(user_id, username, image_message_id)
            new_balance = db.add_points(user_id, -5)
            bot.reply_to(
                message,
                f"✅ **تم عرض سلعتك للبيع!**\n\n"
                f"📌 تم حفظ الصورة.\n"
                f"👤 اسمك: @{username}\n"
                f"⭐ تم خصم 5 نقاط. رصيدك: {new_balance} نقطة"
            )
            db.clear_user_state(user_id)
        except Exception as e:
            print(f"خطأ في process_store_image: {e}")
            bot.reply_to(message, f"❌ حدث خطأ: {str(e)[:100]}")
            db.clear_user_state(user_id)
    except Exception as e:
        print(f"خطأ عام في process_store_image: {e}")
        bot.reply_to(message, "❌ حدث خطأ غير متوقع.")
        db.clear_user_state(user_id)

# =====================================================================
# 16. معالج تعيين مجموعة الصور
# =====================================================================
def set_image_group_handler(message):
    try:
        user_id = message.from_user.id
        if str(user_id) != str(ADMIN_ID):
            return
        group_id = message.text.strip()
        if not group_id.startswith('@'):
            group_id = '@' + group_id
        try:
            chat = bot.get_chat(group_id)
            if chat.type not in ['group', 'supergroup']:
                send_safe(message.chat.id, f"❌ **خطأ:** {group_id} ليس مجموعة!")
                return
        except:
            send_safe(
                message.chat.id,
                f"❌ **خطأ:** لا يمكن العثور على {group_id}\n"
                "تأكد من المعرف والبوت أدمن."
            )
            return
        if set_image_storage_group(group_id):
            send_safe(
                message.chat.id,
                f"✅ **تم تعيين مجموعة الصور بنجاح!**\n📸 المجموعة: `{group_id}`"
            )
            try:
                bot.send_message(
                    group_id,
                    "📸 **تم تعيين هذه المجموعة لتخزين صور السلع!**"
                )
            except:
                send_safe(
                    message.chat.id,
                    "⚠️ **تنبيه:** لا يمكن إرسال رسالة للمجموعة."
                )
        else:
            send_safe(message.chat.id, "❌ **فشل في تعيين المجموعة.**")
    except Exception as e:
        print(f"خطأ في set_image_group_handler: {e}")
        send_safe(message.chat.id, f"❌ حدث خطأ: {str(e)[:100]}")

# =====================================================================
# 17. معالج تعيين رقم فليكسي
# =====================================================================
def set_flexi_handler(message):
    try:
        user_id = message.from_user.id
        if str(user_id) != str(ADMIN_ID):
            return
        flexi_number = message.text.strip()
        if not flexi_number:
            send_safe(message.chat.id, "❌ الرقم لا يمكن أن يكون فارغاً.")
            return
        if db.set_setting('flexi_number', flexi_number):
            send_safe(message.chat.id, f"✅ **تم تعيين رقم فليكسي:** `{flexi_number}`")
        else:
            send_safe(message.chat.id, "❌ فشل في تعيين الرقم.")
    except Exception as e:
        print(f"خطأ في set_flexi_handler: {e}")

# =====================================================================
# 18. معالج إضافة القناة والإعلان
# =====================================================================
def add_channel_handler(message):
    try:
        user_id = message.from_user.id
        if str(user_id) != str(ADMIN_ID):
            return
        channel = message.text.strip()
        if not channel.startswith('@'):
            channel = '@' + channel
        try:
            chat = bot.get_chat(channel)
            chat_type = chat.type
        except:
            send_safe(
                message.chat.id,
                f"❌ **خطأ:** لا يمكن العثور على {channel}"
            )
            return
        if db.add_force_channel(channel, chat_type):
            send_safe(
                message.chat.id,
                f"✅ **تم إضافة {channel} بنجاح!**\n📌 النوع: {chat_type}"
            )
        else:
            send_safe(
                message.chat.id,
                f"❌ فشل الإضافة! قد تكون {channel} مضافة بالفعل."
            )
    except Exception as e:
        print(f"خطأ في add_channel_handler: {e}")

def admin_announce_handler(message):
    try:
        user_id = message.from_user.id
        if str(user_id) != str(ADMIN_ID):
            return
        announce_text = message.text
        cursor = db.conn.cursor()
        cursor.execute(
            "INSERT INTO announcements (message, date) VALUES (?, ?)",
            (announce_text, datetime.now().strftime('%Y-%m-%d'))
        )
        db.conn.commit()
        cursor.close()
        cursor = db.conn.cursor()
        users = cursor.execute("SELECT id FROM users").fetchall()
        cursor.close()
        sent = 0
        failed = 0
        bot.reply_to(message, "🔄 جاري إرسال الإعلان...")
        for uid in users:
            try:
                bot.send_message(uid[0], f"📢 **إعلان جديد**\n\n{announce_text}")
                sent += 1
                time.sleep(0.05)
            except:
                failed += 1
        bot.send_message(
            ADMIN_ID,
            f"✅ **تم إرسال الإعلان**\n\n• تم الإرسال: {sent}\n• فشل: {failed}\n• المجموع: {len(users)}"
        )
    except Exception as e:
        print(f"خطأ في admin_announce_handler: {e}")

# =====================================================================
# 19. خيط خلفي لفحص انتهاء صلاحية الملف الدارك
# =====================================================================
def dark_file_expiry_checker():
    while True:
        try:
            if db.is_dark_file_expired():
                file_id, _, _ = db.get_dark_file()
                if file_id:
                    db.delete_dark_file()
                    bot.send_message(ADMIN_ID, "⏰ **انتهت صلاحية ملف دارك**\nتم حذفه تلقائياً.")
        except Exception as e:
            print(f"خطأ في dark_file_expiry_checker: {e}")
        time.sleep(60)

# =====================================================================
# 20. تشغيل البوت
# =====================================================================
if __name__ == "__main__":
    threading.Thread(target=dark_file_expiry_checker, daemon=True).start()
    print("=" * 50)
    print(f"⚡ {BOT_NAME} جاهز للعمل")
    print("=" * 50)
    print(f"👤 المطور: {DEVELOPER_USERNAME}")
    print(f"🆔 الآدمن: {ADMIN_ID}")
    print(f"📁 نظام الملف الدارك: نشط")
    print(f"🛒 المتجر: نشط (خصم 5 نقاط، بيع نقاط بحد أدنى 150)")
    print(f"📸 مجموعة الصور: {get_image_storage_group() or '❌ غير محددة'}")
    print(f"💳 رقم فليكسي: {db.get_setting('flexi_number') or '❌ غير محدد'}")
    print(f"📁 ملف دارك: {'✅ موجود' if db.get_dark_file()[0] else '❌ لا يوجد'}")
    print("=" * 50)
    print("🔄 تشغيل البوت...")
    while True:
        try:
            bot.infinity_polling(timeout=10, long_polling_timeout=5)
        except Exception as e:
            print(f"❌ خطأ: {e}")
            traceback.print_exc()
            print("🔄 إعادة المحاولة بعد 5 ثواني...")
            time.sleep(5)