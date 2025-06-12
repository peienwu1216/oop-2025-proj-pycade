# oop-2025-proj-pycade/core/ai_controller_base.py

import pygame
import settings
import random
from collections import deque
import heapq

AI_DEBUG_MODE = True
def ai_log(message):
    """通用的日誌函式，方便除錯。"""
    if AI_DEBUG_MODE:
        print(f"[AI_BASE] {message}")

DIRECTIONS = {"UP": (0, -1), "DOWN": (0, 1), "LEFT": (-1, 0), "RIGHT": (1, 0)}

class TileNode:
    def __init__(self, x, y, tile_char):
        self.x, self.y, self.tile_char = x, y, tile_char
        self.parent = None
        self.g_cost, self.h_cost = float('inf'), float('inf')

    def get_f_cost(self): return self.g_cost + self.h_cost
    def is_walkable_for_astar_planning(self): return self.tile_char in ['.', 'D']
    def is_empty_for_direct_movement(self): return self.tile_char == '.'
    def is_destructible_box(self): return self.tile_char == 'D'
    def get_astar_move_cost_to_here(self):
        COST_MOVE_EMPTY_BASE = 1
        COST_BOMB_BOX_BASE = 3
        if self.tile_char == '.': return COST_MOVE_EMPTY_BASE
        elif self.tile_char == 'D': return COST_BOMB_BOX_BASE
        return float('inf')

    def __lt__(self, other):
        if not isinstance(other, TileNode): return NotImplemented
        f_cost_self = self.get_f_cost()
        f_cost_other = other.get_f_cost()
        if f_cost_self == f_cost_other: return self.h_cost < other.h_cost
        return f_cost_self < f_cost_other
    def __eq__(self, other):
        if not isinstance(other, TileNode): return NotImplemented
        return self.x == other.x and self.y == other.y
    def __hash__(self): return hash((self.x, self.y))
    def __repr__(self):
        g_str = f"{self.g_cost:.1f}" if self.g_cost != float('inf') else 'inf'
        h_str = f"{self.h_cost:.1f}" if self.h_cost != float('inf') else 'inf'
        return f"N_Base({self.x},{self.y},'{self.tile_char}',g={g_str},h={h_str})"

class AIControllerBase:
    def __init__(self, ai_player_sprite, game_instance):
        ai_log(f"AIControllerBase __init__ for Player ID: {id(ai_player_sprite)}")
        self.ai_player = ai_player_sprite
        self.game = game_instance
        self.map_manager = self.game.map_manager
        self.human_player_sprite = getattr(self.game, 'player1', None)

        self.current_state = "IDLE"
        self.state_start_time = 0
        self.ai_decision_interval = settings.AI_MOVE_DELAY
        self.last_decision_time = 0

        self.astar_planned_path = []
        self.astar_path_current_segment_index = 0
        self.current_movement_sub_path = []
        self.current_movement_sub_path_index = 0

        self.last_bomb_placed_time = 0
        self.ai_just_placed_bomb = False
        self.chosen_bombing_spot_coords = None
        self.chosen_retreat_spot_coords = None

        self.movement_history = deque(maxlen=4)
        self.oscillation_stuck_counter = 0
        self.decision_cycle_stuck_counter = 0
        self.last_known_tile = (-1,-1)

        self.target_obstacle_to_bomb = None
        self.target_destructible_wall_node_in_astar = None
        self.roaming_target_tile = None
        self.player_initial_spawn_tile = getattr(self.game, 'player1_start_tile', (1,1))

        self.evasion_urgency_seconds = getattr(settings, "AI_EVASION_SAFETY_CHECK_FUTURE_SECONDS", 0.5)

        self.reset_state()
        
        self.retreat_img = pygame.image.load(settings.AI_RETREAT_IMG)
        self.retreat_img = pygame.transform.smoothscale(self.retreat_img, (settings.TILE_SIZE, settings.TILE_SIZE))

    def reset_state(self):
        ai_log(f"Resetting AI state for Player ID: {id(self.ai_player)}.")
        self.current_state = "PLANNING_PATH" # Default initial state for base, will be changed by derived class
        self.state_start_time = pygame.time.get_ticks()
        self.astar_planned_path = []
        self.astar_path_current_segment_index = 0
        self.current_movement_sub_path = [] # Correctly clears here
        self.current_movement_sub_path_index = 0
        self.last_bomb_placed_time = 0
        self.ai_just_placed_bomb = False
        self.chosen_bombing_spot_coords = None
        self.chosen_retreat_spot_coords = None
        self.target_obstacle_to_bomb = None
        self.target_destructible_wall_node_in_astar = None
        self.roaming_target_tile = None
        self.last_decision_time = pygame.time.get_ticks() - self.ai_decision_interval
        current_ai_tile_tuple = self._get_ai_current_tile()
        self.last_known_tile = current_ai_tile_tuple if current_ai_tile_tuple else (-1,-1)
        self.movement_history.clear()
        self.oscillation_stuck_counter = 0
        self.decision_cycle_stuck_counter = 0

    def change_state(self, new_state):
        if self.current_state != new_state:
            ai_log(f"[STATE_CHANGE] ID: {id(self.ai_player)} From {self.current_state} -> {new_state}")
            self.current_state = new_state
            self.state_start_time = pygame.time.get_ticks()

            # --- MODIFICATION START ---
            # Only clear paths if entering a "planning" state, or a state that specifically requires it.
            # This prevents clearing a path that was just set by a handler before changing to an "execution" state.
            if new_state.startswith("PLANNING_") or new_state == "IDLE" or new_state == "DEAD":
                ai_log(f"    Clearing current_movement_sub_path due to entering state: {new_state}")
                self.current_movement_sub_path = []
                self.current_movement_sub_path_index = 0
            # --- MODIFICATION END ---

            # Clear A* path when entering any top-level planning state
            if new_state.startswith("PLANNING_"):
                 self.astar_planned_path = []
                 self.astar_path_current_segment_index = 0
            
            # Clean up specific target variables based on the new state
            if new_state not in ["EXECUTING_PATH_CLEARANCE", "TACTICAL_RETREAT_AND_WAIT", "ASSESSING_OBSTACLE", "MOVING_TO_BOMB_OBSTACLE", "EXECUTING_ASTAR_PATH_TO_TARGET", "ASSESSING_OBSTACLE_FOR_ITEM"]: # Added ASSESSING_OBSTACLE_FOR_ITEM
                self.target_destructible_wall_node_in_astar = None
                self.target_obstacle_to_bomb = None # This is a base class variable, ensure it's cleared appropriately
                if hasattr(self, 'potential_wall_to_bomb_for_item'): # Specific to ItemFocusedAI but good to be general
                    self.potential_wall_to_bomb_for_item = None


            if new_state not in ["TACTICAL_RETREAT_AND_WAIT", "CLOSE_QUARTERS_COMBAT", "ENGAGING_PLAYER", "ASSESSING_OBSTACLE", "MOVING_TO_BOMB_OBSTACLE", "ASSESSING_OBSTACLE_FOR_ITEM"]:  # Added ASSESSING_OBSTACLE_FOR_ITEM
                self.chosen_bombing_spot_coords = None
                self.chosen_retreat_spot_coords = None

            if new_state != "ROAMING":
                self.roaming_target_tile = None
            
            if new_state != "MOVING_TO_COLLECT_ITEM" and new_state != "EXECUTING_ASTAR_PATH_TO_TARGET" and hasattr(self, 'target_item_on_ground'): # item_focused AI cleanup
                self.target_item_on_ground = None


    def update(self):
        current_time = pygame.time.get_ticks()
        ai_current_tile = self._get_ai_current_tile()

        if not ai_current_tile or not self.ai_player.is_alive:
            if self.current_state != "DEAD": self.change_state("DEAD")
            return

        if self.ai_just_placed_bomb and not self.is_bomb_still_active(self.last_bomb_placed_time):
             ai_log("Bomb flag auto-cleared as bomb effect should have ended.")
             self.ai_just_placed_bomb = False

        evasion_check_seconds = getattr(self, 'evasion_urgency_seconds', getattr(settings, "AI_EVASION_SAFETY_CHECK_FUTURE_SECONDS", 0.5))
        if self.is_tile_dangerous(ai_current_tile[0], ai_current_tile[1], future_seconds=evasion_check_seconds):
            if self.current_state != "EVADING_DANGER":
                ai_log(f"AI at {ai_current_tile} is in DANGER! Switching to EVADING_DANGER.")
                self.change_state("EVADING_DANGER") # change_state now handles path clearing appropriately
                self.last_decision_time = current_time # Ensure immediate reaction in EVADING_DANGER

        if current_time - self.last_decision_time >= self.ai_decision_interval:
            self.last_decision_time = current_time

            stuck_threshold = getattr(settings, "AI_STUCK_THRESHOLD_CYCLES", 5)
            oscillation_threshold = getattr(settings, "AI_OSCILLATION_STUCK_THRESHOLD", 3)

            if self._update_and_check_stuck_conditions(ai_current_tile, stuck_threshold, oscillation_threshold):
                ai_log(f"Stuck detected! Forcing a re-plan. AI Personality: {type(self).__name__}")
                self.movement_history.clear()
                self.decision_cycle_stuck_counter = 0
                self.oscillation_stuck_counter = 0
                
                default_planning_state = "PLANNING_PATH"
                if hasattr(self, 'default_planning_state_on_stuck'):
                    default_planning_state = self.default_planning_state_on_stuck
                self.change_state(default_planning_state) # change_state now handles path clearing
                self.handle_state(ai_current_tile)
                return

            self.handle_state(ai_current_tile)

        if self.ai_player.action_timer <= 0:
            if self.current_movement_sub_path:
                # --- MODIFICATION START: Add logs inside execute_next_move_on_sub_path as per previous suggestion ---
                sub_path_finished = self.execute_next_move_on_sub_path(ai_current_tile)
                # --- MODIFICATION END ---
                if sub_path_finished:
                    self.last_decision_time = pygame.time.get_ticks() - self.ai_decision_interval
            else:
                if hasattr(self.ai_player, 'is_moving'):
                    self.ai_player.is_moving = False
    
    def handle_state(self, ai_current_tile):
        state_handler_method_name = f"handle_{self.current_state.lower()}_state"
        handler = getattr(self, state_handler_method_name, self.handle_unknown_state)
        handler(ai_current_tile)

    def handle_unknown_state(self, ai_current_tile):
        ai_log(f"Warning: Unknown state '{self.current_state}'. Reverting to default PLANNING_PATH.")
        self.change_state("PLANNING_PATH")
        
    def handle_planning_path_state(self, ai_current_tile): # Example base planning state
        ai_log(f"Base: In PLANNING_PATH at {ai_current_tile}. Default: go IDLE.")
        # Ensure paths are cleared when entering a base planning state
        self.current_movement_sub_path = []
        self.current_movement_sub_path_index = 0
        self.astar_planned_path = []
        self.astar_path_current_segment_index = 0
        self.change_state("IDLE")
        
    def handle_roaming_state(self, ai_current_tile):
        ai_log(f"Base: In ROAMING at {ai_current_tile}. Sub-path: {self.current_movement_sub_path}") # Added log for path
        if not self.current_movement_sub_path:
             self.change_state("PLANNING_ROAM")

    def handle_planning_roam_state(self, ai_current_tile): # Example base planning state
        ai_log(f"Base: In PLANNING_ROAM at {ai_current_tile}. Default: go ROAMING.")
        self.current_movement_sub_path = [] # Clear path before planning new roam
        self.current_movement_sub_path_index = 0
        self.change_state("ROAMING") # This will be caught by derived class usually

    def handle_assessing_obstacle_state(self, ai_current_tile):
        ai_log(f"Base: In ASSESSING_OBSTACLE at {ai_current_tile}. Default: go PLANNING_PATH.")
        self.change_state("PLANNING_PATH")

    def handle_moving_to_bomb_obstacle_state(self, ai_current_tile):
        ai_log(f"Base: In MOVING_TO_BOMB_OBSTACLE at {ai_current_tile}. Sub-path: {self.current_movement_sub_path}") # Added log for path
        if not self.current_movement_sub_path:
            self.change_state("PLANNING_PATH")
            
    def handle_moving_to_safe_spot_state(self, ai_current_tile):
        ai_log(f"Base: In MOVING_TO_SAFE_SPOT at {ai_current_tile}. Sub-path: {self.current_movement_sub_path}") # Added log for path
        if not self.current_movement_sub_path:
            self.change_state("IDLE")

    def handle_idle_state(self, ai_current_tile):
        ai_log(f"Base: In IDLE at {ai_current_tile}. Default: go PLANNING_PATH after delay.")
        idle_duration = getattr(self, 'idle_duration_ms', 2000)
        if pygame.time.get_ticks() - self.state_start_time > idle_duration:
            default_planning_state = "PLANNING_PATH"
            if hasattr(self, 'default_planning_state_on_stuck'):
                default_planning_state = self.default_planning_state_on_stuck
            self.change_state(default_planning_state)
            
    def handle_executing_path_clearance_state(self, ai_current_tile):
        ai_log(f"Base: In EXECUTING_PATH_CLEARANCE at {ai_current_tile}. Sub-path: {self.current_movement_sub_path}") # Added log for path
        # Path clearance usually involves A* path and sub-paths. If sub-path is done, it might re-evaluate A* or continue.
        # If no A* path, it should replan.
        if not self.astar_planned_path and not self.current_movement_sub_path:
             self.change_state("PLANNING_PATH")


    def handle_tactical_retreat_and_wait_state(self, ai_current_tile):
        ai_log(f"Base: In TACTICAL_RETREAT_AND_WAIT at {ai_current_tile}. Sub-path: {self.current_movement_sub_path}") # Added log for path
        if not self.is_bomb_still_active(self.last_bomb_placed_time):
            self.ai_just_placed_bomb = False
            self.change_state("PLANNING_PATH") # Or a more specific post-bombing state

    def handle_engaging_player_state(self, ai_current_tile):
        ai_log(f"Base: In ENGAGING_PLAYER at {ai_current_tile}. Sub-path: {self.current_movement_sub_path}") # Added log for path
        if not self.current_movement_sub_path: # If no path to follow towards player
            self.change_state("PLANNING_PATH") # Or a specific "PLANNING_ENGAGEMENT"

    def handle_close_quarters_combat_state(self, ai_current_tile):
        ai_log(f"Base: In CLOSE_QUARTERS_COMBAT at {ai_current_tile}. Sub-path: {self.current_movement_sub_path}") # Added log for path
        # CQC might not always have a sub-path if it's about immediate actions
        # If logic dictates it needs a path and doesn't have one, it should replan.
        # For now, if it gets stuck here without a path, it might need to replan.
        # This is highly dependent on the CQC logic in derived classes.
        # if not self.current_movement_sub_path and not self.ai_just_placed_bomb:
        #     self.change_state("PLANNING_PATH")


    def handle_executing_astar_path_to_target_state(self, ai_current_tile):
        ai_log(f"Base: In EXECUTING_ASTAR_PATH_TO_TARGET at {ai_current_tile}. A*Path: {self.astar_planned_path}, Sub-path: {self.current_movement_sub_path}") # Added log
        if not self.astar_planned_path or self.astar_path_current_segment_index >= len(self.astar_planned_path):
            self.change_state("PLANNING_PATH") # Or specific planning state for this AI type
        elif not self.current_movement_sub_path and ai_current_tile == (self.astar_planned_path[self.astar_path_current_segment_index].x, self.astar_planned_path[self.astar_path_current_segment_index].y) :
             self.astar_path_current_segment_index +=1
             if self.astar_path_current_segment_index >= len(self.astar_planned_path):
                 self.change_state("PLANNING_PATH")
             else:
                 self.last_decision_time = pygame.time.get_ticks() - self.ai_decision_interval


    def handle_moving_to_collect_item_state(self, ai_current_tile):
        ai_log(f"Base: In MOVING_TO_COLLECT_ITEM at {ai_current_tile}. Sub-path: {self.current_movement_sub_path}") # Added log for path
        if not self.current_movement_sub_path:
             self.change_state("PLANNING_ITEM_TARGET")

    def handle_planning_item_target_state(self, ai_current_tile):
        ai_log(f"Base: In PLANNING_ITEM_TARGET at {ai_current_tile}. Default: go IDLE.")
        self.current_movement_sub_path = [] # Explicitly clear here
        self.current_movement_sub_path_index = 0
        self.astar_planned_path = [] # Also A* path
        self.astar_path_current_segment_index = 0
        self.change_state("IDLE")

    def handle_assessing_obstacle_for_item_state(self, ai_current_tile):
        ai_log(f"Base: In ASSESSING_OBSTACLE_FOR_ITEM at {ai_current_tile}. Default: go PLANNING_ITEM_TARGET.")
        self.change_state("PLANNING_ITEM_TARGET")
        
    def handle_evading_danger_state(self, ai_current_tile):
        ai_log(f"Base: EVADING_DANGER at {ai_current_tile} with urgency: {self.evasion_urgency_seconds}s. Sub-path: {self.current_movement_sub_path}")

        if not self.is_tile_dangerous(ai_current_tile[0], ai_current_tile[1], self.evasion_urgency_seconds):
            ai_log("Base: Danger seems to have passed. Re-planning.")
            default_safe_state = "PLANNING_PATH"
            if hasattr(self, 'default_state_after_evasion'):
                default_safe_state = self.default_state_after_evasion
            self.change_state(default_safe_state)
            return

        if self.current_movement_sub_path:
            target_of_current_path = self.current_movement_sub_path[-1]
            if self.is_tile_dangerous(target_of_current_path[0], target_of_current_path[1], 0.05):
                ai_log("Base: Current evasion path target became dangerous. Re-planning evasion.")
                self.current_movement_sub_path = []
                self.current_movement_sub_path_index = 0 # Ensure index is also reset

        if not self.current_movement_sub_path:
            ai_log("Base: Finding new evasion path.")
            retreat_search_depth = getattr(self, 'retreat_search_depth', 7)
            min_options_for_evasion = getattr(self, 'min_retreat_options_for_evasion', 1)

            safe_spots = self.find_safe_tiles_nearby_for_retreat(
                from_coords=ai_current_tile,
                bomb_coords_as_danger_source=ai_current_tile,
                bomb_range_of_danger_source=0,
                max_depth=retreat_search_depth,
                min_options_needed=min_options_for_evasion
            )
            
            best_path_to_safety = None
            if safe_spots:
                candidate_paths = []
                for spot in safe_spots:
                    path = self.bfs_find_direct_movement_path(ai_current_tile, spot, max_depth=retreat_search_depth)
                    if path and len(path) > 1:
                        openness = self._get_tile_openness(spot[0], spot[1])
                        candidate_paths.append({'path': path, 'openness': openness, 'len': len(path)})
                
                if candidate_paths:
                    candidate_paths.sort(key=lambda p: (-p['openness'], p['len']))
                    best_path_to_safety = candidate_paths[0]['path']
            
            if best_path_to_safety:
                ai_log(f"Base: Found best evasion path to {best_path_to_safety[-1]}. Path: {best_path_to_safety}")
                self.set_current_movement_sub_path(best_path_to_safety)
            else:
                ai_log("Base: CRITICAL - No valid evasion path found! Attempting desperate move.")
                self._attempt_desperate_move(ai_current_tile)

    def _attempt_desperate_move(self, ai_current_tile):
        possible_moves = []
        for dx, dy in DIRECTIONS.values():
            next_x, next_y = ai_current_tile[0] + dx, ai_current_tile[1] + dy
            node = self._get_node_at_coords(next_x, next_y)
            if node and node.is_empty_for_direct_movement():
                if self._is_tile_blocked_by_opponent_bomb(next_x, next_y):
                    continue
                danger_score = 0
                if self.is_tile_dangerous(next_x, next_y, 0.05): danger_score += 20
                elif self.is_tile_dangerous(next_x, next_y, 0.15): danger_score += 10
                elif self.is_tile_dangerous(next_x, next_y, 0.3): danger_score += 5
                possible_moves.append(((next_x, next_y), danger_score))
        
        if possible_moves:
            possible_moves.sort(key=lambda m: m[1])
            desperate_target = possible_moves[0][0]
            ai_log(f"Base: Making a desperate random move to {desperate_target}.")
            self.set_current_movement_sub_path([ai_current_tile, desperate_target])
        else:
            ai_log("Base: No desperate moves available. Stuck in danger.")

    def _get_ai_current_tile(self):
        if self.ai_player and self.ai_player.is_alive:
            return (self.ai_player.tile_x, self.ai_player.tile_y)
        return None

    def _get_human_player_current_tile(self):
        if self.human_player_sprite and self.human_player_sprite.is_alive:
            return (self.human_player_sprite.tile_x, self.human_player_sprite.tile_y)
        return None

    def _get_node_at_coords(self, x, y):
        if self.map_manager and 0 <= y < self.map_manager.tile_height and 0 <= x < self.map_manager.tile_width:
            try:
                tile_char = self.map_manager.map_data[y][x]
                return TileNode(x, y, tile_char)
            except IndexError:
                ai_log(f"[ERROR_BASE] Map data access out of bounds for y={y}, x={x}")
                return None
            except TypeError:
                 ai_log(f"[ERROR_BASE] Map data not subscriptable for y={y}, x={x}. map_data type: {type(self.map_manager.map_data)}")
                 return None
        return None

    def _is_tile_blocked_by_opponent_bomb(self, tile_x, tile_y):
        if hasattr(self.game, 'bombs_group'):
            for bomb in self.game.bombs_group:
                if not bomb.exploded and \
                   bomb.current_tile_x == tile_x and \
                   bomb.current_tile_y == tile_y and \
                   bomb.placed_by_player is not self.ai_player:
                    return True
        return False

    def _get_node_neighbors(self, node: TileNode, for_astar_planning=True):
        neighbors = []
        for dx, dy in DIRECTIONS.values():
            nx, ny = node.x + dx, node.y + dy
            neighbor_node_template = self._get_node_at_coords(nx, ny)
            if neighbor_node_template:
                if self._is_tile_blocked_by_opponent_bomb(nx, ny):
                    continue

                if for_astar_planning:
                    if neighbor_node_template.is_walkable_for_astar_planning():
                        neighbors.append(neighbor_node_template)
                else:
                    if neighbor_node_template.is_empty_for_direct_movement():
                        neighbors.append(neighbor_node_template)
        return neighbors

    def _update_and_check_stuck_conditions(self, ai_current_tile, stuck_threshold, oscillation_threshold):
        is_waiting_after_bomb_for_stuck_check = False
        if self.ai_just_placed_bomb:
            if self.is_bomb_still_active(self.last_bomb_placed_time):
                is_waiting_after_bomb_for_stuck_check = True

        if not self.current_movement_sub_path and not is_waiting_after_bomb_for_stuck_check:
            if self.last_known_tile == ai_current_tile:
                self.decision_cycle_stuck_counter += 1
            else:
                self.decision_cycle_stuck_counter = 0
        else:
            self.decision_cycle_stuck_counter = 0
        self.last_known_tile = ai_current_tile

        is_oscillating = False
        if len(self.movement_history) == self.movement_history.maxlen:
            history = list(self.movement_history)
            if history[0] == history[2] and \
               history[1] == history[3] and \
               history[0] != history[1] and \
               ai_current_tile == history[3]:
                self.oscillation_stuck_counter += 1
                is_oscillating = True
                ai_log(f"[STUCK_BASE_OSCILLATION] Oscillation detected. Count: {self.oscillation_stuck_counter}. History: {history}")
            else:
                self.oscillation_stuck_counter = 0
        else:
            self.oscillation_stuck_counter = 0
        
        stuck = self.decision_cycle_stuck_counter >= stuck_threshold
        oscillating = self.oscillation_stuck_counter >= oscillation_threshold

        if stuck and not is_oscillating :
            ai_log(f"[STUCK_BASE_TILE] AI stuck at {ai_current_tile} for {self.decision_cycle_stuck_counter} cycles (threshold: {stuck_threshold}).")
        
        return stuck or oscillating

    def astar_find_path(self, start_coords, target_coords):
        ai_log(f"A* Pathfinding from {start_coords} to {target_coords}")
        start_node = self._get_node_at_coords(start_coords[0], start_coords[1])
        target_node = self._get_node_at_coords(target_coords[0], target_coords[1])
        if not start_node or not target_node: return []

        open_set = []
        heapq.heappush(open_set, (0, 0, start_node))
        node_data = {(start_node.x, start_node.y): start_node}
        closed_set = set()
        start_node.g_cost = 0
        start_node.h_cost = abs(start_node.x - target_node.x) + abs(start_node.y - target_node.y)
        start_node.parent = None

        while open_set:
            current_f, current_h, current_node_from_heap = heapq.heappop(open_set)
            if (current_node_from_heap.x, current_node_from_heap.y) not in node_data or \
               node_data[(current_node_from_heap.x, current_node_from_heap.y)].g_cost < current_node_from_heap.g_cost:
                continue
            current_node = node_data[(current_node_from_heap.x, current_node_from_heap.y)]

            if current_node == target_node:
                path = []
                temp = current_node
                while temp: path.append(temp); temp = temp.parent
                return path[::-1]
            closed_set.add((current_node.x, current_node.y))

            for neighbor_template in self._get_node_neighbors(current_node, for_astar_planning=True):
                if (neighbor_template.x, neighbor_template.y) in closed_set: continue
                tentative_g_cost = current_node.g_cost + neighbor_template.get_astar_move_cost_to_here()
                neighbor_coords = (neighbor_template.x, neighbor_template.y)
                current_neighbor_data = node_data.get(neighbor_coords)
                if current_neighbor_data is None or tentative_g_cost < current_neighbor_data.g_cost:
                    if current_neighbor_data is None:
                        actual_neighbor_node = TileNode(neighbor_template.x, neighbor_template.y, neighbor_template.tile_char)
                    else: actual_neighbor_node = current_neighbor_data
                    actual_neighbor_node.parent = current_node
                    actual_neighbor_node.g_cost = tentative_g_cost
                    actual_neighbor_node.h_cost = abs(actual_neighbor_node.x - target_node.x) + abs(actual_neighbor_node.y - target_node.y)
                    heapq.heappush(open_set, (actual_neighbor_node.get_f_cost(), actual_neighbor_node.h_cost, actual_neighbor_node))
                    node_data[neighbor_coords] = actual_neighbor_node
        ai_log(f"A* Pathfinding failed to find path from {start_coords} to {target_coords}")
        return []

    def bfs_find_direct_movement_path(self, start_coords, target_coords, max_depth=20, avoid_specific_tile=None):
        q = deque([(start_coords, [start_coords])])
        visited = {start_coords}
        while q:
            (curr_x, curr_y), path = q.popleft()
            if len(path) -1 > max_depth : continue
            if (curr_x, curr_y) == target_coords: return path
            shuffled_directions = list(DIRECTIONS.values()); random.shuffle(shuffled_directions)
            for dx, dy in shuffled_directions:
                next_x, next_y = curr_x + dx, curr_y + dy
                next_coords = (next_x, next_y)
                if next_coords not in visited:
                    if avoid_specific_tile and next_coords == avoid_specific_tile: continue
                    node = self._get_node_at_coords(next_x, next_y)
                    if node and node.is_empty_for_direct_movement() and \
                       not self.is_tile_dangerous(next_x, next_y, future_seconds=0.15) and \
                       not self._is_tile_blocked_by_opponent_bomb(next_x, next_y):
                        visited.add(next_coords)
                        q.append((next_coords, path + [next_coords]))
        return []
        
    def can_place_bomb_and_retreat(self, bomb_placement_coords):
        ai_log(f"    [AI_BOMB_DECISION_HELPER] can_place_bomb_and_retreat called for: {bomb_placement_coords}")

        # --- BUG FIX START ---
        # Check if the bomb_placement_coords is a valid spot to place a bomb
        placement_node = self._get_node_at_coords(bomb_placement_coords[0], bomb_placement_coords[1])
        if not placement_node or not placement_node.is_empty_for_direct_movement(): # Must be an empty tile (not a wall)
            ai_log(f"      [AI_BOMB_DECISION_HELPER] Bomb spot {bomb_placement_coords} is not an empty tile. Returning False.")
            return False, None

        # Check if another player (not AI itself) is at the bomb_placement_coords
        human_player_tile = self._get_human_player_current_tile() # Get human player's current tile
        if human_player_tile and human_player_tile == bomb_placement_coords:
            ai_log(f"      [AI_BOMB_DECISION_HELPER] Human player is at bomb spot {bomb_placement_coords}. Returning False.")
            return False, None
        
        # Check if another AI (if any, and not self) is at the bomb_placement_coords
        # This is more for future-proofing if you have multiple AIs.
        for player_sprite in self.game.players_group: # Iterate through all players
            if player_sprite is not self.ai_player and player_sprite.is_alive: # Check if it's another player and alive
                if player_sprite.tile_x == bomb_placement_coords[0] and player_sprite.tile_y == bomb_placement_coords[1]:
                    ai_log(f"      [AI_BOMB_DECISION_HELPER] Another player (ID: {id(player_sprite)}) is at bomb spot {bomb_placement_coords}. Returning False.")
                    return False, None
        
        # Check if there's already a non-exploded bomb at the spot
        for bomb in self.game.bombs_group:
            if not bomb.exploded and \
               bomb.current_tile_x == bomb_placement_coords[0] and \
               bomb.current_tile_y == bomb_placement_coords[1]:
                # Optional: Could allow placing if it's AI's own bomb and owner_has_left_tile is False,
                # but Player.place_bomb already has complex logic for this.
                # Simplest for decision making: if any bomb is there, don't place another.
                ai_log(f"      [AI_BOMB_DECISION_HELPER] Existing non-exploded bomb at {bomb_placement_coords}. Returning False.")
                return False, None
        # --- BUG FIX END ---

        # Check if the spot itself is immediately dangerous (e.g., in an ongoing explosion)
        if self.is_tile_dangerous(bomb_placement_coords[0], bomb_placement_coords[1], future_seconds=0.1): # Check for very immediate danger
            ai_log(f"      [AI_BOMB_DECISION_HELPER] Bomb spot {bomb_placement_coords} is ALREADY dangerous (e.g. existing explosion). Returning False.")
            return False, None

        bomb_range_to_use = self.ai_player.bomb_range
        ai_log(f"      [AI_BOMB_DECISION_HELPER] AI bomb_range for this check: {bomb_range_to_use}")
        
        retreat_search_depth = getattr(self, 'retreat_search_depth', 7)
        min_options = getattr(self, 'min_retreat_options_for_bombing', 1)

        # Find safe retreat spots, considering the bomb placed at bomb_placement_coords as the danger source
        retreat_spots = self.find_safe_tiles_nearby_for_retreat(
            from_coords=bomb_placement_coords, # AI will be at bomb_placement_coords initially
            bomb_coords_as_danger_source=bomb_placement_coords, # The new bomb is the danger
            bomb_range_of_danger_source=bomb_range_to_use,
            max_depth=retreat_search_depth,
            min_options_needed=min_options
        )
        ai_log(f"      [AI_BOMB_DECISION_HELPER] find_safe_tiles_nearby_for_retreat for spot {bomb_placement_coords} (range {bomb_range_to_use}) found: {retreat_spots}")

        if retreat_spots:
            best_retreat_spot = retreat_spots[0] # find_safe_tiles_nearby_for_retreat sorts by preference
            
            # Check if AI can actually path from the bomb_placement_coords to the best_retreat_spot
            path_to_retreat = self.bfs_find_direct_movement_path(bomb_placement_coords, best_retreat_spot, max_depth=retreat_search_depth)
            
            if path_to_retreat and len(path_to_retreat) > 1 : # Path must involve at least one step
                ai_log(f"      [AI_BOMB_DECISION_HELPER] Can bomb at {bomb_placement_coords}, best retreat to {best_retreat_spot} (path: {path_to_retreat}). Returning True.")
                return True, best_retreat_spot
            else:
                ai_log(f"      [AI_BOMB_DECISION_HELPER] Can bomb at {bomb_placement_coords}, found retreat spot {best_retreat_spot}, BUT no valid BFS path from bomb spot to retreat. Returning False.")
                return False, None
        else:
            ai_log(f"      [AI_BOMB_DECISION_HELPER] Cannot bomb at {bomb_placement_coords}, no safe retreat found by find_safe_tiles_nearby_for_retreat. Returning False.")
            return False, None

    def find_safe_tiles_nearby_for_retreat(self, from_coords, bomb_coords_as_danger_source, bomb_range_of_danger_source, max_depth=6, min_options_needed=1):
        ai_log(f"Finding safe retreat from {from_coords}, danger at {bomb_coords_as_danger_source} (range {bomb_range_of_danger_source}), depth {max_depth}")
        q = deque([(from_coords, [from_coords], 0)])
        visited = {from_coords}
        potential_safe_spots = []
        future_check_seconds = getattr(settings, "AI_RETREAT_SPOT_OTHER_DANGER_FUTURE_SECONDS", self.evasion_urgency_seconds)
        while q:
            (curr_x, curr_y), path, depth = q.popleft()
            if depth > max_depth: continue
            is_safe_from_this_bomb = True
            if bomb_range_of_danger_source > 0:
                is_safe_from_this_bomb = not self._is_tile_in_hypothetical_blast(curr_x, curr_y, bomb_coords_as_danger_source[0], bomb_coords_as_danger_source[1], bomb_range_of_danger_source)
            is_safe_from_others = not self.is_tile_dangerous(curr_x, curr_y, future_seconds=future_check_seconds)
            is_blocked_by_opponent_bomb = self._is_tile_blocked_by_opponent_bomb(curr_x, curr_y)
            if is_safe_from_this_bomb and is_safe_from_others and not is_blocked_by_opponent_bomb:
                openness = self._get_tile_openness(curr_x, curr_y)
                potential_safe_spots.append({
                    'coords': (curr_x, curr_y),
                    'path_len': len(path) - 1,
                    'depth': depth,
                    'openness': openness })
            if depth < max_depth:
                shuffled_directions = list(DIRECTIONS.values()); random.shuffle(shuffled_directions)
                for dx, dy in shuffled_directions:
                    next_coords = (curr_x + dx, curr_y + dy)
                    if next_coords not in visited:
                        node = self._get_node_at_coords(next_coords[0], next_coords[1])
                        if node and node.is_empty_for_direct_movement():
                            if not self.is_tile_dangerous(next_coords[0], next_coords[1], 0.05) and \
                               not self._is_tile_blocked_by_opponent_bomb(next_coords[0], next_coords[1]):
                                visited.add(next_coords)
                                q.append((next_coords, path + [next_coords], depth + 1))
        if not potential_safe_spots: return []
        potential_safe_spots.sort(key=lambda s: (-s['openness'], -s['depth'], s['path_len']))
        return [spot['coords'] for spot in potential_safe_spots[:max(min_options_needed, len(potential_safe_spots))]]
        
    def set_current_movement_sub_path(self, path_coords_list):
        if path_coords_list and len(path_coords_list) > 1:
            self.current_movement_sub_path = path_coords_list
            self.current_movement_sub_path_index = 0
            ai_log(f"    Set new sub-path: {self.current_movement_sub_path}")
        else:
            self.current_movement_sub_path = []
            self.current_movement_sub_path_index = 0
            ai_log(f"    Cleared sub-path (path too short or None). Received: {path_coords_list}")

    def execute_next_move_on_sub_path(self, ai_current_tile):
        if not self.current_movement_sub_path: 
            return True
        if ai_current_tile == self.current_movement_sub_path[-1]:
            if self.current_movement_sub_path_index == len(self.current_movement_sub_path) -1 :
                 self.movement_history.append(ai_current_tile)
                 self.current_movement_sub_path = []
                 self.current_movement_sub_path_index = 0
                 if hasattr(self.ai_player, 'is_moving'): self.ai_player.is_moving = False
                 return True
            else: 
                self.current_movement_sub_path = []; self.current_movement_sub_path_index = 0; return True
        if self.current_movement_sub_path_index >= len(self.current_movement_sub_path):
            self.current_movement_sub_path = []; self.current_movement_sub_path_index = 0; return True
        expected_current_sub_path_tile = self.current_movement_sub_path[self.current_movement_sub_path_index]
        if ai_current_tile != expected_current_sub_path_tile:
            self.current_movement_sub_path = []; self.current_movement_sub_path_index = 0; return True
        if self.current_movement_sub_path_index + 1 >= len(self.current_movement_sub_path): 
            self.current_movement_sub_path = []; self.current_movement_sub_path_index = 0; return True
        
        next_target_tile_in_sub_path = self.current_movement_sub_path[self.current_movement_sub_path_index + 1]
        dx = next_target_tile_in_sub_path[0] - ai_current_tile[0]; dy = next_target_tile_in_sub_path[1] - ai_current_tile[1]
        
        if not (abs(dx) <= 1 and abs(dy) <= 1 and (dx != 0 or dy != 0) and (dx == 0 or dy == 0)):
            self.current_movement_sub_path = []; self.current_movement_sub_path_index = 0; return True
        

        moved = self.ai_player.attempt_move_to_tile(dx, dy)
        if moved:
            moved_to_tile = (self.ai_player.tile_x, self.ai_player.tile_y)
            self.movement_history.append(moved_to_tile)
            self.current_movement_sub_path_index += 1
            if moved_to_tile == self.current_movement_sub_path[-1]: 
                self.current_movement_sub_path = []
                self.current_movement_sub_path_index = 0
                if hasattr(self.ai_player, 'is_moving'): self.ai_player.is_moving = False
                return True 
            return False 
        else:
            ai_log(f"    Sub-path move from {ai_current_tile} to {next_target_tile_in_sub_path} FAILED (blocked by attempt_move_to_tile). Clearing.") # 修改日誌以區分
            self.current_movement_sub_path = []; self.current_movement_sub_path_index = 0; return True

    def is_bomb_still_active(self, bomb_placed_timestamp):
        if bomb_placed_timestamp == 0: return False
        elapsed_time = pygame.time.get_ticks() - bomb_placed_timestamp
        bomb_timer_duration = getattr(settings, 'BOMB_TIMER', 3000)
        explosion_effect_duration = getattr(settings, 'EXPLOSION_DURATION', 300)
        buffer_time = 200 
        return elapsed_time < (bomb_timer_duration + explosion_effect_duration + buffer_time)

    def _get_tile_openness(self, tile_x, tile_y, radius=1):
        if not self._get_node_at_coords(tile_x, tile_y): return -1 
        open_count = 0 
        for r_offset in range(-radius, radius + 1): 
            for c_offset in range(-radius, radius + 1): 
                if r_offset == 0 and c_offset == 0: continue 
                node = self._get_node_at_coords(tile_x + c_offset, tile_y + r_offset) 
                if node and node.is_empty_for_direct_movement(): open_count += 1 
        return open_count 

    def _is_tile_in_hypothetical_blast(self, check_tile_x, check_tile_y, bomb_placed_at_x, bomb_placed_at_y, bomb_range):
        if not (0 <= check_tile_x < self.map_manager.tile_width and 0 <= check_tile_y < self.map_manager.tile_height): return False
        if check_tile_x == bomb_placed_at_x and check_tile_y == bomb_placed_at_y: return True
        if check_tile_y == bomb_placed_at_y and abs(check_tile_x - bomb_placed_at_x) <= bomb_range:
            blocked = False; step = 1 if check_tile_x > bomb_placed_at_x else -1
            for i in range(1, abs(check_tile_x - bomb_placed_at_x) + 1): 
                current_check_x = bomb_placed_at_x + i * step
                if self.map_manager.is_solid_wall_at(current_check_x, bomb_placed_at_y): blocked = True; break
                if current_check_x == check_tile_x: break 
                node_between = self._get_node_at_coords(current_check_x, bomb_placed_at_y) 
                if node_between and node_between.is_destructible_box(): blocked = True; break 
            if not blocked and (bomb_placed_at_x + (abs(check_tile_x - bomb_placed_at_x) * step)) == check_tile_x : return True
        if check_tile_x == bomb_placed_at_x and abs(check_tile_y - bomb_placed_at_y) <= bomb_range:
            blocked = False; step = 1 if check_tile_y > bomb_placed_at_y else -1
            for i in range(1, abs(check_tile_y - bomb_placed_at_y) + 1): 
                current_check_y = bomb_placed_at_y + i * step
                if self.map_manager.is_solid_wall_at(bomb_placed_at_x, current_check_y): blocked = True; break
                if current_check_y == check_tile_y: break
                node_between = self._get_node_at_coords(bomb_placed_at_x, current_check_y)
                if node_between and node_between.is_destructible_box(): blocked = True; break
            if not blocked and (bomb_placed_at_y + (abs(check_tile_y - bomb_placed_at_y) * step)) == check_tile_y : return True
        return False

    def is_tile_dangerous(self, tile_x, tile_y, future_seconds=0.3):
        tile_rect = pygame.Rect(tile_x * settings.TILE_SIZE, tile_y * settings.TILE_SIZE, settings.TILE_SIZE, settings.TILE_SIZE)
        if hasattr(self.game, 'explosions_group'):
            for exp_sprite in self.game.explosions_group:
                if exp_sprite.rect.colliderect(tile_rect): return True
        if hasattr(self.game, 'bombs_group'):
            for bomb in self.game.bombs_group:
                if bomb.exploded: continue
                time_to_explosion_ms = bomb.time_left
                if 0 < time_to_explosion_ms < future_seconds * 1000:
                    range_to_check = bomb.placed_by_player.bomb_range if hasattr(bomb.placed_by_player, 'bomb_range') else 1
                    if self._is_tile_in_hypothetical_blast(tile_x, tile_y, bomb.current_tile_x, bomb.current_tile_y, range_to_check): return True
        return False
        
    def debug_draw_path(self, surface):
        if not self.ai_player or not self.ai_player.is_alive:
            return
        
        ai_current_tile_coords = self._get_ai_current_tile()
        if not ai_current_tile_coords:
            return

        try:
            tile_size = settings.TILE_SIZE
            half_tile = tile_size // 2

            COLOR_AI_POS = (0, 0, 255, 100) 
            COLOR_ASTAR_PATH = (0, 128, 255, 180) 
            COLOR_SUB_PATH = (0, 255, 0, 220)     
            COLOR_NEXT_STEP = (255, 255, 0, 255)  
            COLOR_BOMBING_SPOT = (255, 0, 0, 200) 
            COLOR_RETREAT_SPOT = (0, 200, 0, 200) 
            COLOR_TARGET_OBSTACLE = (255, 165, 0, 180) 
            COLOR_DANGEROUS_TILE = (200, 0, 0, 70) 

            ai_rect_surface = pygame.Surface((tile_size, tile_size), pygame.SRCALPHA)
            ai_rect_surface.fill(COLOR_AI_POS)
            surface.blit(ai_rect_surface, (ai_current_tile_coords[0] * tile_size, ai_current_tile_coords[1] * tile_size))
            pygame.draw.rect(surface, (0,0,200), (ai_current_tile_coords[0] * tile_size, ai_current_tile_coords[1] * tile_size, tile_size, tile_size), 1)

            if self.astar_planned_path and self.astar_path_current_segment_index < len(self.astar_planned_path):
                astar_points = [(ai_current_tile_coords[0] * tile_size + half_tile, ai_current_tile_coords[1] * tile_size + half_tile)]
                for i in range(self.astar_path_current_segment_index, len(self.astar_planned_path)):
                    node = self.astar_planned_path[i]
                    astar_points.append((node.x * tile_size + half_tile, node.y * tile_size + half_tile))
                if len(astar_points) > 1: pygame.draw.lines(surface, COLOR_ASTAR_PATH, False, astar_points, 2)
                final_astar_target = self.astar_planned_path[-1]
                pygame.draw.circle(surface, COLOR_ASTAR_PATH, (final_astar_target.x * tile_size + half_tile, final_astar_target.y * tile_size + half_tile), tile_size // 4, 2)
                pygame.draw.line(surface, COLOR_ASTAR_PATH, (final_astar_target.x * tile_size + half_tile - 5, final_astar_target.y * tile_size + half_tile - 5), (final_astar_target.x * tile_size + half_tile + 5, final_astar_target.y * tile_size + half_tile + 5), 2)
                pygame.draw.line(surface, COLOR_ASTAR_PATH, (final_astar_target.x * tile_size + half_tile - 5, final_astar_target.y * tile_size + half_tile + 5), (final_astar_target.x * tile_size + half_tile + 5, final_astar_target.y * tile_size + half_tile - 5), 2)

            if self.current_movement_sub_path and len(self.current_movement_sub_path) > self.current_movement_sub_path_index:
                sub_path_points = [(ai_current_tile_coords[0] * tile_size + half_tile, ai_current_tile_coords[1] * tile_size + half_tile)]
                for i in range(self.current_movement_sub_path_index +1, len(self.current_movement_sub_path)):
                    tile_coords = self.current_movement_sub_path[i]
                    sub_path_points.append((tile_coords[0] * tile_size + half_tile, tile_coords[1] * tile_size + half_tile))
                if len(sub_path_points) > 1: pygame.draw.lines(surface, COLOR_SUB_PATH, False, sub_path_points, 3)

                if self.current_movement_sub_path_index + 1 < len(self.current_movement_sub_path):
                    next_step_coords = self.current_movement_sub_path[self.current_movement_sub_path_index + 1]
                    next_px, next_py = next_step_coords[0] * tile_size + half_tile, next_step_coords[1] * tile_size + half_tile
                    pulse = abs(pygame.time.get_ticks() % 1000 - 500) / 500.0
                    radius = int(half_tile * 0.3 + (half_tile * 0.2 * pulse))
                    alpha = int(150 + 105 * pulse)
                    pulse_s = pygame.Surface((radius*2,radius*2), pygame.SRCALPHA); pygame.draw.circle(pulse_s, (*COLOR_NEXT_STEP[:3], alpha), (radius,radius), radius); surface.blit(pulse_s, (next_px-radius, next_py-radius))

            if hasattr(self, 'chosen_bombing_spot_coords') and self.chosen_bombing_spot_coords:
                bx, by = self.chosen_bombing_spot_coords
                b_px, b_py = bx * tile_size + half_tile, by * tile_size + half_tile
                #pygame.draw.circle(surface, COLOR_BOMBING_SPOT, (b_px, b_py), half_tile//2); pygame.draw.circle(surface, settings.BLACK, (b_px,b_py), half_tile//2,1); pygame.draw.line(surface, settings.BLACK, (b_px, b_py-half_tile//2-2),(b_px,b_py-half_tile//2+3),2)
            
            if hasattr(self, 'chosen_retreat_spot_coords') and self.chosen_retreat_spot_coords and \
               (self.current_state == "TACTICAL_RETREAT_AND_WAIT" or self.current_state == "EVADING_DANGER" or self.ai_just_placed_bomb):
                rx, ry = self.chosen_retreat_spot_coords
                img_rect = self.retreat_img.get_rect()
                img_rect.topleft = (rx * tile_size, ry * tile_size)
                surface.blit(self.retreat_img, img_rect)

                #pygame.draw.rect(surface, COLOR_RETREAT_SPOT, (rx*tile_size+4,ry*tile_size+4,tile_size-8,tile_size-8),0,border_radius=3); pygame.draw.rect(surface, settings.BLACK, (rx*tile_size+4,ry*tile_size+4,tile_size-8,tile_size-8),1,border_radius=3)
            
            obstacle = getattr(self, 'target_obstacle_to_bomb', None) or getattr(self, 'target_destructible_wall_node_in_astar', None)
            if obstacle:
                ox, oy = obstacle.x, obstacle.y
                obs_s = pygame.Surface((tile_size,tile_size), pygame.SRCALPHA); obs_s.fill((*COLOR_TARGET_OBSTACLE[:3],100)); surface.blit(obs_s, (ox*tile_size,oy*tile_size)); pygame.draw.rect(surface, COLOR_TARGET_OBSTACLE, (ox*tile_size,oy*tile_size,tile_size,tile_size),2)

            evasion_check_seconds = getattr(self, 'evasion_urgency_seconds', 0.5)
            if self.current_state == "EVADING_DANGER" or (pygame.time.get_ticks() // 250) % 2 == 0:
                check_radius = 4 
                for r_offset in range(-check_radius, check_radius + 1):
                    for c_offset in range(-check_radius, check_radius + 1):
                        cx, cy = ai_current_tile_coords[0]+c_offset, ai_current_tile_coords[1]+r_offset
                        if 0 <= cx < self.map_manager.tile_width and 0 <= cy < self.map_manager.tile_height:
                            if self.is_tile_dangerous(cx, cy, evasion_check_seconds):
                                danger_s = pygame.Surface((tile_size,tile_size), pygame.SRCALPHA); danger_s.fill(COLOR_DANGEROUS_TILE); surface.blit(danger_s, (cx*tile_size, cy*tile_size))
        
        except AttributeError as e:
            if 'TILE_SIZE' in str(e) or 'game' in str(e) or 'map_manager' in str(e): pass
            else: ai_log(f"Debug Draw AttributeError: {e}")
        except Exception as e:
            ai_log(f"Error during AI debug_draw_path: {e}")