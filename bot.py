import faiss, json, numpy as np
import google.generativeai as genai
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

# مفاتيحك
TELEGRAM_BOT_TOKEN = "8367431259:AAEa_O2BzOQ6cpgX4rdOS3SiTKdvMbWAtQM"
GEMINI_API_KEY = "AIzaSyDGS38J3w0t5cSKXwAQWBG_GUkJL8wdA14"

genai.configure(api_key=GEMINI_API_KEY)
GEN_MODEL = "gemini-1.5-flash"
EMBED_MODEL = "text-embedding-004"

INDEX_PATH = "faiss_index.bin"
META_PATH = "faiss_meta.json"

# تحميل الفهرس إذا متوفر
try:
    index = faiss.read_index(INDEX_PATH)
    meta = json.load(open(META_PATH, encoding="utf-8"))
    DOCS_META, CHUNKS = meta["meta"], meta["chunks"]
except Exception:
    index, DOCS_META, CHUNKS = None, [], []

def embed(q: str):
    v = genai.embed_content(model=EMBED_MODEL, content=q)["embedding"]["values"]
    v = np.array(v, dtype="float32")
    return v / (np.linalg.norm(v) + 1e-12)

def retrieve(query, k=5):
    if not index:
        return []
    v = embed(query).reshape(1, -1)
    sims, idxs = index.search(v, k)
    results = []
    for sim, ix in zip(sims[0], idxs[0]):
        results.append({"text": CHUNKS[ix], "source": DOCS_META[ix]["source"]})
    return results

def answer(query):
    ctx = ""
    docs = retrieve(query)
    for d in docs:
        ctx += f"[{d['source']}] {d['text']}\n"
    prompt = f"""
أجب جواباً سلفياً بالكتاب والسنة وأقوال العلماء الثقات فقط.
السؤال: {query}
المراجع:
{ctx}
"""
    res = genai.GenerativeModel(GEN_MODEL).generate_content(prompt)
    return res.text.strip()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("السلام عليكم! أرسل سؤالك.")

async def handle_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.message.text
    a = answer(q)
    await update.message.reply_text(a[:4000])

def main():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_msg))
    print("Bot running...")
    app.run_polling()

if __name__ == "__main__":
    main()
