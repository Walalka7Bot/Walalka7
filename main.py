from telegram.ext import (
    ApplicationBuilder, CommandHandler, ContextTypes
)
from telegram import Update, ReplyKeyboardMarkup, Bot
from config import BOT_TOKEN, CHAT_ID

import asyncio
import re
import os
import csv
from datetime import datetime
from fpdf import FPDF

# --- STATIC SETTINGS ---
BALANCE = 5000
MAX_DRAWDOWN = 250
VALID_SYMBOLS = ["BTC", "ETH", "SOL", "XRP", "GOLD", "SILVER", "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD"]
VIP_USERS = [CHAT_ID]  # Isticmaal chat ID sax ah

# --- TELEGRAM BOT ---
app = ApplicationBuilder().token(BOT_TOKEN).build()
bot = Bot(token=BOT_TOKEN)

# --- UI: /start ---
menu_buttons = [
    ['📈 Get Signal', '📄 My Journal'],
    ['💰 Upgrade to VIP', '🔕 Mute Voice Alerts'],
    ['🪙 Crypto: BTC / ETH / SOL / XRP'],
    ['📊 Forex: EURUSD / GBPUSD / USDJPY / AUDUSD / USDCAD'],
    ['🥇 Metals: GOLD / SILVER']
]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 *Salaam!* \nKu soo dhowow *ICT Forex Signals Bot* 📈\n\n"
        "➤ Fadlan dooro qaybta aad xiiseyneyso:\n\n"
        "🪙 *Crypto:* BTC, ETH, SOL, XRP\n"
        "🥇 *Metals:* GOLD, SILVER\n"
        "📊 *Forex:* EURUSD, GBPUSD, USDJPY, AUDUSD, USDCAD",
        reply_markup=ReplyKeyboardMarkup(menu_buttons, resize_keyboard=True),
        parse_mode='Markdown'
    )

# --- /sendsignal ---
async def sendsignal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        text = " ".join(context.args)
        pattern = r'(\w+)\s+EN=(\d+\.\d+)\s+TP=(\d+\.\d+)\s+SL=(\d+\.\d+)\s+TF=(\w+)\s+Exp=(.+)'
        match = re.search(pattern, text)
        if not match:
            await update.message.reply_text(
                "❌ Format: `/sendsignal EURUSD EN=1.0845 TP=1.0880 SL=1.0825 TF=15min Exp=FVG + SMT`",
                parse_mode='Markdown'
            )
            return
        symbol, en, tp, sl, tf, explanation = match.groups()
        signal_msg = f"""
📈 *New ICT Signal - {symbol.upper()} ({tf})*

*ENTRY:* {en}  
*TP:* 🎯 {tp}  
*SL:* 🔻 {sl}  

📚 *Explanation:* {explanation}
⏰ *Time:* Auto Detected (London/NYC Session)
"""
        await update.message.reply_text(signal_msg, parse_mode='Markdown')
    except Exception as e:
        await update.message.reply_text(f"⚠️ Error: {str(e)}")

# --- /tp /sl /entry ---
TP_SOUND = "assets/tp_sound.mp3"
SL_SOUND = "assets/sl_sound.mp3"
EN_SOUND = "assets/entry_sound.mp3"

async def tp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ *TP hit!* 💰", parse_mode='Markdown')
    with open(TP_SOUND, 'rb') as audio:
        await update.message.reply_audio(audio=audio)

async def sl(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ *SL hit!* 😢", parse_mode='Markdown')
    with open(SL_SOUND, 'rb') as audio:
        await update.message.reply_audio(audio=audio)

async def entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🟡 *Entry reached!*", parse_mode='Markdown')
    with open(EN_SOUND, 'rb') as audio:
        await update.message.reply_audio(audio=audio)

# --- /sendchart ---
CHART_PATH = "assets/chart_sample.jpg"
async def sendchart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        with open(CHART_PATH, 'rb') as photo:
            await update.message.reply_photo(photo=photo, caption="🖼️ *Chart-ka la xiriira signalka*", parse_mode='Markdown')
    except FileNotFoundError:
        await update.message.reply_text("❌ Chart image ma jiro.")

# --- /risk ---
def calculate_lot(risk_percent, sl_pips):
    risk_dollars = (risk_percent / 100) * BALANCE
    lot_size = risk_dollars / (sl_pips * 10)
    return round(lot_size, 2), risk_dollars

async def risk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if len(context.args) != 2:
            await update.message.reply_text("❌ Format: `/risk 1 20`", parse_mode='Markdown')
            return
        risk_percent = float(context.args[0])
        sl_pips = float(context.args[1])
        lot, dollars = calculate_lot(risk_percent, sl_pips)
        await update.message.reply_text(
            f"📊 *Lot Size Calculation*\n\n"
            f"- Risk: {risk_percent}% (${dollars:.2f})\n"
            f"- SL: {sl_pips} pips\n"
            f"- 🔢 Lot: *{lot}* lots", parse_mode='Markdown'
        )
    except Exception as e:
        await update.message.reply_text(f"⚠️ Error: {str(e)}")

# --- /getreport ---
trades = [
    {"symbol": "EURUSD", "EN": "1.0845", "TP": "1.0880", "SL": "1.0825", "result": "WIN", "pnl": "+35 pips"},
    {"symbol": "GOLD", "EN": "2310.0", "TP": "2330.0", "SL": "2290.0", "result": "LOSS", "pnl": "-20 pips"},
    {"symbol": "BTC", "EN": "65000", "TP": "67000", "SL": "64000", "result": "WIN", "pnl": "+2000"},
    {"symbol": "ETH", "EN": "3000", "TP": "3200", "SL": "2900", "result": "WIN", "pnl": "+20"}  # 💵 lacag 20
]

def generate_pdf():
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, txt="📊 Daily Trade Report", ln=True, align='C')
    pdf.cell(200, 10, txt=f"Date: {datetime.now().strftime('%Y-%m-%d')}", ln=True, align='C')
    pdf.ln(10)
    for trade in trades:
        pdf.cell(200, 10, txt=f"{trade['symbol']} | EN: {trade['EN']} | TP: {trade['TP']} | SL: {trade['SL']}", ln=True)
        pdf.cell(200, 10, txt=f"Result: {trade['result']} | P&L: {trade['pnl']}", ln=True)
        pdf.ln(5)
    filepath = "daily_report.pdf"
    pdf.output(filepath)
    return filepath

async def getreport(update: Update, context: ContextTypes.DEFAULT_TYPE):
    filepath = generate_pdf()
    with open(filepath, 'rb') as doc:
        await update.message.reply_document(document=doc, filename=filepath, caption="📄 *Daily Trade Report*", parse_mode='Markdown')
    os.remove(filepath)

# --- /result ---
CSV_FILE = "results.csv"
async def result(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if len(context.args) != 3:
            await update.message.reply_text("❌ Format: `/result GOLD WIN +180`", parse_mode='Markdown')
            return
        symbol = context.args[0].upper()
        outcome = context.args[1].upper()
        pnl = context.args[2]
        if symbol not in VALID_SYMBOLS or outcome not in ["WIN", "LOSS"]:
            await update.message.reply_text("❌ SYMBOL ama RESULT khaldan", parse_mode='Markdown')
            return
        date = datetime.now().strftime("%Y-%m-%d")
        row = [date, symbol, outcome, pnl]
        file_exists = os.path.isfile(CSV_FILE)
        with open(CSV_FILE, mode='a', newline='') as file:
            writer = csv.writer(file)
            if not file_exists:
                writer.writerow(["Date", "Symbol", "Result", "P&L"])
            writer.writerow(row)
        await update.message.reply_text(f"✅ Result saved: {symbol} → {outcome} {pnl}")
    except Exception as e:
        await update.message.reply_text(f"⚠️ Error: {e}")

# --- /vip & /market ---
async def vip_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in VIP_USERS:
        await update.message.reply_text("❌ Only VIPs allowed.")
        return
    await update.message.reply_text("✅ VIP access granted.")

async def market(update: Update, context: ContextTypes.DEFAULT_TYPE):
    summary = f"""
📊 *Daily Market Overview*  
🕒 {datetime.now().strftime("%Y-%m-%d %H:%M")}

🔸 *Crypto*
- BTC: $64,300 ↑
- ETH: $3,250 ↑
- SOL: $145 ↑

🔸 *Forex*
- EURUSD: 1.0845 ↓
- GBPUSD: 1.2750 →
- USDJPY: 158.30 ↑

🔸 *Stocks*
- AAPL: $210.50 ↑
- TSLA: $690.20 ↓
- AMZN: $134.10 →

📈 Xogtan waa guudmarka suuqa maanta.
"""
    await update.message.reply_text(summary, parse_mode='Markdown')

# --- Register Handlers ---
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("sendsignal", sendsignal))
app.add_handler(CommandHandler("tp", tp))
app.add_handler(CommandHandler("sl", sl))
app.add_handler(CommandHandler("entry", entry))
app.add_handler(CommandHandler("sendchart", sendchart))
app.add_handler(CommandHandler("risk", risk))
app.add_handler(CommandHandler("getreport", getreport))
app.add_handler(CommandHandler("result", result))
app.add_handler(CommandHandler("vip", vip_command))
app.add_handler(CommandHandler("market", market))

# --- Start Polling ---
print("✅ ALL MODULES READY — Bot is Live")
app.run_polling()
