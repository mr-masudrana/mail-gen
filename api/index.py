from flask import Flask, request
import os
import requests
import json
import qrcode
import io
import base64
import hashlib
import random
import string
from gtts import gTTS
from fpdf import FPDF
from PIL import Image

app = Flask(__name__)

# --- কনফিগারেশন ---
BOT_TOKEN = os.environ.get('BOT_TOKEN')
BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
MAIL_API_URL = "https://api.mail.tm"

# ইউজার স্টেট (মেমোরি)
user_states = {}

# --- ১. মেনু বাটন ---
def get_main_menu():
    return json.dumps({
        "keyboard": [
            [{"text": "📧 Temp Mail"}, {"text": "🛠 Generator Tool"}],
            [{"text": "📂 PDF Tool"}, {"text": "🗣 Voice Tool"}],
            [{"text": "🖼 Image Tool"}, {"text": "📝 Text Tool"}]
        ],
        "resize_keyboard": True,
        "one_time_keyboard": False
    })

# সাব-মেনু
def get_temp_mail_menu(): return json.dumps({"keyboard": [[{"text": "📧 New Mail"}], [{"text": "🔙 Back"}]], "resize_keyboard": True})
def get_gen_menu(): return json.dumps({"keyboard": [[{"text": "🟦 QR Code"}, {"text": "🔑 Password Gen"}], [{"text": "🔗 Link Shortener"}, {"text": "🔙 Back"}]], "resize_keyboard": True})
def get_pdf_menu(): return json.dumps({"keyboard": [[{"text": "🖼 Img to PDF"}, {"text": "📄 Text to PDF"}], [{"text": "🔙 Back"}]], "resize_keyboard": True})
def get_voice_menu(): return json.dumps({"keyboard": [[{"text": "🗣 Text to Voice"}, {"text": "🔙 Back"}]], "resize_keyboard": True})
def get_image_menu(): return json.dumps({"keyboard": [[{"text": "⚫ Grayscale"}, {"text": "📐 Resize (50%)"}], [{"text": "🔙 Back"}]], "resize_keyboard": True})
def get_text_menu(): return json.dumps({"keyboard": [[{"text": "🔐 Base64 Enc"}, {"text": "🔓 Base64 Dec"}], [{"text": "#️⃣ MD5 Hash"}, {"text": "🔠 Uppercase"}], [{"text": "🔙 Back"}]], "resize_keyboard": True})

# --- ২. হেল্পার ফাংশন ---
def send_reply(chat_id, text, reply_markup=None):
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}
    if reply_markup: payload["reply_markup"] = reply_markup
    try: requests.post(f"{BASE_URL}/sendMessage", json=payload)
    except: pass

def send_file(chat_id, file_data, file_type, caption=None, filename="file"):
    files = {}
    if file_type == "photo": files = {'photo': (f"{filename}.jpg", file_data, 'image/jpeg')}
    elif file_type == "document": files = {'document': (f"{filename}.pdf", file_data, 'application/pdf')}
    elif file_type == "audio": files = {'audio': (f"{filename}.mp3", file_data, 'audio/mpeg')}
    
    url = f"{BASE_URL}/send{file_type.capitalize()}"
    data = {'chat_id': chat_id, 'caption': caption}
    try: requests.post(url, data=data, files=files)
    except: pass

def get_file_content(file_id):
    r = requests.get(f"{BASE_URL}/getFile?file_id={file_id}")
    file_path = r.json()["result"]["file_path"]
    return requests.get(f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}").content

def format_size(size):
    power = 2**10
    n = 0
    power_labels = {0 : '', 1: 'KB', 2: 'MB', 3: 'GB'}
    while size > power:
        size /= power
        n += 1
    return f"{round(size, 2)} {power_labels[n]}"

def format_duration(seconds):
    m, s = divmod(seconds, 60)
    return f"{m:02d}:{s:02d}"

# --- ৩. Temp Mail API ---
def create_mail_account():
    try:
        domain = requests.get(f"{MAIL_API_URL}/domains").json()['hydra:member'][0]['domain']
        username = ''.join(random.choices(string.ascii_lowercase, k=6))
        password = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
        address = f"{username}@{domain}"
        requests.post(f"{MAIL_API_URL}/accounts", json={"address": address, "password": password})
        return address, password
    except: return None, None

def get_mail_token(address, password):
    try:
        r = requests.post(f"{MAIL_API_URL}/token", json={"address": address, "password": password})
        return r.json()['token'] if r.status_code == 200 else None
    except: return None

def get_mails(token):
    try:
        headers = {"Authorization": f"Bearer {token}"}
        return requests.get(f"{MAIL_API_URL}/messages", headers=headers).json()['hydra:member']
    except: return []

def read_mail(msg_id, token):
    try:
        headers = {"Authorization": f"Bearer {token}"}
        return requests.get(f"{MAIL_API_URL}/messages/{msg_id}", headers=headers).json()
    except: return None

# --- মেইন রাউট ---
@app.route('/')
def home(): return "Bot with /help Command Running! 🚀"

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        data = request.get_json(force=True)
        
        # --- CALLBACK QUERY ---
        if "callback_query" in data:
            call = data["callback_query"]
            chat_id = call["message"]["chat"]["id"]
            data_text = call["data"]
            parts = data_text.split("|")
            action, address, password = parts[0], parts[1], parts[2]
            
            token = get_mail_token(address, password)
            if not token:
                requests.post(f"{BASE_URL}/answerCallbackQuery", json={"callback_query_id": call["id"], "text": "❌ মেয়াদ শেষ।", "show_alert": True})
                return "ok", 200

            if action == "check":
                msgs = get_mails(token)
                if not msgs:
                    requests.post(f"{BASE_URL}/answerCallbackQuery", json={"callback_query_id": call["id"], "text": "📭 ইনবক্স খালি!", "show_alert": True})
                else:
                    text = f"📬 <b>Inbox:</b> {address}\n\n"
                    kb = {"inline_keyboard": []}
                    for m in msgs[:5]:
                        sub = m.get('subject', '(No Subject)')
                        kb["inline_keyboard"].append([{"text": f"📖 {sub[:15]}..", "callback_data": f"read|{address}|{password}|{m['id']}"}])
                    kb["inline_keyboard"].append([{"text": "🔄 Refresh", "callback_data": f"check|{address}|{password}"}])
                    send_reply(chat_id, text, kb)
            
            elif action == "read":
                msg_id = parts[3]
                full = read_mail(msg_id, token)
                if full:
                    body = full.get('text', 'No text')[:3000]
                    view = f"📩 <b>From:</b> {full['from']['address']}\n<b>Sub:</b> {full.get('subject')}\n\n{body}"
                    kb = {"inline_keyboard": [[{"text": "🔙 Back", "callback_data": f"check|{address}|{password}"}]]}
                    send_reply(chat_id, view, kb)

            requests.post(f"{BASE_URL}/answerCallbackQuery", json={"callback_query_id": call["id"]})
            return "ok", 200

        # --- TEXT MESSAGES ---
        if "message" in data:
            msg = data["message"]
            chat_id = msg["chat"]["id"]
            text = msg.get("text", "")
            
            state = user_states.get(chat_id, None)

            # --- START COMMAND ---
            if text == "/start":
                user_states[chat_id] = None
                u = msg.get("from", {})
                fname = u.get("first_name", "")
                lname = u.get("last_name", "")
                full_name = f"{fname} {lname}".strip()
                username = f"@{u.get('username')}" if u.get('username') else "N/A"
                
                start_msg = (
                    f"👋 হ্যালো <b>{fname}</b>!\n\n"
                    "আমি একটি অ্যাডভান্সড ইনফো বট।\n"
                    "আমার কাজ হলো যেকোনো চ্যাট, ইউজার বা চ্যানেলের গোপন তথ্য বের করা।\n\n"
                    "👤 <b>YOUR PROFILE:</b>\n\n"
                    f"🆔 <b>ID:</b> <code>{u.get('id')}</code>\n"
                    f"📛 <b>Name:</b> {full_name}\n"
                    f"🔗 <b>Username:</b> {username}\n\n"
                    "ℹ️ <i>সাহায্যের জন্য /help চাপুন।</i>"
                )
                send_reply(chat_id, start_msg, get_main_menu())

            # --- HELP COMMAND (নতুন যুক্ত করা হয়েছে) ---
            elif text == "/help":
                help_text = (
                    "🤖 <b>বট গাইডলাইন (Help Menu)</b>\n\n"
                    "আমি একটি মাল্টি-ফাংশনাল টুল বট। নিচে আমার ফিচারগুলো দেওয়া হলো:\n\n"
                    "<b>১. অটোমেটিক ইনফো (Auto Info):</b>\n"
                    "🔹 যেকোনো মেসেজ <b>Forward</b> করুন, আমি তার গোপন আইডি ও সোর্স বলে দেব।\n"
                    "🔹 যেকোনো ফাইল/ছবি/ভিডিও পাঠান, আমি তার সাইজ ও ডিটেইলস দেব।\n\n"
                    "<b>২. মেনু টুলস (Menu Tools):</b>\n"
                    "📧 <b>Temp Mail:</b> আনলিমিটেড টেম্পোরারি মেইল ও ইনবক্স।\n"
                    "🛠 <b>Generator:</b> QR Code, Password, Link Shortener.\n"
                    "📂 <b>PDF Tools:</b> ছবি বা লেখা থেকে PDF তৈরি।\n"
                    "🗣 <b>Voice Tools:</b> লেখা (English) থেকে ভয়েস তৈরি।\n"
                    "🖼 <b>Image Tools:</b> ছবির সাইজ কমানো, সাদা-কালো করা।\n"
                    "📝 <b>Text Tools:</b> Base64, Hash, Uppercase ইত্যাদি।\n\n"
                    "🚀 <b>শুরু করবেন কিভাবে?</b>\n"
                    "নিচের মেনু বাটনগুলো ব্যবহার করুন অথবা /start চাপুন।"
                )
                send_reply(chat_id, help_text)

            elif text == "🔙 Back":
                user_states[chat_id] = None
                send_reply(chat_id, "👋 <b>Main Menu</b>", get_main_menu())

            # --- Menu Navigation ---
            elif text == "📧 Temp Mail":
                send_reply(chat_id, "📧 <b>Temp Mail System</b>\nনতুন মেইল তৈরি করতে নিচের বাটনে চাপুন:", get_temp_mail_menu())
            elif text == "📧 New Mail":
                addr, pwd = create_mail_account()
                if addr:
                    res = f"✅ <b>Temp Mail Created!</b>\n\n📧 <code>{addr}</code>\n\n(ইনবক্স চেক করতে নিচের বাটনে চাপুন)"
                    kb = {"inline_keyboard": [[{"text": "📩 Check Inbox", "callback_data": f"check|{addr}|{pwd}"}]]}
                    send_reply(chat_id, res, kb)
                else: send_reply(chat_id, "⚠️ Server Error.")

            elif text == "🛠 Generator Tool": send_reply(chat_id, "🛠 Tools:", get_gen_menu())
            elif text == "📂 PDF Tool": send_reply(chat_id, "📂 Tools:", get_pdf_menu())
            elif text == "🗣 Voice Tool": send_reply(chat_id, "🗣 Tools:", get_voice_menu())
            elif text == "🖼 Image Tool": send_reply(chat_id, "🖼 Tools:", get_image_menu())
            elif text == "📝 Text Tool": send_reply(chat_id, "📝 Tools:", get_text_menu())
            
            # --- Tool Activation ---
            elif text == "🟦 QR Code":
                user_states[chat_id] = "qr"
                send_reply(chat_id, "👉 টেক্সট দিন:")
            elif text == "🔗 Link Shortener":
                user_states[chat_id] = "shorten"
                send_reply(chat_id, "👉 লিংক দিন:")
            elif text == "🔑 Password Gen":
                pwd = ''.join(random.choices(string.ascii_letters + string.digits + "!@#", k=12))
                send_reply(chat_id, f"🔑 Pass: <code>{pwd}</code>")
            elif text == "🗣 Text to Voice":
                user_states[chat_id] = "tts"
                send_reply(chat_id, "👉 ইংরেজি টেক্সট দিন:")
            elif text == "🖼 Img to PDF":
                user_states[chat_id] = "img2pdf"
                send_reply(chat_id, "👉 ছবি পাঠান:")
            elif text == "📄 Text to PDF":
                user_states[chat_id] = "text2pdf"
                send_reply(chat_id, "👉 টেক্সট পাঠান:")
            elif text == "⚫ Grayscale":
                user_states[chat_id] = "grayscale"
                send_reply(chat_id, "👉 ছবি পাঠান:")
            elif text == "📐 Resize (50%)":
                user_states[chat_id] = "resize"
                send_reply(chat_id, "👉 ছবি পাঠান:")
            elif text == "🔐 Base64 Enc":
                user_states[chat_id] = "b64_enc"
                send_reply(chat_id, "👉 টেক্সট দিন:")
            elif text == "🔓 Base64 Dec":
                user_states[chat_id] = "b64_dec"
                send_reply(chat_id, "👉 কোড দিন:")
            elif text == "#️⃣ MD5 Hash":
                user_states[chat_id] = "hash"
                send_reply(chat_id, "👉 টেক্সট দিন:")
            elif text == "🔠 Uppercase":
                user_states[chat_id] = "upper"
                send_reply(chat_id, "👉 টেক্সট দিন:")
            
            # --- Input Handling ---
            else:
                # ক) Forwarded Info
                if "forward_date" in msg:
                    chat = msg.get("forward_from_chat")
                    user = msg.get("forward_from")
                    if chat:
                        info = (
                            "📢 <b>CHANNEL SOURCE</b>\n\n"
                            f"🆔 <b>ID:</b> <code>{chat.get('id')}</code>\n"
                            f"📛 <b>Name:</b> {chat.get('title')}\n"
                            f"🔗 <b>Username:</b> @{chat.get('username','None')}"
                        )
                    elif user:
                        u_type = "🤖 BOT" if user.get("is_bot") else "👤 USER"
                        fname = user.get("first_name", "")
                        lname = user.get("last_name", "")
                        full = f"{fname} {lname}".strip()
                        info = (
                            f"{u_type} <b>SOURCE</b>\n\n"
                            f"🆔 <b>ID:</b> <code>{user.get('id')}</code>\n"
                            f"📛 <b>Name:</b> {full}\n"
                            f"🔗 <b>Username:</b> @{user.get('username','None')}"
                        )
                    else:
                        info = (
                            "🔒 <b>HIDDEN SOURCE</b>\n\n"
                            f"📛 <b>Name:</b> {msg.get('forward_sender_name')}\n"
                            "⚠️ <i>ID Hidden by Privacy</i>"
                        )
                    send_reply(chat_id, info)

                # খ) File Info
                elif (msg.get("photo") or msg.get("document") or msg.get("video") or msg.get("audio")):
                    if state == "img2pdf" and "photo" in msg:
                         file_id = msg["photo"][-1]["file_id"]
                         img_bytes = get_file_content(file_id)
                         img = Image.open(io.BytesIO(img_bytes)).convert('RGB')
                         bio = io.BytesIO()
                         img.save(bio, 'PDF')
                         bio.seek(0)
                         send_file(chat_id, bio, "document", caption="✅ Image to PDF", filename="converted")
                    
                    elif state == "grayscale" and "photo" in msg:
                         file_id = msg["photo"][-1]["file_id"]
                         img_bytes = get_file_content(file_id)
                         img = Image.open(io.BytesIO(img_bytes)).convert('L')
                         bio = io.BytesIO()
                         img.save(bio, 'JPEG')
                         bio.seek(0)
                         send_file(chat_id, bio, "photo", caption="⚫ Grayscale")

                    elif state == "resize" and "photo" in msg:
                         file_id = msg["photo"][-1]["file_id"]
                         img_bytes = get_file_content(file_id)
                         img = Image.open(io.BytesIO(img_bytes))
                         w, h = img.size
                         img = img.resize((int(w/2), int(h/2)))
                         bio = io.BytesIO()
                         img.save(bio, 'JPEG')
                         bio.seek(0)
                         send_file(chat_id, bio, "photo", caption="📐 Resized 50%")

                    elif not state:
                        icon = "📁"
                        type_name = "UNKNOWN"
                        details = ""
                        
                        if "document" in msg:
                            doc = msg["document"]
                            icon = "📄"
                            type_name = "DOCUMENT"
                            details = (
                                f"📛 <b>Title:</b> {doc.get('file_name', 'No Name')}\n"
                                f"📦 <b>Size:</b> {format_size(doc['file_size'])}\n"
                                f"🏷 <b>Mime:</b> {doc.get('mime_type')}"
                            )
                        elif "photo" in msg:
                            p = msg['photo'][-1]
                            icon = "🖼"
                            type_name = "IMAGE"
                            details = (
                                f"📦 <b>Size:</b> {format_size(p['file_size'])}\n"
                                f"📐 <b>Resolution:</b> {p['width']}x{p['height']} px"
                            )
                        elif "video" in msg:
                            v = msg['video']
                            icon = "🎥"
                            type_name = "VIDEO"
                            details = (
                                f"📛 <b>Title:</b> {v.get('file_name', 'Video')}\n"
                                f"📦 <b>Size:</b> {format_size(v['file_size'])}\n"
                                f"⏱ <b>Duration:</b> {format_duration(v.get('duration', 0))}\n"
                                f"📐 <b>Resolution:</b> {v['width']}x{v['height']} px"
                            )
                        elif "audio" in msg:
                            a = msg['audio']
                            icon = "🎵"
                            type_name = "AUDIO"
                            details = (
                                f"📛 <b>Title:</b> {a.get('title', 'Unknown')}\n"
                                f"👤 <b>Artist:</b> {a.get('performer', 'Unknown')}\n"
                                f"📦 <b>Size:</b> {format_size(a['file_size'])}\n"
                                f"⏱ <b>Duration:</b> {format_duration(a.get('duration', 0))}"
                            )
                        
                        info_msg = (
                            f"{icon} <b>{type_name} INFO</b>\n\n"
                            f"{details}"
                        )
                        send_reply(chat_id, info_msg)

                # গ) Text Tools
                elif state and text:
                    if state == "qr":
                        img = qrcode.make(text)
                        bio = io.BytesIO()
                        img.save(bio, 'PNG')
                        bio.seek(0)
                        send_file(chat_id, bio, "photo", caption="✅ QR Code")
                    elif state == "shorten":
                        try: res = requests.get(f"http://tinyurl.com/api-create.php?url={text}").text
                        except: res = "Error"
                        send_reply(chat_id, f"🔗 Link: {res}")
                    elif state == "tts":
                        try:
                            tts = gTTS(text, lang='en')
                            bio = io.BytesIO()
                            tts.write_to_fp(bio)
                            bio.seek(0)
                            send_file(chat_id, bio, "audio", caption="🗣 Voice")
                        except: send_reply(chat_id, "Error")
                    elif state == "text2pdf":
                        pdf = FPDF()
                        pdf.add_page()
                        pdf.set_font("Arial", size=12)
                        pdf.multi_cell(0, 10, text.encode('latin-1', 'replace').decode('latin-1'))
                        bio = io.BytesIO()
                        bio.write(pdf.output(dest='S').encode('latin-1'))
                        bio.seek(0)
                        send_file(chat_id, bio, "document", filename="text_doc")
                    elif state == "b64_enc": send_reply(chat_id, base64.b64encode(text.encode()).decode())
                    elif state == "b64_dec": 
                        try: send_reply(chat_id, base64.b64decode(text).decode())
                        except: send_reply(chat_id, "Error")
                    elif state == "hash": send_reply(chat_id, hashlib.md5(text.encode()).hexdigest())
                    elif state == "upper": send_reply(chat_id, text.upper())

        return "ok", 200

    except Exception as e:
        print(f"Error: {e}")
        return "error", 200
