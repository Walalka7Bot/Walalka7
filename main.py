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

# ✅ Run bot
app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
app.add_handler(CommandHandler("profit", add_profit))
app.add_handler(CommandHandler("profits", view_profits))
app.add_handler(CommandHandler("withdraw_eth", withdraw_eth))
app.add_handler(CommandHandler("autotrade", toggle_auto_trade))

if __name__ == '__main__':
    app.run_polling()
