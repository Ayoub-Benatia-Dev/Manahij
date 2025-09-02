import os
import requests
import json
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from googleapiclient.discovery import build

# --- Variables and API Key Setup ---
# The keys will be loaded securely from environment variables on Render.com.
# Be sure to set them in the Render.com dashboard.
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY")
GOOGLE_CX = os.environ.get("GOOGLE_CX")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# --- Gemini API Call Function ---
def format_results_with_gemini(prompt_text, search_type):
    """
    Sends search results to the Gemini API for formatting and summarization.
    """
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-05-20:generateContent"
    headers = {'Content-Type': 'application/json'}
    payload = {
        "contents": [{
            "parts": [{
                "text": f"كمساعد ذكي، قم بتلخيص وتنظيم نتائج البحث التالية لـ {search_type} في قائمة واضحة ومختصرة.\n\nالنتائج الخام:\n{prompt_text}"
            }]
        }],
        "tools": [{"google_search": {}}]
    }

    try:
        response = requests.post(f"{url}?key={GEMINI_API_KEY}", headers=headers, data=json.dumps(payload))
        response.raise_for_status()
        result = response.json()
        formatted_text = result['candidates'][0]['content']['parts'][0]['text']
        return formatted_text
    except requests.exceptions.RequestException as e:
        print(f"Error calling Gemini API: {e}")
        return f"حدث خطأ في معالجة النتائج. قد لا تكون النتائج مرتبة بشكل جيد. {prompt_text}"
    except (KeyError, IndexError):
        print("Gemini API response format is not as expected.")
        return f"تعذر تنسيق النتائج من قبل Gemini. إليك النتائج الخام:\n{prompt_text}"


# --- Command Handlers ---
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handles the /start command.
    """
    await update.message.reply_text("مرحباً بك! أنا بوت للبحث. \n\nاستخدم: \n/google [عبارة البحث] \n/youtube [عبارة البحث]")

async def google_search_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handles the /google command and performs a Google search.
    """
    query = " ".join(context.args)
    if not query:
        await update.message.reply_text("الرجاء إدخال عبارة بحث بعد الأمر /google.")
        return

    await update.message.reply_text(f"جاري البحث عن: '{query}'...")

    try:
        service = build("customsearch", "v1", developerKey=GOOGLE_API_KEY)
        res = service.cse().list(q=query, cx=GOOGLE_CX).execute()
        
        raw_results = ""
        if 'items' in res:
            for item in res['items']:
                raw_results += f"العنوان: {item.get('title', 'لا يوجد عنوان')}\n"
                raw_results += f"الرابط: {item.get('link', 'لا يوجد رابط')}\n"
                raw_results += f"المقتطف: {item.get('snippet', 'لا يوجد مقتطف')}\n\n"
        else:
            await update.message.reply_text("لم يتم العثور على نتائج لبحثك في جوجل.")
            return

        formatted_results = format_results_with_gemini(raw_results, "Google")
        await update.message.reply_text(formatted_results)

    except Exception as e:
        await update.message.reply_text(f"عذراً، حدث خطأ أثناء البحث في جوجل. الرجاء المحاولة لاحقاً.\nالخطأ: {e}")

async def youtube_search_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handles the /youtube command and performs a YouTube search.
    """
    query = " ".join(context.args)
    if not query:
        await update.message.reply_text("الرجاء إدخال عبارة بحث بعد الأمر /youtube.")
        return

    await update.message.reply_text(f"جاري البحث عن مقاطع فيديو لـ: '{query}'...")

    try:
        service = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)
        res = service.search().list(
            q=query,
            part="id,snippet",
            maxResults=5
        ).execute()

        raw_results = ""
        if 'items' in res:
            for item in res['items']:
                if item['id']['kind'] == 'youtube#video':
                    raw_results += f"العنوان: {item['snippet']['title']}\n"
                    raw_results += f"الرابط: https://www.youtube.com/watch?v={item['id']['videoId']}\n"
                    raw_results += f"الوصف: {item['snippet']['description']}\n\n"
        else:
            await update.message.reply_text("لم يتم العثور على نتائج لبحثك في يوتيوب.")
            return
        
        formatted_results = format_results_with_gemini(raw_results, "YouTube")
        await update.message.reply_text(formatted_results)
    
    except Exception as e:
        await update.message.reply_text(f"عذراً، حدث خطأ أثناء البحث في يوتيوب. الرجاء المحاولة لاحقاً.\nالخطأ: {e}")


# --- Main Function ---
def main():
    """
    Main function to run the bot.
    """
    if not TELEGRAM_TOKEN or not GOOGLE_API_KEY or not YOUTUBE_API_KEY or not GOOGLE_CX or not GEMINI_API_KEY:
        print("خطأ: يرجى إعداد جميع متغيرات البيئة قبل التشغيل.")
        return
        
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Add command handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("google", google_search_command))
    application.add_handler(CommandHandler("youtube", youtube_search_command))

    print("بدأ البوت بنجاح...")
    application.run_polling()


if __name__ == "__main__":
    main()
