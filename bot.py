# bot.py
# نسخة متطوّرة لبوت تليجرام: يبحث في Google + YouTube، يستخدم Gemini لاستخراج كلمات مفتاحية
# ويفلتر النتائج باش يجيب فتاوى المشايخ اللي في قائمتك، ويرجع "الاسم - عنوان الفتوى - النص الكامل - الرابط".
#
# ملاحظة هامة: يجب وضع المفاتيح في Environment Variables على Render:
# TELEGRAM_TOKEN, GOOGLE_API_KEY, GOOGLE_CX, YOUTUBE_API_KEY, GEMINI_API_KEY, (RENDER_EXTERNAL_HOSTNAME)
#
# اعمل deploy على Render كـ Web Service وخلّ Start Command: python bot.py

import os
import re
import asyncio
import logging
import textwrap
from typing import List, Dict, Optional

import requests
from bs4 import BeautifulSoup

from telegram import Update
from telegram.ext import (
    Application,
    ContextTypes,
    CommandHandler,
    MessageHandler,
    filters,
)

# Gemini client (google.generativeai) - نستخدمها لو كانت متوفرة
try:
    import google.generativeai as genai
except Exception:
    genai = None

# مكتبة لجلب تفريغات اليوتيوب إن أمكن
try:
    from youtube_transcript_api import YouTubeTranscriptApi
except Exception:
    YouTubeTranscriptApi = None

# ---------------------- إعدادات ----------------------
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GOOGLE_CX = os.getenv("GOOGLE_CX")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# لوق
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# قائمة المشايخ (خذتها كما عطيتني) - نصيحة: عدّلها لاحقًا إذا حبّيت
SCHOLARS = [
    "ربيع المدخلي","عبيد الجابري","صالح الفوزان","صالح اللاحيدان","عبدالمحسن العباد",
    "محمد بن هادي المدخلي","عبد العزيز آل الشيخ","محمد سعيد رسلان","البرعي","عبد الرزاق عفيفي",
    "حسن بن عبد الوهاب البنا","البهكلي","الأمين الشنقيطي","عبد الرحمن العميسان",
    "سليمان الرحيل","عايد بن خليفة الشمري","محمد بن رمزان الهاجري","صالح آل الشيخ",
    "عبد الرزاق البدر","محمد العنجري","عبد الرحمن الوكيل","محمد العقيل","فلاح مندكار",
    "محمد بن ربيع المدخلي","جمال الحارثي","أسامة بن زيد المدخلي","مزمل فقيري",
    "أبو بكر آداب","خالد عثمان المصري","عزيز فريحان","حمد العثمان","خالد بن عبد الرحمن الزكي",
    "محمود شاكر","علي بن زيد المدخلي","البشير الإبراهيمي","عبد الحميد بن باديس",
    "مبارك الميلي","الطيب العقبي","عادل الشوريجي","عادل السيد","صفي الرحمن المباركفوري",
    "أبو عبد الأعلى المصري","تقي الدين الهلالي","نعمان الوتر","أبو أسامة مصطفى بن وقليل",
    "سالم موريدا","عبد القادر بن محمد الجنيّد","صالح السندي","دغش العجمي","محمد غيث",
    "علي الحذيفي","محمد بن زيد المدخلي","عبد محمد الإمام","صالح العصيمي","علي الحداد",
    "عادل المشوري","عثمان السالمي","عادل منصور الباشا","محمد الفيفي","عبدالسلام السحيمي",
    "صالح السحيمي","محمد بازمول","سعد الحصين","أحمد بازمول","عبد الرزاق حمزة",
    "ابراهيم محمد كشيدان","سعد بن ناصر الشثري","عبد السلام الشويعر","عبد الله الوصابي",
    # أضف أو نقص كما تحب
]

# ---------------------- تهيئة Gemini ----------------------
MODEL = None
if genai and GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        # قد تختلف أسماء الواجهة حسب المكتبة؛ هنا نستخدم طريقة توليد نص بسيطة
        MODEL = "gemini-1.5"  # مؤشر للاستخدام داخل الدوال
        logger.info("Gemini configured")
    except Exception as e:
        logger.warning("Gemini setup failed: %s", e)
        MODEL = None
else:
    logger.info("Gemini not configured or google.generativeai not installed.")


# ---------------------- أدوات مساعدة ----------------------
def chunk_text(text: str, max_size: int = 3900) -> List[str]:
    """نقطع النص لرسائل صغيرة متوافقة مع حد تيليجرام."""
    if not text:
        return []
    paragraphs = text.split("\n")
    chunks = []
    current = ""
    for p in paragraphs:
        if len(current) + len(p) + 1 <= max_size:
            current += (p + "\n")
        else:
            if current:
                chunks.append(current)
            # لو الفقرة وحدة أكبر من max_size نقصها
            if len(p) > max_size:
                for i in range(0, len(p), max_size):
                    chunks.append(p[i:i + max_size])
                current = ""
            else:
                current = p + "\n"
    if current:
        chunks.append(current)
    return chunks


def clean_text(s: str) -> str:
    """تنظيف نص بسيط: إزالة ترويسات HTML زائد المسافات."""
    if not s:
        return ""
    return re.sub(r"\s+", " ", s).strip()


def get_domain_from_url(url: str) -> str:
    try:
        from urllib.parse import urlparse
        return urlparse(url).netloc
    except Exception:
        return ""


# ---------------------- عمليات البحث ----------------------
def google_custom_search(query: str, num: int = 5) -> List[Dict]:
    """بحث بسيط في Google Custom Search (API)."""
    if not GOOGLE_API_KEY or not GOOGLE_CX:
        logger.warning("Google API key or CX not configured.")
        return []
    url = "https://www.googleapis.com/customsearch/v1"
    params = {
        "key": GOOGLE_API_KEY,
        "cx": GOOGLE_CX,
        "q": query,
        "num": num,
    }
    try:
        r = requests.get(url, params=params, timeout=15)
        r.raise_for_status()
        data = r.json()
        return data.get("items", [])
    except Exception as e:
        logger.error("Google search error: %s", e)
        return []


def youtube_search(query: str, max_results: int = 5) -> List[Dict]:
    """بحث في YouTube Data API (search)."""
    if not YOUTUBE_API_KEY:
        logger.warning("YouTube API key not configured.")
        return []
    url = "https://www.googleapis.com/youtube/v3/search"
    params = {
        "part": "snippet",
        "q": query,
        "key": YOUTUBE_API_KEY,
        "type": "video",
        "maxResults": max_results,
    }
    try:
        r = requests.get(url, params=params, timeout=15)
        r.raise_for_status()
        data = r.json()
        return data.get("items", [])
    except Exception as e:
        logger.error("YouTube search error: %s", e)
        return []


# ---------------------- جلب نص من صفحة ويب ----------------------
def fetch_page_text(url: str) -> str:
    """يحاول يستخرج النص الرئيسي من صفحة ويب بطريقة بسيطة."""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; manhaj-bot/1.0)"
        }
        r = requests.get(url, headers=headers, timeout=15)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")

        # نبحث عن عناصر article أو main أولاً
        article = soup.find("article")
        if not article:
            article = soup.find("main")
        if article:
            texts = [p.get_text(separator=" ", strip=True) for p in article.find_all(["p", "h1", "h2", "h3"])]
            joined = "\n".join([t for t in texts if t])
            if len(joined) > 200:
                return clean_text(joined)

        # خلاف ذلك ناخذ كل <p>
        ps = [p.get_text(separator=" ", strip=True) for p in soup.find_all("p")]
        joined = "\n".join([t for t in ps if t])
        return clean_text(joined)
    except Exception as e:
        logger.warning("fetch_page_text error for %s : %s", url, e)
        return ""


# ---------------------- تفريغ YouTube (transcript) ----------------------
def get_youtube_transcript(video_id: str) -> str:
    """يحاول يأخذ التفريغ باستعمال youtube_transcript_api."""
    if YouTubeTranscriptApi is None:
        logger.info("youtube_transcript_api not installed.")
        return ""
    try:
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id, languages=['ar','ar-SA','en'])
        # transcript_list: list of {"text": "...", "start": .., "duration": ..}
        texts = [t["text"] for t in transcript_list]
        joined = "\n".join(texts)
        return clean_text(joined)
    except Exception as e:
        logger.info("No transcript for video %s: %s", video_id, e)
        return ""


# ---------------------- Gemini helpers (نستخدمه لاستخراج كلمات وفلترة) ----------------------
def call_gemini_extract_keywords(prompt: str) -> List[str]:
    """يستعمل Gemini لاستخراج كلمات مفتاحية من النص.
       لو Gemini مش متوفر يرجع كلمات بسيطة من تقسيم النص."""
    if genai and GEMINI_API_KEY:
        try:
            # نستخدم واجهة بسيطة: نطلب من النموذج قائمة كلمات مفتاحية بصيغة JSON أو فواصل
            # ملاحظة: واجهة حقيقية قد تختلف حسب مكتبة genai المتاحة لديك
            full_prompt = (
                "استخراج كلمات مفتاحية قصيرة من النص التالي، فقط كلمات أو عبارات مفردة مفصولة بفواصل:\n\n"
                + prompt
            )
            resp = genai.generate_text(model="gemini-1.5", prompt=full_prompt, max_output_tokens=200)
            text = getattr(resp, "text", None) or str(resp)
            # نقسم على فواصل أو أسطر
            parts = re.split(r"[\n,؛؛،]+", text)
            keywords = [p.strip() for p in parts if p.strip()]
            if keywords:
                return keywords[:12]
        except Exception as e:
            logger.warning("Gemini keyword extraction failed: %s", e)

    # fallback بسيط: نرجع أهم الكلمات (كلمات >3 حروف) من النص
    words = re.findall(r"\b[^\W\d_]{4,}\b", prompt)
    freq = {}
    for w in words:
        wlow = w.lower()
        freq[wlow] = freq.get(wlow, 0) + 1
    sorted_words = sorted(freq.items(), key=lambda x: -x[1])
    return [w for w, _ in sorted_words[:10]]


def call_gemini_classify_if_scholar(result_snippet: str, scholars: List[str]) -> Optional[str]:
    """نسأل Gemini: هل هذي النتيجة تخص واحد من المشايخ؟ رجع اسم الشيخ أو None.
       إذا Gemini مش متوفر نعمل مطابقة نصية بسيطة."""
    # تبسيط: نطلب استجابة قصيرة تحتوي فقط على اسم الشيخ إن وجد
    prompt = (
        "أعطيني اسم الشيخ (من القائمة المعطاة) إذا كانت هذه النتيجة عبارة عن فتوى أو كلام لعالم من أهل السنة السلفيين الموثوقين. "
        "إذا ما كانتش تخص أي واحد رجع NONE. لا تزيد شيء آخر.\n\n"
        "قائمة العلماء:\n" + "\n".join(scholars) + "\n\n"
        f"النص/العنوان/المقتطف:\n{result_snippet}\n\n"
        "أجب باسم الشيخ أو NONE."
    )

    if genai and GEMINI_API_KEY:
        try:
            resp = genai.generate_text(model="gemini-1.5", prompt=prompt, max_output_tokens=60)
            text = getattr(resp, "text", None) or str(resp)
            text = text.strip()
            # نبحث عن أي اسم من القائمة داخل الرد
            for s in scholars:
                if s in text:
                    return s
            if "NONE" in text.upper() or "لا" in text:
                return None
            # لو رجع نص حر وجبناه يشبه اسم
            for s in scholars:
                if s.lower() in text.lower():
                    return s
        except Exception as e:
            logger.warning("Gemini classify failed: %s", e)

    # fallback بسيط: مطابقة نصية في snippet
    snippet_lower = result_snippet.lower()
    for s in scholars:
        if s.lower() in snippet_lower:
            return s
    return None


# ---------------------- منطق المعالجة الرئيسي ----------------------
async def handle_user_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = (update.message.text or "").strip()
    if not user_text:
        return

    chat_id = update.effective_chat.id
    logger.info("Received message from %s: %s", chat_id, user_text)

    # 1) استخراج كلمات مفتاحية عبر Gemini (أو fallback)
    keywords = call_gemini_extract_keywords(user_text)
    logger.info("Keywords: %s", keywords)

    # نركّب عدة استعلامات بحث: العبارة الأصلية + كلمات مفتاحية (نقلل عدد النتائج)
    search_queries = []
    search_queries.append(user_text)
    for k in keywords[:4]:
        search_queries.append(f"{user_text} {k}")

    # 2) بحث Google و YouTube بالتوازي (asyncio.to_thread لأن requests سناب)
    loop = asyncio.get_event_loop()
    tasks = []
    for q in search_queries[:4]:
        tasks.append(loop.run_in_executor(None, google_custom_search, q, 5))
        tasks.append(loop.run_in_executor(None, youtube_search, q, 5))
    done = await asyncio.gather(*tasks, return_exceptions=True)

    # نجمع النتائج في لائحة مسطحة
    google_results = []
    youtube_results = []
    for res in done:
        if isinstance(res, Exception):
            continue
        if not res:
            continue
        # نميّز بنتيجة Google أو YouTube عن طريق الشكل
        if isinstance(res, list) and res and "link" in res[0].keys():
            google_results.extend(res)
        elif isinstance(res, list) and res and "id" in res[0].keys():
            youtube_results.extend(res)
        else:
            # محاولة تحديد محتوى
            for item in res:
                if isinstance(item, dict) and item.get("link"):
                    google_results.append(item)
                elif isinstance(item, dict) and item.get("id"):
                    youtube_results.append(item)

    # 3) نمر على النتائج ونفحص إذا تخص أحد المشايخ
    matched_entries = []

    # فحص نتائج جوجل
    for g in google_results:
        title = g.get("title", "")
        snippet = g.get("snippet", "")
        link = g.get("link") or g.get("formattedUrl") or ""
        preview = f"{title}\n{snippet}\n{link}"
        scholar = call_gemini_classify_if_scholar(preview, SCHOLARS)
        if not scholar:
            continue
        # جلب النص الأصلي من الصفحة
        page_text = await asyncio.get_event_loop().run_in_executor(None, fetch_page_text, link)
        if not page_text:
            # إذا ما قدرنا نجيب النص، نخزن المقتطف
            page_text = snippet or title
        matched_entries.append({
            "scholar": scholar,
            "title": title or snippet or "عنوان غير متوفر",
            "text": page_text,
            "link": link,
        })

    # فحص نتائج يوتيوب
    for y in youtube_results:
        snippet = y.get("snippet", {})
        title = snippet.get("title", "")
        description = snippet.get("description", "") or ""
        video_id = None
        if isinstance(y.get("id"), dict):
            video_id = y["id"].get("videoId")
        elif isinstance(y.get("id"), str):
            video_id = y["id"]
        link = f"https://www.youtube.com/watch?v={video_id}" if video_id else ""

        preview = f"{title}\n{description}\n{link}"
        scholar = call_gemini_classify_if_scholar(preview, SCHOLARS)
        if not scholar:
            continue

        # نحاول نجيب التفريغ (transcript)
        transcript = ""
        if video_id:
            transcript = await asyncio.get_event_loop().run_in_executor(None, get_youtube_transcript, video_id)

        # لو ما كانش transcript، نحاول ناخو الوصف كامل
        final_text = transcript or description or title

        matched_entries.append({
            "scholar": scholar,
            "title": title or "عنوان فيديو",
            "text": final_text,
            "link": link,
        })

    # 4) نرتّب ونرسل النتيجة للمستخدم: فقط الفتاوى اللي لقاها البوت
    if not matched_entries:
        await update.message.reply_text("ما لقيتش فتوى لأي واحد من المشايخ اللي عندي. حاول صياغة السؤال بطريقة أخرى.")
        return

    # نرتّب بحسب اي قنينة: حاليا نبعث كما هو
    # لكن لازم نتأكد من طول الرسائل (تلغرام حدودها ~4096)
    for entry in matched_entries:
        header = f"{entry['scholar']} – {entry['title']} –\n"
        body = entry['text'] or ""
        footer = f"\n\n{entry['link']}"
        full = header + body + footer

        # لو النص طويل نقصّه شوية (لكن المستخدم طلب النص كما هو — نرسل كل ما نقدر)
        chunks = chunk_text(full)
        for c in chunks:
            await update.message.reply_text(c)

    logger.info("Replied with %d matched entries", len(matched_entries))


# أمر /start بسيط
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("بسم الله، بوت المنهج حاضر. كتب السؤال وخلّي الباقي علينا.")


def main():
    if not TELEGRAM_TOKEN:
        logger.error("TELEGRAM_TOKEN not set in env.")
        return

    app = Application.builder().token(TELEGRAM_TOKEN).build()

    # handlers
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_user_message))

    # webhook run (مناسب لـ Render)
    port = int(os.environ.get("PORT", 8080))
    external_host = os.environ.get("RENDER_EXTERNAL_HOSTNAME") or os.environ.get("EXTERNAL_HOSTNAME")
    if not external_host:
        logger.warning("RENDER_EXTERNAL_HOSTNAME not set; webhook URL may be invalid on Render.")
    webhook_url = f"https://{external_host}/{TELEGRAM_TOKEN}" if external_host else None

    if webhook_url:
        logger.info("Starting webhook on port %s, url_path token used.", port)
        app.run_webhook(
            listen="0.0.0.0",
            port=port,
            url_path=TELEGRAM_TOKEN,
            webhook_url=webhook_url,
        )
    else:
        # fallback to polling (مفيد وقت التجربة محليًا)
        logger.info("Starting polling (no webhook URL).")
        app.run_polling()


if __name__ == "__main__":
    main()
