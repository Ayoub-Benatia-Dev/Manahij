import os
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# === مفاتيح API ===
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")  # مفتاح بوت التلغرام
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")  # مفتاح Google API
CX_ID = os.getenv("CX_ID")  # ID لمحرك البحث المخصص (CSE)
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")  # مفتاح YouTube API

# === البحث في Google ===
def google_search(query):
    url = f"https://www.googleapis.com/customsearch/v1?q={query}&key={GOOGLE_API_KEY}&cx={CX_ID}"
    response = requests.get(url).json()
    results = []
    if "items" in response:
        for item in response["items"][:3]:  # نرجع 3 نتائج فقط
            results.append(f"- {item['title']}\n{item['link']}\n")
    return "\n".join(results) if results else "ما لقيتش نتائج 😔"

# === البحث في YouTube ===
def youtube_search(query):
    url = f"https://www.googleapis.com/youtube/v3/search?part=snippet&q={query}&type=video&key={YOUTUBE_API_KEY}&maxResults=3"
    response = requests.get(url).json()
    results = []
    if "items" in response:
        for item in response["items"]:
            video_title = item["snippet"]["title"]
            video_id = item["id"]["videoId"]
            video_url = f"https://www.youtube.com/watch?v={video_id}"
            results.append(f"- {video_title}\n{video_url}\n")
    return "\n".join(results) if results else "ما لقيتش فيديوهات 😔"

# === التعامل مع الرسائل ===
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text.lower()

    if "يوتيوب" in user_message or "مقطع" in user_message or "محاضرة" in user_message:
        results = youtube_search(user_message)
    else:
        results = google_search(user_message)

    await update.message.reply_text(results)

# === تشغيل البوت ===
def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()

if __name__ == "__main__":
    main()
