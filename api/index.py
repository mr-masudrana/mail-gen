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

# --- ১. মেনু বাটন (Updated) ---
def get_main_menu():
    return json.dumps({
        "keyboard": [
            [{"text": "📧 Temp Mail"}, {"text": "🛠 Generator Tool"}],
            [{"text": "📂 PDF Tool"}, {"text": "🗣 Voice Tool"}],
            [{"text": "🖼 Image Tool"}, {"text": "📝 Text Tool"}],
            [{"text": "🆔 Telegram Info"}, {"text": "ℹ️ File Info"}]
        ],
        "resize_keyboard": True,
        "one_time_keyboard": False
    })

# সাব-মেনু ফাংশনগুলো (সংক্ষেপে)
def get_gen_menu(): return json.dumps({"keyboard": [[{"text": "🟦 QR Code"}, {"text": "🔑 Password Gen"}], [{"text": "🔗 Link Shortener"}, {"text": "🔙 Back"}]], "resize_keyboard": True})
def get_pdf_menu(): return json.dumps({"keyboard": [[{"text": "🖼 Img to PDF"}, {"text": "📄 Text to PDF"}], [{"text": "🔙 Back"}]], "resize_keyboard": True})
def get_voice_menu(): return json.dumps({"keyboard": [[{"text": "🗣 Text to Voice"}, {"text": "🔙 Back"}]], "resize_keyboard": True})
def get_image_menu(): return json.dumps({"keyboard": [[{"text": "⚫ Grayscale"}, {"text": "📐 Resize (50%)"}], [{"text": "🔙 Back"}]], "resize_keyboard": True})
def get_text_menu(): return json.dumps({"keyboard": [[{"text": "🔐 Base64 Enc"}, {"text": "🔓 Base64 Dec"}], [{"text": "#️⃣ MD5 Hash"}, {"text": "🔠 Uppercase"}], [{"text": "🔙 Back"}]], "resize_keyboard": True})

# --- ২. হেল্পার ফাংশন (Tools) ---
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

# --- ৩. Temp Mail ফাংশন (Mail.tm) ---
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
def home(): return "All-in-One Bot (Tools + TempMail) Running! 🚀"

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        data = request.get_json(force=True)
        
        # --- CALLBACK QUERY (Temp Mail Button Click) ---
        if "callback_query" in data:
            call = data["callback_query"]
            chat_id = call["message"]["chat"]["id"]
            data_text = call["data"]
            parts = data_text.split("|")
            action, address, password = parts[0], parts[1], parts[2]
            
            token = get_mail_token(address, password)
            if not token:
                requests.post(f"{BASE_URL}/answerCallbackQuery", json={"callback_query_id": call["id"], "text": "❌ মেয়াদ শেষ। নতুন মেইল নিন।", "show_alert": True})
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

            # --- ১. মেনু নেভিগেশন ---
            if text == "/start" or text == "🔙 Back":
                user_states[chat_id] = None
                send_reply(chat_id, "👋 <b>Main Menu</b>\nনিচ থেকে একটি টুল সিলেক্ট করুন:", get_main_menu())

            # --- Temp Mail Button ---
            elif text == "📧 Temp Mail":
                addr, pwd = create_mail_account()
                if addr:
                    res = f"✅ <b>Temp Mail Generated!</b>\n\n📧 <code>{addr}</code>\n\n(ইনবক্স চেক করতে নিচের বাটনে চাপুন)"
                    kb = {"inline_keyboard": [[{"text": "📩 Check Inbox", "callback_data": f"check|{addr}|{pwd}"}]]}
                    send_reply(chat_id, res, kb)
                else: send_reply(chat_id, "⚠️ মেইল সার্ভার এরর।")

            # --- অন্যান্য টুল মেনু ---
            elif text == "🛠 Generator Tool": send_reply(chat_id, "🛠 Tools:", get_gen_menu())
            elif text == "📂 PDF Tool": send_reply(chat_id, "📂 Tools:", get_pdf_menu())
            elif text == "🗣 Voice Tool": send_reply(chat_id, "🗣 Tools:", get_voice_menu())
            elif text == "🖼 Image Tool": send_reply(chat_id, "🖼 Tools:", get_image_menu())
            elif text == "📝 Text Tool": send_reply(chat_id, "📝 Tools:", get_text_menu())
            
            # --- Info Buttons ---
            elif text == "🆔 Telegram Info":
                user_states[chat_id] = "tg_info"
                send_reply(chat_id, "ℹ️ <b>Telegram Info Mode</b>\n\n🔹 অন্য কারো মেসেজ <b>Forward</b> করুন তার আইডি জানতে।\n🔹 অথবা যেকোনো মেসেজ লিখুন নিজের ইনফো জানতে।")
            elif text == "ℹ️ File Info":
                user_states[chat_id] = "file_info"
                send_reply(chat_id, "ℹ️ <b>File Info Mode</b>\n\n📂 যেকোনো ফাইল, ছবি বা ভিডিও পাঠান। আমি সেটার বিস্তারিত সাইজ ও টাইপ বলে দেব।")

            # --- ২. টুল অ্যাক্টিভেশন (States) ---
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
            # (অন্যান্য টুল স্টেট আগের মতোই...)
            
            # --- ৩. ইনপুট হ্যান্ডলিং ---
            else:
                # ক) Forwarded Message (Auto Telegram Info)
                if "forward_date" in msg:
                    chat = msg.get("forward_from_chat")
                    user = msg.get("forward_from")
                    if chat:
                        info = f"📢 <b>CHANNEL SOURCE</b>\nTitle: {chat.get('title')}\nID: <code>{chat.get('id')}</code>\nUser: @{chat.get('username','None')}"
                    elif user:
                        info = f"👤 <b>USER SOURCE</b>\nName: {user.get('first_name')}\nID: <code>{user.get('id')}</code>\nUser: @{user.get('username','None')}"
                    else:
                        info = f"🔒 <b>HIDDEN SOURCE</b>\nName: {msg.get('forward_sender_name')}"
                    send_reply(chat_id, info)

                # খ) File Handling (Auto File Info)
                elif (msg.get("photo") or msg.get("document") or msg.get("video")):
                    # যদি নির্দিষ্ট টুল সিলেক্ট করা থাকে (যেমন Img2PDF)
                    if state == "img2pdf" and "photo" in msg:
                         # Img2PDF Logic
                         file_id = msg["photo"][-1]["file_id"]
                         img_bytes = get_file_content(file_id)
                         img = Image.open(io.BytesIO(img_bytes)).convert('RGB')
                         bio = io.BytesIO()
                         img.save(bio, 'PDF')
                         bio.seek(0)
                         send_file(chat_id, bio, "document", caption="✅ Image to PDF", filename="converted")
                    
                    # যদি কোনো স্টেট না থাকে অথবা 'file_info' মোডে থাকে -> Auto File Info
                    else:
                        f_type = "Unknown"
                        f_size = 0
                        if "document" in msg:
                            f_type = f"📄 Document ({msg['document'].get('mime_type')})"
                            f_size = msg['document']['file_size']
                        elif "photo" in msg:
                            p = msg['photo'][-1]
                            f_type = f"🖼 Photo ({p['width']}x{p['height']})"
                            f_size = p['file_size']
                        elif "video" in msg:
                            f_type = "🎥 Video"
                            f_size = msg['video']['file_size']
                        
                        send_reply(chat_id, f"📂 <b>FILE INFO (Auto)</b>\n\nType: {f_type}\nSize: {round(f_size/1024/1024, 2)} MB")

                # গ) Text Tools Processing
                elif state and text:
                    if state == "qr":
                        img = qrcode.make(text)
                        bio = io.BytesIO()
                        img.save(bio, 'PNG')
                        bio.seek(0)
                        send_file(chat_id, bio, "photo", caption="✅ QR Code")
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
                    # (অন্যান্য টেক্সট টুল লজিক...)

        return "ok", 200

    except Exception as e:
        print(f"Error: {e}")
        return "error", 200
        
