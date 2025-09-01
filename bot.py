import logging
import os
import requests
import json
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
from googleapiclient.discovery import build

# إعدادات التسجيل لتتبع ما يحدث في البوت
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

# استيراد مفاتيح API من متغيرات البيئة.
# القيم الافتراضية هنا هي لأغراض الاختبار فقط.
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "8367431259:AAEa_O2BzOQ6cpgX4rdOS3SiTKdvMbWAtQM")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "AIzaSyDCay69bExFEAt4y7XEiSK1WmG6KB5l-yw")
GOOGLE_CX = os.getenv("GOOGLE_CX", "369d6d61d01414942")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "AIzaSyBMa4CY_Ndc6RDq2uIDO0nZvhtxvsdF4h4")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "AIzaSyDGS38J3w0t5cSKXwAQWBG_GUkJL8wdA14")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
PORT = int(os.environ.get('PORT', '8443'))

# دالة للرد على أمر /start
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """ترحب بالمستخدم وتشرح كيفية استخدام البوت."""
    user_name = update.effective_user.first_name
    await update.message.reply_text(
        f"أهلاً بك يا {user_name}!\n"
        "أنا بوت ذكي يمكنني البحث والإجابة على أسئلتك. يمكنك أن تطلب مني ما تريد مباشرة!"
    )

# دالة للبحث في جوجل باستخدام Google Custom Search API
async def google_search(update: Update, context: ContextTypes.DEFAULT_TYPE, query: str) -> None:
    """يبحث في جوجل عن النص الذي يكتبه المستخدم ويرسل النتائج."""
    await update.message.reply_text(f"جاري البحث في جوجل عن: '{query}'...")

    try:
        service = build("customsearch", "v1", developerKey=GOOGLE_API_KEY)
        res = service.cse().list(q=query, cx=GOOGLE_CX, num=5).execute()
        
        if "items" in res:
            response_message = f"أفضل 5 نتائج لجوجل عن '{query}':\n\n"
            for item in res["items"]:
                title = item.get("title", "لا يوجد عنوان")
                link = item.get("link", "#")
                snippet = item.get("snippet", "لا يوجد وصف")
                response_message += f"**{title}**\n{snippet}\n[الرابط]({link})\n\n"

            await update.message.reply_markdown_v2(
                response_message,
                disable_web_page_preview=True
            )
        else:
            await update.message.reply_text("عذرًا، لم يتم العثور على أي نتائج.")

    except Exception as e:
        logger.error(f"خطأ أثناء البحث في جوجل: {e}")
        await update.message.reply_text("عذرًا، حدث خطأ أثناء البحث. يرجى التأكد من أن مفاتيح API صحيحة.")


# دالة للبحث في يوتيوب باستخدام YouTube Data API
async def youtube_search(update: Update, context: ContextTypes.DEFAULT_TYPE, query: str) -> None:
    """يبحث في يوتيوب عن النص الذي يكتبه المستخدم ويرسل الروابط."""
    await update.message.reply_text(f"جاري البحث في يوتيوب عن: '{query}'...")

    try:
        youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)
        request = youtube.search().list(
            q=query,
            part="snippet",
            type="video",
            maxResults=5
        )
        response = request.execute()
        
        if "items" in response:
            response_message = f"أفضل 5 نتائج ليوتيوب عن '{query}':\n\n"
            for item in response["items"]:
                title = item["snippet"]["title"]
                video_id = item["id"]["videoId"]
                link = f"https://www.youtube.com/watch?v={video_id}"
                response_message += f"**{title}**\nالرابط: {link}\n\n"
            
            await update.message.reply_text(response_message)
        else:
            await update.message.reply_text("عذرًا، لم يتم العثور على أي نتائج.")

    except Exception as e:
        logger.error(f"خطأ أثناء البحث في يوتيوب: {e}")
        await update.message.reply_text("عذرًا، حدث خطأ أثناء البحث. يرجى التأكد من أن مفاتيح API صحيحة.")


# دالة للتعامل مع الرسائل النصية
async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """يستخدم Gemini لتحديد ما إذا كانت الرسالة تحتاج إلى بحث أو إجابة مباشرة."""
    user_message = update.message.text
    
    # رسالة التوجيه لنموذج Gemini
    prompt_for_gemini = f"""
    Given the following user query, determine its intent. Respond with one of the following JSON objects:
    1. For a question that requires a general answer, use: {{"intent": "general_answer", "query": "[The original query]"}}
    2. For a search query on Google, use: {{"intent": "google_search", "query": "[The search query]"}}
    3. For a search query for a video on YouTube, use: {{"intent": "youtube_search", "query": "[The search query]"}}
    
    User query: "{user_message}"
    """
    
    try:
        # إرسال طلب إلى Gemini API
        api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-05-20:generateContent?key={GEMINI_API_KEY}"
        payload = {
            "contents": [{"parts": [{"text": prompt_for_gemini}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseSchema": {
                    "type": "OBJECT",
                    "properties": {
                        "intent": {"type": "STRING", "enum": ["general_answer", "google_search", "youtube_search"]},
                        "query": {"type": "STRING"}
                    },
                    "propertyOrdering": ["intent", "query"]
                }
            }
        }

        response = requests.post(api_url, json=payload)
        response.raise_for_status() # إلقاء خطأ إذا كان هناك خطأ HTTP
        result = response.json()
        
        # استخراج وتحليل الرد من Gemini
        generated_json_string = result["candidates"][0]["content"]["parts"][0]["text"]
        parsed_response = json.loads(generated_json_string)
        
        intent = parsed_response.get("intent")
        query_text = parsed_response.get("query", user_message)

        if intent == "google_search":
            await google_search(update, context, query_text)
        elif intent == "youtube_search":
            await youtube_search(update, context, query_text)
        elif intent == "general_answer":
            # في حال كان السؤال عامًا، نستخدم Gemini للإجابة عليه
            await update.message.reply_text("جاري الإجابة على سؤالك باستخدام Gemini...")
            general_prompt = f"قم بالإجابة على هذا السؤال بشكل مختصر: {query_text}"
            
            # Use Google Search grounding to get the source
            payload_with_grounding = {
                "contents": [{
                    "parts": [{"text": general_prompt}]
                }],
                "tools": [{"google_search": {}}],
            }
            
            general_response = requests.post(api_url, json=payload_with_grounding)
            general_response.raise_for_status()
            general_result = general_response.json()
            
            # Extract the text and the source
            general_text = general_result["candidates"][0]["content"]["parts"][0]["text"]
            sources = general_result.get("candidates", [{}])[0].get("groundingMetadata", {}).get("groundingAttributions", [])
            
            final_message = general_text
            if sources:
                final_message += "\n\n**المصدر:**"
                for i, source in enumerate(sources, 1):
                    uri = source.get("web", {}).get("uri", "")
                    title = source.get("web", {}).get("title", "")
                    if uri and title:
                        final_message += f"\n- [{i}]({uri}) {title}"

            await update.message.reply_markdown_v2(final_message)
        else:
            await update.message.reply_text("عذرًا، لم أتمكن من فهم طلبك.")

    except Exception as e:
        logger.error(f"حدث خطأ أثناء معالجة الرسالة: {e}")
        await update.message.reply_text("عذرًا، حدث خطأ ما. يرجى المحاولة مرة أخرى.")

# دالة رئيسية لتشغيل البوت
def main() -> None:
    """يشغل البوت."""
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # إضافة الأوامر (Handlers)
    application.add_handler(CommandHandler("start", start_command))
    
    # إضافة معالج لجميع الرسائل النصية التي لا تبدأ بعلامة /
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
    
    # تشغيل البوت باستخدام الـ Webhook
    if WEBHOOK_URL:
        # إعداد الـ Webhook
        application.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            url_path=TELEGRAM_TOKEN,
            webhook_url=WEBHOOK_URL
        )
        print(f"البوت يعمل الآن باستخدام Webhook على المنفذ {PORT}...")
    else:
        # في حال لم يتم العثور على رابط الـ Webhook، استخدم طريقة Polling كخيار احتياطي
        application.run_polling(allowed_updates=Update.ALL_TYPES)
        print("البوت يعمل الآن باستخدام Polling...")


if __name__ == "__main__":
    main()
