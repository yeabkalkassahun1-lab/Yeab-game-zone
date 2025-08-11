import os
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from .callbacks import handle_button_press
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")

application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

async def start(update, context):
    await update.message.reply_text("Welcome to Yeab Game Zone! Use /play to start a new game.")

async def play(update, context):
    keyboard = [
        [InlineKeyboardButton("50 ETB", callback_data='stake_50'),
         InlineKeyboardButton("100 ETB", callback_data='stake_100')],
        [InlineKeyboardButton("Win: 1 Token", callback_data='win_1'),
         InlineKeyboardButton("Win: 2 Tokens", callback_data='win_2')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text('Choose your stake and win condition:', reply_markup=reply_markup)

# Add handlers
application.add_handler(CommandHandler('start', start))
application.add_handler(CommandHandler('play', play))
application.add_handler(CallbackQueryHandler(handle_button_press))