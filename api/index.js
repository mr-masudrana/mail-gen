from flask import Flask, request, redirect
import os
import requests
import io # মেমোরিতে ফাইল বানানোর জন্য

app = Flask(__name__)

BOT_TOKEN = os.environ.get('BOT_TOKEN')
BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

# --- অটোমেটিক ইউজারনেম (রিডাইরেক্টের জন্য) ---
BOT_USERNAME = None
def get_bot_username():
    global BOT_USERNAME
    if BOT_USERNAME: return BOT_USERNAME
    try:
        response = requests.get(f"{BASE_URL}/getMe")
        data = response.json()
        if data["ok"]:
            BOT_USERNAME = data["result"]["username"]
            return BOT_USERNAME
    except: pass
    return "Telegram"

# --- 1. Dot Trick Generator (Logic) ---
def generate_dot_aliases(email):
    username, domain = email.split('@')
    if domain != 'gmail.com': return None
    
    emails = set()
    username_length = len(username)
    
    # বাইনারি লজিক ব্যবহার করে ডট কম্বিনেশন তৈরি
    # (খুব বড় ইউজারনেম হলে Vercel এ টাইমআউট হতে পারে, তাই লিমিট ১০২৪ রাখা হলো)
    limit = 2**(username_length - 1)
    if limit > 2000: limit = 2000 # সেফটি লিমিট
    
    for i in range(limit):
        new_user = ""
        for j in range(username_length):
            new_user += username[j]
            # বিট চেক করে ডট বসানো
            if (i >> j) & 1:
                new_user += "."
        
        # শেষের ডট বা ডাবল ডট ক্লিন করা
        clean_user = new_user.strip('.')
        emails.add(f"{clean_user}@{domain}")
    
    return list(emails)

# --- 2. Plus Trick Generator (Logic) ---
def generate_plus_aliases(email, count=100):
    username, domain = email.split('@')
    emails = []
    for i in range(1, int(count) + 1):
        emails.append(f"{username}+id{i}@{domain}")
    return emails

# --- মেসেজ বা ফাইল পাঠানোর ফাংশন ---
def send_message(chat_id, text):
    requests.post(f"{BASE_URL}/sendMessage", json={
        "chat_id": chat_id, "text": text, "parse_mode": "HTML"
    })

def send_file(chat_id, file_content, filename, caption):
    # মেমোরিতে ফাইল তৈরি (সার্ভারে সেভ না করে)
    file_obj = io.BytesIO(file_content.encode('utf-8'))
    file_obj.name = filename
    
    url = f"{BASE_URL}/sendDocument"
    data = {"chat_id": chat_id, "caption": caption}
    files = {"document": file_obj}
    
    try:
        requests.post(url, data=data, files=files)
    except Exception as e:
        print(e)

# --- routes ---
@app.route('/')
def home():
    return redirect(f"https://t.me/{get_bot_username()}")

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        data = request.get_json(force=True)
        if "message" in data:
            msg = data["message"]
            chat_id = msg["chat"]["id"]
            text = msg.get("text", "").strip()

            # --- START COMMAND ---
            if text == "/start":
                welcome = (
                    "👋 <b>Gmail Generator Bot-এ স্বাগতম!</b>\n\n"
                    "আমি আপনার একটি জিমেইল থেকে হাজার হাজার ভেলিড জিমেইল বানিয়ে দিতে পারি।\n\n"
                    "⚙️ <b>কমান্ডসমূহ:</b>\n"
                    "১. <b>Dot Trick:</b> <code>/dot yourname@gmail.com</code>\n"
                    "২. <b>Plus Trick:</b> <code>/plus yourname@gmail.com</code>\n\n"
                    "ℹ️ <i>এই জিমেইলগুলো দিয়ে আপনি যেকোনো সাইটে বারবার অ্যাকাউন্ট খুলতে পারবেন।</i>"
                )
                send_message(chat_id, welcome)

            # --- DOT TRICK ---
            elif text.startswith("/dot"):
                try:
                    email = text.split(" ")[1]
                    if "@gmail.com" not in email:
                        send_message(chat_id, "⚠️ দয়া করে একটি ভেলিড <b>@gmail.com</b> অ্যাড্রেস দিন।")
                    else:
                        send_message(chat_id, "⏳ জেনারেট হচ্ছে... একটু অপেক্ষা করুন।")
                        aliases = generate_dot_aliases(email)
                        
                        if aliases:
                            file_text = "\n".join(aliases)
                            caption = f"✅ <b>{len(aliases)}</b> টি জিমেইল তৈরি হয়েছে!"
                            send_file(chat_id, file_text, "dot_emails.txt", caption)
                        else:
                            send_message(chat_id, "⚠️ এরর হয়েছে। নাম খুব ছোট হলে ডট ট্রিক কাজ করে না।")
                except:
                    send_message(chat_id, "ভুল ফরম্যাট! লিখুন: <code>/dot user@gmail.com</code>")

            # --- PLUS TRICK ---
            elif text.startswith("/plus"):
                try:
                    email = text.split(" ")[1]
                    # ডিফল্ট ১০০টি বানাবে
                    aliases = generate_plus_aliases(email, 100) 
                    
                    file_text = "\n".join(aliases)
                    caption = "✅ <b>১০০টি Plus Alias</b> তৈরি হয়েছে!"
                    send_file(chat_id, file_text, "plus_emails.txt", caption)
                except:
                    send_message(chat_id, "ভুল ফরম্যাট! লিখুন: <code>/plus user@gmail.com</code>")

            else:
                send_message(chat_id, "দয়া করে <b>/start</b> চাপুন নিয়ম জানার জন্য।")

        return "ok", 200
    except:
        return "error", 200
