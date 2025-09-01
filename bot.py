import requests
from telegram.ext import Application, CommandHandler, MessageHandler, filters

# ---- API KEYS ----
TELEGRAM_TOKEN = "8367431259:AAEa_O2BzOQ6cpgX4rdOS3SiTKdvMbWAtQM"
GOOGLE_API_KEY_1 = "AIzaSyDCay69bExFEAt4y7XEiSK1WmG6KB5l-yw"
YOUTUBE_API_KEY = "AIzaSyBMa4CY_Ndc6RDq2uIDO0nZvhtxvsdF4h4"

# ---- GOOGLE SEARCH ----
def search_google(query: str):
    url = f"https://www.googleapis.com/customsearch/v1?q={query}&key={GOOGLE_API_KEY_1}&cx=017576662512468239146:omuauf_lfve"
    try:
        r = requests.get(url)
        results = r.json().get("items", [])
        if not results:
            return "ما لقيتش نتائج في جوجل."
        first = results[0]
        return f"{first['title']}\n{first['link']}"
    except Exception as e:
        return f"خطأ في Google Search: {e}"

# ---- YOUTUBE SEARCH ----
def search_youtube(query: str):
    url = f"https://www.googleapis.com/youtube/v3/search?part=snippet&q={query}&key={YOUTUBE_API_KEY}&maxResults=1&type=video"
    try:
        r = requests.get(url)
        items = r.json().get("items", [])
        if not items:
            return "ما لقيتش فيديو في يوتيوب."
        video_id = items[0]["id"]["videoId"]
        title = items[0]["snippet"]["title"]
        return f"{title}\nhttps://www.youtube.com/watch?v={video_id}"
    except Exception as e:
        return f"خطأ في YouTube API: {e}"

# ---- TELEGRAM BOT ----
async def start(update, context):
    await update.message.reply_text("📚 مرحبا بك في *بوت مناهج*.\nاكتب سؤالك وسيتم البحث في Google و YouTube.")

async def handle_message(update, context):
    question = update.message.text

    await update.message.reply_text("⏳ جاري البحث .. استنى شوي")

    google_result = search_google(question)
    youtube_result = search_youtube(question)

    response = f"🔎 *من Google:*\n{google_result}\n\n▶️ *من YouTube:*\n{youtube_result}"
    await update.message.reply_text(response, parse_mode="Markdown")

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()

if __name__ == "__main__":
    main()
