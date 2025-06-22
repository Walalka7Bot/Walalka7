import os
from telegram.ext import Application, CommandHandler
from dotenv import load_dotenv

# ✅ Load .env file
load_dotenv()
TOKEN = os.getenv("TELEGRAM_TOKEN")

# ✅ Bot function
async def start(update, context):
    await update.message.reply_text("✅ Hussein7 Tradebot wuu shaqeynayaa!")

# ✅ Setup bot
app = Application.builder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))

# ✅ Run bot
app.run_polling()
