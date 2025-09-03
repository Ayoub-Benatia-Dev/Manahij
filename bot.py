import os
import logging
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import google.generativeai as genai

# ---- API KEYS ----
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", ":")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "-")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "")
GOOGLE_CX = os.getenv("GOOGLE_CX", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# إعدادات اللوج
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Gemini إعداد
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel("gemini-1.5-flash")
else:
    model = None


# -------- Google Search --------
def google_search(query):
    url = "https://www.googleapis.com/customsearch/v1"
    params = {
        "key": GOOGLE_API_KEY,
        "cx": GOOGLE_CX,
        "q": query,
    }
    r = requests.get(url, params=params)
    results = r.json().get("items", [])
    return results


# -------- YouTube Search --------
def youtube_search(query):
    url = "https://www.googleapis.com/youtube/v3/search"
    params = {
        "key": YOUTUBE_API_KEY,
        "q": query,
        "part": "snippet",
        "maxResults": 5,
        "type": "video"
    }
    r = requests.get(url, params=params)
    results = r.json().get("items", [])
    return results


# -------- تحسين النتائج بـ Gemini --------
def refine_results(query, results):
    if not model:
        return results  # إذا ما كاش Gemini رجع كما جاو

    text_results = []
    for i, res in enumerate(results, start=1):
        if "title" in res:
            title = res["title"]
            link = res.get("link", res.get("url", ""))
        else:
            title = res["snippet"]["title"]
            link = f"https://www.youtube.com/watch?v={res['id']['videoId']}"
        text_results.append(f"{i}. {title} - {link}")

    prompt = f"""
    هذه نتائج بحث عن: {query}
    رتّبها وخليها أوضح للمستخدم الجزائري.
    النتائج:
    {chr(10).join(text_results)}
    """
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        logger.error(f"Gemini Error: {e}")
        return "\n".join(text_results)


# -------- أوامر البوت --------
async def google_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = " ".join(context.args)
    if not query:
        await update.message.reply_text("اكتب هكذا: /google عبارة البحث")
        return

    results = google_search(query)
    if not results:
        await update.message.reply_text("ما لقيتش نتائج 🤷‍♂️")
        return

    text = refine_results(query, results)
    await update.message.reply_text(text)


async def youtube_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = " ".join(context.args)
    if not query:
        await update.message.reply_text("اكتب هكذا: /youtube عبارة البحث")
        return

    results = youtube_search(query)
    if not results:
        await update.message.reply_text("ما لقيتش فيديوهات 🤷‍♂️")
        return

    text = refine_results(query, results)
    await update.message.reply_text(text)


# -------- تشغيل البوت --------
def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("google", google_command))
    app.add_handler(CommandHandler("youtube", youtube_command))

    port = int(os.environ.get("PORT", 8080))
    app.run_webhook(
        listen="0.0.0.0",
        port=port,
        url_path=TELEGRAM_TOKEN,
        webhook_url=f"https://{os.environ.get('RENDER_EXTERNAL_HOSTNAME')}/{TELEGRAM_TOKEN}"
    )


if __name__ == "__main__":
    main()
