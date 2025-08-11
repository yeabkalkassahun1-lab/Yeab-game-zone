import os
import logging
import json
from decimal import Decimal
from typing import List, Dict, Set

from fastapi import WebSocket
from telegram import (
    Update, Bot, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
)
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, ContextTypes
)

from . import callbacks
from .game_logic import LudoGame
from database_models.manager import db_manager

# --- Setup ---
logger = logging.getLogger(__name__)
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

# --- WebSocket Connection Manager ---
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[int, WebSocket] = {}

    async def connect(self, websocket: WebSocket, user_id: int):
        await websocket.accept()
        self.active_connections[user_id] = websocket
        # You could send initial data here, like the user's balance
        initial_data = {"event": "connection_ack", "user_id": user_id}
        await websocket.send_text(json.dumps(initial_data))


    def disconnect(self, user_id: int):
        if user_id in self.active_connections:
            del self.active_connections[user_id]

    async def broadcast(self, message: str):
        for connection in self.active_connections.values():
            await connection.send_text(message)

connection_manager = ConnectionManager()

# --- Bot and Application Setup ---
bot = Bot(token=TELEGRAM_BOT_TOKEN)
application = Application.builder().bot(bot).build()

# --- Command Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the /start command."""
    user = update.effective_user
    await db_manager.get_or_create_user(user.id, user.username)
    
    # Button to open the Web App
    web_app_url = os.getenv("WEB_APP_URL", WEBHOOK_URL) # Use WEBHOOK_URL as a fallback
    keyboard = [[
        InlineKeyboardButton(
            "🎮 Open Game Lobby", 
            web_app=WebAppInfo(url=web_app_url)
        )
    ]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_html(
        f"👋 Welcome, <b>{user.first_name}</b>!\n\n"
        "Click the button below to see open games, create a new one, or manage your funds.",
        reply_markup=reply_markup
    )

async def play(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handles /play command. Creates a new game lobby.
    Usage: /play <stake> <win_condition>
    Example: /play 50 2
    """
    user = update.effective_user
    try:
        stake = Decimal(context.args[0])
        win_condition = int(context.args[1])
        
        if stake <= 0 or win_condition not in [1, 2, 4]:
            raise ValueError

        # Check if user has sufficient balance
        balance = await db_manager.get_user_balance(user.id)
        if balance < stake:
            await update.message.reply_text("You have insufficient funds to create this game.")
            return

        # Create a new LudoGame instance and store it
        game = LudoGame(creator_id=user.id, stake=float(stake), win_condition=win_condition)
        game_id = await db_manager.create_game(
            creator_id=user.id,
            stake=stake,
            win_condition=win_condition,
            game_data=game.get_state()
        )

        # Send lobby message
        prize = (stake * 2) * Decimal('0.9')
        join_button = InlineKeyboardButton("⚔️ Join Game", callback_data=f"join:{game_id}")
        reply_markup = InlineKeyboardMarkup([[join_button]])
        
        await update.message.reply_html(
            f"<b>A new Ludo game has started!</b>\n\n"
            f"👤 Creator: {user.first_name}\n"
            f"💰 Stake: {stake:.2f} ETB\n"
            f"🏆 Prize: {prize:.2f} ETB\n"
            f"🎯 Win Condition: First to get <b>{win_condition}</b> token(s) home.",
            reply_markup=reply_markup
        )

    except (IndexError, ValueError):
        await update.message.reply_text(
            "Invalid command format.\n"
            "Usage: /play <stake> <win_condition>\n"
            "Example: /play 50 2"
        )

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Checks user's balance."""
    user_id = update.effective_user.id
    balance_val = await db_manager.get_user_balance(user_id)
    await update.message.reply_text(f"💰 Your current balance is: {balance_val:.2f} ETB")

async def deposit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Initiates a deposit."""
    # This would typically involve generating a unique payment link via Chapa
    await update.message.reply_text("Deposit functionality is handled via the Web App for a better experience.")

# --- Register Handlers ---
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("play", play))
application.add_handler(CommandHandler("balance", balance))
application.add_handler(CommandHandler("deposit", deposit))

# Main dispatcher for all button clicks (Callback Queries)
application.add_handler(CallbackQueryHandler(callbacks.dispatch))