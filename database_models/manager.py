import os
import asyncpg
import logging
from decimal import Decimal
from typing import Dict, Any, List

# --- Setup ---
logger = logging.getLogger(__name__)

class DBManager:
    """A singleton class to manage the application's database connection pool and execute queries."""
    _pool = None

    @classmethod
    async def get_pool(cls):
        """Initializes and returns the asyncpg connection pool."""
        if cls._pool is None:
            try:
                cls._pool = await asyncpg.create_pool(
                    dsn=os.getenv("DATABASE_URL"),
                    min_size=2,  # Maintain a minimum number of connections
                    max_size=20, # Limit the maximum number of connections
                    command_timeout=60,
                )
                logger.info("Database connection pool created successfully.")
            except Exception as e:
                logger.critical(f"Failed to create database connection pool: {e}", exc_info=True)
                raise
        return cls._pool

    async def setup_database(self):
        """Creates the necessary tables if they don't already exist."""
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    telegram_id BIGINT PRIMARY KEY,
                    username TEXT,
                    balance DECIMAL(12, 2) DEFAULT 0.00
                );
            ''')
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS games (
                    game_id SERIAL PRIMARY KEY,
                    creator_id BIGINT NOT NULL REFERENCES users(telegram_id),
                    opponent_id BIGINT REFERENCES users(telegram_id),
                    stake DECIMAL(10, 2) NOT NULL,
                    win_condition INT NOT NULL,
                    winner_id BIGINT,
                    status TEXT NOT NULL, -- 'lobby', 'active', 'finished', 'forfeited'
                    current_turn_id BIGINT,
                    board_message_id BIGINT,
                    game_data JSONB, -- Stores the entire LudoGame object state
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    last_action_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
            ''')
            logger.info("Database tables checked/created successfully.")

    async def get_or_create_user(self, user_id: int, username: str = None) -> asyncpg.Record:
        """Retrieves a user record or creates a new one if it doesn't exist."""
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            # Using an upsert for efficiency
            await conn.execute('''
                INSERT INTO users (telegram_id, username) VALUES ($1, $2)
                ON CONFLICT (telegram_id) DO NOTHING;
            ''', user_id, username)
            return await conn.fetchrow("SELECT * FROM users WHERE telegram_id = $1", user_id)

    async def get_user_balance(self, user_id: int) -> Decimal:
        """Gets a user's balance, returning 0.00 if the user doesn't exist."""
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            balance = await conn.fetchval("SELECT balance FROM users WHERE telegram_id = $1", user_id)
            return balance if balance is not None else Decimal('0.00')

    async def create_game(self, creator_id: int, stake: Decimal, win_condition: int, game_data: dict) -> int:
        """Creates a new game lobby and returns the new game_id."""
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            game_id = await conn.fetchval('''
                INSERT INTO games (creator_id, stake, win_condition, status, current_turn_id, game_data)
                VALUES ($1, $2, $3, 'lobby', $1, $4)
                RETURNING game_id;
            ''', creator_id, stake, win_condition, game_data)
            return game_id

    async def start_game_transaction(self, game_id: int, creator_id: int, opponent_id: int, stake: Decimal) -> bool:
        """
        Atomically checks balances, deducts stakes, and sets game to 'active'.
        Returns True on success, False on failure (e.g., insufficient funds).
        """
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                # Lock rows to prevent race conditions
                creator_balance = await conn.fetchval("SELECT balance FROM users WHERE telegram_id = $1 FOR UPDATE", creator_id)
                opponent_balance = await conn.fetchval("SELECT balance FROM users WHERE telegram_id = $1 FOR UPDATE", opponent_id)

                if creator_balance < stake or opponent_balance < stake:
                    logger.warning(f"Failed to start game {game_id}: Insufficient funds.")
                    return False

                # Deduct from both players
                await conn.execute("UPDATE users SET balance = balance - $1 WHERE telegram_id = $2", stake, creator_id)
                await conn.execute("UPDATE users SET balance = balance - $1 WHERE telegram_id = $2", stake, opponent_id)
                return True

    async def update_game_after_start(self, game_id: int, game_data: dict, message_id: int):
        """Updates the game record after a successful start transaction."""
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            opponent_id = next(pid for pid in game_data['player_order'] if pid != game_data['players'][pid]['player_index'] == 0)
            await conn.execute('''
                UPDATE games
                SET status = 'active', opponent_id = $1, game_data = $2, board_message_id = $3, last_action_at = NOW()
                WHERE game_id = $4
            ''', opponent_id, game_data, message_id, game_id)


    async def get_game(self, game_id: int) -> asyncpg.Record | None:
        """Retrieves basic information about a game."""
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            return await conn.fetchrow("SELECT * FROM games WHERE game_id = $1", game_id)

    async def get_full_game_state(self, game_id: int) -> asyncpg.Record | None:
        """Retrieves the full game record, including the JSONB data for gameplay."""
        return await self.get_game(game_id) # Same as get_game, more descriptive name for use in callbacks

    async def save_game_state(self, game_id: int, game_data: dict, current_turn_id: int):
        """Updates the game state in the database, resetting the inactivity timer."""
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            await conn.execute('''
                UPDATE games
                SET game_data = $1, current_turn_id = $2, last_action_at = NOW()
                WHERE game_id = $3
            ''', game_data, current_turn_id, game_id)

    async def end_game_transaction(self, game_id: int, winner_id: int, stake: Decimal, forfeited: bool = False) -> Decimal:
        """Atomically awards the prize to the winner and marks the game as finished."""
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                total_pot = stake * 2
                commission = total_pot * Decimal('0.10')
                prize = total_pot - commission

                # Add prize to winner's balance
                await conn.execute("UPDATE users SET balance = balance + $1 WHERE telegram_id = $2", prize, winner_id)

                # Update game status
                final_status = 'forfeited' if forfeited else 'finished'
                await conn.execute(
                    "UPDATE games SET status = $1, winner_id = $2 WHERE game_id = $3",
                    final_status, winner_id, game_id
                )
                logger.info(f"Game {game_id} ended. Winner: {winner_id}, Prize: {prize}")
                return prize

    async def process_deposit(self, telegram_id: int, amount: float):
        """Credits a user's account after a deposit, applying a 2% fee."""
        pool = await self.get_pool()
        amount_decimal = Decimal(str(amount))
        fee = amount_decimal * Decimal('0.02')
        final_amount = amount_decimal - fee

        async with pool.acquire() as conn:
            await self.get_or_create_user(telegram_id) # Ensure user exists
            await conn.execute("UPDATE users SET balance = balance + $1 WHERE telegram_id = $2", final_amount, telegram_id)
            logger.info(f"Credited {final_amount:.2f} to user {telegram_id} (Amount: {amount}, Fee: {fee:.2f})")

    async def find_inactive_games(self, timeout_seconds: int) -> List[asyncpg.Record]:
        """Finds active games where the last action was longer ago than the timeout."""
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            return await conn.fetch(
                """
                SELECT * FROM games
                WHERE status = 'active' AND last_action_at < NOW() - MAKE_INTERVAL(secs => $1)
                """,
                timeout_seconds
            )

# Create a single, globally accessible instance of the DBManager.
db_manager = DBManager()