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
import google.generativeai as genai

app = Flask(__name__)

# --- কনফিগারেশন ---
BOT_TOKEN = os.environ.get('BOT_TOKEN')
BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')

# Gemini সেটআপ
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# ইউজার স্টেট (মেমোরি)
user_states = {}

# --- মেনু বাটন (JSON) ---
def get_main_menu():
    return json.dumps({
        "keyboard": [
            [{"text": "🛠 Generator Tool"}, {"text": "📂 PDF Tool"}],
            [{"text": "🗣 Voice Tool"}, {"text": "🖼 Image Tool"}],
            [{"text": "📝 Text Tool"}, {"text": "ℹ️ File Info"}]
        ],
        "resize_keyboard": True,
        "one_time_keyboard": False
    })

def get_gen_menu():
    return json.dumps({"keyboard": [[{"text": "🟦 QR Code"}, {"text": "🔑 Password Gen"}], [{"text": "🔗 Link Shortener"}, {"text": "🔙 Back"}]], "resize_keyboard": True})

def get_pdf_menu():
    return json.dumps({"keyboard": [[{"text": "🖼 Img to PDF"}, {"text": "📄 Text to PDF"}], [{"text": "🔙 Back"}]], "resize_keyboard": True})

def get_voice_menu():
    return json.dumps({"keyboard": [[{"text": "🗣 Text to Voice"}, {"text": "🔙 Back"}]], "resize_keyboard": True})

def get_image_menu():
    return json.dumps({"keyboard": [[{"text": "⚫ Grayscale"}, {"text": "📐 Resize (50%)"}], [{"text": "🔙 Back"}]], "resize_keyboard": True})

def get_text_menu():
    return json.dumps({"keyboard": [[{"text": "🔐 Base64 Enc"}, {"text": "🔓 Base64 Dec"}], [{"text": "#️⃣ MD5 Hash"}, {"text": "🔠 Uppercase"}], [{"text": "🔙 Back"}]], "resize_keyboard": True})


# --- হেল্পার ফাংশন ---
def send_reply(chat_id, text, reply_markup=None):
    payload = {"chat_id": chat_id, "text": text}
    if reply_markup: payload["reply_markup"] = reply_markup
    try: requests.post(f"{BASE_URL}/sendMessage", json=payload)
    except: pass

def send_file(chat_id, file_data, file_type, caption=None, filename="file"):
    if file_type == "photo":
        files = {'photo': (f"{filename}.jpg", file_data, 'image/jpeg')}
        url = f"{BASE_URL}/sendPhoto"
    elif file_type == "document":
        files = {'document': (f"{filename}.pdf", file_data, 'application/pdf')}
        url = f"{BASE_URL}/sendDocument"
    elif file_type == "audio":
        files = {'audio': (f"{filename}.mp3", file_data, 'audio/mpeg')}
        url = f"{BASE_URL}/sendAudio"
    
    data = {'chat_id': chat_id, 'caption': caption}
    try: requests.post(url, data=data, files=files)
    except: pass

# --- AI রেসপন্স ফাংশন (FIXED MODEL) ---
def get_ai_reply(prompt):
    if not GEMINI_API_KEY:
        return "⚠️ Error: Vercel সেটিংসে GEMINI_API_KEY খুঁজে পাওয়া যায়নি!"

    try:
        # মডেল পরিবর্তন করে 'gemini-pro' করা হয়েছে (এটি সব একাউন্টে কাজ করে)
        model = genai.GenerativeModel('gemini-pro')
        response = model.generate_content(prompt)
        
        if response.text:
            return response.text
        else:
            return "⚠️ AI কোনো উত্তর দিতে পারেনি (Safety Block)।"

    except Exception as e:
        print(f"Gemini Error: {e}")
        return f"⚠️ AI Error: {str(e)}"

# --- মেইন রাউট ---
@app.route('/')
def home():
    return "AI Bot Fixed (Gemini Pro)! 🚀"

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        data = request.get_json(force=True)
        if "message" not in data: return "ok", 200

        msg = data["message"]
        chat_id = msg["chat"]["id"]
        text = msg.get("text", "")
        
        state = user_states.get(chat_id, None)

        # --- ১. মেনু নেভিগেশন ---
        if text == "/start" or text == "🔙 Back":
            user_states[chat_id] = None
            send_reply(chat_id, "👋 <b>Main Menu</b>\nAI চ্যাট করতে কিছু লিখুন অথবা টুল সিলেক্ট করুন:", get_main_menu())

        elif text == "🛠 Generator Tool": send_reply(chat_id, "🛠 Tools:", get_gen_menu())
        elif text == "📂 PDF Tool": send_reply(chat_id, "📂 Tools:", get_pdf_menu())
        elif text == "🗣 Voice Tool": send_reply(chat_id, "🗣 Tools:", get_voice_menu())
        elif text == "🖼 Image Tool": send_reply(chat_id, "🖼 Tools:", get_image_menu())
        elif text == "📝 Text Tool": send_reply(chat_id, "📝 Tools:", get_text_menu())
        elif text == "ℹ️ File Info":
            user_states[chat_id] = "file_info"
            send_reply(chat_id, "ℹ️ ফাইল পাঠান।")

        # --- ২. টুল অ্যাক্টিভেশন ---
        elif text == "🟦 QR Code":
            user_states[chat_id] = "qr"
            send_reply(chat_id, "👉 QR এর জন্য টেক্সট দিন:")
        elif text == "🔗 Link Shortener":
            user_states[chat_id] = "shorten"
            send_reply(chat_id, "👉 লিংক দিন:")
        elif text == "🔑 Password Gen":
            pwd = ''.join(random.choices(string.ascii_letters + string.digits + "!@#", k=12))
            send_reply(chat_id, f"🔑 Pass: {pwd}")
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

        # --- ৩. ইনপুট হ্যান্ডলিং ---
        else:
            if state:
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
                    send_file(chat_id, bio, "document", filename="doc")

                elif state == "b64_enc": send_reply(chat_id, base64.b64encode(text.encode()).decode())
                elif state == "b64_dec": 
                    try: send_reply(chat_id, base64.b64decode(text).decode())
                    except: send_reply(chat_id, "Error")
                elif state == "hash": send_reply(chat_id, hashlib.md5(text.encode()).hexdigest())
                elif state == "upper": send_reply(chat_id, text.upper())

            # খ) ফাইল হ্যান্ডলিং (যদি স্টেট থাকে)
            elif (msg.get("photo") or msg.get("document")) and state:
                 if state == "file_info":
                     send_reply(chat_id, "📂 File Received")
                 elif state == "img2pdf":
                     send_reply(chat_id, "Processing Image...")

            # গ) AI চ্যাট (GEMINI PRO)
            elif text:
                requests.post(f"{BASE_URL}/sendChatAction", json={"chat_id": chat_id, "action": "typing"})
                ai_response = get_ai_reply(text)
                send_reply(chat_id, ai_response)

        return "ok", 200

    except Exception as e:
        print(f"Error: {e}")
        return "error", 200
            
