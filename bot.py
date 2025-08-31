# bot.py  -- webhook version + Google Custom Search + YouTube search
import os
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

import requests

# ---------- مفاتيح (موجودين هنا حسب اللي عطيتني) ----------
TELEGRAM_TOKEN = "8367431259:AAEa_O2BzOQ6cpgX4rdOS3SiTKdvMbWAtQM"
GOOGLE_API_KEY   = "AIzaSyDCay69bExFEAt4y7XEiSK1WmG6KB5l-yw"   # انت عطيت هاذي
YOUTUBE_API_KEY  = "AIzaSyBMa4CY_Ndc6RDq2uIDO0nZvhtxvsdF4h4"  # انت عطيت هاذي
CX_ID = "PUT_YOUR_CX_ID_HERE"  # لازم تعوضها بالـ CSE ID تاعك من cse.google.com

# ---------- دوال البحث ----------
def google_search(query, max_results=3):
    if CX_ID == "PUT_YOUR_CX_ID_HERE":
        return "❗ لازم تدخل CX_ID (معرّف محرك البحث المخصّص). راني مبينش المصادر بدونو."
    url = "https://www.googleapis.com/customsearch/v1"
    params = {"key": GOOGLE_API_KEY, "cx": CX_ID, "q": query, "num": max_results}
    r = requests.get(url, params=params, timeout=15)
    if r.status_code != 200:
        return f"❌ خطأ من Google Search API: {r.status_code}"
    data = r.json()
    items = data.get("items", [])
    if not items:
        return "ما لقيتش نتائج في جوجل."
    out = []
    for it in items:
        title = it.get("title", "No title")
        snippet = it.get("snippet", "")
        link = it.get("link", "")
        out.append(f"📌 *{title}*\n{snippet}\n🔗 {link}\n")
    return "\n".join(out)

def youtube_search(query, max_results=3):
    url = "https://www.googleapis.com/youtube/v3/search"
    params = {"part": "snippet", "q": query, "key": YOUTUBE_API_KEY, "maxResults": max_results, "type": "video"}
    r = requests.get(url, params=params, timeout=15)
    if r.status_code != 200:
        return f"❌ خطأ من YouTube API: {r.status_code}"
    data = r.json()
    items = data.get("items", [])
    if not items:
        return "ما لقيتش فيديوهات في يوتيوب."
    out = []
    for it in items:
        title = it["snippet"].get("title", "No title")
        vid = it["id"].get("videoId")
        if vid:
            out.append(f"🎬 *{title}*\n🔗 https://www.youtube.com/watch?v={vid}\n")
    return "\n".join(out)

# ---------- handlers ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("السلام عليكم — راني هنا نبحث في Google وYouTube. اطرح سؤالك.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()
    lower = text.lower()
    # لو في كلمات تورّينا يطلب فيديو
    if any(k in lower for k in ["يوتيوب", "مقطع", "محاضرة", "فيديو", "شرح"]):
        res = youtube_search(text)
    else:
        res = google_search(text)
    # لو كبير بزاف نقصو (تلغرام يقبل ~4096 حرف)
    if len(res) > 3800:
        res = res[:3800] + "\n\n...(مقتطف)"
    await update.message.reply_text(res, parse_mode="Markdown", disable_web_page_preview=False)

# ---------- تهيئة التطبيق ----------
app = Application.builder().token(TELEGRAM_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

# ---------- webhook endpoint (Run with Render) ----------
if __name__ == "__main__":
    PORT = int(os.environ.get("PORT", 443))
    # run webhook: يقوم بتسجيل الـ webhook عند تشغيله
    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=TELEGRAM_TOKEN,
        webhook_url=f"https://manhaj-bot.onrender.com/{TELEGRAM_TOKEN}"
    )
