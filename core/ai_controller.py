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
        """Decides the AI's state based on game conditions. Escape has highest priority."""
        current_ai_tile = (self.ai_player.rect.centerx // settings.TILE_SIZE,
                           self.ai_player.rect.centery // settings.TILE_SIZE)

        # --- PRIORITY 1: ESCAPE ---
        # Is the AI's current tile dangerous, or will it be imminently dangerous?
        if self.is_tile_dangerous(current_ai_tile[0], current_ai_tile[1]):
            if self.current_state != AI_STATE_ESCAPE: # Only change if not already escaping
                print(f"[AI DECISION] AI at {current_ai_tile} is in DANGER!")
                safe_escape_spots = self.find_safe_tiles_nearby(current_ai_tile)
                if safe_escape_spots:
                    # Choose the closest safe spot (BFS ensures closer ones are found first if depth limited)
                    # Or simply pick one. For now, let's pick the first one found.
                    chosen_escape_tile = safe_escape_spots[0] 
                    # We need a path to this chosen escape tile
                    path_to_safe_spot = self.bfs_find_path(current_ai_tile, chosen_escape_tile, 
                                                           avoid_danger_from_bombs=True, 
                                                           avoid_current_explosions=True)
                    if path_to_safe_spot:
                        self.current_path = path_to_safe_spot # Set the path for handle_escape_state
                        self.current_path_index = 0
                        self.change_state(AI_STATE_ESCAPE, escape_tile=chosen_escape_tile)
                        return # Decision made: Escape
                    else:
                        print(f"[AI WARNING] In danger at {current_ai_tile}, found safe spot {chosen_escape_tile}, but NO PATH!")
                        # No path to chosen safe spot, maybe try another safe spot or panic (e.g., random move)
                        # For now, might fall through to IDLE or another state if no path.
                        # This scenario (safe spot exists but no path) should be rare if find_safe_tiles_nearby works.
                        self.change_state(AI_STATE_IDLE) # Fallback if no path to safe spot
                else:
                    print(f"[AI CRITICAL] In danger at {current_ai_tile} and NO SAFE SPOTS FOUND NEARBY!")
                    # Panic mode: Try a random move, hoping to get lucky.
                    # This is a last resort.
                    self.current_path = [] # Clear any old path
                    # Attempt a random move (will be handled by IDLE if we switch to it, or needs specific panic logic)
                    self.change_state(AI_STATE_IDLE) # Fallback if truly trapped
                return # Decision made or attempted

        # If currently escaping, but current path leads to a now dangerous tile, or current tile on path is dangerous
        if self.current_state == AI_STATE_ESCAPE:
            # Check if the current path is still valid (e.g., target isn't now dangerous)
            if self.current_path:
                next_immediate_tile_on_path = self.current_path[self.current_path_index + 1] if self.current_path_index + 1 < len(self.current_path) else None
                if next_immediate_tile_on_path and self.is_tile_dangerous(next_immediate_tile_on_path[0], next_immediate_tile_on_path[1]):
                    print(f"[AI ESCAPE] Path to {self.escape_target_tile} has become dangerous at {next_immediate_tile_on_path}. Re-evaluating escape.")
                    self.current_path = [] # Invalidate path
                    # Fall through to re-trigger escape logic to find a new path/spot
                elif self.escape_target_tile and self.is_tile_dangerous(self.escape_target_tile[0], self.escape_target_tile[1]):
                     print(f"[AI ESCAPE] Target escape tile {self.escape_target_tile} has become dangerous. Re-evaluating escape.")
                     self.current_path = [] # Invalidate path
                     self.escape_target_tile = None
                     # Fall through
                else:
                    return # Continue escaping along current valid path


        # --- PRIORITY 2: WAIT_EXPLOSION (if AI placed a bomb and is not currently escaping danger) ---
        if self.ai_placed_bomb_recently:
            time_since_bomb = pygame.time.get_ticks() - self.last_bomb_placed_time
            # If bomb is still ticking and AI is not primarily escaping something else
            if time_since_bomb < (settings.BOMB_TIMER + settings.EXPLOSION_DURATION / 2): # Wait until bomb + half explosion
                if self.current_state != AI_STATE_WAIT_EXPLOSION and self.current_state != AI_STATE_ESCAPE:
                    # AI should have already moved to a safe spot after placing the bomb.
                    # This state is more about "don't do anything else rash until my bomb is done"
                    print(f"[AI DECISION] AI placed bomb, current state {self.current_state}, considering WAIT_EXPLOSION")
                    # If current tile is safe, can wait. If not, ESCAPE should have triggered.
                    if not self.is_tile_dangerous(current_ai_tile[0], current_ai_tile[1], check_bombs=True, check_explosions=False, future_seconds=0.5): # check immediate future
                        self.change_state(AI_STATE_WAIT_EXPLOSION)
                        return
                    # else ESCAPE should handle it.
            else: # Bomb has exploded
                self.ai_placed_bomb_recently = False # Reset flag

        # --- Placeholder for ATTACK_PLAYER and FETCH_ITEMS ---
        # (These will be based on your C++ logic: find target, get path, change state)
        # For now, if not escaping or waiting for own bomb, consider IDLE or fetching.

        # Example: Try to find an item if IDLE or finished waiting
        if self.current_state in [AI_STATE_IDLE, AI_STATE_WAIT_EXPLOSION] and not self.ai_placed_bomb_recently:
            # closest_item = self.find_closest_item() # We need to implement find_closest_item
            # if closest_item:
            #     if self.current_state != AI_STATE_FETCH_ITEMS or self.target_item != closest_item:
            #         path_to_item = self.bfs_find_path(current_ai_tile, 
            #                                           (closest_item.rect.centerx // settings.TILE_SIZE, 
            #                                            closest_item.rect.centery // settings.TILE_SIZE))
            #         if path_to_item:
            #             self.current_path = path_to_item
            #             self.current_path_index = 0
            #             self.change_state(AI_STATE_FETCH_ITEMS, target_item=closest_item)
            #             return
            pass # Item fetching to be added

        # Default to IDLE if no other state is applicable or path is completed
        if not self.current_path and self.current_state not in [AI_STATE_WAIT_EXPLOSION]: # Don't idle if waiting for bomb
            if self.current_state != AI_STATE_IDLE:
                self.change_state(AI_STATE_IDLE)

        # If IDLE for too long, just reset the timer (handle_idle_state might pick a random move)
        if self.current_state == AI_STATE_IDLE and \
           pygame.time.get_ticks() - self.state_start_time > 3000:
            self.state_start_time = pygame.time.get_ticks() # Reset idle timer


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


    def find_safe_tiles_nearby(self, start_tile, max_search_depth=5):
        """
        Uses BFS to find the closest safe tiles nearby, up to a certain depth.
        A tile is "safe" if it's walkable and not currently dangerous.
        """
        q = deque([(start_tile, 0)]) # (tile, depth)
        visited = {start_tile}
        safe_tiles_found = []

        map_mgr = self.game.map_manager

        while q:
            (curr_x, curr_y), depth = q.popleft()

            if depth > max_search_depth: # Don't search too far for an immediate escape
                continue

            # Check if this current tile is safe
            if not self.is_tile_dangerous(curr_x, curr_y):
                safe_tiles_found.append((curr_x, curr_y))
                # Optimization: if we want the *closest* safe tiles,
                # and we are doing BFS, the first ones found at a certain depth are good.
                # We could return immediately or collect all at this depth.
                # For now, let's collect a few. If too many, BFS can be slow.
                if len(safe_tiles_found) >= 5: # Collect up to 5 candidates
                    break 

            if depth < max_search_depth: # Only expand if not at max depth
                for dx, dy in DIRECTIONS.values():
                    next_x, next_y = curr_x + dx, curr_y + dy
                    if (next_x, next_y) not in visited:
                        if map_mgr.is_walkable(next_x, next_y): # Must be walkable
                            visited.add((next_x, next_y))
                            q.append(((next_x, next_y), depth + 1))
        
        # print(f"[AI ESCAPE] Found {len(safe_tiles_found)} safe tiles near {start_tile}: {safe_tiles_found}")
        return safe_tiles_found
    
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
        """
        AI is trying to escape to self.escape_target_tile using self.current_path.
        If path is finished or invalid, it should re-evaluate its situation.
        """
        ai_current_tile = (self.ai_player.rect.centerx // settings.TILE_SIZE,
                           self.ai_player.rect.centery // settings.TILE_SIZE)

        if not self.current_path: # No path currently, or path was invalidated
            # This means update_state_machine decided to escape but couldn't set a path,
            # or an existing escape path became invalid.
            # update_state_machine should try to find a new escape path/target.
            # If it can't, it might switch to IDLE (which might make a random move).
            print(f"[AI ESCAPE] In escape state but no current path. AI at {ai_current_tile}. Re-evaluating next cycle.")
            # Forcing a quick re-evaluation by a small trick:
            self.last_decision_time = 0 # Force decision in next AI update
            return

        # If AI has a path, move_along_path is called by AIController.update()
        # We need to check if the escape target has been reached or if the AI is now safe.

        # Is the AI at the target escape tile?
        if self.escape_target_tile and \
           ai_current_tile[0] == self.escape_target_tile[0] and \
           ai_current_tile[1] == self.escape_target_tile[1]:
            # Reached the intended safe spot. Is it ACTUALLY safe now?
            if not self.is_tile_dangerous(ai_current_tile[0], ai_current_tile[1], future_seconds=0.5): # Check immediate safety
                print(f"[AI ESCAPE] Reached safe escape target {self.escape_target_tile} and it's safe. Switching to IDLE.")
                self.change_state(AI_STATE_IDLE)
            else:
                print(f"[AI ESCAPE] Reached escape target {self.escape_target_tile} BUT IT'S STILL DANGEROUS! Re-evaluating.")
                self.current_path = [] # Path led to danger
                self.escape_target_tile = None
                self.last_decision_time = 0 # Force re-evaluation
            return
        
        # If the path is completed (move_along_path clears it), but not at escape_target_tile (should be rare)
        # or if simply the AI is no longer in an immediately dangerous spot even if not at escape_target_tile
        if not self.is_tile_dangerous(ai_current_tile[0], ai_current_tile[1], future_seconds=0.2):
             # Optimization: If current spot is safe, no need to continue to original escape_target_tile if it's far
             # unless that original target was strategically very safe.
             # For now, if current spot is safe, let's re-evaluate by going IDLE.
             # print(f"[AI ESCAPE] AI at {ai_current_tile} is now safe (even if not at escape_target_tile). Switching to IDLE.")
             # self.change_state(AI_STATE_IDLE) # This might be too quick to switch out of escape.
             # Let's only switch if path is done OR current target becomes dangerous
             pass


        # If still on a path, AIController.update() will call move_along_path().
        # No specific action here other than path validation done in update_state_machine.

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

    def is_tile_dangerous(self, tile_x, tile_y, check_bombs=True, check_explosions=True, future_seconds=settings.BOMB_TIMER / 1000.0 + 0.2): # Predict slightly beyond bomb timer
        """
        Checks if a given tile is currently dangerous or will be dangerous soon (within future_seconds).
        """
        target_pixel_x = tile_x * settings.TILE_SIZE + settings.TILE_SIZE // 2
        target_pixel_y = tile_y * settings.TILE_SIZE + settings.TILE_SIZE // 2

        if check_explosions:
            for explosion in self.game.explosions_group:
                if explosion.rect.collidepoint(target_pixel_x, target_pixel_y):
                    # print(f"[AI DANGER] Tile ({tile_x},{tile_y}) is dangerous due to current explosion.")
                    return True
        
        if check_bombs:
            for bomb in self.game.bombs_group:
                if bomb.exploded: continue # Ignore already exploded bombs

                time_until_explosion_ms = (bomb.spawn_time + bomb.timer) - pygame.time.get_ticks()
                
                # Only consider bombs that will explode within our prediction window
                if 0 < time_until_explosion_ms < future_seconds * 1000:
                    bomb_center_x, bomb_center_y = bomb.current_tile_x, bomb.current_tile_y
                    bomb_range = bomb.placed_by_player.bomb_range # Use actual range of the bomb

                    # Check if (tile_x, tile_y) is in this bomb's direct line of fire
                    # This is a simplified check, a more accurate one would trace the explosion path like in Bomb.explode()

                    # Is the tile the bomb itself?
                    if bomb_center_x == tile_x and bomb_center_y == tile_y:
                        # print(f"[AI DANGER] Tile ({tile_x},{tile_y}) is dangerous, bomb is on it, exploding in {time_until_explosion_ms/1000:.1f}s.")
                        return True

                    # Is the tile in the horizontal path of the bomb?
                    if bomb_center_y == tile_y and abs(bomb_center_x - tile_x) <= bomb_range:
                        # Check for blocking solid walls between bomb and tile
                        blocked = False
                        step = 1 if tile_x > bomb_center_x else -1
                        for i_check in range(1, abs(bomb_center_x - tile_x)): # Check tiles *between* bomb and target
                            check_x = bomb_center_x + i_check * step
                            if self.game.map_manager.is_solid_wall_at(check_x, bomb_center_y):
                                blocked = True
                                break
                        if not blocked:
                            # print(f"[AI DANGER] Tile ({tile_x},{tile_y}) in horizontal danger from bomb at ({bomb_center_x},{bomb_center_y}), exploding in {time_until_explosion_ms/1000:.1f}s.")
                            return True
                    
                    # Is the tile in the vertical path of the bomb?
                    if bomb_center_x == tile_x and abs(bomb_center_y - tile_y) <= bomb_range:
                        blocked = False
                        step = 1 if tile_y > bomb_center_y else -1
                        for i_check in range(1, abs(bomb_center_y - tile_y)): # Check tiles *between* bomb and target
                            check_y = bomb_center_y + i_check * step
                            if self.game.map_manager.is_solid_wall_at(bomb_center_x, check_y):
                                blocked = True
                                break
                        if not blocked:
                            # print(f"[AI DANGER] Tile ({tile_x},{tile_y}) in vertical danger from bomb at ({bomb_center_x},{bomb_center_y}), exploding in {time_until_explosion_ms/1000:.1f}s.")
                            return True
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