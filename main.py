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
# ✅ CUTUBKA 11: Daily Report Generator (Single File)
import os, json, asyncio
from datetime import datetime
from fpdf import FPDF
from apscheduler.schedulers.background import BackgroundScheduler
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler

LOG_FILE = "daily_trades.json"
CHAT_ID = os.getenv("CHAT_ID")

# 1️⃣ Trade Logger
def log_trade_result(symbol, result, pnl):
    today = datetime.now().strftime("%Y-%m-%d")
    log_entry = {"date": today, "symbol": symbol, "result": result, "pnl": pnl}

    try:
        with open(LOG_FILE, "r") as f:
            data = json.load(f)
    except (FileNotFoundError, json.decoder.JSONDecodeError):
        data = []

    data.append(log_entry)

    with open(LOG_FILE, "w") as f:
        json.dump(data, f, indent=2)

# 2️⃣ PDF Generator
def generate_daily_report():
    today = datetime.now().strftime("%Y-%m-%d")
    try:
        with open(LOG_FILE, "r") as f:
            data = json.load(f)
    except:
        return None

    today_trades = [d for d in data if d["date"] == today]
    if not today_trades:
        return None

    win_count = sum(1 for d in today_trades if d["result"].upper() == "WIN")
    loss_count = sum(1 for d in today_trades if d["result"].upper() == "LOSS")
    total_pnl = sum(float(d["pnl"]) for d in today_trades)

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=14)
    pdf.cell(200, 10, txt=f"📊 Daily Report – {today}", ln=True, align='C')
    pdf.ln(10)

    for trade in today_trades:
        line = f"{trade['symbol']} - {trade['result']} - P&L: ${trade['pnl']}"
        pdf.cell(200, 10, txt=line, ln=True)

    pdf.ln(10)
    pdf.cell(200, 10, txt=f"✅ Wins: {win_count} | ❌ Losses: {loss_count} | 💰 Net P&L: ${round(total_pnl, 2)}", ln=True)

    file_path = f"report_{today}.pdf"
    pdf.output(file_path)
    return file_path

# 3️⃣ /report Command Handler
async def report_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pdf_path = generate_daily_report()
    if not pdf_path:
        await update.message.reply_text("⚠️ Ma jiro report maanta.")
        return

    with open(pdf_path, "rb") as f:
        await context.bot.send_document(chat_id=update.effective_chat.id, document=f, filename=pdf_path)

# ✅ Add this in your main.py:
# app.add_handler(CommandHandler("report", report_command))

# 4️⃣ Automatic Schedule @ 23:59
def schedule_daily_report(bot):
    scheduler = BackgroundScheduler()

    def job():
        pdf_path = generate_daily_report()
        if pdf_path and CHAT_ID:
            asyncio.run(bot.send_document(chat_id=CHAT_ID, document=open(pdf_path, "rb"), filename=pdf_path))

    scheduler.add_job(job, 'cron', hour=23, minute=59)
    scheduler.start()
## ✅ Cutubka 12: Trade Result Buttons (WIN / LOSS / BE)

### 🎯 Ujeeddo
Markaad gujiso `Confirm` signal-ka, bot-ku wuxuu kuusoo bandhigayaa **3 buttons** si aad u sheegto natiijada ganacsiga:

- ✅ `WIN`
- ❌ `LOSS`
- 🤝 `BE` (Breakeven)

Bot-ka wuxuu si toos ah:
- U keydiyaa result-kii
- U xisaabiyaa P&L
- U diiwaangeliyaa file JSON ah (`daily_trades.json`)
- Waxaana lagu dari karaa `PDF` report-ka habeen kasta 23:59

---

### 🧠 Tallaabooyinka Code-ka:

#### ✅ Update `signal_webhook` – Add callback to "Confirm"

```python
buttons = [[
    InlineKeyboardButton("✅ Confirm", callback_data=f"CONFIRM:{symbol}:{direction}"),
    InlineKeyboardButton("❌ Ignore", callback_data="IGNORE")
]]
```

#### ✅ Add Callback for "CONFIRM" – Show Result Options

```python
@app.callback_query_handler(lambda c: c.data and c.data.startswith("CONFIRM:"))
async def handle_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    _, symbol, direction = query.data.split(":")

    buttons = [
        [
            InlineKeyboardButton("✅ WIN", callback_data=f"RESULT:WIN:{symbol}"),
            InlineKeyboardButton("❌ LOSS", callback_data=f"RESULT:LOSS:{symbol}"),
            InlineKeyboardButton("🤝 BE", callback_data=f"RESULT:BE:{symbol}")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(buttons)
    await query.message.reply_text(f"📊 What was the result for {symbol}?", reply_markup=reply_markup)
```

#### ✅ Handle Result Selection + Save to JSON

```python
import json
from datetime import datetime

DAILY_LOG = "daily_trades.json"

@app.callback_query_handler(lambda c: c.data and c.data.startswith("RESULT:"))
async def handle_result(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    _, result, symbol = query.data.split(":")
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

    trade_entry = {
        "symbol": symbol,
        "result": result,
        "time": timestamp
    }

    try:
        with open(DAILY_LOG, "r") as f:
            data = json.load(f)
    except:
        data = []

    data.append(trade_entry)

    with open(DAILY_LOG, "w") as f:
        json.dump(data, f, indent=2)

    await query.message.reply_text(f"✅ Result saved: {symbol} → {result}")
```

---

### 🧾 Tusaale JSON Format:
```json
[
  {
    "symbol": "EURUSD",
    "result": "WIN",
    "time": "2025-06-25 15:15"
  }
]
```

---

## 🔄 Xiriir la leh:
- ✅ **Cutubka 11**: Jadwal PDF report oo uu ka akhrisanayo file-ka `daily_trades.json`
- ✅ **Cutubka 10**: Auto Lot Calculation si aad ugu xisaabiso result kasta
# ✅ Cutubka 13: Memecoin Detector + Auto Halal Filter
# Waxay raadisaa memecoins cusub, u diraa Telegram signal + halal status, wallet & chain info

import requests, asyncio
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import CommandHandler
from apscheduler.schedulers.background import BackgroundScheduler

# 🔒 Halal filter keywords
HARAM_KEYWORDS = ["casino", "bet", "gamble", "loan", "alcohol", "riba", "sex"]

# 🔎 Halal Checker
def is_halal_coin(symbol: str) -> bool:
    return not any(haram in symbol.lower() for haram in HARAM_KEYWORDS)

# 📡 Fetch trending memecoins (from DEXscreener sample API)
def fetch_trending_coins():
    try:
        response = requests.get("https://api.dexscreener.com/latest/dex/pairs")
        data = response.json()

        coins = []
        for pair in data.get("pairs", [])[:5]:  # Top 5 only
            coin = {
                "name": pair["baseToken"]["name"],
                "symbol": pair["baseToken"]["symbol"],
                "chain": pair["chainId"],
                "wallet": pair["pairAddress"],
                "image": pair.get("imageUrl", None)
            }
            coins.append(coin)

        return coins
    except Exception as e:
        print(f"Memecoin fetch error: {e}")
        return []

# 🚀 Send Telegram Alert with Halal status
async def send_memecoin_alert(app, chat_id):
    trending = fetch_trending_coins()
    for coin in trending:
        status = "🟢 Halal" if is_halal_coin(coin["symbol"]) else "🔴 Haram"
        msg = (
            f"🚀 *Trending Memecoin Alert!*\n\n"
            f"Name: {coin['name']}\n"
            f"Symbol: `{coin['symbol']}`\n"
            f"Chain: {coin['chain']}\n"
            f"Wallet: `{coin['wallet']}`\n"
            f"Status: {status}"
        )

        buttons = [[
            InlineKeyboardButton("🧾 View on DexTools", url=f"https://www.dexscreener.com/{coin['chain']}/{coin['wallet']}"),
            InlineKeyboardButton("📥 Add to Watchlist", callback_data=f"WATCH_{coin['symbol']}")
        ]]
        reply_markup = InlineKeyboardMarkup(buttons)

        try:
            if coin["image"]:
                await app.bot.send_photo(chat_id=chat_id, photo=coin["image"], caption=msg, parse_mode="Markdown", reply_markup=reply_markup)
            else:
                await app.bot.send_message(chat_id=chat_id, text=msg, parse_mode="Markdown", reply_markup=reply_markup)
        except Exception as e:
            print(f"Send error: {e}")

# 🧪 /memecoins command
app.add_handler(CommandHandler("memecoins", lambda u, c: asyncio.create_task(send_memecoin_alert(app, u.effective_chat.id))))

# ⏰ Jadwal automatic ah – 60 daqiiqo kasta
scheduler = BackgroundScheduler()
scheduler.add_job(lambda: asyncio.run(send_memecoin_alert(app, chat_id=os.getenv("CHAT_ID"))), 'interval', minutes=60)
scheduler.start()
# ✅ Cutubka 14: Auto Withdraw ETH
# Si fudud ETH uga dir bot-ka wallet-kiisa adigoo isticmaalaya command /withdraw_eth

import os, json
from web3 import Web3
from telegram.ext import CommandHandler

INFURA_URL = os.getenv("INFURA_URL")
PRIVATE_KEY_ETH = os.getenv("PRIVATE_KEY_ETH")
WALLET_ADDRESS_ETH = os.getenv("WALLET_ADDRESS_ETH")

web3 = Web3(Web3.HTTPProvider(INFURA_URL))

# 🏦 Function: ETH Transfer
def send_eth(destination: str, amount_eth: float) -> str:
    try:
        account = web3.eth.account.from_key(PRIVATE_KEY_ETH)
        nonce = web3.eth.get_transaction_count(account.address)
        tx = {
            'nonce': nonce,
            'to': destination,
            'value': web3.to_wei(amount_eth, 'ether'),
            'gas': 21000,
            'gasPrice': web3.eth.gas_price
        }
        signed_tx = web3.eth.account.sign_transaction(tx, PRIVATE_KEY_ETH)
        tx_hash = web3.eth.send_raw_transaction(signed_tx.rawTransaction)
        return web3.to_hex(tx_hash)
    except Exception as e:
        return f"❌ Error: {e}"

# 💬 Telegram Command: /withdraw_eth <wallet> <amount>
async def withdraw_eth(update, context):
    try:
        args = context.args
        if len(args) != 2:
            await update.message.reply_text("❗ Format: /withdraw_eth <wallet_address> <amount>")
            return

        dest_wallet = args[0]
        amount = float(args[1])

        tx_hash = send_eth(dest_wallet, amount)
        if tx_hash.startswith("0x"):
            await update.message.reply_text(f"✅ ETH sent successfully!\nTransaction: https://etherscan.io/tx/{tx_hash}")
        else:
            await update.message.reply_text(tx_hash)
    except Exception as e:
        await update.message.reply_text(f"⚠️ Error: {e}")

# 🧩 Add command handler
app.add_handler(CommandHandler("withdraw_eth", withdraw_eth))
# ✅ TP/SL Voice Alerts – Gool & Guuldarro Codad kala duwan
from gtts import gTTS
import tempfile
from telegram.constants import ChatAction
from telegram.ext import CommandHandler

# 🔊 Play voice alert based on trade result
async def play_result_voice(result_type: str, context, chat_id: str):
    try:
        await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.RECORD_AUDIO)

        if result_type == "TP":
            message = "Congratulations! Take Profit hit. Ka-ching!"
        elif result_type == "SL":
            message = "Stop Loss hit. Wax meynas galay!"
        else:
            message = "Unknown trade result."

        tts = gTTS(message)
        with tempfile.NamedTemporaryFile(delete=True) as tmp:
            tts.save(tmp.name + ".mp3")
            with open(tmp.name + ".mp3", "rb") as audio:
                await context.bot.send_voice(chat_id=chat_id, voice=audio)
    except Exception as e:
        print(f"Voice alert error: {e}")

# ✅ Manual Test Commands: /tp and /sl
async def tp_alert(update, context):
    await play_result_voice("TP", context, update.effective_chat.id)

async def sl_alert(update, context):
    await play_result_voice("SL", context, update.effective_chat.id)

# ✅ Add handlers
app.add_handler(CommandHandler("tp", tp_alert))
app.add_handler(CommandHandler("sl", sl_alert))

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
