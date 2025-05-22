# oop-2025-proj-pycade/core/ai_controller.py

import pygame
import settings
import random
from collections import deque
import heapq 

AI_DEBUG_MODE = True

def ai_log(message):
    if AI_DEBUG_MODE:
        print(message)

AI_STATE_PLANNING_PATH_TO_PLAYER = "PLANNING_PATH_TO_PLAYER"
AI_STATE_EXECUTING_PATH_CLEARANCE = "EXECUTING_PATH_CLEARANCE"
AI_STATE_TACTICAL_RETREAT_AND_WAIT = "TACTICAL_RETREAT_AND_WAIT"
AI_STATE_ENGAGING_PLAYER = "ENGAGING_PLAYER"
AI_STATE_EVADING_DANGER = "EVADING_DANGER"
AI_STATE_DEAD = "DEAD"

COST_MOVE_EMPTY = 1
COST_BOMB_BOX = 3

DIRECTIONS = {"UP": (0, -1), "DOWN": (0, 1), "LEFT": (-1, 0), "RIGHT": (1, 0)}

class TileNode:
    def __init__(self, x, y, tile_char):
        self.x = x
        self.y = y
        self.tile_char = tile_char
        self.parent = None
        self.g_cost = float('inf')
        self.h_cost = float('inf')

    def get_f_cost(self): return self.g_cost + self.h_cost
    def is_walkable_for_astar_planning(self): return self.tile_char == '.' or self.tile_char == 'D'
    def is_empty_for_direct_movement(self): return self.tile_char == '.'
    def is_destructible_box(self): return self.tile_char == 'D'
    def get_astar_move_cost_to_here(self):
        if self.tile_char == '.': return COST_MOVE_EMPTY
        elif self.tile_char == 'D': return COST_BOMB_BOX
        return float('inf')

    def __lt__(self, other):
        if not isinstance(other, TileNode): return NotImplemented
        if self.get_f_cost() == other.get_f_cost(): return self.h_cost < other.h_cost
        return self.get_f_cost() < other.get_f_cost()
    def __eq__(self, other):
        if not isinstance(other, TileNode): return NotImplemented
        return self.x == other.x and self.y == other.y
    def __hash__(self): return hash((self.x, self.y))
    def __repr__(self):
        g_str = f"{self.g_cost:.1f}" if self.g_cost != float('inf') else 'inf'
        h_str = f"{self.h_cost:.1f}" if self.h_cost != float('inf') else 'inf'
        return f"N({self.x},{self.y},'{self.tile_char}',g={g_str},h={h_str})"

class AIController:
    def __init__(self, ai_player_sprite, game_instance):
        self.ai_player = ai_player_sprite
        self.game = game_instance
        self.map_manager = self.game.map_manager
        self.current_state = AI_STATE_PLANNING_PATH_TO_PLAYER
        self.state_start_time = pygame.time.get_ticks()
        self.ai_decision_interval = settings.AI_MOVE_DELAY
        self.last_decision_time = pygame.time.get_ticks() - self.ai_decision_interval
        self.human_player_sprite = self.game.player1
        self.player_initial_spawn_tile = None
        self.astar_planned_path = []
        self.astar_path_current_segment_index = 0
        self.current_movement_sub_path = []
        self.current_movement_sub_path_index = 0
        self.target_destructible_wall_node_in_astar = None
        self.chosen_bombing_spot_coords = None
        self.chosen_retreat_spot_coords = None
        self.last_bomb_placed_time = 0
        self.ai_just_placed_bomb = False
        self.path_to_player_initial_spawn_clear = False
        self.last_known_tile = (-1,-1)
        self.decision_cycle_stuck_counter = 0
        self.stuck_threshold_decision_cycles = 5
        ai_log(f"[AI_INIT] AIController for Player ID: {id(self.ai_player)} initialized. Initial state: {self.current_state}. Debug Mode: {AI_DEBUG_MODE}")
        self.reset_state()

    def reset_state(self):
        ai_log(f"[AI_RESET] Resetting AI state for Player ID: {id(self.ai_player)}.")
        self.current_state = AI_STATE_PLANNING_PATH_TO_PLAYER
        self.state_start_time = pygame.time.get_ticks()
        self.astar_planned_path = []
        self.astar_path_current_segment_index = 0
        self.current_movement_sub_path = []
        self.current_movement_sub_path_index = 0
        self.target_destructible_wall_node_in_astar = None
        self.chosen_bombing_spot_coords = None
        self.chosen_retreat_spot_coords = None
        self.last_bomb_placed_time = 0
        self.ai_just_placed_bomb = False
        self.path_to_player_initial_spawn_clear = False
        self.last_decision_time = pygame.time.get_ticks() - self.ai_decision_interval
        self.player_initial_spawn_tile = getattr(self.game, 'player1_start_tile', (1,1))
        ai_log(f"[AI_RESET] Target player initial spawn tile set to: {self.player_initial_spawn_tile}")
        self.decision_cycle_stuck_counter = 0
        current_ai_tile_tuple = self._get_ai_current_tile()
        self.last_known_tile = current_ai_tile_tuple if current_ai_tile_tuple else (-1,-1)


    def change_state(self, new_state):
        if self.current_state != new_state:
            ai_log(f"[AI_STATE_CHANGE] ID: {id(self.ai_player)} From {self.current_state} -> {new_state}")
            self.current_state = new_state
            self.state_start_time = pygame.time.get_ticks()
            self.current_movement_sub_path = [] # Always clear sub-path on major state change
            self.current_movement_sub_path_index = 0
            if new_state == AI_STATE_PLANNING_PATH_TO_PLAYER:
                self.astar_planned_path = []
                self.astar_path_current_segment_index = 0
                self.target_destructible_wall_node_in_astar = None
                self.chosen_bombing_spot_coords = None
                self.chosen_retreat_spot_coords = None

    def _get_ai_current_tile(self):
        if self.ai_player and self.ai_player.is_alive:
            return (self.ai_player.tile_x, self.ai_player.tile_y)
        return None

    def _get_human_player_current_tile(self):
        if self.human_player_sprite and self.human_player_sprite.is_alive:
            return (self.human_player_sprite.tile_x, self.human_player_sprite.tile_y)
        return None

    def _get_node_at_coords(self, x, y):
        if 0 <= y < self.map_manager.tile_height and 0 <= x < self.map_manager.tile_width:
            tile_char = self.map_manager.map_data[y][x]
            return TileNode(x, y, tile_char)
        return None

    def _get_node_neighbors(self, node: TileNode, for_astar_planning=True):
        neighbors = []
        for dx, dy in DIRECTIONS.values():
            nx, ny = node.x + dx, node.y + dy
            neighbor_node = self._get_node_at_coords(nx, ny)
            if neighbor_node:
                if for_astar_planning and neighbor_node.is_walkable_for_astar_planning(): neighbors.append(neighbor_node)
                elif not for_astar_planning and neighbor_node.is_empty_for_direct_movement(): neighbors.append(neighbor_node)
        return neighbors

    def _is_tile_in_hypothetical_blast(self, check_tile_x, check_tile_y, bomb_placed_at_x, bomb_placed_at_y, bomb_range):
        if not (0 <= check_tile_x < self.map_manager.tile_width and \
                0 <= check_tile_y < self.map_manager.tile_height):
            return False 

        if check_tile_x == bomb_placed_at_x and check_tile_y == bomb_placed_at_y: return True
        
        if check_tile_y == bomb_placed_at_y and abs(check_tile_x - bomb_placed_at_x) <= bomb_range:
            blocked = False; step = 1 if check_tile_x > bomb_placed_at_x else -1
            for i in range(1, abs(check_tile_x - bomb_placed_at_x)): 
                if self.map_manager.is_solid_wall_at(bomb_placed_at_x + i * step, bomb_placed_at_y):
                    blocked = True; break
            if not blocked: # Check for destructible walls in between, only if not blocked by solid
                 for i in range(1, abs(check_tile_x - bomb_placed_at_x)):
                      tile_char_between = self.map_manager.map_data[bomb_placed_at_y][bomb_placed_at_x + i * step]
                      if tile_char_between == 'D': blocked = True; break
            if not blocked: return True

        if check_tile_x == bomb_placed_at_x and abs(check_tile_y - bomb_placed_at_y) <= bomb_range:
            blocked = False; step = 1 if check_tile_y > bomb_placed_at_y else -1
            for i in range(1, abs(check_tile_y - bomb_placed_at_y)):
                if self.map_manager.is_solid_wall_at(bomb_placed_at_x, bomb_placed_at_y + i * step):
                    blocked = True; break
            if not blocked: # Check for destructible walls in between
                 for i in range(1, abs(check_tile_y - bomb_placed_at_y)):
                      tile_char_between = self.map_manager.map_data[bomb_placed_at_y + i * step][bomb_placed_at_x]
                      if tile_char_between == 'D': blocked = True; break
            if not blocked: return True
        return False

    def is_tile_dangerous(self, tile_x, tile_y, future_seconds=0.3):
        tile_rect = pygame.Rect(tile_x * settings.TILE_SIZE, tile_y * settings.TILE_SIZE, settings.TILE_SIZE, settings.TILE_SIZE)
        for exp_sprite in self.game.explosions_group:
            if exp_sprite.rect.colliderect(tile_rect): return True
        for bomb in self.game.bombs_group:
            if bomb.exploded: continue
            time_to_explosion_ms = (bomb.spawn_time + bomb.timer) - pygame.time.get_ticks()
            if 0 < time_to_explosion_ms < future_seconds * 1000:
                range_to_check = bomb.placed_by_player.bomb_range if hasattr(bomb.placed_by_player, 'bomb_range') else 1
                if self._is_tile_in_hypothetical_blast(tile_x, tile_y, bomb.current_tile_x, bomb.current_tile_y, range_to_check):
                    return True
        return False

    def find_safe_tiles_nearby_for_retreat(self, from_tile_coords, bomb_just_placed_at_coords, bomb_range, max_depth=6):
        q = deque([(from_tile_coords, [from_tile_coords], 0)])
        visited = {from_tile_coords}
        safe_retreat_spots = []
        while q:
            (curr_x, curr_y), path, depth = q.popleft()
            if depth > max_depth: continue
            is_safe_from_this_bomb = not self._is_tile_in_hypothetical_blast(curr_x, curr_y, bomb_just_placed_at_coords[0], bomb_just_placed_at_coords[1], bomb_range)
            is_safe_from_other_dangers = not self.is_tile_dangerous(curr_x, curr_y, future_seconds=settings.BOMB_TIMER/1000 * 0.8)
            if is_safe_from_this_bomb and is_safe_from_other_dangers:
                safe_retreat_spots.append({'coords': (curr_x, curr_y), 'path_len': len(path)})
                if len(safe_retreat_spots) >= 5: break
            if depth < max_depth:
                shuffled_directions = list(DIRECTIONS.values()); random.shuffle(shuffled_directions)
                for dx, dy in shuffled_directions:
                    next_x, next_y = curr_x + dx, curr_y + dy
                    if (next_x, next_y) not in visited:
                        node = self._get_node_at_coords(next_x, next_y)
                        if node and node.is_empty_for_direct_movement():
                            if not self.is_tile_dangerous(next_x, next_y, future_seconds=0.2):
                                visited.add((next_x, next_y)); q.append(((next_x, next_y), path + [(next_x, next_y)], depth + 1))
        if safe_retreat_spots:
            safe_retreat_spots.sort(key=lambda x: x['path_len'])
            return [spot['coords'] for spot in safe_retreat_spots]
        return []

    def can_place_bomb_and_retreat(self, bomb_placement_coords):
        if self.is_tile_dangerous(bomb_placement_coords[0], bomb_placement_coords[1], future_seconds=0.1):
            ai_log(f"  [AI_BOMB_CHECK] Bomb spot {bomb_placement_coords} is ALREADY dangerous.")
            return False, None
        bomb_range = self.ai_player.bomb_range
        retreat_spots = self.find_safe_tiles_nearby_for_retreat(bomb_placement_coords, bomb_placement_coords, bomb_range)
        if retreat_spots:
            ai_log(f"  [AI_BOMB_CHECK] Can bomb at {bomb_placement_coords}, best retreat to {retreat_spots[0]}.")
            return True, retreat_spots[0]
        ai_log(f"  [AI_BOMB_CHECK] Cannot bomb at {bomb_placement_coords}, no safe retreat found.")
        return False, None

    def astar_find_path(self, start_coords, target_coords):
        ai_log(f"[AI_ASTAR] Planning path from {start_coords} to {target_coords}...")
        start_node = self._get_node_at_coords(start_coords[0], start_coords[1])
        target_node = self._get_node_at_coords(target_coords[0], target_coords[1])
        if not start_node or not target_node:
            ai_log(f"[AI_ASTAR_ERROR] Invalid start ({start_node}) or target ({target_node}) node."); return []
        
        # Reset g_cost, h_cost, parent for all potential nodes before search if nodes are persistent
        # For this implementation, _get_node_at_coords creates fresh nodes, so no reset needed here.

        open_set = []; closed_set = set(); open_set_dict = {}
        start_node.g_cost = 0; start_node.h_cost = abs(start_node.x - target_node.x) + abs(start_node.y - target_node.y)
        start_node.parent = None
        heapq.heappush(open_set, (start_node.get_f_cost(), start_node.h_cost, start_node))
        open_set_dict[(start_node.x, start_node.y)] = start_node
        path_found = False; final_node = None
        while open_set:
            _, _, current_node = heapq.heappop(open_set)
            open_set_dict.pop((current_node.x, current_node.y), None)
            if current_node == target_node: final_node = current_node; path_found = True; break
            if (current_node.x, current_node.y) in closed_set: continue # Already processed (if pushed multiple times)
            closed_set.add((current_node.x, current_node.y))
            for neighbor_node in self._get_node_neighbors(current_node, for_astar_planning=True):
                if (neighbor_node.x, neighbor_node.y) in closed_set: continue
                move_cost_to_neighbor = neighbor_node.get_astar_move_cost_to_here()
                tentative_g_cost = current_node.g_cost + move_cost_to_neighbor
                
                current_neighbor_in_open = open_set_dict.get((neighbor_node.x, neighbor_node.y))
                if tentative_g_cost < neighbor_node.g_cost : # Also covers if neighbor_node.g_cost was inf
                    neighbor_node.parent = current_node; neighbor_node.g_cost = tentative_g_cost
                    neighbor_node.h_cost = abs(neighbor_node.x - target_node.x) + abs(neighbor_node.y - target_node.y)
                    # Add to heap, heapq handles duplicates by order of insertion for same priority
                    heapq.heappush(open_set, (neighbor_node.get_f_cost(), neighbor_node.h_cost, neighbor_node))
                    open_set_dict[(neighbor_node.x, neighbor_node.y)] = neighbor_node # Keep track of best node

        path = []
        if path_found and final_node:
            temp = final_node
            while temp: path.append(temp); temp = temp.parent
            path.reverse(); ai_log(f"[AI_ASTAR_SUCCESS] Path found ({len(path)} segments).")
        else: ai_log(f"[AI_ASTAR_FAIL] No path found from {start_coords} to {target_coords}.")
        return path

    def bfs_find_direct_movement_path(self, start_coords, target_coords, max_depth=15):
        q = deque([(start_coords, [start_coords])]); visited = {start_coords}
        while q:
            (curr_x, curr_y), path = q.popleft()
            if len(path) > max_depth : continue
            if (curr_x, curr_y) == target_coords: return path
            shuffled_directions = list(DIRECTIONS.values()); random.shuffle(shuffled_directions)
            for dx, dy in shuffled_directions:
                next_x, next_y = curr_x + dx, curr_y + dy
                if (next_x, next_y) not in visited:
                    node = self._get_node_at_coords(next_x, next_y)
                    if node and node.is_empty_for_direct_movement() and \
                       not self.is_tile_dangerous(next_x, next_y, future_seconds=0.15):
                        visited.add((next_x, next_y)); q.append(((next_x, next_y), path + [(next_x, next_y)]))
        return []

    def _find_optimal_bombing_and_retreat_spot(self, wall_to_bomb_node: TileNode, ai_current_tile):
        candidate_placements = []
        for dx_wall_offset, dy_wall_offset in DIRECTIONS.values():
            bomb_spot_x = wall_to_bomb_node.x + dx_wall_offset; bomb_spot_y = wall_to_bomb_node.y + dy_wall_offset
            bomb_spot_node = self._get_node_at_coords(bomb_spot_x, bomb_spot_y)
            if not (bomb_spot_node and bomb_spot_node.is_empty_for_direct_movement()): continue
            path_to_bomb_spot = self.bfs_find_direct_movement_path(ai_current_tile, (bomb_spot_x, bomb_spot_y))
            if not path_to_bomb_spot: continue # Cannot reach this potential bombing spot
            
            # Check if this bomb spot is the AI's current tile, or if path_to_bomb_spot is just the AI's current tile
            # This means path_to_bomb_spot would be [(ai_current_tile_x, ai_current_tile_y)]
            is_already_at_spot = (ai_current_tile == (bomb_spot_x, bomb_spot_y))

            can_bomb, retreat_spot_coords = self.can_place_bomb_and_retreat((bomb_spot_x, bomb_spot_y))
            if can_bomb and retreat_spot_coords:
                candidate_placements.append({
                    'bomb_spot': (bomb_spot_x, bomb_spot_y), 
                    'retreat_spot': retreat_spot_coords, 
                    'path_to_bomb_spot_len': len(path_to_bomb_spot) if not is_already_at_spot else 0 # Path len 0 if already there
                })
        if not candidate_placements: return None, None
        candidate_placements.sort(key=lambda p: p['path_to_bomb_spot_len'])
        ai_log(f"  Found optimal bombing setup: {candidate_placements[0]}")
        return candidate_placements[0]['bomb_spot'], candidate_placements[0]['retreat_spot']

    def is_bomb_still_active(self, bomb_placed_timestamp):
        if bomb_placed_timestamp == 0: return False
        elapsed_time = pygame.time.get_ticks() - bomb_placed_timestamp
        return elapsed_time < (settings.BOMB_TIMER + settings.EXPLOSION_DURATION + 200)

    def is_path_to_player_initial_spawn_clear(self):
        if not self.player_initial_spawn_tile: return False
        ai_tile = self._get_ai_current_tile()
        if not ai_tile: return False
        
        # (1)！！！ 修正 NameError: name 'node' is not defined
        # 應為 node_in_path.y
        if self.astar_planned_path and self.astar_path_current_segment_index < len(self.astar_planned_path):
            path_segment_clear = True
            for i in range(self.astar_path_current_segment_index, len(self.astar_planned_path)):
                node_in_path = self.astar_planned_path[i]
                current_node_on_map = self._get_node_at_coords(node_in_path.x, node_in_path.y) # Corrected: node_in_path.y
                if current_node_on_map and current_node_on_map.is_destructible_box():
                    path_segment_clear = False; break
            if path_segment_clear:
                self.path_to_player_initial_spawn_clear = True; return True
        
        direct_path_tuples = self.bfs_find_direct_movement_path(ai_tile, self.player_initial_spawn_tile, max_depth=float('inf'))
        if direct_path_tuples:
             self.path_to_player_initial_spawn_clear = True; return True
        
        self.path_to_player_initial_spawn_clear = False; return False

    def set_current_movement_sub_path(self, path_tuples):
        if path_tuples and len(path_tuples) >= 1: # Allow path of length 1 (already at target)
            self.current_movement_sub_path = path_tuples
            self.current_movement_sub_path_index = 0 
            if len(path_tuples) == 1:
                 ai_log(f"  Set sub-path of length 1 (AI already at target): {self.current_movement_sub_path}")
            else:
                 ai_log(f"  Set new movement sub-path: {self.current_movement_sub_path}")
        else:
            self.current_movement_sub_path = []
            self.current_movement_sub_path_index = 0
            ai_log("  Cleared sub-path (attempted to set empty or invalid).")


    def execute_next_move_on_sub_path(self, ai_current_tile):
        if not self.current_movement_sub_path: return True # No sub-path to execute

        # (2)！！！ 修正：如果子路徑只有一個點（AI當前點），視為已完成
        if len(self.current_movement_sub_path) == 1 and ai_current_tile == self.current_movement_sub_path[0]:
            ai_log(f"    Sub-path is just current tile {ai_current_tile}. Considered complete.")
            self.current_movement_sub_path = []
            self.current_movement_sub_path_index = 0
            self.ai_player.is_moving = False
            return True


        if self.current_movement_sub_path_index >= len(self.current_movement_sub_path) -1 :
            # This condition means we are at the last point of a path > 1, or index is out of bounds for path len 1
            # If path was len 1, it's handled above. If len > 1 and index is last, means sub-path completed on previous step.
            ai_log(f"    Sub-path effectively finished or invalid index. Path: {self.current_movement_sub_path}, Index: {self.current_movement_sub_path_index}")
            self.current_movement_sub_path = []; self.current_movement_sub_path_index = 0; self.ai_player.is_moving = False
            return True

        expected_current_sub_path_tile = self.current_movement_sub_path[self.current_movement_sub_path_index]
        if ai_current_tile != expected_current_sub_path_tile:
            ai_log(f"[AI_MOVE_SUB_PATH_WARN] AI at {ai_current_tile} but sub-path expected {expected_current_sub_path_tile} at index {self.current_movement_sub_path_index}. Resetting sub-path.")
            self.current_movement_sub_path = []; self.current_movement_sub_path_index = 0; return True
        
        next_target_tile_in_sub_path = self.current_movement_sub_path[self.current_movement_sub_path_index + 1]
        dx = next_target_tile_in_sub_path[0] - ai_current_tile[0]; dy = next_target_tile_in_sub_path[1] - ai_current_tile[1]

        if abs(dx) > 1 or abs(dy) > 1 or (dx != 0 and dy != 0):
            ai_log(f"[AI_MOVE_SUB_PATH_ERROR] Invalid step from {ai_current_tile} to {next_target_tile_in_sub_path}. Clearing.")
            self.current_movement_sub_path = []; self.current_movement_sub_path_index = 0; return True
        
        moved = self.ai_player.attempt_move_to_tile(dx, dy)
        if moved:
            self.current_movement_sub_path_index += 1
            # Check if this move completed the sub-path
            if self.current_movement_sub_path_index >= len(self.current_movement_sub_path) -1:
                ai_log(f"    Sub-path to {next_target_tile_in_sub_path} completed by this move.")
                self.current_movement_sub_path = []; self.current_movement_sub_path_index = 0
                return True # Sub-path is now finished
            return False # Move initiated, sub-path ongoing
        else:
            ai_log(f"  Sub-path Move from {ai_current_tile} to {next_target_tile_in_sub_path} FAILED (blocked). Clearing sub-path.")
            self.current_movement_sub_path = []; self.current_movement_sub_path_index = 0; return True

    def update(self):
        current_time = pygame.time.get_ticks()
        ai_current_tile = self._get_ai_current_tile()

        if not ai_current_tile or not self.ai_player or not self.ai_player.is_alive:
            if self.current_state != AI_STATE_DEAD: self.change_state(AI_STATE_DEAD)
            return

        current_decision_tile = ai_current_tile
        
        if self.is_tile_dangerous(ai_current_tile[0], ai_current_tile[1], future_seconds=0.4):
            if self.current_state != AI_STATE_EVADING_DANGER:
                ai_log(f"[AI_DANGER_IMMEDIATE] AI at {ai_current_tile} is in danger! Switching to EVADING_DANGER.")
                self.change_state(AI_STATE_EVADING_DANGER)
        
        if current_time - self.last_decision_time >= self.ai_decision_interval or \
           self.current_state == AI_STATE_EVADING_DANGER:
            if self.current_state != AI_STATE_EVADING_DANGER: self.last_decision_time = current_time
            
            # (3)！！！ 卡住檢測邏輯調整：只在AI沒有移動子路徑且不在等待炸彈時才計數
            if not self.current_movement_sub_path and \
               not (self.current_state == AI_STATE_TACTICAL_RETREAT_AND_WAIT and self.ai_just_placed_bomb):
                if self.last_known_tile == current_decision_tile: 
                    self.decision_cycle_stuck_counter += 1
                else: 
                    self.decision_cycle_stuck_counter = 0
            else: # If AI is moving or legitimately waiting, reset stuck counter
                self.decision_cycle_stuck_counter = 0
            self.last_known_tile = current_decision_tile

            if self.decision_cycle_stuck_counter >= self.stuck_threshold_decision_cycles:
                ai_log(f"[AI_STUCK_DETECTED] AI stuck at {current_decision_tile} for {self.decision_cycle_stuck_counter} decision cycles. Forcing re-plan.")
                self.decision_cycle_stuck_counter = 0
                self.change_state(AI_STATE_PLANNING_PATH_TO_PLAYER) # This will also clear sub_path

            # Execute state handler
            if self.current_state == AI_STATE_EVADING_DANGER: self.handle_evading_danger_state(ai_current_tile)
            elif self.current_state == AI_STATE_PLANNING_PATH_TO_PLAYER: self.handle_planning_path_to_player_state(ai_current_tile)
            elif self.current_state == AI_STATE_EXECUTING_PATH_CLEARANCE: self.handle_executing_path_clearance_state(ai_current_tile)
            elif self.current_state == AI_STATE_TACTICAL_RETREAT_AND_WAIT: self.handle_tactical_retreat_and_wait_state(ai_current_tile)
            elif self.current_state == AI_STATE_ENGAGING_PLAYER: self.handle_engaging_player_state(ai_current_tile)
        
        if self.ai_player.action_timer <= 0:
            sub_path_finished_or_failed = False
            if self.current_movement_sub_path:
                sub_path_finished_or_failed = self.execute_next_move_on_sub_path(ai_current_tile)
            
            if sub_path_finished_or_failed: # If sub-path just finished/failed
                # Trigger an immediate re-evaluation of state logic for faster reaction
                self.last_decision_time = pygame.time.get_ticks() - self.ai_decision_interval -1 
            
            if not self.current_movement_sub_path: # No active sub-path (either finished or never set)
                self.ai_player.is_moving = False 
        
        if AI_DEBUG_MODE and hasattr(self.game, 'screen') and self.game.screen:
             self.debug_draw_path(self.game.screen)

    def handle_planning_path_to_player_state(self, ai_current_tile):
        ai_log(f"[AI_HANDLER] PLANNING_PATH_TO_PLAYER at {ai_current_tile}")
        if not self.player_initial_spawn_tile:
            ai_log("[AI_ERROR] Player initial spawn tile not set!"); self.player_initial_spawn_tile = self._get_human_player_current_tile() or (1,1)
        
        self.astar_planned_path = self.astar_find_path(ai_current_tile, self.player_initial_spawn_tile)
        if self.astar_planned_path:
            self.astar_path_current_segment_index = 0 # Reset A* path index
            self.path_to_player_initial_spawn_clear = not any(node.is_destructible_box() for node in self.astar_planned_path)
            if self.path_to_player_initial_spawn_clear:
                ai_log("  A* Path to player initial spawn is ALREADY CLEAR."); self.change_state(AI_STATE_ENGAGING_PLAYER)
            else:
                ai_log(f"  New A* path set, needs clearing. First segment: {self.astar_planned_path[0] if self.astar_planned_path else 'None'}")
                self.change_state(AI_STATE_EXECUTING_PATH_CLEARANCE)
        else: ai_log(f"  A* failed to find path from {ai_current_tile} to {self.player_initial_spawn_tile}. AI will wait.")

    def handle_executing_path_clearance_state(self, ai_current_tile):
        if self.ai_just_placed_bomb: return

        if not self.astar_planned_path or self.astar_path_current_segment_index >= len(self.astar_planned_path):
            ai_log("  A* path finished/invalid in EXECUTING_PATH_CLEARANCE.")
            # (4)！！！ 在這裡重新檢查路徑是否真的通了
            if self.is_path_to_player_initial_spawn_clear(): # Verify after A* path depletion
                ai_log("    Path to player spawn confirmed clear!")
                self.path_to_player_initial_spawn_clear = True
                self.change_state(AI_STATE_ENGAGING_PLAYER)
            else:
                ai_log("    Path still not clear or A* path was incomplete. Re-planning.")
                self.change_state(AI_STATE_PLANNING_PATH_TO_PLAYER)
            return

        if self.current_movement_sub_path: return # Busy with sub-path

        # (5)！！！ 修改後的 EXECUTING_PATH_CLEARANCE 核心邏輯
        # Process current A* segment, advance if AI is already on it and it's empty
        made_decision_for_segment = False
        while self.astar_planned_path and self.astar_path_current_segment_index < len(self.astar_planned_path):
            current_astar_target_node = self.astar_planned_path[self.astar_path_current_segment_index]
            ai_log(f"  EXECUTE_CLEARANCE: Evaluating A* segment idx {self.astar_path_current_segment_index}: {current_astar_target_node} from current AI tile {ai_current_tile}")

            if ai_current_tile == (current_astar_target_node.x, current_astar_target_node.y):
                # AI is already AT this A* node. It should be an empty tile.
                ai_log(f"    AI is AT A* target node {current_astar_target_node}. Advancing A* path index.")
                self.astar_path_current_segment_index += 1
                if self.astar_path_current_segment_index >= len(self.astar_planned_path): # Path ended
                    ai_log("    Reached end of A* path by being on its last node.")
                    self.change_state(AI_STATE_PLANNING_PATH_TO_PLAYER) # Re-plan or engage
                    return
                # Continue loop to process the NEW current_astar_target_node
            else: 
                # AI is NOT at current_astar_target_node, so this is the node to act upon.
                if current_astar_target_node.is_empty_for_direct_movement():
                    ai_log(f"    A* segment is EMPTY: {current_astar_target_node}. Setting sub-path to move.")
                    path_tuples = self.bfs_find_direct_movement_path(ai_current_tile, (current_astar_target_node.x, current_astar_target_node.y))
                    if path_tuples: self.set_current_movement_sub_path(path_tuples)
                    else:
                        ai_log(f"    Cannot BFS to A* empty node {current_astar_target_node}. Obstruction? Re-planning A* path.")
                        self.change_state(AI_STATE_PLANNING_PATH_TO_PLAYER)
                    made_decision_for_segment = True; break # Break while loop

                elif current_astar_target_node.is_destructible_box():
                    self.target_destructible_wall_node_in_astar = current_astar_target_node
                    ai_log(f"    A* segment is DESTRUCTIBLE_BOX: {self.target_destructible_wall_node_in_astar}. Finding bombing spot.")
                    bomb_spot_coord, retreat_spot_coord = self._find_optimal_bombing_and_retreat_spot(self.target_destructible_wall_node_in_astar, ai_current_tile)
                    if bomb_spot_coord and retreat_spot_coord:
                        self.chosen_bombing_spot_coords = bomb_spot_coord
                        self.chosen_retreat_spot_coords = retreat_spot_coord
                        ai_log(f"      Optimal bombing spot: {self.chosen_bombing_spot_coords}, retreat to: {self.chosen_retreat_spot_coords}")
                        if ai_current_tile == self.chosen_bombing_spot_coords:
                            ai_log(f"      AI is ALREADY at bombing spot {self.chosen_bombing_spot_coords}. Attempting to place bomb.")
                            if self.ai_player.bombs_placed_count < self.ai_player.max_bombs:
                                self.ai_player.place_bomb(); self.last_bomb_placed_time = pygame.time.get_ticks(); self.ai_just_placed_bomb = True
                                retreat_path_tuples = self.bfs_find_direct_movement_path(ai_current_tile, self.chosen_retreat_spot_coords)
                                if retreat_path_tuples: self.set_current_movement_sub_path(retreat_path_tuples)
                                else: ai_log(f"      [CRITICAL_BOMB_PLACE] Placed bomb but cannot find path to retreat spot {self.chosen_retreat_spot_coords}!")
                                self.change_state(AI_STATE_TACTICAL_RETREAT_AND_WAIT)
                            else:
                                ai_log("      AI at bombing spot, but no bombs available. Re-planning."); self.change_state(AI_STATE_PLANNING_PATH_TO_PLAYER)
                        else:
                            path_to_bomb_spot = self.bfs_find_direct_movement_path(ai_current_tile, self.chosen_bombing_spot_coords)
                            if path_to_bomb_spot: self.set_current_movement_sub_path(path_to_bomb_spot)
                            else:
                                ai_log(f"      Cannot BFS to chosen bombing spot {self.chosen_bombing_spot_coords}. Re-planning A*."); self.target_destructible_wall_node_in_astar = None; self.change_state(AI_STATE_PLANNING_PATH_TO_PLAYER)
                    else:
                        ai_log(f"      Cannot find safe bombing/retreat for wall {self.target_destructible_wall_node_in_astar}. Re-planning A*."); self.target_destructible_wall_node_in_astar = None; self.change_state(AI_STATE_PLANNING_PATH_TO_PLAYER)
                    made_decision_for_segment = True; break # Break while loop
                else:
                    ai_log(f"[AI_ERROR] A* path segment {current_astar_target_node} is invalid. Re-planning."); self.change_state(AI_STATE_PLANNING_PATH_TO_PLAYER)
                    made_decision_for_segment = True; break # Break while loop
        
        if not made_decision_for_segment and (not self.astar_planned_path or self.astar_path_current_segment_index >= len(self.astar_planned_path)):
            # This means the while loop finished because the A* path was exhausted by AI being on the nodes
            ai_log("  EXECUTE_CLEARANCE: A* path exhausted by AI being on all remaining empty nodes. Re-evaluating path completion.")
            if self.is_path_to_player_initial_spawn_clear():
                 self.change_state(AI_STATE_ENGAGING_PLAYER)
            else:
                 self.change_state(AI_STATE_PLANNING_PATH_TO_PLAYER)


    def handle_tactical_retreat_and_wait_state(self, ai_current_tile):
        if self.current_movement_sub_path: return 
        if ai_current_tile == self.chosen_retreat_spot_coords:
            if not self.is_bomb_still_active(self.last_bomb_placed_time):
                ai_log(f"  Bomb (placed at {self.last_bomb_placed_time}) has cleared.")
                self.ai_just_placed_bomb = False
                # (6)！！！ 修正：確保 target_destructible_wall_node_in_astar 在判斷後再清除
                wall_destroyed = False
                if self.target_destructible_wall_node_in_astar:
                    updated_wall_node = self._get_node_at_coords(self.target_destructible_wall_node_in_astar.x, self.target_destructible_wall_node_in_astar.y)
                    if updated_wall_node and updated_wall_node.is_empty_for_direct_movement():
                        ai_log(f"    Target wall {self.target_destructible_wall_node_in_astar} confirmed destroyed.")
                        self.astar_path_current_segment_index += 1 
                        wall_destroyed = True
                    else:
                        ai_log(f"    Target wall {self.target_destructible_wall_node_in_astar} still exists or check failed. A* path will re-evaluate.")
                
                self.target_destructible_wall_node_in_astar = None # Clear after checking
                self.chosen_bombing_spot_coords = None
                self.chosen_retreat_spot_coords = None

                # (7)！！！ 修正：在決定下一個狀態前，先檢查 is_path_to_player_initial_spawn_clear
                # 這個檢查現在會考慮 A* 路徑的剩餘部分
                if self.is_path_to_player_initial_spawn_clear(): # This will also update self.path_to_player_initial_spawn_clear
                    ai_log("    Path to player spawn is now clear after bombing.")
                    self.change_state(AI_STATE_ENGAGING_PLAYER)
                elif self.astar_planned_path and self.astar_path_current_segment_index < len(self.astar_planned_path):
                     ai_log("    Path not fully clear, continuing A* path execution.")
                     self.change_state(AI_STATE_EXECUTING_PATH_CLEARANCE)
                else: 
                    ai_log("    A* path finished or became invalid after bombing. Re-planning.")
                    self.change_state(AI_STATE_PLANNING_PATH_TO_PLAYER)
        else: 
            ai_log(f"  Not at chosen retreat spot {self.chosen_retreat_spot_coords} and no sub-path. Trying to re-path or re-plan.")
            if self.chosen_retreat_spot_coords:
                path_tuples = self.bfs_find_direct_movement_path(ai_current_tile, self.chosen_retreat_spot_coords)
                if path_tuples: self.set_current_movement_sub_path(path_tuples)
                else: 
                    ai_log(f"  [CRITICAL_RETREAT_FAIL] Cannot BFS to {self.chosen_retreat_spot_coords}! Re-planning A*.")
                    self.ai_just_placed_bomb = False; self.change_state(AI_STATE_PLANNING_PATH_TO_PLAYER)
            else:
                 ai_log(f"  [CRITICAL_RETREAT_FAIL] No chosen_retreat_spot. Re-planning A*.")
                 self.ai_just_placed_bomb = False; self.change_state(AI_STATE_PLANNING_PATH_TO_PLAYER)

    def handle_engaging_player_state(self, ai_current_tile):
        ai_log(f"[AI_HANDLER] ENGAGING_PLAYER at {ai_current_tile}")
        self.path_to_player_initial_spawn_clear = True 

        human_pos = self._get_human_player_current_tile()
        if not human_pos:
            ai_log("  ENGAGE: Human player not found or not alive. Switching to PLANNING.")
            self.change_state(AI_STATE_PLANNING_PATH_TO_PLAYER)
            return

        # --- 策略 1: 檢查是否可以在當前位置或鄰近位置放置炸彈來攻擊 ---
        # 候選炸彈放置點：AI當前位置以及其周圍的空格子
        potential_bombing_spots = [ai_current_tile]
        for dx, dy in DIRECTIONS.values():
            adj_x, adj_y = ai_current_tile[0] + dx, ai_current_tile[1] + dy
            adj_node = self._get_node_at_coords(adj_x, adj_y)
            if adj_node and adj_node.is_empty_for_direct_movement() and not self.is_tile_dangerous(adj_x, adj_y, 0.1):
                potential_bombing_spots.append((adj_x, adj_y))
        
        ai_log(f"  ENGAGE: Potential bombing spots to check: {potential_bombing_spots}")

        best_bombing_action = None # Store a dictionary: {'bomb_spot': (x,y), 'retreat_spot': (x,y), 'path_to_bomb_spot': list}

        if not self.ai_just_placed_bomb and self.ai_player.bombs_placed_count < self.ai_player.max_bombs:
            for spot_to_bomb_from in potential_bombing_spots:
                dist_human_to_potential_bomb = abs(spot_to_bomb_from[0] - human_pos[0]) + abs(spot_to_bomb_from[1] - human_pos[1])
                
                # 只有當這個潛在炸彈點本身離玩家夠近時才考慮 (避免AI繞遠路去一個點放炸彈)
                # 並且，這個炸彈點的炸彈能炸到玩家
                # bomb_range + 1 意味著炸彈本身或緊鄰的格子
                if dist_human_to_potential_bomb <= self.ai_player.bomb_range: # 玩家必須在炸彈本身的爆炸範圍內
                    ai_log(f"    ENGAGE: Checking bombing from {spot_to_bomb_from} (dist to human from here: {dist_human_to_potential_bomb})")
                    
                    is_player_in_blast = self._is_tile_in_hypothetical_blast(
                        human_pos[0], human_pos[1], 
                        spot_to_bomb_from[0], spot_to_bomb_from[1], 
                        self.ai_player.bomb_range
                    )
                    ai_log(f"      ENGAGE: Is player {human_pos} in blast if bombed from {spot_to_bomb_from}? {is_player_in_blast}")

                    if is_player_in_blast:
                        can_bomb_at_spot, retreat_spot = self.can_place_bomb_and_retreat(spot_to_bomb_from)
                        ai_log(f"      ENGAGE: Can place bomb at {spot_to_bomb_from} and retreat to {retreat_spot}? {can_bomb_at_spot}")
                        
                        if can_bomb_at_spot:
                            path_to_this_bomb_spot = []
                            if spot_to_bomb_from == ai_current_tile:
                                path_to_this_bomb_spot = [ai_current_tile] # 長度為1的路徑
                            else:
                                path_to_this_bomb_spot = self.bfs_find_direct_movement_path(ai_current_tile, spot_to_bomb_from, max_depth=3) # 短路徑到鄰近炸彈點

                            if path_to_this_bomb_spot: # 確保能到達這個選定的炸彈放置點
                                if best_bombing_action is None or len(path_to_this_bomb_spot) < len(best_bombing_action['path_to_bomb_spot']):
                                    best_bombing_action = {
                                        'bomb_spot': spot_to_bomb_from,
                                        'retreat_spot': retreat_spot,
                                        'path_to_bomb_spot': path_to_this_bomb_spot
                                    }
                                    ai_log(f"        ENGAGE: Found a good bombing action: {best_bombing_action}")
            
            if best_bombing_action:
                ai_log(f"    ENGAGE: BEST BOMBING ACTION CHOSEN: {best_bombing_action}")
                self.chosen_bombing_spot_coords = best_bombing_action['bomb_spot']
                self.chosen_retreat_spot_coords = best_bombing_action['retreat_spot']

                if ai_current_tile == self.chosen_bombing_spot_coords:
                    ai_log(f"      AI is ALREADY at best bombing spot {self.chosen_bombing_spot_coords}. Placing bomb.")
                    self.ai_player.place_bomb()
                    self.last_bomb_placed_time = pygame.time.get_ticks()
                    self.ai_just_placed_bomb = True
                    retreat_path_tuples = self.bfs_find_direct_movement_path(ai_current_tile, self.chosen_retreat_spot_coords)
                    if retreat_path_tuples: self.set_current_movement_sub_path(retreat_path_tuples)
                    else: ai_log(f"      [CRITICAL_BOMB_PLACE] Placed bomb but CANNOT find path to retreat spot {self.chosen_retreat_spot_coords}!")
                    self.change_state(AI_STATE_TACTICAL_RETREAT_AND_WAIT)
                    return
                else:
                    ai_log(f"      Setting sub-path to chosen bombing spot: {best_bombing_action['path_to_bomb_spot']}")
                    self.set_current_movement_sub_path(best_bombing_action['path_to_bomb_spot'])
                    # 等待移動到炸彈點後，下一次 handle_engaging_player_state 會再次評估並可能放置炸彈
                    return # 設定了移動到炸彈點的路徑，等待執行

        # --- 如果沒有選擇放置炸彈，並且AI不在移動動畫中，再嘗試移動到玩家 ---
        if self.ai_player.action_timer > 0: 
            ai_log("  ENGAGE: AI is currently in action_timer (from previous bomb placement or move), waiting.")
            return

        if not self.current_movement_sub_path: 
            ai_log(f"  ENGAGE: No bomb action taken & no current sub-path. Attempting to path to human at {human_pos}.")
            path_to_human = self.bfs_find_direct_movement_path(ai_current_tile, human_pos, max_depth=10) 
            
            if path_to_human and len(path_to_human) > 1: 
                self.set_current_movement_sub_path(path_to_human)
                ai_log(f"  ENGAGE: New sub-path set to human: {path_to_human}")
            else:
                ai_log(f"  ENGAGE: Cannot find direct path to human at {human_pos} or path is trivial. AI may wait or stuck detection will trigger.")

    def handle_evading_danger_state(self, ai_current_tile):
        ai_log(f"[AI_HANDLER] EVADING_DANGER at {ai_current_tile}")
        if not self.is_tile_dangerous(ai_current_tile[0], ai_current_tile[1], future_seconds=0.1):
            ai_log("  EVADE: Current tile now safe. Deciding next.")
            self.current_movement_sub_path = []
            if self.path_to_player_initial_spawn_clear: self.change_state(AI_STATE_ENGAGING_PLAYER)
            elif self.astar_planned_path and self.astar_path_current_segment_index < len(self.astar_planned_path):
                self.change_state(AI_STATE_EXECUTING_PATH_CLEARANCE)
            else: self.change_state(AI_STATE_PLANNING_PATH_TO_PLAYER)
            return
        if not self.current_movement_sub_path or \
           (self.current_movement_sub_path and self.is_tile_dangerous(self.current_movement_sub_path[-1][0], self.current_movement_sub_path[-1][1], future_seconds=0.2)):
            ai_log("  EVADE: Finding new evasion path.")
            safe_options_coords = self.find_safe_tiles_nearby_for_retreat(ai_current_tile, ai_current_tile, 0, max_depth=7)
            best_evasion_path = []
            if safe_options_coords:
                for safe_spot_coord in safe_options_coords[:3]:
                    evasion_path_tuples = self.bfs_find_direct_movement_path(ai_current_tile, safe_spot_coord, max_depth=7)
                    if evasion_path_tuples: best_evasion_path = evasion_path_tuples; break
            if best_evasion_path: self.set_current_movement_sub_path(best_evasion_path); ai_log(f"    New evasion sub-path set: {best_evasion_path}")
            else: ai_log("    EVADE: Cannot find any safe evasion path! AI trapped."); self.current_movement_sub_path = []; self.ai_player.is_moving = False

    
    def debug_draw_path(self, surface):
        if not self.ai_player or not self.ai_player.is_alive: return
        ai_tile_now = self._get_ai_current_tile()
        if not ai_tile_now: return

        try:
            current_game_time = pygame.time.get_ticks()
            show_strategic_path = True # 預設顯示

            # 條件1: 開局一段時間後不再顯示 A* 戰略路徑
            if hasattr(settings, 'AI_STRATEGIC_PATH_DISPLAY_DURATION'):
                if (current_game_time - self.game_start_time) / 1000 > settings.AI_STRATEGIC_PATH_DISPLAY_DURATION:
                    show_strategic_path = False
            
            # 條件2: 或者當 AI 進入 ENGAGING_PLAYER 狀態後，也可以選擇不顯示總體戰略路徑
            # (你可以選擇啟用這個條件，或者只用時間條件)
            # if self.current_state == AI_STATE_ENGAGING_PLAYER:
            #     show_strategic_path = False


            # --- A* 戰略路徑 (深藍色線) ---
            # 代表 AI 的長期目標路徑，用於清除障礙。
            if show_strategic_path and self.astar_planned_path and \
               self.astar_path_current_segment_index < len(self.astar_planned_path):
                astar_points_to_draw = []
                
                start_px_astar = ai_tile_now[0] * settings.TILE_SIZE + settings.TILE_SIZE // 2
                start_py_astar = ai_tile_now[1] * settings.TILE_SIZE + settings.TILE_SIZE // 2
                astar_points_to_draw.append((start_px_astar, start_py_astar))

                for i in range(self.astar_path_current_segment_index, len(self.astar_planned_path)):
                    node = self.astar_planned_path[i]
                    px = node.x * settings.TILE_SIZE + settings.TILE_SIZE // 2
                    py = node.y * settings.TILE_SIZE + settings.TILE_SIZE // 2
                    astar_points_to_draw.append((px,py))
                    
                    if i == self.astar_path_current_segment_index:
                         pygame.draw.circle(surface, (255, 165, 0, 220), (px,py), settings.TILE_SIZE//3 + 1, 3) 
                
                if len(astar_points_to_draw) > 1:
                     pygame.draw.lines(surface, (0, 0, 139, 180), False, astar_points_to_draw, 2) 
                elif len(astar_points_to_draw) == 1 and astar_points_to_draw[0] != (start_px_astar, start_py_astar) :
                    pygame.draw.circle(surface, (255,165,0, 200), astar_points_to_draw[0], settings.TILE_SIZE//3 + 3, 3)


            # --- 即時移動子路徑 (BFS 短途移動，紫紅色線) ---
            # 代表 AI 當前正在執行的短程移動。
            if self.current_movement_sub_path and \
               self.current_movement_sub_path_index < len(self.current_movement_sub_path) -1 : 
                sub_path_points_to_draw = []
                
                start_px_sub = ai_tile_now[0] * settings.TILE_SIZE + settings.TILE_SIZE // 2
                start_py_sub = ai_tile_now[1] * settings.TILE_SIZE + settings.TILE_SIZE // 2
                sub_path_points_to_draw.append((start_px_sub, start_py_sub))

                for i in range(self.current_movement_sub_path_index + 1, len(self.current_movement_sub_path)):
                    tile_coords = self.current_movement_sub_path[i]
                    px = tile_coords[0] * settings.TILE_SIZE + settings.TILE_SIZE // 2
                    py = tile_coords[1] * settings.TILE_SIZE + settings.TILE_SIZE // 2
                    sub_path_points_to_draw.append((px,py))
                
                if len(sub_path_points_to_draw) > 1: 
                    pygame.draw.lines(surface, (138, 43, 226, 200), False, sub_path_points_to_draw, 3) 
                    next_sub_step_coords = self.current_movement_sub_path[self.current_movement_sub_path_index + 1]
                    next_px = next_sub_step_coords[0] * settings.TILE_SIZE + settings.TILE_SIZE // 2
                    next_py = next_sub_step_coords[1] * settings.TILE_SIZE + settings.TILE_SIZE // 2
                    pygame.draw.circle(surface, (0, 220, 220, 220), (next_px, next_py), settings.TILE_SIZE//5, 2) 


            # --- 撤退點標記 (淺藍色半透明小方塊) ---
            if self.chosen_retreat_spot_coords and self.current_state == AI_STATE_TACTICAL_RETREAT_AND_WAIT:
                # （之前已修改）使淺藍色撤退方塊變小並保持半透明
                square_size = settings.TILE_SIZE // 2 
                offset = (settings.TILE_SIZE - square_size) // 2 
                
                rx_pixel = self.chosen_retreat_spot_coords[0] * settings.TILE_SIZE + offset
                ry_pixel = self.chosen_retreat_spot_coords[1] * settings.TILE_SIZE + offset
                
                s = pygame.Surface((square_size, square_size), pygame.SRCALPHA)
                pygame.draw.rect(s, (173, 216, 230, 120), s.get_rect())  
                surface.blit(s, (rx_pixel, ry_pixel))


            # --- 炸彈放置點標記 (紅色目標圈) ---
            if self.chosen_bombing_spot_coords and \
               (self.current_state == AI_STATE_EXECUTING_PATH_CLEARANCE or \
                (self.current_state == AI_STATE_ENGAGING_PLAYER and self.ai_just_placed_bomb)):
                pygame.draw.circle(surface, (255,0,0,180), 
                                   (self.chosen_bombing_spot_coords[0]*settings.TILE_SIZE+settings.TILE_SIZE//2, 
                                    self.chosen_bombing_spot_coords[1]*settings.TILE_SIZE+settings.TILE_SIZE//2), 
                                   settings.TILE_SIZE//3 -1, 3) 

            # --- A*路徑上要炸的牆 (黃色框) ---
            # （2）！！！ 修改：只有在 show_strategic_path 為 True 時才顯示目標牆的黃色框 ！！！（2）
            if show_strategic_path and self.target_destructible_wall_node_in_astar and \
               self.current_state == AI_STATE_EXECUTING_PATH_CLEARANCE : 
                wall_node = self.target_destructible_wall_node_in_astar
                pygame.draw.rect(surface, (255,255,0, 120), 
                                 (wall_node.x*settings.TILE_SIZE, wall_node.y*settings.TILE_SIZE, 
                                  settings.TILE_SIZE, settings.TILE_SIZE), 3) 
            # （2）！！！ 修改結束 ！！！（2）
        
        except AttributeError as e:
            if 'TILE_SIZE' in str(e): pass 
            else: ai_log(f"Debug Draw AttributeError: {e}") # 增加日誌以便追蹤其他 AttributeErrors
        except Exception as e: 
            ai_log(f"Error during debug_draw_path: {e}")