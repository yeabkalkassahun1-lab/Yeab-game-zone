import os
import asyncio
import logging
from fastapi import FastAPI, Request, Response, HTTPException, WebSocket
from fastapi.staticfiles import StaticFiles
from telegram import Update
from bot.handlers import application, bot, connection_manager
from database_models.manager import db_manager
from dotenv import load_dotenv

# --- Setup ---
load_dotenv()
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Environment & FastAPI App ---
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
app = FastAPI()

# --- Event Handlers ---
@app.on_event("startup")
async def startup():
    """On startup, setup the database and Telegram webhook."""
    await db_manager.get_pool()  # Initialize the DB pool
    if WEBHOOK_URL:
        webhook_full_url = f"{WEBHOOK_URL}/api/telegram"
        await bot.set_webhook(url=webhook_full_url, allowed_updates=Update.ALL_TYPES)
        logger.info(f"Webhook set to {webhook_full_url}")
    else:
        logger.warning("WEBHOOK_URL not set. Running in polling mode is not supported by this setup.")

# --- API Routes ---
@app.post("/api/telegram")
async def telegram_webhook(request: Request):
    """Handle incoming Telegram updates."""
    try:
        data = await request.json()
        update = Update.de_json(data, bot)
        await application.process_update(update)
    except Exception as e:
        logger.error(f"Error processing update: {e}", exc_info=True)
    return Response(status_code=200)

@app.post("/api/chapa/webhook")
async def chapa_webhook(request: Request):
    """Handle incoming Chapa payment confirmations."""
    # Note: In production, it's vital to verify the webhook's authenticity
    try:
        payload = await request.json()
        logger.info(f"Chapa webhook received: {payload}")
        if payload.get("status") == "success":
            tx_ref = payload.get("tx_ref")
            amount = payload.get("amount")
            telegram_id = int(tx_ref.split('-')[-1])
            await db_manager.process_deposit(telegram_id, float(amount))
            await bot.send_message(
                chat_id=telegram_id,
                text=f"✅ Your deposit of {amount} ETB is confirmed and has been added to your balance."
            )
    except Exception as e:
        logger.error(f"Error processing Chapa webhook: {e}", exc_info=True)
    return Response(status_code=200) # Always return 200 to Chapa

@app.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: int):
    """Handle WebSocket connections from the Web App."""
    await connection_manager.connect(websocket, user_id)
    try:
        while True:
            data = await websocket.receive_text()
            # Logic to handle messages from client (e.g., create_game, join_game)
            # This part needs to be built out based on client-side events.
            logger.info(f"Received from {user_id}: {data}")
    except Exception:
        connection_manager.disconnect(user_id)

# --- Static Files ---
app.mount("/", StaticFiles(directory="static", html=True), name="static")