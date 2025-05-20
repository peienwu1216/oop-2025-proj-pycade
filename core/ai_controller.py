# oop-2025-proj-pycade/core/ai_controller.py

import pygame
import settings
import random # For random movements or decisions
from collections import deque # For BFS pathfinding

# Define AI States (similar to your C++ enum)
# We can use an Enum class for better organization if preferred,
# but strings or simple constants work too.
AI_STATE_IDLE = "IDLE"
AI_STATE_ESCAPE = "ESCAPE"
AI_STATE_ATTACK_PLAYER = "ATTACK_PLAYER"
AI_STATE_FETCH_ITEMS = "FETCH_ITEMS"
AI_STATE_WAIT_EXPLOSION = "WAIT_EXPLOSION" # If AI places a bomb and needs to wait

# Directions for BFS and movement
DIRECTIONS = {
    "UP": (0, -1),
    "DOWN": (0, 1),
    "LEFT": (-1, 0),
    "RIGHT": (1, 0)
}
# Reverse mapping for converting delta to direction string (optional, for debugging)
DELTA_TO_DIRECTION = {v: k for k, v in DIRECTIONS.items()}


class AIController:
    """
    Manages the AI player's behavior using a Finite State Machine (FSM)
    and Breadth-First Search (BFS) for pathfinding.
    """
    def __init__(self, ai_player_sprite, game_instance):
        """
        Initializes the AIController.

        Args:
            ai_player_sprite (Player): The Player sprite instance that this AI will control.
            game_instance (Game): The main game instance for accessing game state.
        """
        self.ai_player = ai_player_sprite # The Player object this AI controls
        self.game = game_instance
        
        self.current_state = AI_STATE_IDLE
        self.state_start_time = pygame.time.get_ticks() # Time when the current state started

        # Pathfinding attributes
        self.current_path = [] # List of (tile_x, tile_y) tuples representing the path
        self.current_path_index = 0
        
        # AI behavior parameters (can be tuned)
        self.ai_move_delay = settings.AI_MOVE_DELAY if hasattr(settings, 'AI_MOVE_DELAY') else 200 # Milliseconds between AI "thinking" or major moves
        self.last_ai_move_time = pygame.time.get_ticks()
        
        self.target_player = None # Typically player1 if AI is player2
        self.target_item = None   # Target item sprite
        self.escape_target_tile = None # Tile to escape to

        self.last_bomb_placed_time = 0 # When AI last placed a bomb
        self.ai_placed_bomb_recently = False

        # For BFS debugging or visualization (optional)
        self.bfs_visited_visual = [] 

        print(f"AIController initialized for Player ID: {id(self.ai_player)}")

    def update_state_machine(self):
        """
        The 'brain' of the AI. Decides which state the AI should be in
        based on the current game situation. This will be similar to your
        C++ updateState method.
        
        Order of priority for state changes (example):
        1. Escape if in danger.
        2. Attack if player is vulnerable and AI is safe.
        3. Fetch items if available and safe.
        4. Idle or patrol.
        """
        # This will be a complex function determining state transitions.
        # For now, let's keep it simple or as a placeholder.
        
        # Placeholder: Simple logic to switch state if idle for too long (e.g., to fetch items)
        if self.current_state == AI_STATE_IDLE and \
           pygame.time.get_ticks() - self.state_start_time > 5000: # If idle for 5 seconds
            # Try to find an item (we'll implement find_closest_item later)
            # closest_item = self.find_closest_item()
            # if closest_item:
            #     self.change_state(AI_STATE_FETCH_ITEMS, target_item=closest_item)
            pass # We'll fill this in later with more sophisticated logic


    def change_state(self, new_state, target_player=None, target_item=None, escape_tile=None):
        """Changes the AI's current state and resets necessary variables."""
        if self.current_state != new_state:
            print(f"AI (Player {id(self.ai_player)}) changing state from {self.current_state} to {new_state}")
            self.current_state = new_state
            self.state_start_time = pygame.time.get_ticks()
            self.current_path = [] # Clear any previous path
            self.current_path_index = 0
            
            # Store targets relevant to the new state
            self.target_player = target_player
            self.target_item = target_item
            self.escape_target_tile = escape_tile
        elif new_state == AI_STATE_FETCH_ITEMS and target_item != self.target_item:
            # If already fetching but target item changes
             print(f"AI (Player {id(self.ai_player)}) updating fetch item target.")
             self.target_item = target_item
             self.current_path = []
             self.current_path_index = 0


    def perform_current_state_action(self):
        """
        Executes actions based on the AI's current state.
        This will call specific handler methods like handle_idle_state, handle_attack_state, etc.
        """
        if self.current_state == AI_STATE_IDLE:
            self.handle_idle_state()
        elif self.current_state == AI_STATE_ESCAPE:
            self.handle_escape_state()
        elif self.current_state == AI_STATE_ATTACK_PLAYER:
            self.handle_attack_player_state()
        elif self.current_state == AI_STATE_FETCH_ITEMS:
            self.handle_fetch_items_state()
        elif self.current_state == AI_STATE_WAIT_EXPLOSION:
            self.handle_wait_explosion_state()

    # --- Placeholder Handler Methods (to be implemented one by one) ---
    def handle_idle_state(self):
        # Example: Move randomly or patrol a small area
        # For now, do nothing or a very simple random move
        if random.random() < 0.1: # Small chance to move
            direction = random.choice(list(DIRECTIONS.keys()))
            # self.ai_player.attempt_move(direction) # We'll need a way for AI to tell player to move
            # For now, print intention
            # print(f"AI Idle: intends to move {direction}")
            pass


    def handle_escape_state(self):
        # Find a safe path and move along it.
        # If no path, or at destination, what to do?
        # print(f"AI Escaping: current path {self.current_path}")
        pass

    def handle_attack_player_state(self):
        # Move towards target_player, decide when to place a bomb.
        # print(f"AI Attacking: target {self.target_player}, path {self.current_path}")
        pass

    def handle_fetch_items_state(self):
        # Move towards target_item.
        # print(f"AI Fetching: target {self.target_item}, path {self.current_path}")
        pass
        
    def handle_wait_explosion_state(self):
        # AI has placed a bomb and is waiting for it to explode,
        # possibly while at a safe spot.
        # print(f"AI Waiting for explosion.")
        # if pygame.time.get_ticks() - self.last_bomb_placed_time > settings.BOMB_TIMER + 500: # Wait a bit after explosion
        #     self.ai_placed_bomb_recently = False
        #     self.change_state(AI_STATE_IDLE) # Or re-evaluate
        pass

    # --- Pathfinding (BFS) ---
    def bfs_find_path(self, start_tile, end_tile_or_tiles, avoid_danger=True):
        """
        Performs Breadth-First Search to find a path.
        Args:
            start_tile (tuple): (tile_x, tile_y) start position.
            end_tile_or_tiles (tuple or list): (tile_x, tile_y) target, or list of possible targets.
            avoid_danger (bool): If true, avoid tiles marked as dangerous.
        Returns:
            list: A list of (tile_x, tile_y) tuples representing the path, or empty list if no path.
        """
        # This will be a direct translation of your C++ BFS.
        # Key components:
        # - Queue (collections.deque)
        # - Visited set/array
        # - Parent tracking array (to reconstruct path)
        # - Map data access (is_walkable, is_dangerous) from self.game.map_manager
        #   or a danger map computed by the AI.
        
        # Placeholder
        # print(f"BFS: Start {start_tile}, End {end_tile_or_tiles}, Avoid Danger {avoid_danger}")
        self.current_path = [] # Clear path before new search
        self.current_path_index = 0
        self.bfs_visited_visual = [] # For debugging pathfinding

        q = deque([(start_tile, [start_tile])]) # (current_tile, path_so_far)
        visited = {start_tile}

        map_mgr = self.game.map_manager
        
        # Handle single or multiple targets
        targets = []
        if isinstance(end_tile_or_tiles, list):
            targets.extend(end_tile_or_tiles)
        else:
            targets.append(end_tile_or_tiles)
        
        if not targets: return []


        while q:
            (curr_x, curr_y), path = q.popleft()
            self.bfs_visited_visual.append((curr_x, curr_y)) # For debug drawing

            if (curr_x, curr_y) in targets: # Found a path to one of the targets
                # print(f"BFS: Path found to {(curr_x, curr_y)}: {path}")
                return path

            for dir_name, (dx, dy) in DIRECTIONS.items():
                next_x, next_y = curr_x + dx, curr_y + dy

                if (next_x, next_y) not in visited:
                    if map_mgr.is_walkable(next_x, next_y): # Check map boundaries and non-obstacle tiles
                        # TODO: Add danger avoidance logic if avoid_danger is True
                        # is_dangerous = self.is_tile_dangerous(next_x, next_y)
                        # if avoid_danger and is_dangerous:
                        #     continue
                        
                        visited.add((next_x, next_y))
                        new_path = list(path)
                        new_path.append((next_x, next_y))
                        q.append(((next_x, next_y), new_path))
        
        # print("BFS: No path found.")
        return [] # No path found

    def move_along_path(self):
        """Moves the AI player one step along the self.current_path."""
        if not self.current_path or self.current_path_index >= len(self.current_path) -1:
            # print("AI: Path completed or no path to follow.")
            self.current_path = []
            self.current_path_index = 0
            return False # Path finished or invalid

        next_tile_x, next_tile_y = self.current_path[self.current_path_index + 1]
        
        current_ai_tile_x = self.ai_player.rect.centerx // settings.TILE_SIZE
        current_ai_tile_y = self.ai_player.rect.centery // settings.TILE_SIZE

        dx = next_tile_x - current_ai_tile_x
        dy = next_tile_y - current_ai_tile_y

        # Determine direction based on dx, dy
        # This needs to trigger the AI Player's movement.
        # The Player sprite needs a method like attempt_move(direction_vector) or similar
        # For now, let's just print the intended move and advance path.
        
        # print(f"AI (Player {id(self.ai_player)}) moving from ({current_ai_tile_x},{current_ai_tile_y}) towards ({next_tile_x},{next_tile_y}). Delta: ({dx},{dy})")

        # --- This is where AI tells its Player sprite to move ---
        # This requires Player class to have a method that AI can call.
        # For example: self.ai_player.set_ai_movement_intent(dx, dy)
        # And Player.update would use this intent instead of get_input() if it's an AI.
        # For now, we'll directly manipulate vx, vy if player type is AI
        # THIS IS A SIMPLIFICATION and might need refinement.
        if hasattr(self.ai_player, 'is_ai') and self.ai_player.is_ai:
            # Ensure player is aligned to grid before making a "tile step" decision
            # This is a common issue in tile-based AI movement.
            # If not perfectly aligned, AI might try to move based on a slightly off current tile.
            # For now, we assume AI moves are "sharp" from tile center to tile center.

            if dx == 1: self.ai_player.vx = self.ai_player.speed
            elif dx == -1: self.ai_player.vx = -self.ai_player.speed
            else: self.ai_player.vx = 0

            if dy == 1: self.ai_player.vy = self.ai_player.speed
            elif dy == -1: self.ai_player.vy = -self.ai_player.speed
            else: self.ai_player.vy = 0
            
            # A more robust way is for Player to have:
            # self.ai_player.move_to_tile(next_tile_x, next_tile_y)
            # which would then handle the sub-tile pixel movement over a few frames.
            # For this step, directly setting vx,vy will make it try to move.
            # The Player's own update and collision will handle the actual pixel move.
            # We only advance the path index if the AI has reached the center of the next tile.
            
            # Crude check if AI is close to the center of the next target tile in path
            next_pixel_x = next_tile_x * settings.TILE_SIZE + settings.TILE_SIZE // 2
            next_pixel_y = next_tile_y * settings.TILE_SIZE + settings.TILE_SIZE // 2
            dist_to_next_target_center = pygame.math.Vector2(self.ai_player.rect.centerx - next_pixel_x, 
                                                            self.ai_player.rect.centery - next_pixel_y).length()

            if dist_to_next_target_center < self.ai_player.speed : # If close enough to center
                self.current_path_index += 1
                # Snap to center to avoid overshooting if movement is fast
                self.ai_player.rect.centerx = next_pixel_x
                self.ai_player.rect.centery = next_pixel_y
                self.ai_player.vx = 0 # Stop once snapped
                self.ai_player.vy = 0 
                if self.current_path_index >= len(self.current_path) -1:
                     # print("AI: Reached end of current path.")
                     self.current_path = [] # Clear path
                     self.current_path_index = 0
                return True # Advanced path

        return False # Did not advance path index this frame (still moving towards current next_tile)

    def is_tile_dangerous(self, tile_x, tile_y):
        """Checks if a given tile is currently in an explosion's path or has a ticking bomb."""
        # Check active bombs (bombs that will explode soon)
        for bomb in self.game.bombs_group:
            # If the bomb is on the tile or its explosion range covers this tile
            # This needs a more sophisticated check based on bomb's timer and range
            # For now, let's say if a bomb is on the tile, it's dangerous
            if bomb.current_tile_x == tile_x and bomb.current_tile_y == tile_y:
                return True 
            # TODO: Check bomb's explosion range against (tile_x, tile_y)
            # based on bomb.placed_by_player.bomb_range and bomb's position.

        # Check active explosions
        for explosion in self.game.explosions_group:
            if explosion.rect.collidepoint(tile_x * settings.TILE_SIZE + settings.TILE_SIZE // 2,
                                           tile_y * settings.TILE_SIZE + settings.TILE_SIZE // 2):
                return True
        return False


    def update(self):
        """Main update call for the AI controller, called each game frame."""
        current_time = pygame.time.get_ticks()
        if current_time - self.last_ai_move_time > self.ai_move_delay:
            self.last_ai_move_time = current_time

            # 1. Update State Machine (decide what to do)
            self.update_state_machine()

            # 2. Execute actions for the current state
            # This might involve calculating a new path if not already on one,
            # or if the current path becomes invalid.
            self.perform_current_state_action()
        
        # 3. If AI has a path, try to move along it
        #    This part might run more frequently than the "thinking" part above,
        #    or be part of perform_current_state_action().
        #    For now, let's assume move_along_path is part of the AI's "action" for
        #    states that involve movement.
        if self.current_path:
            self.move_along_path()
        elif not self.current_path and self.current_state not in [AI_STATE_IDLE, AI_STATE_WAIT_EXPLOSION]:
            # If in a movement state but no path, try to recalculate path in next thinking cycle
            # or immediately if appropriate for the state.
            # print(f"AI (Player {id(self.ai_player)}) in state {self.current_state} but has no path.")
            pass


    def debug_draw_path(self, surface):
        """(Optional) Draws the AI's current path for debugging."""
        # Draw visited BFS tiles (light grey)
        for (vx, vy) in self.bfs_visited_visual:
            rect = pygame.Rect(vx * settings.TILE_SIZE, vy * settings.TILE_SIZE, settings.TILE_SIZE, settings.TILE_SIZE)
            pygame.draw.rect(surface, (50,50,50), rect, 1) # Light grey small rect

        if self.current_path:
            points = []
            for i, (tile_x, tile_y) in enumerate(self.current_path):
                center_x = tile_x * settings.TILE_SIZE + settings.TILE_SIZE // 2
                center_y = tile_y * settings.TILE_SIZE + settings.TILE_SIZE // 2
                points.append((center_x, center_y))
                # Mark current target in path
                if i == self.current_path_index +1 and i < len(self.current_path):
                     pygame.draw.circle(surface, (0,255,255), (center_x, center_y), 5) # Cyan circle

            if len(points) > 1:
                pygame.draw.lines(surface, (255, 0, 255), False, points, 2) # Magenta path line
        
        # Draw AI's current target tile for escape or item
        target_to_draw = None
        if self.current_state == AI_STATE_ESCAPE and self.escape_target_tile:
            target_to_draw = self.escape_target_tile
        elif self.current_state == AI_STATE_FETCH_ITEMS and self.target_item:
            target_to_draw = (self.target_item.rect.centerx // settings.TILE_SIZE, 
                              self.target_item.rect.centery // settings.TILE_SIZE)
        
        if target_to_draw:
            center_x = target_to_draw[0] * settings.TILE_SIZE + settings.TILE_SIZE // 2
            center_y = target_to_draw[1] * settings.TILE_SIZE + settings.TILE_SIZE // 2
            pygame.draw.circle(surface, (255,255,0), (center_x, center_y), settings.TILE_SIZE // 3, 3) # Yellow target circle