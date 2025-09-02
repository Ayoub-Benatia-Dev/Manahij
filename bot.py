# -*- coding: utf-8 -*-

# بوت تلجرام للبحث في جوجل ويوتيوب باستخدام Gemini
# هذا الكود يستخدم مكتبة python-telegram-bot
# ومكتبة google-api-python-client للبحث الرسمي
# ومكتبة requests للتفاعل مع Gemini API

# --- المتطلبات (Requirements) ---
# يجب عليك تحديث ملف "requirements.txt" ليتضمن المكتبات الجديدة.
# يجب أن يحتوي على السطور التالية:
# python-telegram-bot
# google-api-python-client
# requests
# uvicorn

# --- الحصول على مفاتيح API ---
# 1. مفتاح بوت التلجرام:
#    يُمكنك الحصول عليه من @BotFather.
# 2. مفتاح Google API و Google CX (Custom Search ID):
#    تحتاج إلى تفعيل Google Custom Search API من Google Cloud Console.
#    وإنشاء محرك بحث مخصص (Custom Search Engine) للحصول على مفتاح CX.
# 3. مفتاح YouTube API:
#    يُمكنك الحصول عليه من Google Cloud Console بعد تفعيل YouTube Data API.
# 4. مفتاح Gemini API:
#    يُمكنك الحصول عليه من Google AI Studio.

# ملاحظة: أفضل طريقة لتخزين هذه المفاتيح هي كمتغيرات بيئة على Render.com.
# لقد قمنا بتحديث الكود لاستخدام os.getenv() لجلبها.

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
        "يمكنك استخدام الأوامر التالية للبحث:\n"
        "1. /google [عبارة البحث]\n"
        "2. /youtube [عبارة البحث]\n\n"
        "مثال: /google أفضل طريقة لتعلم بايثون"
    )

# دالة للبحث في جوجل باستخدام Google Custom Search API
async def google_search_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """يبحث في جوجل عن النص الذي يكتبه المستخدم ويرسل النتائج."""
    query = " ".join(context.args)
    if not query:
        await update.message.reply_text("يرجى إدخال عبارة البحث بعد أمر /google.")
        return
        
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
async def youtube_search_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """يبحث في يوتيوب عن النص الذي يكتبه المستخدم ويرسل الروابط."""
    query = " ".join(context.args)
    if not query:
        await update.message.reply_text("يرجى إدخال عبارة البحث بعد أمر /youtube.")
        return

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


# إعداد تطبيق التلجرام مباشرة
# هذا هو التطبيق الذي سيتم تشغيله بواسطة uvicorn
application = Application.builder().token(TELEGRAM_TOKEN).build()

# إضافة الأوامر (Handlers)
application.add_handler(CommandHandler("start", start_command))
application.add_handler(CommandHandler("google", google_search_command))
application.add_handler(CommandHandler("youtube", youtube_search_command))
