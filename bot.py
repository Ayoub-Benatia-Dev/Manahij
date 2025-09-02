import logging
import json
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

# === إعداد اللوج
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# === مفتاح API و URL Gemini
API_KEY = "AIzaSyB0shigVYV5Yl8XjL49AcwnuTMl94mMoQM"
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"

# === دالة لاستدعاء Gemini
def call_gemini(prompt_text):
    headers = {
        "Content-Type": "application/json",
        "X-goog-api-key": API_KEY
    }
    payload = {
        "contents": [
            {"parts": [{"text": prompt_text}]}
        ]
    }
    try:
        response = requests.post(GEMINI_URL, headers=headers, data=json.dumps(payload))
        response.raise_for_status()
        data = response.json()
        # نرجع النص من أول candidate
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        logger.error(f"Gemini API call failed: {e}")
        return "عذراً، لم أتمكن من الحصول على إجابة الآن."

# === أوامر تيليجرام
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("مرحباً! أرسل لي أي سؤال وسأجيبك باستخدام Gemini AI.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    logger.info(f"Received: {user_text}")
    reply = call_gemini(user_text)
    await update.message.reply_text(reply)

# === تشغيل البوت
if __name__ == "__main__":
    TELEGRAM_TOKEN = "PUT_YOUR_TELEGRAM_BOT_TOKEN_HERE"

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Bot is running...")
    app.run_polling()
