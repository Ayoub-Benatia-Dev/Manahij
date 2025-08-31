import os
from flask import Flask, request
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from googleapiclient.discovery import build

# --------------------------
TELEGRAM_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"  # لازم تبدلو بتاعك من BotFather
GOOGLE_API_KEY = "AIzaSyDCay69bExFEAt4y7XEiSK1WmG6KB5l-yw"
CX_ID = "YOUR_CUSTOM_SEARCH_ENGINE_ID"  # خاص ب Google Custom Search Engine
YOUTUBE_API_KEY = "AIzaSyBMa4CY_Ndc6RDq2uIDO0nZvhtxvsdF4h4"

# إنشاء تطبيق تيليغرام
app = Application.builder().token(TELEGRAM_TOKEN).build()

# أوامر عادية
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("السلام عليكم 👋 أنا بوت منهجي 🚀")

async def search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = " ".join(context.args)
    if not query:
        await update.message.reply_text("🔎 اكتب هكذا:\n/search حكم الحجاب")
        return
    
    service = build("customsearch", "v1", developerKey=GOOGLE_API_KEY)
    res = service.cse().list(q=query, cx="YOUR_SEARCH_ENGINE_ID").execute()

    if "items" not in res:
        await update.message.reply_text("❌ ما لقيتش نتائج")
        return
    
    first_result = res["items"][0]
    title = first_result["title"]
    link = first_result["link"]
    await update.message.reply_text(f"📖 {title}\n🔗 {link}")

async def youtube(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = " ".join(context.args)
    if not query:
        await update.message.reply_text("📺 اكتب هكذا:\n/youtube شرح البخاري")
        return
    
    yt = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)
    req = yt.search().list(q=query, part="snippet", type="video", maxResults=1)
    res = req.execute()

    if not res["items"]:
        await update.message.reply_text("❌ ما لقيتش فيديو")
        return
    
    video = res["items"][0]
    video_id = video["id"]["videoId"]
    title = video["snippet"]["title"]
    await update.message.reply_text(f"🎥 {title}\nhttps://www.youtube.com/watch?v={video_id}")

# handlers
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("search", search))
app.add_handler(CommandHandler("youtube", youtube))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, start))

# Flask
flask_app = Flask(__name__)

@flask_app.route(f"/{TELEGRAM_TOKEN}", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), app.bot)
    app.update_queue.put_nowait(update)
    return "ok"

if __name__ == "__main__":
    PORT = int(os.environ.get("PORT", 8443))
    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=TELEGRAM_TOKEN,
        webhook_url=f"https://manhaj-bot.onrender.com/{TELEGRAM_TOKEN}"
    )
