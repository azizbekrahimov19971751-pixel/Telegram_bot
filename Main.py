import logging
import os
import re
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from google import genai
from google.genai import types
import telebot
import telebot.apihelper
from flask import Flask

# ── Flask & Health server ─────────────────────────────────────

app = Flask("")


@app.route("/")
def home():
  return "Bot ishlayapti!"


def run_flask():
  port = int(os.environ.get("PORT", 8080))
  app.run(host="0.0.0.0", port=port)


class _HealthHandler(BaseHTTPRequestHandler):

  def do_GET(self):
    self.send_response(200)
    self.end_headers()
    self.wfile.write(b"Bot ishlayapti!")

  def log_message(self, *args):
    pass


def _keep_alive_loop():
  import urllib.request
  dev_domain = os.environ.get("REPLIT_DEV_DOMAIN", "")
  external_url = f"https://{dev_domain}/api/healthz" if dev_domain else None
  time.sleep(30)
  while True:
    try:
      if external_url:
        urllib.request.urlopen(external_url, timeout=15)
        logger.info("Keep-alive (tashqi) ping yuborildi: %s", external_url)
      else:
        urllib.request.urlopen(f"http://localhost:{PORT}/", timeout=10)
        logger.info("Keep-alive (ichki) ping yuborildi")
    except Exception as e:
      logger.warning("Keep-alive xato: %s", e)
    time.sleep(240)


# ── Bot sozlamalari ───────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
if not TOKEN:
  raise RuntimeError("TELEGRAM_BOT_TOKEN environment variable is not set")

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if not GEMINI_API_KEY:
  raise RuntimeError("GEMINI_API_KEY environment variable is not set")

PORT = int(os.environ.get("PORT", 8080))

gemini_client = genai.Client(api_key=GEMINI_API_KEY)
bot = telebot.TeleBot(TOKEN, parse_mode=None, threaded=True)

BOT_USERNAME = None

MY_NAMES = [
    "abdulaziz",
    "muhidin tabib",
    "muhiddin tabib",
    "muhidin",
    "muhiddin",
    "tabib",
    "rahiymov",
    "bim",
    "@azizbekrahimov1",
]

NAME_PATTERN = re.compile(
    r"(?<![a-zA-Z0-9])("
    + "|".join(re.escape(n) for n in sorted(MY_NAMES, key=len, reverse=True))
    + r")(?![a-zA-Z0-9])",
    re.IGNORECASE,
)

SALOM_PATTERN = re.compile(
    r"(?<![a-zA-Z0-9'`'])("
    r"assalomu\s*alaykum|assalomu\s*aleykum|"
    r"assalomalaykum|assalomaleykum|"
    r"salomu\s*alaykum|salomu\s*aleykum|"
    r"vassalom|"
    r"assalom\w*|"
    r"salom\w*|"
    r"salam\w*|"
    r"salomatmisiz|salomatmisizlar"
    r")(?![a-zA-Z0-9'`'])",
    re.IGNORECASE,
)

NARXI_PATTERN = re.compile(
    r"(?<![a-zA-Z0-9'`'])("
    r"narx\w*|"
    r"baho\w*|"
    r"qiymat\w*|"
    r"qimmat\w*|"
    r"necha\s*pul|"
    r"necha\s*so'?m|necha\s*som|"
    r"qancha\s*turadi|qancha\s*turibdi|qancha\s*turyapti|"
    r"qancha\s*pul|qancha\s*so'?m|qancha\s*som|"
    r"qancha\?|qancha$|"
    r"price"
    r")(?![a-zA-Z0-9'`'])",
    re.IGNORECASE,
)

GURUH_USLUBI = (
    "Sen 'Mening yordamchim' botsan. Sen o'zbek yigitlari guruhida yashaysan. "
    "Shu guruh uslubida gaplash — qisqa, do'stona, ba'zan hazilkash.\n\n"
    "Guruh so'zlari va uslubi:\n"
    "- 'bolla', 'oshna', 'dos' — do'stga murojaat\n"
    "- 'davay', 'go go go' — rag'batlantirish\n"
    "- 'kontr' — Counter Strike o'yini\n"
    "- 'za' — 'man za' = men ham\n"
    "- 'kettumi', 'qaydasila' — qayerdasizlar\n"
    "- 'tuzumisan' — yaxshimisan\n"
    "- 'zor' — ajoyib, yaxshi\n"
    "Javoblar QISQA bo'lsin — 1-2 so'z yoki 1 gap. Ba'zan emoji ishlat."
)

GEMINI_MODELS = ["gemini-2.5-flash", "gemini-1.5-flash", "gemini-2.5-pro"]

HELP_TEXT = (
    "Salom oshna! Men guruh-yordamchiman.\n\n"
    "Imkoniyatlarim:\n\n"
    "1) Salomlashish (guruhda) — 'Vaalaykum assalom!'\n\n"
    "2) Narx so'raganida (guruhda) — 'Tez orada javob beramiz'\n\n"
    "3) Abdulazizni tilga olsang — u band ekanini aytaman\n"
    "   (abdulaziz, muhidin, tabib, rahiymov, bim ...)\n\n"
    "4) Guruhda menga @mention yoki reply qil — do'stona javob beraman\n\n"
    "5) Shaxsiy chatda — har qanday savol yoz, javob beraman\n\n"
    "6) Aniq qidiruv: /qidir dollar kursi qancha?\n\n"
    "Komandalar:\n"
    "/start  — ishga tushirish\n"
    "/help   — yordam\n"
    "/qidir <savol> — aniq ma'lumot olish"
)


def _call_gemini(contents: str, system_instruction: str | None = None) -> str:
  search_tool = types.Tool(google_search=types.GoogleSearch())
  config_kwargs: dict = {"tools": [search_tool]}
  if system_instruction:
    config_kwargs["system_instruction"] = system_instruction
  config = types.GenerateContentConfig(**config_kwargs)

  last_error = None
  for model in GEMINI_MODELS:
    try:
      response = gemini_client.models.generate_content(
          model=model,
          contents=contents,
          config=config,
      )
      return response.text
    except Exception as e:
      last_error = e
      logger.warning("Model %s xato: %s — keyingisini sinaydi...", model, e)
      time.sleep(1)
  raise last_error


def safe_reply(message, text: str):
  try:
    return bot.reply_to(message, text)
  except Exception as e:
    logger.warning("safe_reply xato: %s", e)
    return None


def safe_edit(chat_id, message_id, text: str):
  try:
    bot.edit_message_text(text, chat_id=chat_id, message_id=message_id)
  except Exception as e:
    logger.warning("safe_edit xato: %s", e)


def safe_delete(chat_id, message_id):
  try:
    bot.delete_message(chat_id=chat_id, message_id=message_id)
  except Exception:
    pass


def gemini_answer(message, query: str):
  query = query.strip()
  if not query:
    return
  wait_msg = safe_reply(message, "Qidirilmoqda...")
  try:
    text = _call_gemini(
        contents=f"Quyidagi savolga qisqa va aniq javob ber (o'zbek tilida): {query}"
    )
    if wait_msg:
      safe_edit(message.chat.id, wait_msg.message_id, text)
    else:
      safe_reply(message, text)
  except Exception as e:
    logger.error("Gemini xatoligi: %s", e)
    if wait_msg:
      safe_edit(
          message.chat.id,
          wait_msg.message_id,
          "Hozir AI serveri band. Bir necha soniyadan so'ng qayta urinib"
          " ko'ring.",
      )


def gemini_chat(message, query: str):
  query = query.strip()
  if not query:
    return
  wait_msg = safe_reply(message, "...")
  try:
    text = _call_gemini(contents=query, system_instruction=GURUH_USLUBI)
    if wait_msg:
      safe_edit(message.chat.id, wait_msg.message_id, text)
    else:
      safe_reply(message, text)
  except Exception as e:
    logger.error("Gemini xatoligi: %s", e)
    if wait_msg:
      safe_delete(message.chat.id, wait_msg.message_id)


def is_bot_mentioned(message) -> bool:
  if not BOT_USERNAME:
    return False
  if message.reply_to_message:
    ru = message.reply_to_message.from_user
    if ru and ru.username and ru.username.lower() == BOT_USERNAME.lower():
      return True
  if message.entities:
    for entity in message.entities:
      if entity.type == "mention":
        mention = message.text[entity.offset : entity.offset + entity.length]
        if mention.lower() == f"@{BOT_USERNAME.lower()}":
          return True
  return False


def strip_bot_mention(text: str) -> str:
  if BOT_USERNAME:
    text = re.sub(
        re.escape(f"@{BOT_USERNAME}"), "", text, flags=re.IGNORECASE
    ).strip()
  return text


@bot.message_handler(commands=["start", "help"])
def handle_help(message):
  safe_reply(message, HELP_TEXT)


@bot.message_handler(commands=["qidir"])
def handle_qidir_command(message):
  parts = message.text.split(maxsplit=1)
  query = parts[1] if len(parts) > 1 else ""
  if not query.strip():
    safe_reply(message, "Savol kiriting. Misol: /qidir dollar kursi qancha?")
    return
  gemini_answer(message, query)


@bot.message_handler(func=lambda m: m.text is not None)
def handle_all_messages(message):
  try:
    text = message.text or ""
    chat_type = message.chat.type

    if text.lower().startswith("qidir:"):
      gemini_answer(message, text[6:])
      return

    if NAME_PATTERN.search(text):
      safe_reply(
          message,
          "Abdulaziz hozir band oshna 😊 Gaping bo'lsa menga ayt!",
      )
      return

    if chat_type in ("group", "supergroup"):
      if SALOM_PATTERN.search(text):
        safe_reply(message, "Vaalaykum assalom!")
        return
      if NARXI_PATTERN.search(text):
        safe_reply(message, "Tez orada javob beramiz")
        return
      if is_bot_mentioned(message):
        gemini_chat(message, strip_bot_mention(text))
      return

    if chat_type == "private":
      gemini_chat(message, text)
  except Exception as e:
    logger.error("handle_all_messages xato: %s", e)


# ── Entry point ───────────────────────────────────────────────

def main():
  global BOT_USERNAME

  # Flask server
  flask_thread = threading.Thread(target=run_flask, daemon=True)
  flask_thread.start()



  # Keep-alive
  ka = threading.Thread(target=_keep_alive_loop, daemon=True)
  ka.start()

  me = bot.get_me()
  BOT_USERNAME = me.username
  logger.info("Bot username: @%s", BOT_USERNAME)

  time.sleep(3)
  try:
    bot.remove_webhook()
  except Exception as e:
    logger.warning("remove_webhook: %s", e)

  logger.info("Polling boshlandi — 24/7 rejim...")
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
      logger.error("Polling xato, 10 soniyadan keyin qayta urinadi: %s", e)
      time.sleep(10)


if __name__ == "__main__":
  main()
