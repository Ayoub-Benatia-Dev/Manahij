import requests
from bs4 import BeautifulSoup
from telegram.ext import Application, CommandHandler, MessageHandler, filters

# ---- API KEYS ----
TELEGRAM_TOKEN = "8367431259:AAEa_O2BzOQ6cpgX4rdOS3SiTKdvMbWAtQM"
GOOGLE_API_KEY = "AIzaSyDCay69bExFEAt4y7XEiSK1WmG6KB5l-yw"
YOUTUBE_API_KEY = "AIzaSyBMa4CY_Ndc6RDq2uIDO0nZvhtxvsdF4h4"
GOOGLE_CX = "369d6d61d01414942"

# ---- GOOGLE SEARCH + EXTRACT TEXT ----
def search_google(query: str):
    url = f"https://www.googleapis.com/customsearch/v1?q={query}&key={GOOGLE_API_KEY}&cx={GOOGLE_CX}"
    try:
        r = requests.get(url)
        results = r.json().get("items", [])
        if not results:
            return "ما لقيتش نتائج في جوجل."
        text = ""
        for i, result in enumerate(results[:3], start=1):
            link = result['link']
            title = result['title']
            snippet = get_page_text(link)
            text += f"{i}. {title}\n{link}\n{snippet}\n\n"
        return text.strip()
    except Exception as e:
        return f"خطأ في Google Search: {e}"

def get_page_text(url):
    try:
        r = requests.get(url, timeout=5)
        soup = BeautifulSoup(r.text, "html.parser")
        p = soup.find('p')
        if p:
            return p.get_text()[:250] + "..."
        return ""
    except:
        return ""

# ---- YOUTUBE SEARCH ----
def search_youtube(query: str):
    url = f"https://www.googleapis.com/youtube/v3/search?part=snippet&q={query}&key={YOUTUBE_API_KEY}&maxResults=3&type=video"
    try:
        r = requests.get(url)
        items = r.json().get("items", [])
        if not items:
            return "ما لقيتش فيديو في يوتيوب."
        text = ""
        for i, item in enumerate(items, start=1):
            video_id = item["id"]["videoId"]
            title = item["snippet"]["title"]
            text += f"{i}. {title}\nhttps://www.youtube.com/watch?v={video_id}\n\n"
        return text.strip()
    except Exception as e:
        return f"خطأ في YouTube API: {e}"

# ---- TELEGRAM BOT ----
async def start(update, context):
    await update.message.reply_text(
        "📚 مرحبا بك في *بوت مناهج*.\nاكتب سؤالك وسيتم البحث في Google و YouTube."
    )

async def handle_message(update, context):
    question = update.message.text
    await update.message.reply_text("⏳ جاري البحث .. استنى شوي")
    google_result = search_google(question)
    youtube_result = search_youtube(question)
    response = f"🔎 *من Google:*\n{google_result}\n\n▶️ *من YouTube:*\n{youtube_result}"
    await update.message.reply_text(response, parse_mode="Markdown")

# ---- MAIN ----
if __name__ == "__main__":
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # ---- WEBHOOK ----
    app.run_webhook(
        listen="0.0.0.0",
        port=10000,
        url_path=TELEGRAM_TOKEN,
        webhook_url=f"https://manhaj-bot.onrender.com/{TELEGRAM_TOKEN}"
    )
