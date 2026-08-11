import os
import re
import telebot
from yt_dlp import YoutubeDL

# Tokeningiz o'z joyiga qo'yildi
TOKEN = "7909385317:AAF70hK0T7724:AA6w0V8bB07724:AAG"
bot = telebot.TeleBot(TOKEN)


@bot.message_handler(content_types=['text'])
def handle_link(message):
  text = message.text

  # 1. Agar xabarda matn bo'lmasa yoki "http" bo'lmasa, darhol to'xtaydi (oddiy gaplarga aralashmaydi)
  if not text or "http" not in text:
    return

  # 2. Matn ichidan aniq havolani qidirib topamiz
  url_match = re.search(r'https?://[^\s]+', text)
  if not url_match:
    return

  url = url_match.group(0)

  # 3. Videoni yuklab olish va yuborish jarayoni
  try:
    sent_msg = bot.reply_to(message, "⏳ Video yuklanmoqda, biroz kuting...")

    # Fayl nomi to'qnashib ketmasligi uchun oldingisini o'chirib tashlaymiz
    if os.path.exists('video.mp4'):
      os.remove('video.mp4')

    ydl_opts = {
        'format': 'best',
        'outtmpl': 'video.mp4',
        'max_filesize': 50 * 1024 * 1024,  # 50MB gacha cheklov
    }

    with YoutubeDL(ydl_opts) as ydl:
      ydl.download([url])

    # Videoni yuborish
    with open('video.mp4', 'rb') as video:
      bot.send_video(message.chat.id, video, reply_to_message_id=message.message_id)

    # Yuklanmoqda xabarini o'chirib tashlaymiz
    bot.delete_message(message.chat.id, sent_msg.message_id)

  except Exception as e:
    bot.reply_to(
        message, '❌ Videoni yuklab bo\'lmadi. Havolani qayta tekshiring.'
    )


# Botni uzluksiz ishga tushirib turish
if __name__ == '__main__':
  bot.infinity_polling()
