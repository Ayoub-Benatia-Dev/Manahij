# bot.py
import os
import re
import time
import asyncio
import logging
from typing import List, Dict, Optional

import requests
from bs4 import BeautifulSoup

from telegram import Update
from telegram.ext import Application, ContextTypes, CommandHandler, MessageHandler, filters

try:
    import google.generativeai as genai
except Exception:
    genai = None

try:
    from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
except Exception:
    YouTubeTranscriptApi = None
    TranscriptsDisabled = Exception
    NoTranscriptFound = Exception

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GOOGLE_CX = os.getenv("GOOGLE_CX")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

MODEL_NAME = os.getenv("GEMINI_MODEL", "models/gemini-1.5")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
]

if genai and GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        logger.info("Gemini configured (base model name: %s).", MODEL_NAME)
    except Exception as e:
        logger.warning("Gemini configure failed: %s", e)
else:
    logger.info("Gemini not available or GEMINI_API_KEY missing.")

def load_prompt_file(path: str = "prompt.txt") -> str:
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
            return content.strip()
    except FileNotFoundError:
        logger.warning("prompt.txt not found. Using empty instructions.")
        return ""

def clean_text(s: str) -> str:
    if not s:
        return ""
    return re.sub(r"\s+", " ", s).strip()

def chunk_text(text: str, max_size: int = 3900) -> List[str]:
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
            if len(p) > max_size:
                for i in range(0, len(p), max_size):
                    chunks.append(p[i:i + max_size])
                current = ""
            else:
                current = p + "\n"
    if current:
        chunks.append(current)
    return chunks

def google_custom_search(query: str, num: int = 4) -> List[Dict]:
    if not GOOGLE_API_KEY or not GOOGLE_CX:
        return []
    url = "https://www.googleapis.com/customsearch/v1"
    params = {"key": GOOGLE_API_KEY, "cx": GOOGLE_CX, "q": query, "num": num}
    try:
        r = requests.get(url, params=params, timeout=15)
        r.raise_for_status()
        return r.json().get("items", [])
    except Exception as e:
        logger.warning("Google search error for '%s': %s", query, e)
        return []

def youtube_search(query: str, max_results: int = 4) -> List[Dict]:
    if not YOUTUBE_API_KEY:
        return []
    url = "https://www.googleapis.com/youtube/v3/search"
    params = {"part": "snippet", "q": query, "key": YOUTUBE_API_KEY, "type": "video", "maxResults": max_results}
    try:
        r = requests.get(url, params=params, timeout=15)
        r.raise_for_status()
        return r.json().get("items", [])
    except Exception as e:
        logger.warning("YouTube search error for '%s': %s", query, e)
        return []

def fetch_page_text(url: str) -> str:
    try:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; manhaj-bot/1.0)"}
        r = requests.get(url, headers=headers, timeout=15)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        article = soup.find("article") or soup.find("main")
        if article:
            texts = [p.get_text(separator=" ", strip=True) for p in article.find_all(["p", "h1", "h2", "h3"])]
            joined = "\n".join([t for t in texts if t])
            if len(joined) > 200:
                return clean_text(joined)
        ps = [p.get_text(separator=" ", strip=True) for p in soup.find_all("p")]
        joined = "\n".join([t for t in ps if t])
        return clean_text(joined)
    except Exception as e:
        logger.debug("fetch_page_text error: %s", e)
        return ""

def safe_get_youtube_transcript(video_id: str, max_attempts: int = 4) -> str:
    if YouTubeTranscriptApi is None:
        return ""
    wait = 1
    for attempt in range(max_attempts):
        try:
            transcript_list = YouTubeTranscriptApi.get_transcript(video_id, languages=['ar', 'ar-SA', 'en'])
            texts = [t["text"] for t in transcript_list]
            return clean_text("\n".join(texts))
        except (TranscriptsDisabled, NoTranscriptFound):
            logger.info("No transcript available for video %s", video_id)
            return ""
        except Exception as e:
            logger.info("Transcript attempt %d for %s failed: %s", attempt + 1, video_id, e)
            time.sleep(wait)
            wait *= 2
    logger.info("Failed to get transcript for %s after retries.", video_id)
    return ""

def gemini_generate_text(instructions: str, user_prompt: str, max_tokens: int = 300, attempts: int = 3) -> Optional[str]:
    if not genai or not GEMINI_API_KEY:
        return None
    full_input = instructions + "\n\n" + user_prompt if instructions else user_prompt
    for i in range(attempts):
        try:
            resp = genai.generate_text(model=MODEL_NAME, prompt=full_input, max_output_tokens=max_tokens)
            text = getattr(resp, "text", None) or str(resp)
            return text.strip()
        except Exception as e:
            logger.warning("Gemini call attempt %d failed: %s", i + 1, e)
            time.sleep(1 + i * 1.2)
    return None

def call_gemini_extract_keywords(instructions: str, user_text: str) -> List[str]:
    prompt = "استخراج كلمات مفتاحية قصيرة مفيدة للبحث من النص التالي، رجعها مفصولة بفواصل:\n\n" + user_text
    result = gemini_generate_text(instructions, prompt, max_tokens=120)
    if result:
        parts = re.split(r"[,؛\n]+", result)
        keywords = [p.strip() for p in parts if p.strip()]
        return keywords[:12]
    words = re.findall(r"\b[^\W\d_]{4,}\b", user_text)
    freq = {}
    for w in words:
        wlow = w.lower()
        freq[wlow] = freq.get(wlow, 0) + 1
    sorted_words = sorted(freq.items(), key=lambda x: -x[1])
    return [w for w, _ in sorted_words[:8]

def call_gemini_classify_if_scholar(instructions: str, snippet: str, scholars: List[str]) -> Optional[str]:
    prompt = (
        "هل هذا النص أو العنوان ينتمي لفتوى أو كلام واحد من هذه القائمة من المشايخ؟ "
        "أجب باسم الشيخ فقط إن كان من أحدهم، وإلا اكتب NONE.\n\n"
        "قائمة المشايخ:\n" + "\n".join(scholars) + "\n\n"
        f"النص/العنوان:\n{snippet}\n\n"
        "أجب باسم الشيخ أو NONE."
    )
    result = gemini_generate_text(instructions, prompt, max_tokens=80)
    if result:
        text_up = result.upper()
        if "NONE" in text_up:
            return None
        for s in scholars:
            if s in result:
                return s
            if s.lower() in result.lower():
                return s
    snip_low = snippet.lower()
    for s in scholars:
        if s.lower() in snip_low:
            return s
    return None

async def handle_user_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = (update.message.text or "").strip()
    if not user_text:
        return
    logger.info("Received: %s", user_text)

    instructions = load_prompt_file()

    keywords = call_gemini_extract_keywords(instructions, user_text)
    logger.info("Keywords: %s", keywords)

    search_queries = [user_text] + [f"{user_text} {k}" for k in keywords[:3]]

    google_results = []
    youtube_results = []
    for q in search_queries[:3]:
        g = await asyncio.get_event_loop().run_in_executor(None, google_custom_search, q, 3)
        y = await asyncio.get_event_loop().run_in_executor(None, youtube_search, q, 3)
        google_results.extend(g or [])
        youtube_results.extend(y or [])
        await asyncio.sleep(0.6)

    matched_entries = []

    for g in google_results:
        title = g.get("title", "")
        snippet = g.get("snippet", "") or ""
        link = g.get("link") or g.get("formattedUrl") or ""
        preview = f"{title}\n{snippet}\n{link}"
        scholar = call_gemini_classify_if_scholar(instructions, preview, SCHOLARS)
        if not scholar:
            continue
        page_text = await asyncio.get_event_loop().run_in_executor(None, fetch_page_text, link)
        if not page_text:
            page_text = snippet or title
        matched_entries.append({"scholar": scholar, "title": title or snippet, "text": page_text, "link": link})

    for y in youtube_results:
        snippet = y.get("snippet", {}) or {}
        title = snippet.get("title", "")
        description = snippet.get("description", "") or ""
        vid_id = None
        id_field = y.get("id")
        if isinstance(id_field, dict):
            vid_id = id_field.get("videoId")
        elif isinstance(id_field, str):
            vid_id = id_field
        link = f"https://www.youtube.com/watch?v={vid_id}" if vid_id else ""
        preview = f"{title}\n{description}\n{link}"
        scholar = call_gemini_classify_if_scholar(instructions, preview, SCHOLARS)
        if not scholar:
            continue
        transcript = ""
        if vid_id:
            transcript = await asyncio.get_event_loop().run_in_executor(None, safe_get_youtube_transcript, vid_id)
        final_text = transcript or description or title
        matched_entries.append({"scholar": scholar, "title": title or "video", "text": final_text, "link": link})

    if not matched_entries:
        await update.message.reply_text("ما لقيتش فتوى لأي من المشايخ في قائمتي. حاول تصوغ السؤال بطريقة أخرى.")
        return

    for entry in matched_entries:
        header = f"{entry['scholar']} – {entry['title']} –\n"
        body = entry['text'] or ""
        footer = f"\n\n{entry['link']}"
        full = header + body + footer
        for chunk in chunk_text(full):
            await update.message.reply_text(chunk)

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("بسم الله، بوت المنهج حاضر. اكتب سؤالك.")

def main():
    if not TELEGRAM_TOKEN:
        logger.error("TELEGRAM_TOKEN not set.")
        return
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_user_message))

    port = int(os.environ.get("PORT", 8080))
    external_host = os.environ.get("RENDER_EXTERNAL_HOSTNAME") or os.environ.get("EXTERNAL_HOSTNAME")
    webhook_url = f"https://{external_host}/{TELEGRAM_TOKEN}" if external_host else None

    if webhook_url:
        logger.info("Starting webhook on port %s", port)
        app.run_webhook(listen="0.0.0.0", port=port, url_path=TELEGRAM_TOKEN, webhook_url=webhook_url)
    else:
        logger.info("No external host found, starting polling.")
        app.run_polling()

if __name__ == "__main__":
    main()
