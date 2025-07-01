import os
import asyncio
import logging
from flask import Flask, request, jsonify
from web3 import Web3
# from web3.middleware import geth_poa_middleware # If you need this for PoA networks
from eth_account import Account
from gtts import gTTS
from fpdf import FPDF
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from PIL import Image
import io
import json # For signal data filtering

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters
)

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Global Variables and Environment Configuration ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL") # This should be your public URL, e.g., https://your-app-name.onrender.com
INFURA_URL = os.getenv("INFURA_URL")
ETH_PRIVATE_KEY = os.getenv("ETH_PRIVATE_KEY")
CHAT_ID = os.getenv("CHAT_ID")
ADMIN_IDS_STR = os.getenv("ADMIN_IDS")
ADMIN_IDS = [int(x.strip()) for x in ADMIN_IDS_STR.split(',')] if ADMIN_IDS_STR else []

# Global Application instance
app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

# Flask app instance
flask_app = Flask(__name__)

# Global Web3 instance
w3 = None

# In-memory storage for simplicity (for persistent data, use a database)
user_data = {} # To store autotrade status, etc.
profit_goals = {} # {user_id: goal_amount}
current_profits = {} # {user_id: current_total_profit}
user_market_visibility = {} # {user_id: {market: True/False}}
user_ict_filter_status = {} # {user_id: True/False}
user_search_mode = {} # {user_id: True/False}

# --- Helper Functions (keep these as they are, just ensure they use 'app.bot' for sending messages) ---
async def send_voice_alert(text, bot_instance, chat_id):
    try:
        if not text.strip():
            logger.warning("Voice alert text is empty, skipping.")
            return

        tts = gTTS(text=text, lang='en')
        audio_fp = io.BytesIO()
        tts.save(audio_fp)
        audio_fp.seek(0)
        await bot_instance.send_voice(chat_id=chat_id, voice=audio_fp)
        logger.info(f"Voice alert sent for chat {chat_id}")
    except Exception as e:
        logger.error(f"Error sending voice alert: {e}", exc_info=True)

def get_voice_text(alert_type):
    if alert_type == "signal":
        return "New signal detected."
    elif alert_type == "profit":
        return "Profit logged."
    elif alert_type == "withdrawal_success":
        return "Ethereum withdrawal successful."
    elif alert_type == "withdrawal_failed":
        return "Ethereum withdrawal failed."
    return ""

def is_admin(user_id):
    return user_id in ADMIN_IDS

def should_send_signal_based_on_filters(signal_data):
    """
    Checks if a signal should be sent based on user filters.
    This logic needs to iterate through all relevant users/groups.
    For simplicity, let's assume we send to CHAT_ID and check its settings.
    """
    if CHAT_ID:
        chat_id = int(CHAT_ID)
        # Check market visibility
        if chat_id in user_market_visibility:
            market_settings = user_market_visibility[chat_id]
            if not market_settings.get(signal_data["market"].lower(), True):
                logger.info(f"Signal for {signal_data['symbol']} ({signal_data['market']}) filtered by market visibility for chat {chat_id}.")
                return False

        # Check ICT filter (if enabled for this chat)
        if user_ict_filter_status.get(chat_id, False):
            if not (signal_data.get("liquidity") or signal_data.get("order_block") or signal_data.get("fvg")):
                logger.info(f"Signal for {signal_data['symbol']} filtered by ICT due to missing ICT elements for chat {chat_id}.")
                return False
        
        # Check Halal only filter
        if user_data.get(chat_id, {}).get('halal_only', False):
            if signal_data["market"].lower() in ["crypto", "memecoins"] and not is_coin_halal(signal_data["symbol"], signal_data["description"]):
                logger.info(f"Signal for {signal_data['symbol']} filtered by Halal Only for chat {chat_id}.")
                return False
    return True # Default to sending if no specific filters prevent it or if CHAT_ID is not set (will be caught later).

# Example for is_coin_halal - expand as needed
def is_coin_halal(symbol, description):
    # This is a placeholder. You need a robust method to determine halal status.
    # This could involve an external API, a database, or a more complex rule set.
    haram_keywords = ["gambling", "porn", "alcohol", "interest", "riba", "lending", "borrowing"]
    for keyword in haram_keywords:
        if keyword in description.lower() or keyword in symbol.lower():
            return False
    # More sophisticated logic would be needed here.
    return True

# --- Telegram Command Handlers (keep these as they are) ---
# (start_command, help_command, log_profit_command, show_profits_command, etc.)
# ... (paste all your command handlers here, from start_command to add_profit_goal_command) ...

async def start_command(update: Update, context):
    user = update.effective_user
    await update.message.reply_html(
        f"Assalamu Alaikum {user.mention_html()}! I am your AI trading assistant. "
        "Type /help to see available commands."
    )
    # Initialize user settings if not present
    if user.id not in user_data:
        user_data[user.id] = {'autotrade_enabled': False, 'halal_only': False}
    if user.id not in user_market_visibility:
        user_market_visibility[user.id] = {
            "forex": True, "crypto": True, "stocks": True, "memecoins": True, "polymarket": True
        }
    if user.id not in user_ict_filter_status:
        user_ict_filter_status[user.id] = False
    logger.info(f"User {user.id} ({user.first_name}) started the bot.")

async def help_command(update: Update, context):
    help_text = (
        "Here are the commands you can use:\n"
        "/start - Start the bot and get a greeting.\n"
        "/help - Show this help message.\n"
        "/profit <amount> - Log your profit for today. Example: /profit 100\n"
        "/profits - Show your total logged profits.\n"
        "/forex - Simulate a Forex trade signal.\n"
        "/autotrade - Toggle auto-trading feature (admins only).\n"
        "/halalonly - Toggle Halal-only filter for crypto/memecoin signals.\n"
        "/withdraw_eth <amount> <address> - Withdraw ETH from the bot's wallet (admins only).\n"
        "/report - Generate and send a PDF report of your profits.\n"
        "/marketvisibility - Toggle visibility for specific markets (Forex, Crypto, Stocks, Memecoins, Polymarket).\n"
        "/search <query> - Search for information (e.g., crypto, financial news).\n"
        "/ictfilter - Toggle ICT (Inner Circle Trader) filter for signals.\n"
        "/goal - Show your current profit goal and progress.\n"
        "/addprofit <amount> - Add profit to your goal tracker.\n"
        "\n*Simulated Market Commands (for testing):*\n"
        "/crypto - Simulate a Crypto trade signal.\n"
        "/stocks - Simulate a Stocks trade signal.\n"
        "/memecoins - Simulate a Memecoins trade signal.\n"
        "/polymarket - Simulate a Polymarket signal."
    )
    await update.message.reply_text(help_text)
    logger.info(f"User {update.effective_user.id} requested help.")

async def log_profit_command(update: Update, context):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("You are not authorized to use this command.")
        return

    try:
        amount = float(context.args[0])
        user_id = update.effective_user.id
        today = datetime.now().strftime("%Y-%m-%d")

        if user_id not in current_profits:
            current_profits[user_id] = 0.0

        current_profits[user_id] += amount
        
        # Store profit for daily report
        if user_id not in user_data:
            user_data[user_id] = {}
        if 'daily_profits' not in user_data[user_id]:
            user_data[user_id]['daily_profits'] = {}
        if today not in user_data[user_id]['daily_profits']:
            user_data[user_id]['daily_profits'][today] = 0.0
        
        user_data[user_id]['daily_profits'][today] += amount

        await update.message.reply_text(f"Profit of ${amount:.2f} logged for today. Total profit: ${current_profits[user_id]:.2f}")
        await send_voice_alert(get_voice_text("profit"), app.bot, update.effective_chat.id) # Pass app.bot

        logger.info(f"Admin {user_id} logged profit: ${amount}. Total: ${current_profits[user_id]}")

    except (IndexError, ValueError):
        await update.message.reply_text("Usage: /profit <amount>")
    except Exception as e:
        logger.error(f"Error logging profit: {e}", exc_info=True)
        await update.message.reply_text("An error occurred while logging profit.")

async def show_profits_command(update: Update, context):
    user_id = update.effective_user.id
    total_profit = current_profits.get(user_id, 0.0)
    await update.message.reply_text(f"Your total logged profits: ${total_profit:.2f}")
    logger.info(f"User {user_id} requested total profits: ${total_profit}")

async def toggle_autotrade(update: Update, context):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("You are not authorized to use this command.")
        return

    user_id = update.effective_user.id
    if user_id not in user_data:
        user_data[user_id] = {'autotrade_enabled': False}
    
    user_data[user_id]['autotrade_enabled'] = not user_data[user_id]['autotrade_enabled']
    status = "enabled" if user_data[user_id]['autotrade_enabled'] else "disabled"
    await update.message.reply_text(f"Auto-trading is now {status}.")
    logger.info(f"Admin {user_id} toggled autotrade to {status}.")

async def toggle_halal_only_command(update: Update, context):
    user_id = update.effective_user.id
    if user_id not in user_data:
        user_data[user_id] = {'halal_only': False} # Ensure the key exists

    user_data[user_id]['halal_only'] = not user_data[user.id]['halal_only']
    status = "enabled" if user_data[user_id]['halal_only'] else "disabled"
    await update.message.reply_text(f"Halal-only filter for crypto/memecoin signals is now {status}.")
    logger.info(f"User {user_id} toggled Halal-only filter to {status}.")

async def withdraw_eth_command(update: Update, context):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("You are not authorized to use this command.")
        return

    if not w3 or not w3.is_connected():
        await update.message.reply_text("Ethereum node not connected. Cannot process withdrawal.")
        logger.error("ETH withdrawal requested but Infura node is not connected.")
        return

    if not ETH_PRIVATE_KEY:
        await update.message.reply_text("ETH_PRIVATE_KEY is not set. Cannot withdraw.")
        logger.error("ETH_PRIVATE_KEY is not set.")
        return

    try:
        amount_eth = float(context.args[0])
        to_address = context.args[1]

        # Convert ETH to Wei
        amount_wei = w3.to_wei(amount_eth, 'ether')

        # Get account from private key
        account = Account.from_key(ETH_PRIVATE_KEY)
        from_address = account.address

        # Get nonce
        nonce = w3.eth.get_transaction_count(from_address)

        # Estimate gas (simple estimation, can be more complex)
        # It's crucial to have enough ETH for gas!
        gas_price = w3.eth.gas_price
        estimated_gas = 21000 # Standard gas for simple ETH transfer

        # Build transaction
        transaction = {
            'from': from_address,
            'to': to_address,
            'value': amount_wei,
            'nonce': nonce,
            'gas': estimated_gas,
            'gasPrice': gas_price
        }

        # Sign transaction
        signed_txn = w3.eth.account.sign_transaction(transaction, ETH_PRIVATE_KEY)

        # Send transaction
        tx_hash = w3.eth.send_raw_transaction(signed_txn.rawTransaction)
        await update.message.reply_text(f"Attempting to withdraw {amount_eth} ETH to {to_address}. Transaction Hash: {tx_hash.hex()}")
        await send_voice_alert(get_voice_text("withdrawal_success"), app.bot, update.effective_chat.id)
        logger.info(f"ETH withdrawal initiated by {update.effective_user.id}: {amount_eth} ETH to {to_address}. Tx: {tx_hash.hex()}")

    except (IndexError, ValueError):
        await update.message.reply_text("Usage: /withdraw_eth <amount> <address>")
    except Exception as e:
        await update.message.reply_text(f"Error during ETH withdrawal: {e}")
        await send_voice_alert(get_voice_text("withdrawal_failed"), app.bot, update.effective_chat.id)
        logger.error(f"Error during ETH withdrawal by {update.effective_user.id}: {e}", exc_info=True)

async def send_report_command(update: Update, context):
    user_id = update.effective_user.id
    if user_id not in user_data or 'daily_profits' not in user_data[user_id]:
        await update.message.reply_text("No profit data available to generate a report.")
        return

    try:
        daily_profits = user_data[user_id]['daily_profits']
        
        pdf_buffer = io.BytesIO()
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=12)
        
        pdf.cell(200, 10, txt="Daily Profit Report", ln=True, align="C")
        pdf.ln(10) # Add some line breaks

        for date, profit in daily_profits.items():
            pdf.cell(200, 10, txt=f"Date: {date}, Profit: ${profit:.2f}", ln=True)

        pdf.output(pdf_buffer)
        pdf_buffer.seek(0)
        
        await update.message.reply_document(document=pdf_buffer, filename="profit_report.pdf")
        logger.info(f"User {user_id} requested and received profit report.")

    except Exception as e:
        logger.error(f"Error generating or sending PDF report: {e}", exc_info=True)
        await update.message.reply_text("An error occurred while generating the report.")

async def toggle_market_visibility_command(update: Update, context):
    user_id = update.effective_user.id
    if user_id not in user_market_visibility:
        user_market_visibility[user_id] = {
            "forex": True, "crypto": True, "stocks": True, "memecoins": True, "polymarket": True
        }
    
    current_settings = user_market_visibility[user_id]
    
    if not context.args:
        # Display current settings and offer buttons
        message = "Current market visibility settings:\n"
        for market, visible in current_settings.items():
            message += f"{market.capitalize()}: {'✅ Visible' if visible else '❌ Hidden'}\n"
        
        buttons = []
        for market in ["forex", "crypto", "stocks", "memecoins", "polymarket"]:
            label = f"Toggle {market.capitalize()}"
            callback_data = f"TOGGLE_MARKET:{market}"
            buttons.append([InlineKeyboardButton(label, callback_data=callback_data)])
        
        reply_markup = InlineKeyboardMarkup(buttons)
        await update.message.reply_text(message, reply_markup=reply_markup)
        logger.info(f"User {user_id} requested market visibility settings.")
    else:
        # Direct toggle via command (e.g., /marketvisibility forex)
        market_to_toggle = context.args[0].lower()
        if market_to_toggle in current_settings:
            current_settings[market_to_toggle] = not current_settings[market_to_toggle]
            status = "visible" if current_settings[market_to_toggle] else "hidden"
            await update.message.reply_text(f"{market_to_toggle.capitalize()} signals are now {status}.")
            logger.info(f"User {user_id} toggled {market_to_toggle} visibility to {status}.")
        else:
            await update.message.reply_text(f"Invalid market: {market_to_toggle}. Available: forex, crypto, stocks, memecoins, polymarket.")

async def search_command(update: Update, context):
    user_id = update.effective_user.id
    if not context.args:
        user_search_mode[user_id] = True
        await update.message.reply_text("Please enter your search query. I can search for crypto info, financial news, etc. Type /search again to exit search mode.")
    else:
        query = " ".join(context.args)
        await update.message.reply_text(f"Searching for: {query} (Feature to be implemented)")
        # In a real bot, you'd integrate with a search API (e.g., Google Search, Brave Search, specific crypto APIs)
        user_search_mode[user_id] = False # Exit search mode after direct query
    logger.info(f"User {user_id} initiated search mode or performed direct search: {context.args}")

async def handle_search_query(update: Update, context):
    user_id = update.effective_user.id
    if user_search_mode.get(user_id, False):
        query = update.message.text
        if query.lower() == "/search": # Allow exiting search mode
            user_search_mode[user_id] = False
            await update.message.reply_text("Exited search mode.")
            return

        await update.message.reply_text(f"Searching for: {query} (Feature to be implemented)")
        # In a real bot, you'd integrate with a search API (e.g., Google Search, Brave Search, specific crypto APIs)
        logger.info(f"User {user_id} searching: {query}")
        # Optionally, you could keep them in search mode until they type /exitsearch or /search again

async def toggle_ict_filter_command(update: Update, context):
    user_id = update.effective_user.id
    if user_id not in user_ict_filter_status:
        user_ict_filter_status[user_id] = False # Default to disabled
    
    user_ict_filter_status[user_id] = not user_ict_filter_status[user_id]
    status = "enabled" if user_ict_filter_status[user_id] else "disabled"
    await update.message.reply_text(f"ICT filter for signals is now {status}. Only signals with liquidity, order block, or FVG will be sent.")
    logger.info(f"User {user_id} toggled ICT filter to {status}.")

async def goal_status_command(update: Update, context):
    user_id = update.effective_user.id
    goal = profit_goals.get(user_id)
    current_profit = current_profits.get(user_id, 0.0)

    if goal is None:
        await update.message.reply_text("You haven't set a profit goal yet. Use /addprofit to set one.")
    else:
        progress = (current_profit / goal) * 100 if goal > 0 else 0
        await update.message.reply_text(f"Your profit goal: ${goal:.2f}\n"
                                     f"Current profit: ${current_profit:.2f}\n"
                                     f"Progress: {progress:.2f}%")
    logger.info(f"User {user_id} checked profit goal.")

async def add_profit_goal_command(update: Update, context):
    user_id = update.effective_user.id
    try:
        amount = float(context.args[0])
        if amount <= 0:
            await update.message.reply_text("Please enter a positive amount for your profit goal.")
            return
        
        profit_goals[user_id] = amount
        current_profits[user_id] = current_profits.get(user_id, 0.0) # Ensure current_profits is initialized
        await update.message.reply_text(f"Your profit goal has been set to ${amount:.2f}.")
        logger.info(f"User {user_id} set profit goal to ${amount}.")
    except (IndexError, ValueError):
        await update.message.reply_text("Usage: /addprofit <amount>")
    except Exception as e:
        logger.error(f"Error setting profit goal: {e}", exc_info=True)
        await update.message.reply_text("An error occurred while setting the profit goal.")

# --- Simulated Market Signal Commands (keep these as they are) ---
async def send_forex_trade_command(update: Update, context):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("You are not authorized to use this command.")
        return
    # This is a placeholder for a simulated signal
    signal_data = {
        "symbol": "EURUSD", "direction": "BUY", "timeframe": "15min", "market": "forex",
        "entry_price": "1.0850", "stop_loss": "1.0820", "take_profit": "1.0900",
        "description": "Strong bullish momentum on lower timeframe. Expect break of structure.",
        "liquidity": True, "order_block": False, "fvg": True
    }
    await send_simulated_signal(signal_data, update.effective_chat.id)
    logger.info(f"Admin {update.effective_user.id} simulated Forex signal.")

async def crypto_command(update: Update, context):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("You are not authorized to use this command.")
        return
    signal_data = {
        "symbol": "BTC/USDT", "direction": "SELL", "timeframe": "1h", "market": "crypto",
        "entry_price": "65000", "stop_loss": "65500", "take_profit": "64000",
        "description": "Bearish divergence on RSI, anticipating a dump. Not Sharia Compliant for some.",
        "liquidity": True, "order_block": True, "fvg": False
    }
    await send_simulated_signal(signal_data, update.effective_chat.id)
    logger.info(f"Admin {update.effective_user.id} simulated Crypto signal.")

async def stocks_command(update: Update, context):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("You are not authorized to use this command.")
        return
    signal_data = {
        "symbol": "AAPL", "direction": "BUY", "timeframe": "Daily", "market": "stocks",
        "entry_price": "170", "stop_loss": "165", "take_profit": "178",
        "description": "Upcoming earnings report looks positive. Breakout from resistance.",
        ""
    }
    await send_simulated_signal(signal_data, update.effective_chat.id)
    logger.info(f"Admin {update.effective_user.id} simulated Stocks signal.")

async def memecoins_command(update: Update, context):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("You are not authorized to use this command.")
        return
    signal_data = {
        "symbol": "DOGE/USDT", "direction": "BUY", "timeframe": "30min", "market": "memecoins",
        "entry_price": "0.15", "stop_loss": "0.14", "take_profit": "0.18",
        "description": "Elon Musk tweet incoming. Very volatile asset.",
        "liquidity": False, "order_block": False, "fvg": False # Meme coins often lack ICT concepts
    }
    await send_simulated_signal(signal_data, update.effective_chat.id)
    logger.info(f"Admin {update.effective_user.id} simulated Memecoins signal.")

async def polymarket_command(update: Update, context):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("You are not authorized to use this command.")
        return
    signal_data = {
        "symbol": "ETH Price > $4000 by July 1", "direction": "YES", "timeframe": "N/A", "market": "polymarket",
        "entry_price": "0.65", "stop_loss": "N/A", "take_profit": "0.90",
        "description": "High probability event predicted by on-chain analysis.",
        "liquidity": True, "order_block": False, "fvg": False
    }
    await send_simulated_signal(signal_data, update.effective_chat.id)
    logger.info(f"Admin {update.effective_user.id} simulated Polymarket signal.")

async def send_simulated_signal(signal_data, target_chat_id):
    if not should_send_signal_based_on_filters(signal_data):
        return "Signal filtered out by bot settings."

    halal_status_text = ""
    if signal_data["market"].lower() in ["crypto", "memecoins"]:
        halal_status_text = "🟢 Halal" if is_coin_halal(signal_data["symbol"], signal_data["description"]) else "🔴 Haram"

    message = (
        f"🚨 New {signal_data['market'].upper()} Signal\n"
        f"Pair: {signal_data['symbol']}\n"
        f"Timeframe: {signal_data['timeframe']}\n"
        f"Direction: {signal_data['direction']}\n"
        f"Entry: {signal_data['entry_price']}\n"
        f"TP: {signal_data['take_profit']}\nSL: {signal_data['stop_loss']}\n"
        f"{halal_status_text}"
    )

    buttons = [[
        InlineKeyboardButton("✅ Confirm", callback_data=f"CONFIRM:{signal_data['symbol']}:{signal_data['direction']}"),
        InlineKeyboardButton("❌ Ignore", callback_data="IGNORE")
    ]]
    reply_markup = InlineKeyboardMarkup(buttons)

    if target_chat_id:
        await app.bot.send_message(chat_id=target_chat_id, text=message, reply_markup=reply_markup)
        await send_voice_alert(get_voice_text("signal"), app.bot, target_chat_id)
    else:
        logger.error("Target CHAT_ID not provided for simulated signal.")

# --- Callback Query Handler ---
async def handle_callback_query(update: Update, context):
    query = update.callback_query
    user_id = query.from_user.id

    # Always answer the callback query to remove the loading state on the button
    await query.answer()

    data = query.data

    if data.startswith("TOGGLE_MARKET:"):
        market = data.split(":")[1]
        if user_id not in user_market_visibility:
            user_market_visibility[user_id] = {
                "forex": True, "crypto": True, "stocks": True, "memecoins": True, "polymarket": True
            }
        
        current_settings = user_market_visibility[user_id]
        if market in current_settings:
            current_settings[market] = not current_settings[market]
            status = "visible" if current_settings[market] else "hidden"
            await query.edit_message_text(f"{market.capitalize()} signals are now {status}.")
            logger.info(f"User {user_id} toggled {market} visibility to {status} via inline button.")
        else:
            await query.edit_message_text(f"Invalid market: {market}.")
    elif data.startswith("CONFIRM:"):
        _, symbol, direction = data.split(":")
        await query.edit_message_text(f"You confirmed {direction} for {symbol}. (Action recorded)")
        logger.info(f"User {user_id} confirmed trade: {direction} {symbol}.")
        # Here you would integrate with an actual trading API to execute the trade
    elif data == "IGNORE":
        await query.edit_message_text("Signal ignored.")
        logger.info(f"User {user_id} ignored signal.")

# --- APScheduler for Daily Report ---
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime
scheduler = AsyncIOScheduler()

async def send_daily_report():
    if not CHAT_ID:
        logger.warning("CHAT_ID not set for daily report. Skipping.")
        return

    report_text = "Daily Trading Report:\n\n"
    today = datetime.now().strftime("%Y-%m-%d")

    # This report combines all admin users' profits for simplicity, or can be individualized
    # For individual reports, you'd iterate through ADMIN_IDS or all user_data keys
    total_today_profit = 0.0
    for user_id in ADMIN_IDS: # Or iterate user_data.keys() if you want report for all
        if user_id in user_data and 'daily_profits' in user_data[user_id] and today in user_data[user_id]['daily_profits']:
            total_today_profit += user_data[user_id]['daily_profits'][today]
    
    report_text += f"Total Profit Today ({today}): ${total_today_profit:.2f}\n"
    report_text += "More detailed breakdown can be added here."

    await app.bot.send_message(chat_id=CHAT_ID, text=report_text)
    logger.info(f"Daily report sent to {CHAT_ID}. Total profit today: ${total_today_profit}")

# Schedule the daily report to run every day at a specific time (e.g., 23:59 local time)
# Note: Render instances might use UTC, adjust time accordingly.
# Adding job tentatively -- it will be properly scheduled when the scheduler starts
scheduler.add_job(send_daily_report, 'cron', hour=23, minute=59, id='daily_report_job', replace_job=True)
scheduler.start()


# --- Main Execution for Webhook Mode ---
# This part is crucial for making Flask and PTB work together with Uvicorn.
async def set_telegram_webhook():
    """Sets the Telegram webhook when the application starts."""
    WEBHOOK_URL = os.getenv("WEBHOOK_URL")
    if not WEBHOOK_URL:
        logger.error("WEBHOOK_URL environment variable is not set. Webhook will not be set.")
        raise ValueError("WEBHOOK_URL environment variable must be set for webhook deployment.")
    else:
        full_webhook_url = f"{WEBHOOK_URL}/telegram-webhook"
        logger.info(f"Setting webhook to: {full_webhook_url}")

        # Initialize the application
        await app.initialize()

        # Start the updater which will process updates put into the queue by the Flask webhook handler
        await app.updater.start()

        # Set the webhook on Telegram's side
        await app.bot.set_webhook(url=full_webhook_url, allowed_updates=Update.ALL_TYPES)
        logger.info("Telegram webhook set successfully.")

# This function adds all handlers. It must be called after 'app' is created.
def setup_handlers():
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("profit", log_profit_command))
    app.add_handler(CommandHandler("profits", show_profits_command))
    app.add_handler(CommandHandler("forex", send_forex_trade_command))
    app.add_handler(CommandHandler("autotrade", toggle_autotrade))
    app.add_handler(CommandHandler("halalonly", toggle_halal_only_command))
    app.add_handler(CommandHandler("withdraw_eth", withdraw_eth_command))
    app.add_handler(CommandHandler("report", send_report_command))
    app.add_handler(CommandHandler("marketvisibility", toggle_market_visibility_command))
    app.add_handler(CommandHandler("search", search_command))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_search_query))
    app.add_handler(CommandHandler("ictfilter", toggle_ict_filter_command))
    app.add_handler(CommandHandler("goal", goal_status_command))
    app.add_handler(CommandHandler("addprofit", add_profit_goal_command))

    app.add_handler(CommandHandler("crypto", crypto_command))
    app.add_handler(CommandHandler("stocks", stocks_command))
    app.add_handler(CommandHandler("memecoins", memecoins_command))
    app.add_handler(CommandHandler("polymarket", polymarket_command))

    app.add_handler(CallbackQueryHandler(handle_callback_query))


# Ensure handlers are set up when the module is imported (e.g., by uvicorn)
setup_handlers()

# Set up Web3 connection immediately (it's not async)
if INFURA_URL:
    try:
        w3 = Web3(Web3.HTTPProvider(INFURA_URL))
        if not w3.is_connected():
            logger.warning("Failed to connect to Infura. ETH withdrawal might not work.")
    except Exception as e:
        logger.error(f"Error connecting to Web3: {e}")

# This is the main entry point when running with `uvicorn main:flask_app`
# We use a special function to set the webhook, which will be called before the app starts
@flask_app.before_first_request
async def before_first_request_func():
    """This runs once before the first request, ensuring webhook is set."""
    await set_telegram_webhook()

# If you run this file directly for local testing (not recommended for production on Render)
if __name__ == "__main__":
    # For local testing, you might want to manually run the webhook setup
    # and then run Flask. However, for a robust production setup with Render,
    # you typically rely on `uvicorn main:flask_app` where `main` is your file
    # and `flask_app` is the Flask instance.

    # To ensure the webhook setup runs once before Flask serves requests,
    # and to properly handle the asyncio loop, the Uvicorn approach is best.

    # If you MUST run this file directly (e.g., for simple local debug):
    # This simulates `uvicorn main:flask_app` by running the Flask app
    # and ensuring the webhook is set up.
    
    # Run the setup for Telegram bot in the same event loop as Flask
    # Note: Flask's default run() is blocking and does not natively integrate
    # with existing asyncio event loops easily.
    # The `uvicorn` solution for `main:flask_app` is the robust way.

    # If you remove the `before_first_request_func` and try to run asyncio.run()
    # here, it will conflict with Flask's internal event loop management.

    # For development on Render: The `uvicorn main:flask_app` command will handle this.
    # The `before_first_request` decorator ensures `set_telegram_webhook` is called.

    # For local testing without uvicorn:
    # You might temporarily uncomment something like this, but be aware of blocking issues:
    # asyncio.run(set_telegram_webhook())
    # PORT = int(os.getenv("PORT", 10000))
    # logger.info(f"Starting Flask app on 0.0.0.0:{PORT}")
    # flask_app.run(host="0.0.0.0", port=PORT, debug=True) # debug=True for local, False for prod


    # The most robust way for local testing and production is to use uvicorn:
    # Example command to run: uvicorn main:flask_app --host 0.0.0.0 --port 10000 --reload
    # In Render, your "Start Command" will be: uvicorn main:flask_app --host 0.0.0.0 --port $PORT
    
    # This block is mostly for explaining the uvicorn setup.
    # You generally don't run flask_app.run() when deploying with uvicorn.
    # Render's "Start Command" should be `uvicorn main:flask_app --host 0.0.0.0 --port $PORT`
    pass
