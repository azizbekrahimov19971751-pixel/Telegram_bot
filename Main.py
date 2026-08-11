    import logging
import os
import re
import threading
import time
from flask import Flask
import telebot
import yt_dlp

# Logging sozlamasi
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Token va Portni olish
TOKEN = os.getenv("BOT_TOKEN")
PORT = int(os.getenv("PORT", 8080))

if not TOKEN:
  raise ValueError("BOT_TOKEN topilmadi! Environment variables ni tekshiring.")

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)


@app.route("/")
def index():
  return "Bot ishlayapti!"


def run_flask():
  app.run(host="0.0.0.0", port=PORT)


def _keep_alive_loop():
  while True:
    time.sleep(300)


# Faqat havola kelganda ishlaydigan funksiya
@bot.message_handler(content_types=["text"])
def handle_link(message):
  text = message.text

  # Matn ichidan havolani qidirib topamiz
  url_match = re.search(r"https?://[^\s]+", text)

  # AGAR HAVOLA BO'LMASA, BOT JAVOB BERMAYDI (JIM TURADI)
  if not url_match:
    return

  url = url_match.group(0)

  # Foydalanuvchiga jarayon boshlanganini bildirish
  sent_msg = bot.reply_to(message, "⏳ Video yuklanmoqda, biroz kuting...")

  try:
    # yt-dlp yordamida video yuklab olish sozlamalari
    ydl_opts = {
        "outtmpl": "video.mp4",
        "format": "best",
        "max_filesize": 50 * 1024 * 1024,  # 50MB gacha
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
      ydl.download([url])

    # Videoni Telegramga yuborish
    with open("video.mp4", "rb") as vid:
      bot.send_video(message.chat.id, vid, reply_to_message_id=message.message_id)

    # Yuklab bo'lingach vaqtinchalik xabarni o'chirish
    bot.delete_message(message.chat.id, sent_msg.message_id)

    # Yuklangan faylni o'chirib tashlash (server to'lib qolmasligi uchun)
    if os.path.exists("video.mp4"):
      os.remove("video.mp4")

  except Exception as e:
    logger.error("Video yuklashda xatolik: %s", e)
    bot.edit_message_text(
        "❌ Videoni yuklab bo'lmadi. Havolani qayta tekshiring.",
        message.chat.id,
        sent_msg.message_id,
    )
    if os.path.exists("video.mp4"):
      os.remove("video.mp4")


def main():
  # Flask serverini ishga tushiramiz
  flask_thread = threading.Thread(target=run_flask, daemon=True)
  flask_thread.start()
  logger.info("Flask server port %d da ishga tushdi", PORT)

  ka = threading.Thread(target=_keep_alive_loop, daemon=True)
  ka.start()

  try:
    bot.remove_webhook()
  except Exception as e:
    logger.warning("remove_webhook: %s", e)

  logger.info("Bot polling rejibida ishga tushdi...")
  while True:
    try:
      bot.polling(
          non_stop=True,
          timeout=30,
          long_polling_timeout=30,
          allowed_updates=["message"],
          interval=5,
      )
    except Exception as e:
      logger.error("Polling xatosi, 10 soniyadan keyin qayta urinadi: %s", e)
      time.sleep(10)


if __name__ == "__main__":
  main()
