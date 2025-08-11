# /bot/renderer.py (Final, Perfected Version with 15x15 Grid)

from typing import Dict, Any

# --- 1. Define the Board's Visual Layout ---
# THIS IS THE FINAL, SYMMETRICAL, AND VISUALLY CORRECT 15x15 LAYOUT.
BOARD_LAYOUT = [
    "⬛️⬛️⬛️⬛️⬛️⬜️⬜️⬜️⬛️⬛️⬛️⬛️⬛️⬛️",
    "⬛️🔴🔴⬛️⬛️⬜️🟩⬜️⬛️⬛️⬛️🟢🟢⬛️",
    "⬛️🔴🔴⬛️⬛️⬜️🟩⬜️⬛️⬛️⬛️🟢🟢⬛️",
    "⬛️⬛️⬛️⬛️⬛️⬜️🟩⬜️⬛️⬛️⬛️⬛️⬛️⬛️",
    "⬛️⬛️⬛️⬛️⬛️⬜️🟩⬜️⬛️⬛️⬛️⬛️⬛️⬛️",
    "⬜️⬜️⬜️⬜️⬜️⬜️⭐️⬜️⬜️⬜️⬜️⬜️⬜️⬜️",
    "⬜️🟥🟥🟥🟥🟥💎🟦🟦🟦🟦🟦🟦⬜️",
    "⬜️⬜️⬜️⬜️⬜️⬜️⭐️⬜️⬜️⬜️⬜️⬜️⬜️⬜️",
    "⬛️⬛️⬛️⬛️⬛️⬜️🟨⬜️⬛️⬛️⬛️⬛️⬛️⬛️",
    "⬛️⬛️⬛️⬛️⬛️⬜️🟨⬜️⬛️⬛️⬛️⬛️⬛️⬛️",
    "⬛️⬛️⬛️⬛️⬛️⬜️🟨⬜️⬛️⬛️⬛️⬛️⬛️⬛️",
    "⬛️🟡🟡⬛️⬛️⬜️🟨⬜️⬛️⬛️⬛️🔵🔵⬛️",
    "⬛️🟡🟡⬛️⬛️⬜️🟨⬜️⬛️⬛️⬛️🔵🔵⬛️",
    "⬛️⬛️⬛️⬛️⬛️⬜️⬜️⬜️⬛️⬛️⬛️⬛️⬛️⬛️",
]

# --- 2. CRITICAL: Re-Calculated Coordinate Maps to Match the New 15x15 Layout ---
# Maps the 52 positions on the main path to (row, col) coordinates.
PATH_COORDS = {
    0: (6, 1), 1: (6, 2), 2: (6, 3), 3: (6, 4), 4: (6, 5),
    5: (5, 6), 6: (4, 6), 7: (3, 6), 8: (2, 6), 9: (1, 6),
    10: (0, 6), 11: (0, 7), 12: (0, 8), # Top-center corrected
    13: (1, 8), 14: (2, 8), 15: (3, 8), 16: (4, 8), 17: (5, 8),
    18: (6, 9), 19: (6, 10), 20: (6, 11), 21: (6, 12), 22: (6, 13),
    23: (7, 14), 24: (8, 14), # Right-center corrected
    25: (8, 13), 26: (8, 12), 27: (8, 11), 28: (8, 10), 29: (8, 9),
    30: (9, 8), 31: (10, 8), 32: (11, 8), 33: (12, 8), 34: (13, 8),
    35: (14, 8), 36: (14, 7), 37: (14, 6), # Bottom-center corrected
    38: (13, 6), 39: (12, 6), 40: (11, 6), 41: (10, 6), 42: (9, 6),
    43: (8, 5), 44: (8, 4), 45: (8, 3), 46: (8, 2), 47: (8, 1),
    48: (7, 0), 49: (6, 0), # Left-center corrected
    50: (5, 0), 51: (4, 0), 52: (3, 0), 53: (2, 0), 54: (1, 0)
}


# Maps for the home yards and home stretches for each player index (0-3).
PLAYER_ZONES = [
    # Red (Player 0) - Bottom Left in grid
    {'yard': [(13, 1), (13, 2), (12, 1), (12, 2)], 'stretch': [(7, 1), (7, 2), (7, 3), (7, 4), (7, 5), (7, 6)]},
    # Green (Player 1) - Top Left in grid
    {'yard': [(1, 1), (1, 2), (2, 1), (2, 2)], 'stretch': [(1, 7), (2, 7), (3, 7), (4, 7), (5, 7), (6, 7)]},
    # Yellow (Player 2) - Top Right in grid
    {'yard': [(1, 12), (1, 13), (2, 12), (2, 13)], 'stretch': [(7, 13), (7, 12), (7, 11), (7, 10), (7, 9), (7, 8)]},
    # Blue (Player 3) - Bottom Right in grid
    {'yard': [(13, 12), (13, 13), (12, 12), (12, 13)], 'stretch': [(13, 7), (12, 7), (11, 7), (10, 7), (9, 7), (8, 7)]}
]

# --- 3. The Main Rendering Function ---
def render_board(game_state: Dict[str, Any]) -> str:
    """
    Generates a visual, emoji-based representation of the Ludo board from a game_state dictionary.
    """
    board = [list(row) for row in BOARD_LAYOUT]
    
    players_data = game_state.get('players', {})
    for player_id, data in players_data.items():
        player_index = data.get('player_index')
        player_color = data.get('color')
        
        # Ensure player_index and color are valid before proceeding
        if player_index is None or player_color is None:
            continue
            
        yard_spot_index = 0
        
        for token_pos in data['tokens']:
            coords = None
            if token_pos == -1:  # Token is in the home yard
                if yard_spot_index < len(PLAYER_ZONES[player_index]['yard']):
                    coords = PLAYER_ZONES[player_index]['yard'][yard_spot_index]
                    yard_spot_index += 1
            
            elif token_pos == 58:  # Token is in the final home position
                # This is the center '💎', no need to draw a token on top
                continue

            elif token_pos >= 52:  # Token is in the home stretch
                stretch_index = token_pos - 52
                if stretch_index < len(PLAYER_ZONES[player_index]['stretch']):
                    coords = PLAYER_ZONES[player_index]['stretch'][stretch_index]
            
            else:  # Token is on the main path
                coords = PATH_COORDS.get(token_pos)

            if coords:
                row, col = coords
                # Check for blocking (multiple tokens on the same spot)
                if board[row][col] in ['🔴', '🟢', '🟡', '🔵', '🧱']:
                    board[row][col] = '🧱' 
                else:
                    board[row][col] = player_color

    return "\n".join("".join(row) for row in board)