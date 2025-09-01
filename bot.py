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
    "إبراهيم محمد كشيدان",
    "Ibrahim Muhammad Kashidan",
    "أحمد بازمول",
    "Ahmad Bazmul",
    "أحمد شاكر",
    "Ahmad Shakir",
    "أحمد النجمي",
    "Ahmad al-Najmi",
    "أسامة بن زيد المدخلي",
    "Usama ibn Zayd al-Madkhali",
    "الأمين الشنقيطي الجكني",
    "al-Amin al-Shinqiti al-Jakni",
    "الأمر تسري",
    "al-Amr Tasri",
    "البشير الإبراهيمي",
    "al-Bashir al-Ibrahimi",
    "البهكلي",
    "al-Bahkali",
    "البرعي اليمني",
    "al-Burai al-Yamani",
    "الطيب العقبي",
    "al-Tayyib al-Uqbi",
    "جمال الحارثي",
    "Jamal al-Harithi",
    "حافظ الحكمي",
    "Hafiz al-Hakami",
    "حامد الفقي",
    "Hamid al-Faqi",
    "حسن بن عبد الوهاب البنا السلفي",
    "Hassan ibn Abdul Wahhab al-Banna al-Salafi",
    "حمد العثمان",
    "Hamad al-Uthman",
    "خالد بن عبد الرحمن ال زكي",
    "Khalid ibn Abdul Rahman Al al-Zaki",
    "خالد عثمان المصري",
    "Khalid Uthman al-Masri",
    "دغش العجمي",
    "Daghash al-Ajmi",
    "ربيع المدخلي",
    "Rabee' al-Madkhali",
    "زيد المدخلي",
    "Zayd al-Madkhali",
    "سالم موريدا",
    "Salim Mawrida",
    "سعد الحصين",
    "Saad al-Hussain",
    "سعد بن ناصر الشثري",
    "Saad ibn Nasser al-Shathri",
    "سليمان الرحيل",
    "Sulaiman al-Rahil",
    "صالح آل الشيخ",
    "Salih Al al-Sheikh",
    "صالح السحيمي",
    "Salih al-Suhaimi",
    "صالح السندي",
    "Salih al-Sindi",
    "صالح العصيمي",
    "Salih al-Usaymi",
    "صالح الفوزان",
    "Salih al-Fawzan",
    "صالح اللحيدان",
    "Salih al-Luhaidan",
    "صفي الرحمن المباركفوري",
    "Safi al-Rahman al-Mubarakpuri",
    "عادل السيد",
    "Adil al-Sayyid",
    "عادل الشوريجي",
    "Adil al-Shuraiji",
    "عادل المشوري",
    "Adil al-Mashuri",
    "عادل منصور الباشا",
    "Adil Mansur al-Basha",
    "عايد بن خليفة الشمري",
    "Ayed bin Khalifa al-Shammari",
    "عبد الرحمن المعلمي اليمني",
    "Abdul Rahman al-Mu'allimi al-Yamani",
    "عبد الرحمن العميسان",
    "Abdurrahman al-Umeisan",
    "عبد الرحمن الوكيل",
    "Abdul Rahman al-Wakil",
    "عبد السلام الشويعر",
    "Abdul Salam al-Shuwair",
    "عبد السلام بن برجس آل عبد الكريم",
    "Abdul Salam ibn Barjis Al Abdul Karim",
    "عبد السلام السحيمي",
    "Abdussalam al-Suhaimi",
    "عبد العزيز آل الشيخ",
    "Abdul Aziz Al al-Sheikh",
    "عبد العزيز بن باز",
    "Abdulaziz ibn Baz",
    "عبد القادر بن محمد الجنيد",
    "Abdul Qadir ibn Muhammad al-Junayd",
    "عبد الله القرعاوي",
    "Abdullah al-Qar'awi",
    "عبد الله بن حميد",
    "Abdullah ibn Humaid",
    "عبد الله الوصابي",
    "Abdullah al-Wassabi",
    "عبد الله الغديان",
    "Abdullah al-Ghudayyan",
    "عبد المحسن العباد البدر",
    "Abdul Muhsin al-Abbad al-Badr",
    "عبد الحميد بن باديس",
    "Abdul Hamid ibn Badis",
    "عبد الرزاق حمزة",
    "Abdul Razzaq Hamza",
    "عبد الرزاق عفيفي",
    "Abdur Razzaq Afifi",
    "عبد الرزاق البدر",
    "Abdul Razzaq al-Badr",
    "عبد محمد الإمام",
    "Abd Muhammad al-Imam",
    "عبيد الجابري",
    "Ubayd al-Jabri",
    "عزيز فريحان",
    "Aziz Furayhan",
    "علي الحدادي",
    "Ali al-Haddadi",
    "علي الحذيفي",
    "Ali al-Huthayfi",
    "علي بن زيد المدخلي",
    "Ali ibn Zayd al-Madkhali",
    "عمر بن محمد فلاته",
    "Umar ibn Muhammad Fallata",
    "عثمان السالمي",
    "Uthman al-Salimi",
    "فلاح مندكار",
    "Fallah Mandakar",
    "مبارك الميلي",
    "Mubarak al-Mili",
    "مزمل فقيري",
    "Muzammil Faqiri",
    "محمود شاكر",
    "Mahmud Shakir",
    "محمد ابن صالح العثيمين",
    "Muhammad ibn Salih al-Uthaymin",
    "محمد بازمول",
    "Muhammad Bazmul",
    "محمد خليل هراس",
    "Muhammad Khalil Haras",
    "محمد سعيد رسلان",
    "Muhammad Saeed Raslan",
    "محمد غيث",
    "Muhammad Ghayth",
    "محمد الفيفي",
    "Muhammad al-Fayfi",
    "محمد العقيل",
    "Muhammad al-Aqeel",
    "محمد العنجرى",
    "Muhammad al-Anjari",
    "محمد ناصر الألباني",
    "Muhammad Nasser al-Albani",
    "محمد أحمد الألباني",
    "Muhammad Ahmad al-Albani",
    "محمد بن إبراهيم الوزير",
    "Muhammad ibn Ibrahim al-Wazir",
    "محمد بن إسماعيل الصنعاني",
    "Muhammad ibn Ismail al-San'ani",
    "محمد بن زيد المدخلي",
    "Muhammad ibn Zayd al-Madkhali",
    "محمد بن عليص الشوكاني",
    "Muhammad ibn Ali al-Shawkani",
    "محمد بن أمان الجامي",
    "Muhammad ibn Aman al-Jami",
    "محمد بن هادي المدخلي",
    "Muhammad ibn Hadi al-Madkhali",
    "محمد بن رمضان الهاجري",
    "Muhammad ibn Ramadan al-Hajri",
    "محمد بن ربيع المدخلي",
    "Muhammad ibn Rabee' al-Madkhali",
    "مقبل بن هادي الوادعي",
    "Muqbil ibn Hadi al-Wadi'i",
    "نعمان الوتر",
    "Nu'man al-Witr"
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

