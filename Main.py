import os
import re
import telebot
import yt_dlp
from flask import Flask
import threading

# Flask (Render uchun)
app = Flask("")
@app.route("/")
def home(): return "Bot ishlayapti!"
threading.Thread(target=lambda: app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080))), daemon=True).start()

# Bot sozlamalari
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
bot = telebot.TeleBot(TOKEN)

# Video yuklovchi funksiya
def download_video(url, message):
    try:
        bot.reply_to(message, "Yuklanmoqda...")
        ydl_opts = {'format': 'best', 'outtmpl': 'video.mp4'}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        with open('video.mp4', 'rb') as video:
            bot.send_video(message.chat.id, video)
        os.remove('video.mp4')
    except Exception as e:
        bot.reply_to(message, f"Xatolik: {e}")

# Xabarlarni qabul qilish
@bot.message_handler(func=lambda m: True)
def handle_all(message):
    text = message.text or ""
    url_match = re.search(r'https?://[^\s]+', text)
    
    if url_match:
        download_video(url_match.group(0), message)
    # Agar havola bo'lmasa, bot indamaydi

bot.polling(non_stop=True)
