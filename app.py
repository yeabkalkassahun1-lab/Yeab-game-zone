# /app.py (Final, Confirmed Version)

import os
import logging
import json
from fastapi import FastAPI, Request, Response, HTTPException, WebSocket
from fastapi.staticfiles import StaticFiles
from telegram import Update
from dotenv import load_dotenv

# --- Key Imports from Bot Logic ---
# These objects are DEFINED in /bot/handlers.py and USED here.
from bot.handlers import application, bot, connection_manager

# --- Key Import for Database ---
from database_models.manager import db_manager

# --- Application Setup ---
load_dotenv()
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

WEBHOOK_URL = os.getenv("WEBHOOK_URL")

app = FastAPI()

# --- FastAPI Event Handlers ---
@app.on_event("startup")
async def on_startup():
    """On startup, initialize the DB pool and set the Telegram webhook."""
    await db_manager.get_pool()  # Initialize the database connection pool
    
    # The webhook URL is provided by Render's environment variables.
    if WEBHOOK_URL:
        webhook_full_url = f"{WEBHOOK_URL}/api/telegram"
        await bot.set_webhook(url=webhook_full_url, allowed_updates=Update.ALL_TYPES)
        logger.info(f"Telegram webhook successfully set to: {webhook_full_url}")
    else:
        logger.warning("WEBHOOK_URL environment variable not set. Webhook not configured.")

# --- API Endpoints ---
@app.post("/api/telegram")
async def telegram_webhook(request: Request):
    """
    This is the single entry point for all Telegram updates.
    It passes the incoming data directly to the `application` object from handlers.py.
    """
    try:
        data = await request.json()
        update = Update.de_json(data, bot)
        await application.process_update(update)
    except Exception as e:
        logger.error(f"Error processing Telegram update: {e}", exc_info=True)
    return Response(status_code=200)

@app.post("/api/chapa/webhook")
async def chapa_webhook(request: Request):
    """Handles deposit confirmations from the Chapa payment gateway."""
    # In a live environment, you MUST verify the webhook signature from Chapa.
    try:
        payload = await request.json()
        logger.info(f"Received Chapa webhook: {payload}")
        
        if payload.get("status") == "success":
            tx_ref = payload.get("tx_ref")
            amount = payload.get("amount")
            
            # The user's Telegram ID is embedded in our transaction reference.
            telegram_id = int(tx_ref.split('-')[-1])

            await db_manager.process_deposit(telegram_id, float(amount))
            await bot.send_message(
                chat_id=telegram_id,
                text=f"✅ Your deposit of {amount} ETB is confirmed and has been added to your balance."
            )
    except Exception as e:
        logger.error(f"Error processing Chapa webhook: {e}", exc_info=True)
    
    # Always return a 200 status to Chapa to prevent them from resending the webhook.
    return Response(status_code=200)

@app.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: int):
    """
    Handles live WebSocket connections from the Web App for real-time updates.
    It uses the `connection_manager` instance from handlers.py.
    """
    await connection_manager.connect(websocket, user_id)
    try:
        while True:
            # This loop keeps the connection alive.
            # You can add logic here to process messages sent FROM the client.
            data = await websocket.receive_text()
            logger.info(f"Received WebSocket data from user {user_id}: {data}")
    except Exception:
        # This block executes when the client disconnects.
        logger.info(f"User {user_id} disconnected from WebSocket.")
        connection_manager.disconnect(user_id)


# --- Static Files Mount ---
# This serves the index.html, styles.css, and app.js files for the Web App.
# It MUST be the last route definition.
app.mount("/", StaticFiles(directory="static", html=True), name="static")