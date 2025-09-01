# -*- coding: utf-8 -*-
import os
import logging
import json
import asyncio
import aiohttp
from bs4 import BeautifulSoup
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# ---- Logging Setup / إعدادات التسجيل ----
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ---- API KEYS (hardcoded from user input) ----
# مفاتيح API (مضافة مباشرة من مدخلات المستخدم)
TELEGRAM_TOKEN = "8367431259:AAEa_O2BzOQ6cpgX4rdOS3SiTKdvMbWAtQM"
GOOGLE_API_KEY = "AIzaSyDCay69bExFEAt4y7XEiSK1WmG6KB5l-yw"
YOUTUBE_API_KEY = "AIzaSyBMa4CY_Ndc6RDq2uIDO0nZvhtxvsdF4h4"
GOOGLE_CX = "369d6d61d01414942"
# Gemini API details for AI filtering
GEMINI_API_KEY = "AIzaSyDGS38J3w0t5cSKXwAQWBG_GUkJL8wdA14"
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-05-20:generateContent"

# ---- Trusted Scholars List (loaded from a file) / قائمة العلماء الموثوقين (يتم تحميلها من ملف) ----
def load_trusted_scholars():
    """Loads the trusted scholars list from a JSON file."""
    # يقوم بتحميل قائمة العلماء الموثوقين من ملف JSON
    try:
        with open("trusted_scholars.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error("trusted_scholars.json file not found.")
        return []
    except json.JSONDecodeError:
        logger.error("Error decoding JSON from trusted_scholars.json.")
        return []

TRUSTED_KEYWORDS = load_trusted_scholars()
if not TRUSTED_KEYWORDS:
    logger.warning("Trusted scholars list is empty. AI filtering will still be applied, but results may be less specific.")

# ---- HELPER FUNCTIONS / دوال مساعدة ----
async def get_page_text(url, session):
    """Fetches a URL and extracts the first paragraph text asynchronously."""
    # يجلب نص الصفحة من رابط ويستخرج الفقرة الأولى بشكل لا متزامن
    try:
        async with session.get(url, timeout=5) as response:
            if response.status == 200:
                html = await response.text()
                soup = BeautifulSoup(html, "html.parser")
                p = soup.find('p')
                if p:
                    return p.get_text()[:250] + "..."
        return ""
    except Exception as e:
        logger.error(f"Error fetching page text from {url}: {e}")
        return ""

# ---- GOOGLE SEARCH (Asynchronous) / بحث جوجل (غير متزامن) ----
async def search_google(query: str, session):
    """Performs a Google search and returns results asynchronously."""
    # يجري بحث جوجل ويعيد النتائج بشكل لا متزامن
    url = f"https://www.googleapis.com/customsearch/v1?q={query}&key={GOOGLE_API_KEY}&cx={GOOGLE_CX}"
    try:
        async with session.get(url) as response:
            results = (await response.json()).get("items", [])
            search_results = []
            for result in results[:5]:
                link = result.get('link')
                title = result.get('title')
                if link and title:
                    snippet = await get_page_text(link, session)
                    search_results.append({"title": title, "link": link, "snippet": snippet})
            return search_results
    except Exception as e:
        logger.error(f"Error during Google search for '{query}': {e}")
        return []

# ---- YOUTUBE SEARCH (Asynchronous) / بحث يوتيوب (غير متزامن) ----
async def search_youtube(query: str, session):
    """Performs a YouTube search and returns results asynchronously."""
    # يجري بحث يوتيوب ويعيد النتائج بشكل لا متزامن
    url = f"https://www.googleapis.com/youtube/v3/search?part=snippet&q={query}&key={YOUTUBE_API_KEY}&maxResults=5&type=video"
    try:
        async with session.get(url) as response:
            items = (await response.json()).get("items", [])
            videos = []
            for item in items:
                video_id = item.get("id", {}).get("videoId")
                title = item.get("snippet", {}).get("title")
                if video_id and title:
                    videos.append({"title": title, "link": f"https://www.youtube.com/watch?v={video_id}"})
            return videos
    except Exception as e:
        logger.error(f"Error during YouTube search for '{query}': {e}")
        return []

# ---- AI FILTERING (using Gemini API) / الفلترة بالذكاء الاصطناعي (باستخدام Gemini API) ----
async def gemini_filter(results, session):
    """
    Uses the Gemini API to filter results based on a list of trusted scholars.
    يستخدم Gemini API لفلترة النتائج بناءً على قائمة العلماء الموثوقين.
    """
    if not TRUSTED_KEYWORDS:
        logger.warning("No trusted scholars list available. Returning all results without AI filtering.")
        return results

    filtered_results = []
    
    # Construct the system instruction and user query
    # بناء التعليمات والمحتوى للمستخدم
    system_instruction = (
        "You are an expert AI filter. Your task is to evaluate a list of search results "
        "and identify which ones are directly related to the trusted scholars provided. "
        "The response MUST be a JSON array containing only the titles of the related results."
    )
    
    trusted_scholars_list = ", ".join(TRUSTED_KEYWORDS)
    
    user_query = (
        f"Here is a list of search results. Based on the titles and snippets, "
        f"which of these are directly related to any of the following scholars: {trusted_scholars_list}?\n\n"
        f"Search Results:\n"
    )
    for i, r in enumerate(results):
        user_query += f"Result {i+1}: Title: {r.get('title', '')} | Snippet: {r.get('snippet', 'N/A')}\n"
    
    user_query += "\nRespond with a JSON array of the titles that are directly related."

    payload = {
        "contents": [{"parts": [{"text": user_query}]}],
        "systemInstruction": {"parts": [{"text": system_instruction}]},
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": {
                "type": "ARRAY",
                "items": {"type": "STRING"}
            }
        },
    }

    try:
        async with session.post(f"{GEMINI_API_URL}?key={GEMINI_API_KEY}", json=payload) as response:
            if response.status == 200:
                result = await response.json()
                response_text = result.get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('text', '[]')
                
                # Sanitize the response to ensure it's a valid JSON array
                response_text = response_text.replace('```json', '').replace('```', '')
                
                related_titles = json.loads(response_text)
                
                # Filter the original results based on the titles returned by Gemini
                for r in results:
                    if r.get('title') in related_titles:
                        filtered_results.append(r)
            else:
                logger.error(f"Gemini API request failed with status code: {response.status}")
                return results # Fallback to no-AI-filtering
    except Exception as e:
        logger.error(f"Error during Gemini filtering: {e}", exc_info=True)
        return results # Fallback to no-AI-filtering

    return filtered_results

# ---- TELEGRAM BOT COMMAND HANDLERS / معالجات أوامر بوت تيليجرام ----
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a welcome message when the command /start is issued."""
    # يرسل رسالة ترحيب عند إعطاء أمر /start
    await update.message.reply_text(
        "📚 مرحبا بك في *بوت مناهج*.\n\n"
        "هذا البوت يساعدك في البحث عن إجابات من مصادر إسلامية موثوقة.\n\n"
        "اكتب سؤالك وسأقوم بالبحث وفلترة النتائج لك.\n"
        "للمزيد من المعلومات، استخدم الأمر /help"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a help message when the command /help is issued."""
    # يرسل رسالة مساعدة عند إعطاء أمر /help
    help_text = (
        "هذا البوت يبحث عن إجابات على أسئلتك من مصادر إسلامية موثوقة.\n\n"
        "**طريقة الاستخدام:**\n"
        "1. فقط أرسل سؤالك في المحادثة.\n"
        "2. سيقوم البوت بالبحث على جوجل ويوتيوب.\n"
        "3. سيتم فلترة النتائج باستخدام الذكاء الاصطناعي لعرض ما هو منسوب لعلماء موثوقين فقط.\n\n"
        "⚠️ **ملاحظة:** قد لا تكون جميع النتائج دقيقة بنسبة 100%، فالعملية آلية. "
        "يجب عليك دائمًا التحقق من صحة المعلومة."
    )
    await update.message.reply_text(help_text)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles user messages, performs search and filtering."""
    # يتعامل مع رسائل المستخدم، يجري البحث والفلترة
    question = update.message.text
    if not question:
        await update.message.reply_text("عذراً، لم أستقبل أي نص. يرجى إرسال سؤالك.")
        return

    await update.message.reply_text("⏳ جاري البحث..")

    try:
        # Use an aiohttp session for all requests
        async with aiohttp.ClientSession() as session:
            google_task = search_google(question, session)
            youtube_task = search_youtube(question, session)
            
            # Run both searches concurrently
            google_results, youtube_results = await asyncio.gather(google_task, youtube_task)

        combined = google_results + youtube_results

        if not combined:
            await update.message.reply_text("❌ عذراً، لم يتم العثور على نتائج للبحث. قد يكون هناك خطأ في الشبكة أو أن السؤال غير واضح.")
            return

        await update.message.reply_text("🧠 جاري الفلترة بواسطة الذكاء الاصطناعي... قد يستغرق هذا بعض الوقت.")

        # AI-powered filtering
        filtered = await gemini_filter(combined, session)

        if not filtered:
            await update.message.reply_text("📖 لم يتم العثور على نتائج موثوقة للعلماء السلفيين.")
        else:
            msg = "✅ إليك النتائج الموثوقة:\n\n"
            for r in filtered:
                msg += f"📌 *{r['title']}*\n"
                msg += f"🔗 {r['link']}\n"
                # Add snippet for more context
                if 'snippet' in r and r['snippet']:
                    msg += f"📝 _{r['snippet']}_\n"
                msg += "\n"
            
            await update.message.reply_text(msg, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"An error occurred: {e}", exc_info=True)
        await update.message.reply_text("❌ حدث خطأ غير متوقع. يرجى المحاولة مرة أخرى لاحقًا.")

# ---- MAIN / البرنامج الرئيسي ----
def main() -> None:
    """Starts the bot."""
    # يبدأ البوت
    try:
        app = Application.builder().token(TELEGRAM_TOKEN).build()
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("help", help_command))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

        # This part remains the same as it's for the deployment environment
        app.run_webhook(
            listen="0.0.0.0",
            port=int(os.environ.get("PORT", 10000)),
            url_path=TELEGRAM_TOKEN,
            webhook_url=os.environ.get("WEBHOOK_URL", f"https://manhaj-bot.onrender.com/{TELEGRAM_TOKEN}")
        )
    except Exception as e:
        logger.error(f"Failed to start bot due to an error: {e}")

if __name__ == "__main__":
    main()
