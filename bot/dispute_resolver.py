# /bot/dispute_resolver.py (Final, Production Version)

import asyncio
import os
import logging
from decimal import Decimal
from dotenv import load_dotenv

# Important: Must be run as a module for relative imports to work
from database_models.manager import db_manager
from bot.handlers import bot # Import the bot instance

# --- Setup ---
load_dotenv()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

GAME_TIMEOUT_SECONDS = 90 # Forfeit after 90 seconds of inactivity
CHECK_INTERVAL_SECONDS = 30 # Check for inactive games every 30 seconds
ADMIN_ID = os.getenv("ADMIN_TELEGRAM_ID")

async def resolve_game(game):
    """Resolves a single timed-out game."""
    logger.warning(f"Game {game['game_id']} has timed out. Resolving...")
    
    forfeiting_player_id = game['current_turn_id']
    
    # Determine the winner
    if forfeiting_player_id == game['creator_id']:
        winner_id = game['opponent_id']
    else:
        winner_id = game['creator_id']
        
    if not winner_id:
        logger.error(f"Cannot resolve game {game['game_id']}: No opponent found.")
        return

    # Process the financial settlement
    prize = await db_manager.end_game_transaction(
        game_id=game['game_id'],
        winner_id=winner_id,
        stake=Decimal(game['stake']),
        forfeited=True
    )
    
    # Notify players
    try:
        await bot.send_message(
            chat_id=winner_id,
            text=f"🎉 Your opponent did not make a move in time. You won by forfeit!\n"
                 f"Prize of {prize:.2f} ETB has been added to your balance."
        )
        await bot.send_message(
            chat_id=forfeiting_player_id,
            text="❌ You did not make a move in time and have forfeited the game."
        )
        # Clean up the original game message if possible
        chat_id_for_board = game['creator_id'] # Or wherever it was sent
        await bot.edit_message_text(
            chat_id=chat_id_for_board,
            message_id=game['board_message_id'],
            text=f"Game Over (Forfeit). Winner: {winner_id}"
        )
    except Exception as e:
        logger.error(f"Failed to notify players for game {game['game_id']}: {e}")

async def check_for_inactive_games():
    """Periodically checks and resolves inactive games."""
    await db_manager.setup_database() # Ensure tables exist before starting
    while True:
        logger.info("Running check for inactive games...")
        try:
            inactive_games = await db_manager.find_inactive_games(GAME_TIMEOUT_SECONDS)
            if inactive_games:
                logger.info(f"Found {len(inactive_games)} inactive games to resolve.")
                for game in inactive_games:
                    await resolve_game(game)
            else:
                logger.info("No inactive games found.")
        except Exception as e:
            logger.error(f"An error occurred in the dispute resolver loop: {e}", exc_info=True)
            if ADMIN_ID:
                try:
                    await bot.send_message(chat_id=ADMIN_ID, text=f"DISPUTE RESOLVER ERROR: {e}")
                except Exception as send_e:
                    logger.error(f"Failed to send error notification to admin: {send_e}")

        await asyncio.sleep(CHECK_INTERVAL_SECONDS)

if __name__ == "__main__":
    logger.info("Starting dispute resolver worker...")
    asyncio.run(check_for_inactive_games())