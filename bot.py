import requests
from bs4 import BeautifulSoup
from telegram.ext import Application, CommandHandler, MessageHandler, filters

# ---- API KEYS ----
TELEGRAM_TOKEN = "8367431259:AAEa_O2BzOQ6cpgX4rdOS3SiTKdvMbWAtQM"
GOOGLE_API_KEY = "AIzaSyDCay69bExFEAt4y7XEiSK1WmG6KB5l-yw"
YOUTUBE_API_KEY = "AIzaSyBMa4CY_Ndc6RDq2uIDO0nZvhtxvsdF4h4"
GOOGLE_CX = "369d6d61d01414942"

# ---- قائمة العلماء الموثوقين ----
trusted_keywords = [
    "الشيخ ربيع المدخلي", "الشيخ عبيد الجابري", "الشيخ صالح الفوزان",
    "الشيخ صالح اللحيدان", "الشيخ عبدالمحسن العباد البدر", "الشيخ محمد بن هادي المدخلي",
    "الشيخ عبد العزيز آل الشيخ", "الشيخ محمد سعيد رسلان", "الشيخ البرعي اليمني",
    "الشيخ عبد الرزاق عفيفي", "الشيخ حسن بن عبد الوهاب البنا السلفي", "الشيخ البهكلي",
    "الشيخ الأمين الشنقيطي الجكني", "الشيخ عبد الرحمن العميسان", "الشيخ سليمان الرحيل",
    "الشيخ عايد بن خليفة الشمري", "الشيخ محمد بن رمضان الهاجري", "الشيخ صالح آل الشيخ",
    "الشيخ عبدالرزاق البدر", "الشيخ محمد العنجرى", "الشيخ عبد الرحمن الوكيل",
    "الشيخ محمد العقيل", "الشيخ فلاح مندكار", "الشيخ محمد بن ربيع المدخلي",
    "الشيخ جمال الحارثي", "الشيخ أسامة بن زيد المدخلي", "الشيخ مزمل فقيري",
    "الشيخ أبو بكر آداب", "الشيخ خالد عثمان المصري", "الشيخ عزيز فريحان",
    "الشيخ حمد العثمان", "الشيخ خالد بن عبد الرحمن ال زكي", "الشيخ محمود شاكر",
    "الشيخ علي بن زيد المدخلي", "الشيخ البشير الإبراهيمي", "الشيخ عبد الحميد بن باديس",
    "الشيخ مبارك الميلي", "الشيخ الطيب العقبي", "الشيخ عادل الشوريجي",
    "الشيخ عادل السيد", "الشيخ صفي الرحمن المباركفوري", "الشيخ أبو عبد الأعلى المصري",
    "الشيخ تقي الدين الهلالي", "الشيخ نعمان الوتر", "الشيخ أبو أسامة مصطفى بن وقليل",
    "الشيخ سالم موريدا", "الشيخ عبد القادر بن محمد الجنيد", "الشيخ صالح السندي",
    "الشيخ دغش العجمي", "الشيخ الأمر تسري", "الشيخ محمد غيث", "الشيخ علي الحذيفي",
    "الشيخ محمد بن زيد المدخلي", "الشيخ عبد محمد الإمام", "الشيخ صالح العصيمي",
    "الشيخ علي الحدادي", "الشيخ عادل المشوري", "الشيخ عثمان السالمي",
    "الشيخ عادل منصور الباشا", "الشيخ محمد الفيفي", "الشيخ عبدالسلام السحيمي",
    "الشيخ صالح السحيمي", "الشيخ محمد بازمول", "الشيخ سعد الحصين",
    "الشيخ أحمد بازمول", "الشيخ عبد الرزاق حمزة", "الشيخ إبراهيم محمد كشيدان",
    "الشيخ سعد بن ناصر الشثري", "الشيخ عبد السلام الشويعر", "الشيخ عبد الله الوصابي",
    "العلامة محمد بن أمان الجامي", "العلامة عبدالعزيز بن باز", "العلامة محمد ابن صالح العثيمين",
    "العلامة محمد ناصر الألباني", "العلامة محمد أحمد الألباني", "العلامة أحمد النجمي",
    "العلامة زيد المدخلي", "الشيخ عبد السلام بن برجس آل عبد الكريم",
    "الشيخ عبد الله بن حميد", "العلامة مقبل بن هادي الوادعي", "العلامة عمر بن محمد فلاته",
    "الشيخ محمد بن إسماعيل الصنعاني", "الشيخ محمد بن إبراهيم الوزير", 
    "الشيخ عبد الرحمن المعلمي اليمني", "الشيخ محمد بن عليص الشوكاني",
    "الشيخ حافظ الحكمي", "العلامة أحمد شاكر", "العلامة حامد الفقي",
    "الشيخ محمد خليل هراس", "الشيخ عبدالله الغديان", "الشيخ عبد الله القرعاوي"
]

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

# ---- SIMPLE FILTER ----
def simple_filter(results):
    filtered = []
    for r in results:
        text = r.get('snippet', '') + " " + r['title']
        for keyword in trusted_keywords:
            if keyword in text:
                filtered.append(r)
                break
    return filtered

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

    filtered = simple_filter(combined)

    if not filtered:
        await update.message.reply_text("📖 لم يتم العثور على نتائج موثوقة للعلماء السلفيين.")
    else:
        msg = ""
        for r in filtered:
            msg += f"📌 {r['title']}\n🔗 {r['link']}\n\n"
        await update.message.reply_text(msg)

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
