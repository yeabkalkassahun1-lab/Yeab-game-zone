# /bot/game_logic.py (Updated to match the new 15x15 renderer)

import random
from typing import Dict, Any, List

class LudoGame:
    # --- Game Constants Synchronized with Renderer ---
    PATH_LENGTH = 52
    HOME_STRETCH_START = 52
    HOME_STRETCH_LENGTH = 6
    WINNING_POSITION = 58  # 52 (start) + 6 (stretch length) = 58
    
    # Player setup: index, color, and start position on the path
    PLAYER_CONFIG = [
        {'color': '🔴', 'start_pos': 0},   # Player 0: Red
        {'color': '🟢', 'start_pos': 13},  # Player 1: Green
        {'color': '🟡', 'start_pos': 26},  # Player 2: Yellow
        {'color': '🔵', 'start_pos': 39},  # Player 3: Blue
    ]
    SAFE_ZONES = [0, 8, 13, 21, 26, 34, 39, 47]

    def __init__(self, creator_id: int, stake: float, win_condition: int):
        self.players: Dict[int, Dict[str, Any]] = {}
        self.player_order: List[int] = []
        self.stake = stake
        self.win_condition = win_condition
        self.current_turn_player_id: int = creator_id
        self.dice_roll: int = 0
        self.consecutive_sixes: int = 0
        self.winner: int | None = None

        # Add the game creator as the first player
        self.add_player(creator_id)

    def add_player(self, player_id: int) -> bool:
        if len(self.players) >= 4:
            return False
        
        player_index = len(self.players)
        config = self.PLAYER_CONFIG[player_index]
        
        self.players[player_id] = {
            'player_index': player_index,
            'color': config['color'],
            'start_pos': config['start_pos'],
            # Positions: -1=Yard, 0-51=Path, 52-57=Stretch, 58=Home
            'tokens': [-1, -1, -1, -1]
        }
        self.player_order.append(player_id)
        return True

    def roll_dice(self) -> (int, bool):
        """Rolls the dice and checks for three consecutive sixes."""
        self.dice_roll = random.randint(1, 6)
        if self.dice_roll == 6:
            self.consecutive_sixes += 1
        else:
            self.consecutive_sixes = 0
        
        turn_lost = self.consecutive_sixes == 3
        if turn_lost:
            self.consecutive_sixes = 0
        return self.dice_roll, turn_lost

    def get_movable_tokens(self, player_id: int) -> List[int]:
        """Returns a list of token indices that can be moved with the current dice roll."""
        player_data = self.players[player_id]
        movable = []
        for i, pos in enumerate(player_data['tokens']):
            if pos == self.WINNING_POSITION:
                continue # Cannot move a token that is already home

            if pos == -1 and self.dice_roll == 6:
                movable.append(i) # Can move from yard
            
            elif pos != -1:
                # Check if an exact roll is needed to get home
                if pos >= self.HOME_STRETCH_START:
                    if pos + self.dice_roll <= self.WINNING_POSITION:
                        movable.append(i)
                else:
                    movable.append(i)
        return movable

    def move_token(self, player_id: int, token_index: int):
        """Executes the move for a given token, including knockouts and winning."""
        player_data = self.players[player_id]
        current_pos = player_data['tokens'][token_index]

        # --- 1. Move from Yard ---
        if current_pos == -1:
            new_pos = player_data['start_pos']
            player_data['tokens'][token_index] = new_pos
            self._handle_knockout(new_pos, player_id)
            return

        # --- 2. Calculate New Position ---
        home_entry_pos = (player_data['start_pos'] - 1 + self.PATH_LENGTH) % self.PATH_LENGTH
        
        # Check if the move crosses the player's home entry point
        is_passing_home = False
        temp_pos = current_pos
        for _ in range(self.dice_roll):
            temp_pos = (temp_pos + 1) % self.PATH_LENGTH
            if temp_pos == player_data['start_pos']:
                is_passing_home = True
                break
        
        if not is_passing_home and current_pos < self.HOME_STRETCH_START:
            new_pos = (current_pos + self.dice_roll) % self.PATH_LENGTH
        else:
            # Entering or moving within the home stretch
            if current_pos < self.HOME_STRETCH_START:
                steps_after_entry = self.dice_roll - ((home_entry_pos - current_pos + self.PATH_LENGTH) % self.PATH_LENGTH)
                new_pos = self.HOME_STRETCH_START + steps_after_entry - 1
            else: # Already in stretch
                new_pos = current_pos + self.dice_roll
        
        # Clamp to winning position
        if new_pos > self.WINNING_POSITION:
             new_pos = player_data['tokens'][token_index] # Invalid move, revert
        
        player_data['tokens'][token_index] = new_pos

        # --- 3. Handle Knockout & Check for Winner ---
        if new_pos < self.HOME_STRETCH_START:
            self._handle_knockout(new_pos, player_id)
        
        self.check_for_winner(player_id)

    def _handle_knockout(self, position: int, current_player_id: int):
        if position in self.SAFE_ZONES:
            return

        for player_id, data in self.players.items():
            if player_id == current_player_id:
                continue
            
            # A block is formed by two or more tokens of the same color on a single spot.
            if data['tokens'].count(position) > 1: return # Position is blocked

            for i, token_pos in enumerate(data['tokens']):
                if token_pos == position:
                    data['tokens'][i] = -1 # Knockout: send back to yard

    def check_for_winner(self, player_id: int):
        """Checks if the player has met the win condition."""
        tokens_home = self.players[player_id]['tokens'].count(self.WINNING_POSITION)
        if tokens_home >= self.win_condition:
            self.winner = player_id

    def advance_turn(self):
        """Moves the turn to the next player in order."""
        current_player_index = self.player_order.index(self.current_turn_player_id)
        next_player_index = (current_player_index + 1) % len(self.player_order)
        self.current_turn_player_id = self.player_order[next_player_index]

    def get_state(self) -> Dict[str, Any]:
        """Returns the current game state in a format the renderer can use."""
        return {
            'players': self.players,
            'current_turn_player_id': self.current_turn_player_id,
            'dice_roll': self.dice_roll,
            'winner': self.winner,
        }