import asyncpg
import os

DATABASE_URL = os.environ.get("DATABASE_URL")

async def get_connection():
    return await asyncpg.connect(DATABASE_URL)

async def setup_database():
    conn = await get_connection()
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            telegram_id BIGINT PRIMARY KEY,
            username TEXT,
            balance DECIMAL(10, 2) DEFAULT 0.00
        );
    ''')
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS games (
            id SERIAL PRIMARY KEY,
            creator_id BIGINT,
            opponent_id BIGINT,
            stake DECIMAL(10, 2),
            win_condition INT,
            winner_id BIGINT,
            status TEXT,
            last_action_timestamp TIMESTAMPTZ DEFAULT NOW()
        );
    ''')
    await conn.close()

async def get_user_balance(user_id):
    conn = await get_connection()
    balance = await conn.fetchval("SELECT balance FROM users WHERE telegram_id = $1", user_id)
    await conn.close()
    return balance

async def update_user_balance(user_id, new_balance):
    conn = await get_connection()
    await conn.execute("UPDATE users SET balance = $1 WHERE telegram_id = $2", new_balance, user_id)
    await conn.close()

# Add more functions for game creation, updates, etc.