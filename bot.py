import os
from telegram.ext import Application, CommandHandler, MessageHandler, filters

TELEGRAM_TOKEN = "8367431259:AAEa_O2BzOQ6cpgX4rdOS3SiTKdvMbWAtQM"
GEMINI_API_KEY = "AIzaSyDGS38J3w0t5cSKXwAQWBG_GUkJL8wdA14"
GOOGLE_API_KEY_1 = "AIzaSyDCay69bExFEAt4y7XEiSK1WmG6KB5l-yw"
YOUTUBE_API_KEY = "AIzaSyBMa4CY_Ndc6RDq2uIDO0nZvhtxvsdF4h4"

async def start(update, context):
    await update.message.reply_text("مرحبا بك في بوت *مناهج*.\nاسأل أي مسألة في العقيدة أو الفقه.")

async def handle_message(update, context):
    question = update.message.text
    # هنا راح تربط بجيميناي API و Google/Youtube API باش تجيب البحث
    await update.message.reply_text(f"سؤالك: {question}\n(جاري البحث ..)")

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()

if __name__ == "__main__":
    main()
