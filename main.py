import os
import nest_asyncio
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from telegram import Update
from datetime import datetime
from decimal import Decimal
from web3 import Web3

nest_asyncio.apply()

# ✅ Load ENV variables
INFURA_URL = os.getenv("INFURA_URL")
WALLET_ADDRESS_ETH = os.getenv("WALLET_ADDRESS_ETH")
PRIVATE_KEY_ETH = os.getenv("PRIVATE_KEY_ETH")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

# ✅ Setup Web3
w3 = Web3(Web3.HTTPProvider(INFURA_URL))

# ✅ Profit tracking
daily_profits = {}
auto_trade_enabled = True  # default ON

# ✅ Command: /profit 50
async def add_profit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 1:
        return await update.message.reply_text("Usage: /profit 50")
    amount = Decimal(context.args[0])
    today = datetime.now().strftime("%Y-%m-%d")
    if today not in daily_profits:
        daily_profits[today] = Decimal("0")
    daily_profits[today] += amount
    await update.message.reply_text(f"✅ Profit added: ${amount} for {today}")

# ✅ Command: /profits
async def view_profits(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not daily_profits:
        return await update.message.reply_text("🚫 No profits recorded.")
    msg = "📊 Daily Profits:\n"
    for day, amount in daily_profits.items():
        msg += f"{day}: ${amount}\n"
    await update.message.reply_text(msg)

# ✅ Command: /withdraw_eth 0.01 0xYourOtherAddress
async def withdraw_eth(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 2:
        return await update.message.reply_text("Usage: /withdraw_eth 0.01 0xYourOtherAddress")
    try:
        amount = Decimal(context.args[0])
        to_address = context.args[1]
        nonce = w3.eth.get_transaction_count(WALLET_ADDRESS_ETH)
        tx = {
            'nonce': nonce,
            'to': to_address,
            'value': w3.to_wei(amount, 'ether'),
            'gas': 21000,
            'gasPrice': w3.to_wei('50', 'gwei')
        }
        signed_tx = w3.eth.account.sign_transaction(tx, private_key=PRIVATE_KEY_ETH)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.rawTransaction)
        await update.message.reply_text(f"✅ Withdraw Success: {w3.to_hex(tx_hash)}")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")

# ✅ Command: /autotrade (toggle ON/OFF)
async def toggle_auto_trade(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global auto_trade_enabled
    auto_trade_enabled = not auto_trade_enabled
    status = "✅ ON" if auto_trade_enabled else "⛔ OFF"
    await update.message.reply_text(f"Auto-Trade is now: {status}")

from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
import threading
import os
import nest_asyncio
nest_asyncio.apply()

# ✅ ENV Variables
INFURA_URL = os.getenv("INFURA_URL")
WALLET_ADDRESS_ETH = os.getenv("WALLET_ADDRESS_ETH")
PRIVATE_KEY_ETH = os.getenv("PRIVATE_KEY_ETH")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

# ✅ Telegram App
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

# ✅ Start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Welcome! Bot is now active.")

# ✅ Push notify command (manual test)
async def notify(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = "🚨 New Trade Opportunity!\nPair: GOLD\nTime: 5min\nStatus: ⬆️ BUY Setup"
    buttons = [[
        InlineKeyboardButton("✅ Confirm", callback_data="CONFIRM:GOLD:BUY"),
        InlineKeyboardButton("❌ Ignore", callback_data="IGNORE")
    ]]
    markup = InlineKeyboardMarkup(buttons)
    await update.message.reply_text(msg, reply_markup=markup)

# ✅ Button click handler
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data.startswith("CONFIRM"):
        _, symbol, direction = query.data.split(":")
        await query.edit_message_text(text=f"✅ Confirmed: {symbol} → {direction}")
    elif query.data == "IGNORE":
        await query.edit_message_text(text="❌ Signal ignored.")

# ✅ Register commands
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("notify", notify))
app.add_handler(CallbackQueryHandler(button_handler))

# ✅ Flask + Webhook route
flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return "Bot is running!"

@flask_app.route('/webhook', methods=["POST"])
def webhook_handler():
    try:
        data = request.get_json()
        symbol = data.get("symbol", "Unknown")
        direction = data.get("direction", "BUY/SELL")
        time_frame = data.get("time", "5min")

        msg = f"🚨 Signal Received!\nPair: {symbol}\nTime: {time_frame}\nDirection: {direction}"
        buttons = [[
            InlineKeyboardButton("✅ Confirm", callback_data=f"CONFIRM:{symbol}:{direction}"),
            InlineKeyboardButton("❌ Ignore", callback_data="IGNORE")
        ]]
        markup = InlineKeyboardMarkup(buttons)

        # ✅ Bedel CHAT ID hoose
        app.bot.send_message(chat_id=CHAT_ID, text=msg, reply_markup=markup)
        return "✅ Signal sent"
    except Exception as e:
        return f"❌ Error: {str(e)}"

# ✅ Run Flask thread + bot
def run_flask():
    flask_app.run(host='0.0.0.0', port=10000)

threading.Thread(target=run_flask).start()
app.run_polling()

# ✅ Run bot
app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
app.add_handler(CommandHandler("profit", add_profit))
app.add_handler(CommandHandler("profits", view_profits))
app.add_handler(CommandHandler("withdraw_eth", withdraw_eth))
app.add_handler(CommandHandler("autotrade", toggle_auto_trade))

if __name__ == '__main__':
    app.run_polling()
