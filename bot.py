import os
import logging
import requests
from telegram import Update
from telegram.ext import Application, MessageHandler, ContextTypes, filters
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

# -------- قراءة قائمة الشيوخ من ملف --------
def load_scholars(filename="scholars.txt"):
    try:
        with open(filename, "r", encoding="utf-8") as file:
            scholars = [line.strip() for line in file if line.strip()]
            return scholars
    except FileNotFoundError:
        logger.error(f"ملف {filename} غير موجود. لن يتم تصفية البحث.")
        return []
    except Exception as e:
        logger.error(f"خطأ في قراءة ملف {filename}: {e}")
        return []


# -------- Google Search --------
def google_search(query):
    url = "https://www.googleapis.com/customsearch/v1"
    params = {
        "key": GOOGLE_API_KEY,
        "cx": GOOGLE_CX,
        "q": query,
    }
    try:
        r = requests.get(url, params=params)
        r.raise_for_status()
        return r.json().get("items", [])
    except requests.exceptions.RequestException as e:
        logger.error(f"Google Search Error: {e}")
        return []


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
    try:
        r = requests.get(url, params=params)
        r.raise_for_status()
        return r.json().get("items", [])
    except requests.exceptions.RequestException as e:
        logger.error(f"YouTube Search Error: {e}")
        return []


# -------- تحسين النتائج بـ Gemini --------
def refine_results(query, results, search_type):
    if not model:
        return results

    personality_prompt = ""
    try:
        with open("prompt.txt", "r", encoding="utf-8") as file:
            personality_prompt = file.read()
    except FileNotFoundError:
        logger.warning("ملف prompt.txt غير موجود. سيتم استخدام الشخصية الافتراضية.")
    except Exception as e:
        logger.error(f"خطأ في قراءة ملف prompt.txt: {e}")

    text_results = []
    for i, res in enumerate(results, start=1):
        if search_type == "google":
            title = res["title"]
            link = res.get("link", res.get("url", ""))
        else:
            title = res["snippet"]["title"]
            link = f"https://www.youtube.com/watch?v={res['id']['videoId']}"
        text_results.append(f"{i}. {title} - {link}")

    final_prompt = f"""
    {personality_prompt}

    هذه نتائج بحث عن: {query} من نوع {search_type}.
    رتبها واكتبها بأسلوب مناسب، اعتمادًا على التعليمات التي قدمتها لك.
    النتائج:
    {chr(10).join(text_results)}
    """
    
    try:
        response = model.generate_content(final_prompt)
        return response.text
    except Exception as e:
        logger.error(f"Gemini Error: {e}")
        return "\n".join(text_results)


# -------- أوامر البوت --------
async def search_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text
    if not query:
        return

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    
    scholars = load_scholars()
    
    all_results = []
    search_type = ""
    
    if scholars:
        for scholar in scholars:
            search_query = f"{query} {scholar}"
            
            youtube_results = youtube_search(search_query)
            if youtube_results:
                all_results.extend(youtube_results)
                search_type = "youtube"
                break 

        if not all_results:
            for scholar in scholars:
                search_query = f"{query} {scholar}"
                google_results = google_search(search_query)
                if google_results:
                    all_results.extend(google_results)
                    search_type = "google"
                    break
    
    if not all_results:
        all_results = youtube_search(query)
        search_type = "youtube"

        if not all_results:
            all_results = google_search(query)
            search_type = "google"


    if not all_results:
        await update.message.reply_text("ما لقيتش نتائج 🤷‍♂️")
        return

    text = refine_results(query, all_results, search_type)
    await update.message.reply_text(text)


# -------- تشغيل البوت --------
def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), search_handler))

    port = int(os.environ.get("PORT", 8080))
    app.run_webhook(
        listen="0.0.0.0",
        port=port,
        url_path=TELEGRAM_TOKEN,
        webhook_url=f"https://{os.environ.get('RENDER_EXTERNAL_HOSTNAME')}/{TELEGRAM_TOKEN}"
    )


if __name__ == "__main__":
    main()
