import requests
from telegram import Update
from telegram.ext import Application, MessageHandler, filters

# 🔑 مفاتيح API
TELEGRAM_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"  # لازم تبدلو بتاعك من BotFather
GOOGLE_API_KEY = "AIzaSyDCay69bExFEAt4y7XEiSK1WmG6KB5l-yw"
CX_ID = "YOUR_CUSTOM_SEARCH_ENGINE_ID"  # خاص ب Google Custom Search Engine
YOUTUBE_API_KEY = "AIzaSyBMa4CY_Ndc6RDq2uIDO0nZvhtxvsdF4h4"

# البحث في جوجل
def search_google(query):
    url = f"https://www.googleapis.com/customsearch/v1?key={GOOGLE_API_KEY}&cx={CX_ID}&q={query}"
    response = requests.get(url).json()
    results = []
    if "items" in response:
        for item in response["items"][:3]:
            results.append(f"{item['title']}\n{item['link']}")
    return "\n\n".join(results) if results else "❌ ما لقيتش نتائج في جوجل."

# البحث في يوتيوب
def search_youtube(query):
    url = f"https://www.googleapis.com/youtube/v3/search?part=snippet&q={query}&key={YOUTUBE_API_KEY}&maxResults=3&type=video"
    response = requests.get(url).json()
    results = []
    if "items" in response:
        for item in response["items"]:
            video_id = item["id"]["videoId"]
            title = item["snippet"]["title"]
            results.append(f"{title}\nhttps://www.youtube.com/watch?v={video_id}")
    return "\n\n".join(results) if results else "❌ ما لقيتش فيديوهات."

# الرد على الرسائل
async def handle_message(update: Update, context):
    query = update.message.text
    google_results = search_google(query)
    youtube_results = search_youtube(query)
    reply = f"🔎 نتائج من جوجل:\n{google_results}\n\n▶️ نتائج من يوتيوب:\n{youtube_results}"
    await update.message.reply_text(reply)

# تشغيل البوت
def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()

if __name__ == "__main__":
    main()
