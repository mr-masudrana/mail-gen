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

# --- ১. মেনু বাটন (আপডেট করা হয়েছে - ইনফো বাটন রিমুভড) ---
def get_main_menu():
    return json.dumps({
        "keyboard": [
            [{"text": "📧 Temp Mail"}, {"text": "🛠 Generator Tool"}],
            [{"text": "📂 PDF Tool"}, {"text": "🗣 Voice Tool"}],
            [{"text": "🖼 Image Tool"}, {"text": "📝 Text Tool"}]
            # Telegram Info এবং File Info বাটন সরিয়ে দেওয়া হয়েছে
        ],
        "resize_keyboard": True,
        "one_time_keyboard": False
    })

# সাব-মেনু
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

# সাইজ ফরম্যাট করা (KB/MB)
def format_size(size):
    if size < 1024: return f"{size} B"
    elif size < 1024*1024: return f"{round(size/1024, 2)} KB"
    else: return f"{round(size/(1024*1024), 2)} MB"

# --- ৩. Temp Mail ফাংশন ---
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
def home(): return "All-in-One Bot (Pro Info) Running! 🚀"

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        data = request.get_json(force=True)
        
        # --- CALLBACK QUERY (Temp Mail) ---
        if "callback_query" in data:
            call = data["callback_query"]
            chat_id = call["message"]["chat"]["id"]
            data_text = call["data"]
            parts = data_text.split("|")
            
            if len(parts) >= 3:
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
            user = msg.get("from", {})
            
            state = user_states.get(chat_id, None)

            # --- ১. START COMMAND (YOUR PROFILE) ---
            if text == "/start" or text == "🔙 Back":
                user_states[chat_id] = None
                
                # নামের লজিক
                full_name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip()
                username = f"@{user.get('username')}" if user.get("username") else "N/A"
                
                profile_msg = (
                    f"👋 হ্যালো <b>{user.get('first_name')}</b>!\n\n"
                    "আমি একটি অ্যাডভান্সড ইনফো বট।\n"
                    "আমার কাজ হলো যেকোনো চ্যাট, ইউজার বা চ্যানেলের গোপন তথ্য বের করা।\n\n"
                    "👤 <b>YOUR PROFILE:</b>\n\n"
                    f"🆔 <b>ID:</b> <code>{user.get('id')}</code>\n"
                    f"📛 <b>Name:</b> {full_name}\n"
                    f"🔗 <b>Username:</b> {username}"
                )
                send_reply(chat_id, profile_msg, get_main_menu())

            # --- Temp Mail ---
            elif text == "📧 Temp Mail":
                addr, pwd = create_mail_account()
                if addr:
                    res = f"✅ <b>Temp Mail Generated!</b>\n\n📧 <code>{addr}</code>\n\n(ইনবক্স চেক করতে নিচের বাটনে চাপুন)"
                    kb = {"inline_keyboard": [[{"text": "📩 Check Inbox", "callback_data": f"check|{addr}|{pwd}"}]]}
                    send_reply(chat_id, res, kb)
                else: send_reply(chat_id, "⚠️ মেইল সার্ভার এরর।")

            # --- টুলস মেনু ---
            elif text == "🛠 Generator Tool": send_reply(chat_id, "🛠 Tools:", get_gen_menu())
            elif text == "📂 PDF Tool": send_reply(chat_id, "📂 Tools:", get_pdf_menu())
            elif text == "🗣 Voice Tool": send_reply(chat_id, "🗣 Tools:", get_voice_menu())
            elif text == "🖼 Image Tool": send_reply(chat_id, "🖼 Tools:", get_image_menu())
            elif text == "📝 Text Tool": send_reply(chat_id, "📝 Tools:", get_text_menu())

            # --- টুল অ্যাক্টিভেশন ---
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

            # --- ৩. মেইন লজিক (Info & Tools) ---
            else:
                # ক) Forwarded Info Logic (Auto Detect)
                if "forward_date" in msg:
                    chat = msg.get("forward_from_chat")
                    f_user = msg.get("forward_from")
                    
                    if chat: # Channel
                        info = (
                            "📢 <b>CHANNEL SOURCE</b>\n\n"
                            f"🆔 <b>ID:</b> <code>{chat.get('id')}</code>\n"
                            f"📛 <b>Name:</b> {chat.get('title')}\n"
                            f"🔗 <b>Username:</b> @{chat.get('username','None')}"
                        )
                    elif f_user: # User or Bot
                        full_name = f"{f_user.get('first_name','')} {f_user.get('last_name','')}".strip()
                        u_name = f"@{f_user.get('username')}" if f_user.get("username") else "None"
                        header = "🤖 <b>BOT SOURCE</b>" if f_user.get("is_bot") else "👤 <b>USER SOURCE</b>"
                        
                        info = (
                            f"{header}\n\n"
                            f"🆔 <b>ID:</b> <code>{f_user.get('id')}</code>\n"
                            f"📛 <b>Name:</b> {full_name}\n"
                            f"🔗 <b>Username:</b> {u_name}"
                        )
                    else: # Hidden User
                        info = (
                            "🔒 <b>HIDDEN SOURCE</b>\n\n"
                            f"📛 <b>Name:</b> {msg.get('forward_sender_name')}\n"
                            "⚠️ ID Hidden"
                        )
                    send_reply(chat_id, info)

                # খ) File Info Logic (Auto Detect)
                elif (msg.get("photo") or msg.get("document") or msg.get("video") or msg.get("audio")):
                    
                    # যদি নির্দিষ্ট টুল (Img2PDF) সিলেক্ট করা থাকে
                    if state == "img2pdf" and "photo" in msg:
                         file_id = msg["photo"][-1]["file_id"]
                         img_bytes = get_file_content(file_id)
                         img = Image.open(io.BytesIO(img_bytes)).convert('RGB')
                         bio = io.BytesIO()
                         img.save(bio, 'PDF')
                         bio.seek(0)
                         send_file(chat_id, bio, "document", caption="✅ Image to PDF", filename="converted")

                    # যদি টুল সিলেক্ট না থাকে -> Show File Info
                    else:
                        f_type = "Unknown"
                        f_size = 0
                        details = ""
                        
                        if "photo" in msg:
                            p = msg['photo'][-1]
                            f_type = "🖼 Photo"
                            f_size = p['file_size']
                            details = f"Resolution: {p['width']}x{p['height']}"
                        
                        elif "video" in msg:
                            v = msg['video']
                            f_type = "🎥 Video"
                            f_size = v['file_size']
                            details = f"Duration: {v['duration']}s | Res: {v['width']}x{v['height']}"
                            
                        elif "audio" in msg:
                            a = msg['audio']
                            f_type = "🎵 Audio"
                            f_size = a['file_size']
                            details = f"Duration: {a['duration']}s"
                            
                        elif "document" in msg:
                            d = msg['document']
                            f_type = f"📄 {d.get('mime_type').split('/')[-1].upper()}"
                            f_size = d['file_size']
                            details = f"Name: {d.get('file_name', 'file')}"

                        info = (
                            "📂 <b>FILE INFO</b>\n\n"
                            f"Type: {f_type}\n"
                            f"Size: {format_size(f_size)}\n"
                            f"{details}"
                        )
                        send_reply(chat_id, info)

                # গ) Text Tools Processing
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
                    # (Other text tools...)
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
