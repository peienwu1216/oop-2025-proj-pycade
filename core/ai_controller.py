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
        self.ai_player = ai_player_sprite
        self.game = game_instance
        self.current_state = AI_STATE_IDLE
        self.state_start_time = pygame.time.get_ticks()
        self.current_path = []
        self.current_path_index = 0
        
        self.ai_decision_interval = settings.AI_MOVE_DELAY # Milliseconds
        self.last_decision_time = pygame.time.get_ticks()
        
        self.target_player = self.game.player1 # AI targets Player 1 by default
        self.target_item = None
        self.escape_target_tile = None
        self.last_bomb_placed_time = 0
        self.ai_placed_bomb_recently = False
        self.bfs_visited_visual = []

        print(f"AIController initialized for Player ID: {id(self.ai_player)}. Targeting Player ID: {id(self.target_player) if self.target_player else 'None'}")

    def update_state_machine(self):
        """Decides the AI's state based on game conditions."""
        # Priority 1: Escape danger (placeholder, will be more complex)
        # current_ai_tile = (self.ai_player.rect.centerx // settings.TILE_SIZE, self.ai_player.rect.centery // settings.TILE_SIZE)
        # if self.is_tile_dangerous(current_ai_tile[0], current_ai_tile[1]):
        #     if self.current_state != AI_STATE_ESCAPE:
        #         # safe_tiles = self.find_safe_tiles_nearby(current_ai_tile)
        #         # if safe_tiles:
        #         #     self.change_state(AI_STATE_ESCAPE, escape_tile=random.choice(safe_tiles))
        #         # else:
        #         #     print(f"AI {id(self.ai_player)} is in danger but found no safe tiles!")
        #         #     self.change_state(AI_STATE_IDLE) # Or a panic state
        #         pass # Escape logic will be detailed later
        #     return # If escaping, no other decisions for now

        # If AI just placed a bomb, wait
        if self.ai_placed_bomb_recently and pygame.time.get_ticks() - self.last_bomb_placed_time < settings.BOMB_TIMER / 2: # Wait a bit
             if self.current_state != AI_STATE_WAIT_EXPLOSION and self.current_state != AI_STATE_ESCAPE:
                # self.change_state(AI_STATE_WAIT_EXPLOSION) # Escape should take precedence if needed
                pass # Let escape logic (when implemented) handle moving away
             return


        # Priority 2: Attack player (placeholder)
        # if self.target_player and self.target_player.is_alive:
        #     # path_to_player = self.bfs_find_path(current_ai_tile, 
        #     #                                   (self.target_player.rect.centerx // settings.TILE_SIZE, 
        #     #                                    self.target_player.rect.centery // settings.TILE_SIZE))
        #     # if path_to_player and len(path_to_player) < 5: # If player is close
        #     #     self.change_state(AI_STATE_ATTACK_PLAYER, target_player=self.target_player)
        #     #     return
        #     pass


        # Priority 3: Fetch items
        # closest_item = self.find_closest_item()
        # if closest_item:
        #     if self.current_state != AI_STATE_FETCH_ITEMS or self.target_item != closest_item:
        #          self.change_state(AI_STATE_FETCH_ITEMS, target_item=closest_item)
        #     return # If fetching, do this

        # Default to IDLE if no other pressing needs or if current path is done
        if not self.current_path: # If no current task or path completed
            if self.current_state not in [AI_STATE_IDLE, AI_STATE_WAIT_EXPLOSION]:
                 self.change_state(AI_STATE_IDLE)
        
        # If IDLE for too long, maybe try to find an item or move
        if self.current_state == AI_STATE_IDLE and \
           pygame.time.get_ticks() - self.state_start_time > 3000: # 3 seconds
            # if closest_item: # Check again for items
            #    self.change_state(AI_STATE_FETCH_ITEMS, target_item=closest_item)
            # else: # No items, just reset IDLE timer or move randomly
                self.state_start_time = pygame.time.get_ticks() # Reset idle timer
                # print(f"AI {id(self.ai_player)} resetting IDLE timer.")


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
        # If no path, or path completed, try to pick a random nearby walkable tile to move to.
        if not self.current_path:
            ai_tile_x = self.ai_player.rect.centerx // settings.TILE_SIZE
            ai_tile_y = self.ai_player.rect.centery // settings.TILE_SIZE
            
            possible_moves = []
            for dx, dy in DIRECTIONS.values():
                next_x, next_y = ai_tile_x + dx, ai_tile_y + dy
                if self.game.map_manager.is_walkable(next_x, next_y) and \
                   not self.is_tile_dangerous(next_x, next_y): # Avoid known danger even in idle
                    possible_moves.append((next_x, next_y))
            
            if possible_moves:
                random_target_tile = random.choice(possible_moves)
                # print(f"AI Idle: New random target {random_target_tile}")
                # Path to just one step away might be overkill, but let's use the path system
                self.current_path = self.bfs_find_path((ai_tile_x, ai_tile_y), random_target_tile, avoid_danger=True)
                self.current_path_index = 0
                if self.current_path:
                    # print(f"AI Idle: Path to random target: {self.current_path}")
                    pass # move_along_path will be called by AIController.update if path exists

        # If already has a path (e.g., to a random spot), move_along_path will handle it.


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
    def bfs_find_path(self, start_tile, end_tile_or_tiles, avoid_danger_from_bombs=True, avoid_current_explosions=True):
        # ... (BFS logic - 之前版本基本可用，但 is_tile_dangerous 需要更完善) ...
        self.current_path = []
        self.current_path_index = 0
        self.bfs_visited_visual = []
        q = deque([(start_tile, [start_tile])])
        visited = {start_tile}
        map_mgr = self.game.map_manager
        targets = []
        if isinstance(end_tile_or_tiles, list): targets.extend(end_tile_or_tiles)
        else: targets.append(end_tile_or_tiles)
        if not targets: return []

        while q:
            (curr_x, curr_y), path = q.popleft()
            self.bfs_visited_visual.append((curr_x, curr_y))
            if (curr_x, curr_y) in targets: return path

            for dir_name, (dx, dy) in DIRECTIONS.items():
                next_x, next_y = curr_x + dx, curr_y + dy
                if (next_x, next_y) not in visited:
                    if map_mgr.is_walkable(next_x, next_y):
                        is_dangerous = self.is_tile_dangerous(next_x, next_y, 
                                                              check_bombs=avoid_danger_from_bombs, 
                                                              check_explosions=avoid_current_explosions)
                        if is_dangerous:
                            continue
                        visited.add((next_x, next_y))
                        new_path = list(path)
                        new_path.append((next_x, next_y))
                        q.append(((next_x, next_y), new_path))
        return []

    def move_along_path(self):
        """Moves the AI player one step along its current path."""
        if not self.current_path or self.current_path_index >= len(self.current_path):
            self.current_path = [] # Path ended or invalid
            self.current_path_index = 0
            self.ai_player.vx, self.ai_player.vy = 0, 0 # Stop AI movement
            return False

        # Get the very next tile in the path
        # Path[0] is start, path[1] is first step, etc.
        # If current_path_index is 0, next target is path[1]
        if self.current_path_index + 1 >= len(self.current_path): # Should not happen if check above is correct
            self.current_path = []
            self.current_path_index = 0
            self.ai_player.vx, self.ai_player.vy = 0, 0
            return False

        next_target_tile_in_path_x, next_target_tile_in_path_y = self.current_path[self.current_path_index + 1]

        current_ai_pixel_center_x = self.ai_player.rect.centerx
        current_ai_pixel_center_y = self.ai_player.rect.centery

        target_pixel_center_x = next_target_tile_in_path_x * settings.TILE_SIZE + settings.TILE_SIZE // 2
        target_pixel_center_y = next_target_tile_in_path_y * settings.TILE_SIZE + settings.TILE_SIZE // 2

        # Determine direction vector towards the center of the target tile
        # These deltas are in pixels
        delta_x_pixel = target_pixel_center_x - current_ai_pixel_center_x
        delta_y_pixel = target_pixel_center_y - current_ai_pixel_center_y

        # If AI is very close to the center of the target tile, snap to it and advance path index
        if abs(delta_x_pixel) < self.ai_player.speed and abs(delta_y_pixel) < self.ai_player.speed:
            self.ai_player.rect.centerx = target_pixel_center_x
            self.ai_player.rect.centery = target_pixel_center_y
            self.ai_player.vx, self.ai_player.vy = 0, 0 # Stop precisely
            self.current_path_index += 1
            # print(f"AI reached path segment: {next_target_tile_in_path_x}, {next_target_tile_in_path_y}. New index: {self.current_path_index}")

            if self.current_path_index + 1 >= len(self.current_path): # Reached end of path
                # print(f"AI reached end of path at {next_target_tile_in_path_x}, {next_target_tile_in_path_y}")
                self.current_path = []
                self.current_path_index = 0
            return True # Advanced path or finished
        else:
            # Normalize pixel delta to get direction, then apply speed
            # This provides smoother movement towards the center of the tile
            # rather than just setting max speed in one cardinal direction.
            vec = pygame.math.Vector2(delta_x_pixel, delta_y_pixel)
            if vec.length_squared() > 0: # Avoid division by zero if already at target
                vec.normalize_ip()
                self.ai_player.vx = vec.x * self.ai_player.speed
                self.ai_player.vy = vec.y * self.ai_player.speed
            else: # Already at the center, but previous check didn't catch it (should be rare)
                self.ai_player.vx, self.ai_player.vy = 0,0

        return False # Still moving towards current segment's target tile center

    def is_tile_dangerous(self, tile_x, tile_y, check_bombs=True, check_explosions=True, future_seconds=1.5):
        """
        Checks if a given tile is currently dangerous or will be dangerous soon.
        Args:
            tile_x, tile_y: Tile coordinates to check.
            check_bombs: Whether to consider active bombs.
            check_explosions: Whether to consider current explosions.
            future_seconds: How far into the future to predict bomb explosions.
        """
        target_pixel_x = tile_x * settings.TILE_SIZE + settings.TILE_SIZE // 2
        target_pixel_y = tile_y * settings.TILE_SIZE + settings.TILE_SIZE // 2

        if check_explosions:
            for explosion in self.game.explosions_group:
                if explosion.rect.collidepoint(target_pixel_x, target_pixel_y):
                    # print(f"Tile ({tile_x},{tile_y}) is dangerous due to current explosion.")
                    return True
        
        if check_bombs:
            for bomb in self.game.bombs_group:
                time_until_explosion = (bomb.spawn_time + bomb.timer) - pygame.time.get_ticks()
                if 0 < time_until_explosion < future_seconds * 1000: # Bomb will explode soon
                    # Check if (tile_x, tile_y) is in this bomb's explosion range
                    bomb_center_x, bomb_center_y = bomb.current_tile_x, bomb.current_tile_y
                    bomb_range = bomb.placed_by_player.bomb_range

                    # Check center
                    if bomb_center_x == tile_x and bomb_center_y == tile_y: return True
                    # Check horizontal line
                    if bomb_center_y == tile_y and abs(bomb_center_x - tile_x) <= bomb_range:
                        # Check if path is blocked by solid wall
                        blocked = False
                        for i in range(1, abs(bomb_center_x - tile_x) + 1):
                            check_x = bomb_center_x + i * (1 if tile_x > bomb_center_x else -1)
                            if self.game.map_manager.is_solid_wall_at(check_x, bomb_center_y):
                                if (tile_x > bomb_center_x and check_x < tile_x) or \
                                   (tile_x < bomb_center_x and check_x > tile_x): # Wall is between bomb and tile
                                    blocked = True
                                    break
                        if not blocked: return True
                    
                    # Check vertical line
                    if bomb_center_x == tile_x and abs(bomb_center_y - tile_y) <= bomb_range:
                        blocked = False
                        for i in range(1, abs(bomb_center_y - tile_y) + 1):
                            check_y = bomb_center_y + i * (1 if tile_y > bomb_center_y else -1)
                            if self.game.map_manager.is_solid_wall_at(bomb_center_x, check_y):
                                 if (tile_y > bomb_center_y and check_y < tile_y) or \
                                    (tile_y < bomb_center_y and check_y > tile_y): # Wall is between bomb and tile
                                    blocked = True
                                    break
                        if not blocked: return True
        return False


    def update(self):
        current_time = pygame.time.get_ticks()
        if current_time - self.last_decision_time > self.ai_decision_interval: # 使用 decision_interval
            self.last_decision_time = current_time

            if not self.ai_player.is_alive: return # Don't update AI if its player is dead

            self.update_state_machine() # Decide what state to be in
            self.perform_current_state_action() # Potentially calculate a new path here
        
        # Movement along path can happen more frequently than decisions
        # or be triggered directly by state handlers.
        # For now, let's tie it to the decision interval as well, 
        # or Player.update handles the continuous movement based on vx, vy.
        # AIController.move_along_path() will set vx, vy for the AI player.
        if self.current_path:
            moved_or_finished_segment = self.move_along_path()
            if moved_or_finished_segment and not self.current_path: # Path was just completed
                # print(f"AI {id(self.ai_player)} completed path, current state {self.current_state}. Re-evaluating.")
                # Force re-evaluation of state if path completed
                self.last_decision_time = 0 # Force next decision cycle
                self.ai_player.vx, self.ai_player.vy = 0,0 # Stop movement


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