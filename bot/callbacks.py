# /bot/callbacks.py (Final, Production Version)

import logging
from decimal import Decimal

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.error import BadRequest

from .game_logic import LudoGame
from .renderer import render_board
from database_models.manager import db_manager

logger = logging.getLogger(__name__)

async def dispatch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Parses all callback queries and routes them to the correct handler."""
    query = update.callback_query
    await query.answer()

    try:
        action, *params = query.data.split(':')
        game_id = int(params[0]) if params else None
    except (ValueError, IndexError):
        await query.edit_message_text("Invalid callback data.")
        return

    # --- Route to the correct function based on the action ---
    if action == 'join':
        await handle_join_game(query, context, game_id)
    elif action == 'roll':
        await handle_roll_dice(query, context, game_id)
    elif action == 'move':
        token_index = int(params[1])
        await handle_move_token(query, context, game_id, token_index)
    elif action == 'pass':
        await handle_pass_turn(query, context, game_id)


async def handle_join_game(query, context, game_id):
    """Handles a player clicking the 'Join Game' button."""
    player_b_id = query.from_user.id
    game_record = await db_manager.get_game(game_id)

    if not game_record or game_record['status'] != 'lobby':
        await query.edit_message_text("This game is no longer available.")
        return
    if player_b_id == game_record['creator_id']:
        await context.bot.answer_callback_query(query.id, "You cannot join your own game.", show_alert=True)
        return

    stake = game_record['stake']
    player_b_balance = await db_manager.get_user_balance(player_b_id)
    if player_b_balance < stake:
        await context.bot.answer_callback_query(query.id, "Insufficient funds to join.", show_alert=True)
        return

    success = await db_manager.start_game_transaction(
        game_id=game_id,
        creator_id=game_record['creator_id'],
        opponent_id=player_b_id,
        stake=stake
    )
    if not success:
        await query.edit_message_text("An error occurred starting the game. Please try again.")
        return

    game = LudoGame(creator_id=0, stake=0, win_condition=0)
    game.players = game_record['game_data']['players']
    game.add_player(player_b_id)
    
    board_text = render_board(game.get_state())
    roll_button = InlineKeyboardButton("🎲 Roll Dice", callback_data=f"roll:{game_id}")
    reply_markup = InlineKeyboardMarkup([[roll_button]])
    
    try:
        await query.edit_message_text(f"{board_text}\n\nTurn: {game.players[game.current_turn_player_id]['color']}", reply_markup=reply_markup)
        await db_manager.update_game_after_start(game_id, game.get_state(), query.message.message_id)
    except BadRequest as e:
        if "message is not modified" not in str(e): logger.error(f"Error updating message on join: {e}")

async def handle_roll_dice(query, context, game_id):
    player_id = query.from_user.id
    game_record = await db_manager.get_full_game_state(game_id)
    
    if not game_record or player_id != game_record['current_turn_id']:
        await context.bot.answer_callback_query(query.id, "It's not your turn!")
        return
    
    game = LudoGame(creator_id=0, stake=0, win_condition=0)
    game.__dict__.update(game_record['game_data'])

    roll, turn_lost = game.roll_dice()
    
    if turn_lost:
        game.advance_turn()
        board_text = render_board(game.get_state())
        next_player_color = game.players[game.current_turn_player_id]['color']
        roll_button = InlineKeyboardButton("🎲 Roll Dice", callback_data=f"roll:{game_id}")
        await query.edit_message_text(
            f"{board_text}\n\nYou rolled three 6s and lost your turn!\n\nTurn: {next_player_color}",
            reply_markup=InlineKeyboardMarkup([[roll_button]])
        )
        await db_manager.save_game_state(game_id, game.get_state(), game.current_turn_player_id)
        return

    movable_tokens = game.get_movable_tokens(player_id)
    board_text = render_board(game.get_state())
    player_color = game.players[player_id]['color']
    
    buttons = []
    if not movable_tokens:
        buttons.append(InlineKeyboardButton("😔 No moves, pass turn", callback_data=f"pass:{game_id}"))
    else:
        for token_idx in movable_tokens:
            buttons.append(InlineKeyboardButton(f"Move Token {token_idx + 1}", callback_data=f"move:{game_id}:{token_idx}"))
    
    await query.edit_message_text(
        f"{board_text}\n\n{player_color} you rolled a {roll}! Choose your move:",
        reply_markup=InlineKeyboardMarkup([buttons])
    )
    await db_manager.save_game_state(game_id, game.get_state(), game.current_turn_player_id)

async def handle_move_token(query, context, game_id, token_index):
    player_id = query.from_user.id
    game_record = await db_manager.get_full_game_state(game_id)

    if not game_record or player_id != game_record['current_turn_id']:
        await context.bot.answer_callback_query(query.id, "It's not your turn!")
        return

    game = LudoGame(creator_id=0, stake=0, win_condition=0)
    game.__dict__.update(game_record['game_data'])

    game.move_token(player_id, token_index)
    
    if game.winner:
        await handle_game_over(query, context, game_id, game_record, game)
        return

    if game.dice_roll != 6:
        game.advance_turn()

    board_text = render_board(game.get_state())
    next_player_color = game.players[game.current_turn_player_id]['color']
    roll_button = InlineKeyboardButton("🎲 Roll Dice", callback_data=f"roll:{game_id}")
    
    await query.edit_message_text(
        f"{board_text}\n\nTurn: {next_player_color}",
        reply_markup=InlineKeyboardMarkup([[roll_button]])
    )
    await db_manager.save_game_state(game_id, game.get_state(), game.current_turn_player_id)

async def handle_pass_turn(query, context, game_id):
    player_id = query.from_user.id
    game_record = await db_manager.get_full_game_state(game_id)
    if not game_record or player_id != game_record['current_turn_id']:
        return

    game = LudoGame(creator_id=0, stake=0, win_condition=0)
    game.__dict__.update(game_record['game_data'])
    game.advance_turn()

    board_text = render_board(game.get_state())
    next_player_color = game.players[game.current_turn_player_id]['color']
    roll_button = InlineKeyboardButton("🎲 Roll Dice", callback_data=f"roll:{game_id}")
    await query.edit_message_text(f"{board_text}\n\nTurn: {next_player_color}", reply_markup=InlineKeyboardMarkup([[roll_button]]))
    await db_manager.save_game_state(game_id, game.get_state(), game.current_turn_player_id)

async def handle_game_over(query, context, game_id, game_record, game_obj):
    winner_id = game_obj.winner
    loser_id = next(pid for pid in game_obj.player_order if pid != winner_id)
    
    prize = await db_manager.end_game_transaction(
        game_id=game_id,
        winner_id=winner_id,
        stake=Decimal(game_record['stake'])
    )
    
    board_text = render_board(game_obj.get_state())
    winner_color = game_obj.players[winner_id]['color']
    await query.edit_message_text(f"{board_text}\n\n🎉 GAME OVER! {winner_color} has won! 🎉")
    
    await context.bot.send_message(winner_id, f"Congratulations! You won the game and a prize of {prize:.2f} ETB has been added to your balance.")
    await context.bot.send_message(loser_id, "You lost the game. Better luck next time!")