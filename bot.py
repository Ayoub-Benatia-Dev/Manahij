import requests
from bs4 import BeautifulSoup
from telegram.ext import Application, CommandHandler, MessageHandler, filters

# ---- API KEYS ----
TELEGRAM_TOKEN = "8367431259:AAEa_O2BzOQ6cpgX4rdOS3SiTKdvMbWAtQM"
GOOGLE_API_KEY = "AIzaSyDCay69bExFEAt4y7XEiSK1WmG6KB5l-yw"
YOUTUBE_API_KEY = "AIzaSyBMa4CY_Ndc6RDq2uIDO0nZvhtxvsdF4h4"
GOOGLE_CX = "369d6d61d01414942"
GEMINI_API_KEY = "AIzaSyDGS38J3w0t5cSKXwAQWBG_GUkJL8wdA14"

# ---- HELPER FUNCTIONS ----
def get_page_text(url):
    try:
        r = requests.get(url, timeout=5)
        soup = BeautifulSoup(r.text, "html.parser")
        p = soup.find('p')
        if p:
            return p.get_text()[:250] + "..."
        return ""
    except:
        return ""

# ---- GOOGLE SEARCH ----
def search_google(query: str):
    url = f"https://www.googleapis.com/customsearch/v1?q={query}&key={GOOGLE_API_KEY}&cx={GOOGLE_CX}"
    try:
        r = requests.get(url)
        results = r.json().get("items", [])
        if not results:
            return []
        search_results = []
        for result in results[:5]:
            link = result['link']
            title = result['title']
            snippet = get_page_text(link)
            search_results.append({"title": title, "link": link, "snippet": snippet})
        return search_results
    except:
        return []

# ---- YOUTUBE SEARCH ----
def search_youtube(query: str):
    url = f"https://www.googleapis.com/youtube/v3/search?part=snippet&q={query}&key={YOUTUBE_API_KEY}&maxResults=5&type=video"
    try:
        r = requests.get(url)
        items = r.json().get("items", [])
        videos = []
        for item in items:
            video_id = item["id"]["videoId"]
            title = item["snippet"]["title"]
            videos.append({"title": title, "link": f"https://www.youtube.com/watch?v={video_id}"})
        return videos
    except:
        return []

# ---- GEMINI FILTER & SORT ----
def gemini_filter_sort(results):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={GEMINI_API_KEY}"
    prompt = "قم بفرز هذه النتائج بحيث تُبقي فقط المصادر الموثوقة علمياً وسلفياً، وتجاهل أي محتوى فيه شبهات أو ضلال:\n\n"
    for r in results:
        snippet = r.get('snippet', '')  # لو مش موجود نخلي نص فارغ
        prompt += f"{r['title']}\n{r['link']}\n{snippet}\n\n"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}]
    }
    try:
        response = requests.post(url, json=payload)
        data = response.json()
        filtered_text = data["candidates"][0]["content"]["parts"][0]["text"]
        return filtered_text
    except:
        return "لم يتمكن النظام من فلترة النتائج."

# ---- TELEGRAM BOT ----
async def start(update, context):
    await update.message.reply_text(
        "📚 مرحبا بك في *بوت مناهج*.\nاكتب سؤالك وسيتم البحث وفلترة النتائج."
    )

async def handle_message(update, context):
    question = update.message.text
    await update.message.reply_text("⏳ جاري البحث .. استنى شوي")

    google_results = search_google(question)
    youtube_results = search_youtube(question)

    combined = google_results + youtube_results
    filtered = gemini_filter_sort(combined)

    await update.message.reply_text(f"📖 *نتائج البحث المصفاة:*\n{filtered}", parse_mode="Markdown")

# ---- MAIN ----
if __name__ == "__main__":
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    app.run_webhook(
        listen="0.0.0.0",
        port=10000,
        url_path=TELEGRAM_TOKEN,
        webhook_url=f"https://manhaj-bot.onrender.com/{TELEGRAM_TOKEN}"
    )
