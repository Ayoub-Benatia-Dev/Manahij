# bot.py
# بوت تليجرام متكامل: يقرأ prompt.txt => يوجه Gemini => يبحث في Google + YouTube => يفلتر على المشايخ => يجيب النص الأصلي
# متطلبات: TELEGRAM_TOKEN, GOOGLE_API_KEY, GOOGLE_CX, YOUTUBE_API_KEY, GEMINI_API_KEY (env vars)
# Start: python bot.py

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

# محاولة استيراد مكتبة Gemini الرسمية (google.generativeai)
try:
    import google.generativeai as genai
except Exception:
    genai = None

# محاولة استيراد youtube_transcript_api
try:
    from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
except Exception:
    YouTubeTranscriptApi = None
    TranscriptsDisabled = Exception
    NoTranscriptFound = Exception

# ---------------- Config ----------------
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GOOGLE_CX = os.getenv("GOOGLE_CX")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Important: model name MUST start with "models/" or "tunedModels/"
MODEL_NAME = os.getenv("GEMINI_MODEL", "models/gemini-1.5")

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Scholars list (عدلها كيما تحب)
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

# ---------------- Init Gemini ----------------
if genai and GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        logger.info("Gemini configured (base model name: %s).", MODEL_NAME)
    except Exception as e:
        logger.warning("Gemini configure failed: %s", e)
else:
    logger.info("Gemini not available or GEMINI_API_KEY missing.")

# ---------------- Prompt file loader ----------------
def load_prompt_file(path: str = "prompt.txt") -> str:
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
            return content.strip()
    except FileNotFoundError:
        logger.warning("prompt.txt not found. Using empty instructions.")
        return ""

# ---------------- Utilities ----------------
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

# ---------------- Search functions ----------------
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

# ---------------- Fetch page text ----------------
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

# ---------------- YouTube transcript safe ----------------
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

# ---------------- Gemini wrappers (تستخدم prompt_file) ----------------
def gemini_generate_text(instructions: str, user_prompt: str, max_tokens: int = 300, attempts: int = 3) -> Optional[str]:
    """
    Send instructions (from prompt.txt) + user_prompt to Gemini and return text.
    """
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

def call_gemini_extract_keywords(instru_
