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
AI_STATE_CLOSE_QUARTERS_COMBAT = "CLOSE_QUARTERS_COMBAT"

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
        self.has_made_contact_with_player = False
        self.player_contact_distance_threshold = 2
        # 新增用於CQC和振盪檢測的屬性
        self.cqc_last_reposition_target = None
        self.movement_history = deque(maxlen=4) # 記錄最近4個AI所在格子
        self.oscillation_stuck_counter = 0

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
        self.ai_just_placed_bomb = False # 確保重置
        self.path_to_player_initial_spawn_clear = False
        self.last_decision_time = pygame.time.get_ticks() - self.ai_decision_interval
        self.player_initial_spawn_tile = getattr(self.game, 'player1_start_tile', (1,1))
        ai_log(f"[AI_RESET] Target player initial spawn tile set to: {self.player_initial_spawn_tile}")
        self.decision_cycle_stuck_counter = 0
        self.has_made_contact_with_player = False
        current_ai_tile_tuple = self._get_ai_current_tile()
        self.last_known_tile = current_ai_tile_tuple if current_ai_tile_tuple else (-1,-1)
        # 重置CQC和振盪檢測相關屬性
        self.cqc_last_reposition_target = None
        self.movement_history.clear()
        self.oscillation_stuck_counter = 0


    def change_state(self, new_state):
        if self.current_state != new_state:
            ai_log(f"[AI_STATE_CHANGE] ID: {id(self.ai_player)} From {self.current_state} -> {new_state}")

            # 狀態切換時的清理邏輯
            if self.current_state == AI_STATE_TACTICAL_RETREAT_AND_WAIT and self.ai_just_placed_bomb:
                if not self.is_bomb_still_active(self.last_bomb_placed_time):
                    ai_log(f"    [STATE_CHANGE_CLEANUP] Resetting ai_just_placed_bomb due to leaving TACTICAL_RETREAT_AND_WAIT and bomb cleared.")
                    self.ai_just_placed_bomb = False
                else:
                    ai_log(f"    [STATE_CHANGE_CLEANUP] Leaving TACTICAL_RETREAT_AND_WAIT but bomb might still be active. ai_just_placed_bomb remains {self.ai_just_placed_bomb}.")

            self.current_state = new_state
            self.state_start_time = pygame.time.get_ticks()
            self.current_movement_sub_path = []
            self.current_movement_sub_path_index = 0
            self.cqc_last_reposition_target = None # 清理CQC的最後移動目標

            if new_state != AI_STATE_EXECUTING_PATH_CLEARANCE and \
               new_state != AI_STATE_TACTICAL_RETREAT_AND_WAIT:
                self.target_destructible_wall_node_in_astar = None
            if new_state != AI_STATE_TACTICAL_RETREAT_AND_WAIT and \
               new_state != AI_STATE_CLOSE_QUARTERS_COMBAT:
                self.chosen_bombing_spot_coords = None
                self.chosen_retreat_spot_coords = None
            if new_state == AI_STATE_PLANNING_PATH_TO_PLAYER:
                 self.astar_planned_path = []
                 self.astar_path_current_segment_index = 0


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
                if for_astar_planning:
                    if neighbor_node.is_walkable_for_astar_planning():
                        neighbors.append(neighbor_node)
                else:
                    if neighbor_node.is_empty_for_direct_movement():
                        neighbors.append(neighbor_node)
        return neighbors

    def _is_tile_in_hypothetical_blast(self, check_tile_x, check_tile_y, bomb_placed_at_x, bomb_placed_at_y, bomb_range):
        if not (0 <= check_tile_x < self.map_manager.tile_width and \
                0 <= check_tile_y < self.map_manager.tile_height):
            return False

        if check_tile_x == bomb_placed_at_x and check_tile_y == bomb_placed_at_y: return True

        if check_tile_y == bomb_placed_at_y and abs(check_tile_x - bomb_placed_at_x) <= bomb_range:
            blocked = False
            step = 1 if check_tile_x > bomb_placed_at_x else -1
            for i in range(1, abs(check_tile_x - bomb_placed_at_x)):
                current_check_x = bomb_placed_at_x + i * step
                if self.map_manager.is_solid_wall_at(current_check_x, bomb_placed_at_y):
                    blocked = True; break
                node_between = self._get_node_at_coords(current_check_x, bomb_placed_at_y)
                if node_between and node_between.is_destructible_box():
                    blocked = True; break
            if not blocked: return True

        if check_tile_x == bomb_placed_at_x and abs(check_tile_y - bomb_placed_at_y) <= bomb_range:
            blocked = False
            step = 1 if check_tile_y > bomb_placed_at_y else -1
            for i in range(1, abs(check_tile_y - bomb_placed_at_y)):
                current_check_y = bomb_placed_at_y + i * step
                if self.map_manager.is_solid_wall_at(bomb_placed_at_x, current_check_y):
                    blocked = True; break
                node_between = self._get_node_at_coords(bomb_placed_at_x, current_check_y)
                if node_between and node_between.is_destructible_box():
                    blocked = True; break
            if not blocked: return True
        return False

    def is_tile_dangerous(self, tile_x, tile_y, future_seconds=0.3):
        tile_rect = pygame.Rect(tile_x * settings.TILE_SIZE, tile_y * settings.TILE_SIZE, settings.TILE_SIZE, settings.TILE_SIZE)
        for exp_sprite in self.game.explosions_group:
            if exp_sprite.rect.colliderect(tile_rect):
                return True
        for bomb in self.game.bombs_group:
            if bomb.exploded: continue
            time_to_explosion_ms = (bomb.spawn_time + bomb.timer) - pygame.time.get_ticks()
            if 0 < time_to_explosion_ms < future_seconds * 1000:
                range_to_check = bomb.placed_by_player.bomb_range if hasattr(bomb.placed_by_player, 'bomb_range') else 1
                if self._is_tile_in_hypothetical_blast(tile_x, tile_y, bomb.current_tile_x, bomb.current_tile_y, range_to_check):
                    return True
        return False

    def find_safe_tiles_nearby_for_retreat(self, from_tile_coords, bomb_just_placed_at_coords, bomb_range, max_depth=6):
        ai_log(f"    [RETREAT_FINDER] find_safe_tiles_nearby_for_retreat: from_tile={from_tile_coords}, bomb_at={bomb_just_placed_at_coords}, range={bomb_range}, max_depth={max_depth}")
        q = deque([(from_tile_coords, [from_tile_coords], 0)])
        visited = {from_tile_coords}
        safe_retreat_spots = []
        nodes_processed_count = 0
        max_nodes_to_log_details_retreat = 25

        while q:
            nodes_processed_count += 1
            (curr_x, curr_y), path, depth = q.popleft()

            if depth > max_depth:
                if nodes_processed_count <= max_nodes_to_log_details_retreat:
                    ai_log(f"      [RETREAT_FINDER] BFS: ({curr_x},{curr_y}) depth {depth} > max_depth. Skipping path: {path}")
                continue

            is_safe_from_this_bomb = not self._is_tile_in_hypothetical_blast(curr_x, curr_y, bomb_just_placed_at_coords[0], bomb_just_placed_at_coords[1], bomb_range)
            is_safe_from_other_dangers = not self.is_tile_dangerous(curr_x, curr_y, future_seconds=settings.AI_RETREAT_SPOT_OTHER_DANGER_FUTURE_SECONDS)

            if nodes_processed_count <= max_nodes_to_log_details_retreat:
                ai_log(f"      [RETREAT_FINDER] BFS: Processing ({curr_x},{curr_y}), depth {depth}. Path: {path}. SafeFromThisBomb: {is_safe_from_this_bomb}, SafeFromOthers: {is_safe_from_other_dangers}")

            if is_safe_from_this_bomb and is_safe_from_other_dangers:
                ai_log(f"        [RETREAT_FINDER] Found SAFE spot: ({curr_x},{curr_y}) with path_len {len(path)-1}")
                safe_retreat_spots.append({'coords': (curr_x, curr_y), 'path_len': len(path) -1 })
                if len(safe_retreat_spots) >= 10:
                    ai_log(f"        [RETREAT_FINDER] Reached 10 safe spots. Breaking.")
                    break

            if depth < max_depth:
                shuffled_directions = list(DIRECTIONS.values()); random.shuffle(shuffled_directions)
                for dx, dy in shuffled_directions:
                    next_x, next_y = curr_x + dx, curr_y + dy
                    if (next_x, next_y) not in visited:
                        node = self._get_node_at_coords(next_x, next_y)
                        if node and node.is_empty_for_direct_movement():
                            if not self.is_tile_dangerous(next_x, next_y, future_seconds=0.2):
                                visited.add((next_x, next_y))
                                q.append(((next_x, next_y), path + [(next_x, next_y)], depth + 1))

        ai_log(f"    [RETREAT_FINDER] find_safe_tiles_nearby_for_retreat finished. Found spots: {safe_retreat_spots}")
        if safe_retreat_spots:
            safe_retreat_spots.sort(key=lambda x: x['path_len'])
            return [spot['coords'] for spot in safe_retreat_spots]
        return []

    def can_place_bomb_and_retreat(self, bomb_placement_coords):
        ai_log(f"    [AI_BOMB_DECISION_HELPER] can_place_bomb_and_retreat called for: {bomb_placement_coords}")
        if self.is_tile_dangerous(bomb_placement_coords[0], bomb_placement_coords[1], future_seconds=0.1):
            ai_log(f"      [AI_BOMB_DECISION_HELPER] Bomb spot {bomb_placement_coords} is ALREADY dangerous. Returning False.")
            return False, None

        bomb_range_to_use = self.ai_player.bomb_range
        ai_log(f"      [AI_BOMB_DECISION_HELPER] AI bomb_range for this check: {bomb_range_to_use}")
        retreat_spots = self.find_safe_tiles_nearby_for_retreat(bomb_placement_coords, bomb_placement_coords, bomb_range_to_use)
        ai_log(f"      [AI_BOMB_DECISION_HELPER] find_safe_tiles_nearby_for_retreat for spot {bomb_placement_coords} (range {bomb_range_to_use}) found: {retreat_spots}")

        if retreat_spots:
            best_retreat_spot = retreat_spots[0]
            path_to_retreat = self.bfs_find_direct_movement_path(bomb_placement_coords, best_retreat_spot, max_depth=7)
            if path_to_retreat and len(path_to_retreat) > 1 :
                ai_log(f"      [AI_BOMB_DECISION_HELPER] Can bomb at {bomb_placement_coords}, best retreat to {best_retreat_spot} (path: {path_to_retreat}). Returning True.")
                return True, best_retreat_spot
            else:
                ai_log(f"      [AI_BOMB_DECISION_HELPER] Can bomb at {bomb_placement_coords}, found retreat spot {best_retreat_spot}, BUT no valid BFS path to it. Returning False.")
                return False, None
        else:
            ai_log(f"      [AI_BOMB_DECISION_HELPER] Cannot bomb at {bomb_placement_coords}, no safe retreat found by find_safe_tiles_nearby_for_retreat. Returning False.")
            return False, None

    def astar_find_path(self, start_coords, target_coords):
        ai_log(f"[AI_ASTAR] Planning path from {start_coords} to {target_coords}...")
        start_node = self._get_node_at_coords(start_coords[0], start_coords[1])
        target_node = self._get_node_at_coords(target_coords[0], target_coords[1])
        if not start_node or not target_node:
            ai_log(f"[AI_ASTAR_ERROR] Invalid start ({start_node}) or target ({target_node}) node."); return []

        open_set = []; closed_set = set(); open_set_dict = {}
        start_node.g_cost = 0
        start_node.h_cost = abs(start_node.x - target_node.x) + abs(start_node.y - target_node.y)
        start_node.parent = None
        heapq.heappush(open_set, (start_node.get_f_cost(), start_node.h_cost, start_node))
        open_set_dict[(start_node.x, start_node.y)] = start_node
        path_found = False; final_node = None

        while open_set:
            _, _, current_node = heapq.heappop(open_set)
            open_set_dict.pop((current_node.x, current_node.y), None)
            if current_node == target_node:
                final_node = current_node; path_found = True; break
            if (current_node.x, current_node.y) in closed_set: continue
            closed_set.add((current_node.x, current_node.y))

            for neighbor_node_template in self._get_node_neighbors(current_node, for_astar_planning=True):
                if (neighbor_node_template.x, neighbor_node_template.y) in closed_set: continue
                move_cost_to_neighbor = neighbor_node_template.get_astar_move_cost_to_here()
                tentative_g_cost = current_node.g_cost + move_cost_to_neighbor
                neighbor_node = open_set_dict.get((neighbor_node_template.x, neighbor_node_template.y), neighbor_node_template)
                if tentative_g_cost < neighbor_node.g_cost:
                    neighbor_node.parent = current_node
                    neighbor_node.g_cost = tentative_g_cost
                    neighbor_node.h_cost = abs(neighbor_node.x - target_node.x) + abs(neighbor_node.y - target_node.y)
                    heapq.heappush(open_set, (neighbor_node.get_f_cost(), neighbor_node.h_cost, neighbor_node))
                    open_set_dict[(neighbor_node.x, neighbor_node.y)] = neighbor_node

        path = []
        if path_found and final_node:
            temp = final_node
            while temp: path.append(temp); temp = temp.parent
            path.reverse()
            ai_log(f"[AI_ASTAR_SUCCESS] Path found ({len(path)} segments). Example segment: {path[0] if path else 'N/A'}")
        else: ai_log(f"[AI_ASTAR_FAIL] No path found from {start_coords} to {target_coords}.")
        return path

    def bfs_find_direct_movement_path(self, start_coords, target_coords, max_depth=15, avoid_specific_tile=None):
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
                       not self.is_tile_dangerous(next_x, next_y, future_seconds=0.15):
                        visited.add(next_coords)
                        q.append((next_coords, path + [next_coords]))
        return []


    def _find_optimal_bombing_and_retreat_spot(self, wall_to_bomb_node: TileNode, ai_current_tile):
        ai_log(f"    [OPTIMAL_BOMB_SPOT_FINDER] For wall {wall_to_bomb_node} from AI at {ai_current_tile}")
        candidate_placements = []
        for dx_wall_offset, dy_wall_offset in DIRECTIONS.values():
            bomb_spot_x = wall_to_bomb_node.x + dx_wall_offset
            bomb_spot_y = wall_to_bomb_node.y + dy_wall_offset
            bomb_spot_coords = (bomb_spot_x, bomb_spot_y)
            bomb_spot_node = self._get_node_at_coords(bomb_spot_x, bomb_spot_y)
            if not (bomb_spot_node and bomb_spot_node.is_empty_for_direct_movement()): continue

            path_to_bomb_spot = []
            is_already_at_spot = (ai_current_tile == bomb_spot_coords)
            if is_already_at_spot: path_to_bomb_spot = [ai_current_tile]
            else: path_to_bomb_spot = self.bfs_find_direct_movement_path(ai_current_tile, bomb_spot_coords, max_depth=10)

            if not path_to_bomb_spot: continue

            can_bomb, retreat_spot_coords = self.can_place_bomb_and_retreat(bomb_spot_coords)
            if can_bomb and retreat_spot_coords:
                candidate_placements.append({
                    'bomb_spot': bomb_spot_coords,
                    'retreat_spot': retreat_spot_coords,
                    'path_to_bomb_spot_len': len(path_to_bomb_spot) -1
                })
                ai_log(f"      [OPTIMAL_BOMB_SPOT_FINDER] Candidate: Bomb at {bomb_spot_coords}, retreat to {retreat_spot_coords}, path_len_to_bomb_spot: {len(path_to_bomb_spot)-1}")

        if not candidate_placements:
            ai_log(f"    [OPTIMAL_BOMB_SPOT_FINDER] No valid bombing setup found for wall {wall_to_bomb_node}.")
            return None, None

        candidate_placements.sort(key=lambda p: p['path_to_bomb_spot_len'])
        best_setup = candidate_placements[0]
        ai_log(f"    [OPTIMAL_BOMB_SPOT_FINDER] Chosen optimal bombing setup: {best_setup}")
        return best_setup['bomb_spot'], best_setup['retreat_spot']

    def is_bomb_still_active(self, bomb_placed_timestamp):
        if bomb_placed_timestamp == 0: return False
        elapsed_time = pygame.time.get_ticks() - bomb_placed_timestamp
        return elapsed_time < (settings.BOMB_TIMER + settings.EXPLOSION_DURATION + 200)

    def is_path_to_player_initial_spawn_clear(self):
        if not self.player_initial_spawn_tile:
            ai_log("[PATH_CLEAR_CHECK] Player initial spawn tile not set.")
            return False
        ai_tile = self._get_ai_current_tile()
        if not ai_tile:
            ai_log("[PATH_CLEAR_CHECK] AI current tile not available.")
            return False

        if self.astar_planned_path and \
           self.astar_planned_path[-1].x == self.player_initial_spawn_tile[0] and \
           self.astar_planned_path[-1].y == self.player_initial_spawn_tile[1] and \
           self.astar_path_current_segment_index < len(self.astar_planned_path):
            path_segment_clear = True
            for i in range(self.astar_path_current_segment_index, len(self.astar_planned_path)):
                node_in_path = self.astar_planned_path[i]
                current_node_on_map = self._get_node_at_coords(node_in_path.x, node_in_path.y)
                if not current_node_on_map or current_node_on_map.is_destructible_box():
                    ai_log(f"[PATH_CLEAR_CHECK] A* path segment {node_in_path} is blocked by destructible or invalid.")
                    path_segment_clear = False; break
            if path_segment_clear:
                ai_log("[PATH_CLEAR_CHECK] Remaining A* path to player spawn is clear of destructibles.")
                self.path_to_player_initial_spawn_clear = True; return True

        direct_path_tuples = self.bfs_find_direct_movement_path(ai_tile, self.player_initial_spawn_tile, max_depth=float('inf'))
        if direct_path_tuples:
             ai_log("[PATH_CLEAR_CHECK] Direct BFS path to player spawn is clear.")
             self.path_to_player_initial_spawn_clear = True; return True

        ai_log("[PATH_CLEAR_CHECK] No clear path (A* or BFS) to player spawn found.")
        self.path_to_player_initial_spawn_clear = False; return False

    def set_current_movement_sub_path(self, path_tuples):
        if path_tuples and len(path_tuples) >= 1:
            self.current_movement_sub_path = path_tuples
            self.current_movement_sub_path_index = 0
            if len(path_tuples) == 1 and path_tuples[0] == self._get_ai_current_tile():
                 ai_log(f"    Set sub-path of length 1 (AI already at target): {self.current_movement_sub_path}")
            else:
                 ai_log(f"    Set new movement sub-path: {self.current_movement_sub_path}")
        else:
            self.current_movement_sub_path = []
            self.current_movement_sub_path_index = 0
            ai_log("    Cleared sub-path (attempted to set empty or invalid path_tuples).")

    def execute_next_move_on_sub_path(self, ai_current_tile):
        if not self.current_movement_sub_path: return True

        if ai_current_tile == self.current_movement_sub_path[-1]:
            ai_log(f"    Sub-path target {self.current_movement_sub_path[-1]} reached. Path: {self.current_movement_sub_path}. AI at: {ai_current_tile}")
            self.movement_history.append(ai_current_tile) # 記錄到達目標點
            self.current_movement_sub_path = []
            self.current_movement_sub_path_index = 0
            self.ai_player.is_moving = False
            return True

        if self.current_movement_sub_path_index >= len(self.current_movement_sub_path):
            ai_log(f"[AI_MOVE_SUB_PATH_ERROR] Index out of bounds. Path: {self.current_movement_sub_path}, Index: {self.current_movement_sub_path_index}. Clearing.")
            self.current_movement_sub_path = []; self.current_movement_sub_path_index = 0; return True

        expected_current_sub_path_tile = self.current_movement_sub_path[self.current_movement_sub_path_index]
        if ai_current_tile != expected_current_sub_path_tile:
            ai_log(f"[AI_MOVE_SUB_PATH_WARN] AI at {ai_current_tile} but sub-path expected {expected_current_sub_path_tile} at index {self.current_movement_sub_path_index}. Current sub_path: {self.current_movement_sub_path}. Resetting sub-path.")
            self.current_movement_sub_path = []; self.current_movement_sub_path_index = 0; return True

        if self.current_movement_sub_path_index + 1 >= len(self.current_movement_sub_path):
             ai_log(f"[AI_MOVE_SUB_PATH_ERROR] Already at or past the end of sub-path logic error. Path: {self.current_movement_sub_path}, Index: {self.current_movement_sub_path_index}. Clearing.")
             self.current_movement_sub_path = []; self.current_movement_sub_path_index = 0; return True

        next_target_tile_in_sub_path = self.current_movement_sub_path[self.current_movement_sub_path_index + 1]
        dx = next_target_tile_in_sub_path[0] - ai_current_tile[0]
        dy = next_target_tile_in_sub_path[1] - ai_current_tile[1]

        if not (abs(dx) <= 1 and abs(dy) <= 1 and (dx != 0 or dy != 0) and (dx == 0 or dy == 0)):
            ai_log(f"[AI_MOVE_SUB_PATH_ERROR] Invalid step in sub-path from {ai_current_tile} to {next_target_tile_in_sub_path}. Dx={dx}, Dy={dy}. Path: {self.current_movement_sub_path}. Clearing.")
            self.current_movement_sub_path = []; self.current_movement_sub_path_index = 0; return True

        moved = self.ai_player.attempt_move_to_tile(dx, dy)
        if moved:
            moved_to_tile = (self.ai_player.tile_x, self.ai_player.tile_y) # Get actual new tile
            self.movement_history.append(moved_to_tile) # 記錄移動歷史
            ai_log(f"    Sub-path: Moved from {ai_current_tile} to {moved_to_tile}. New index: {self.current_movement_sub_path_index + 1}")
            self.current_movement_sub_path_index += 1
            if self.current_movement_sub_path_index == len(self.current_movement_sub_path) -1:
                ai_log(f"    Sub-path to {moved_to_tile} effectively completed by this move (AI is now on the target tile).")
            return False
        else:
            ai_log(f"    Sub-path Move from {ai_current_tile} to {next_target_tile_in_sub_path} FAILED (blocked). Path: {self.current_movement_sub_path}. Clearing sub-path.")
            self.current_movement_sub_path = []; self.current_movement_sub_path_index = 0; return True

    def update(self):
        current_time = pygame.time.get_ticks()
        ai_current_tile = self._get_ai_current_tile()

        if not ai_current_tile or not self.ai_player or not self.ai_player.is_alive:
            if self.current_state != AI_STATE_DEAD: self.change_state(AI_STATE_DEAD)
            return

        # 保險機制：重置 ai_just_placed_bomb 標誌
        if self.ai_just_placed_bomb and self.last_bomb_placed_time > 0:
            time_since_bomb_placed = current_time - self.last_bomb_placed_time
            bomb_clear_timeout = settings.BOMB_TIMER + settings.EXPLOSION_DURATION + 1000 # 1秒緩衝
            if time_since_bomb_placed > bomb_clear_timeout:
                ai_log(f"[AI_BOMB_FLAG_RESET_TIMEOUT] ai_just_placed_bomb was True for too long ({time_since_bomb_placed}ms). Forcing reset.")
                self.ai_just_placed_bomb = False
                self.last_bomb_placed_time = 0

        current_decision_tile = ai_current_tile

        if self.is_tile_dangerous(ai_current_tile[0], ai_current_tile[1], future_seconds=0.4):
            if self.current_state != AI_STATE_EVADING_DANGER:
                ai_log(f"[AI_DANGER_IMMEDIATE] AI at {ai_current_tile} is in danger! Switching to EVADING_DANGER.")
                self.change_state(AI_STATE_EVADING_DANGER)
                self.last_decision_time = current_time - self.ai_decision_interval -1

        if current_time - self.last_decision_time >= self.ai_decision_interval or \
           self.current_state == AI_STATE_EVADING_DANGER:

            if self.current_state != AI_STATE_EVADING_DANGER :
                self.last_decision_time = current_time

            # 單點卡住檢測
            if not self.current_movement_sub_path and \
               not (self.current_state == AI_STATE_TACTICAL_RETREAT_AND_WAIT and self.ai_just_placed_bomb):
                if self.last_known_tile == current_decision_tile:
                    self.decision_cycle_stuck_counter += 1
                else:
                    self.decision_cycle_stuck_counter = 0
            else:
                self.decision_cycle_stuck_counter = 0
            self.last_known_tile = current_decision_tile # 更新 last_known_tile

            # 振盪檢測 (A-B-A-B)
            # is_oscillating = False
            if len(self.movement_history) == self.movement_history.maxlen:
                if self.movement_history[0] == self.movement_history[2] and \
                   self.movement_history[1] == self.movement_history[3] and \
                   self.movement_history[0] != self.movement_history[1] and \
                   ai_current_tile == self.movement_history[3]:
                    self.oscillation_stuck_counter += 1
                    # is_oscillating = True
                    ai_log(f"[AI_OSCILLATION_DETECT] Oscillation detected. Count: {self.oscillation_stuck_counter}. History: {list(self.movement_history)}")
                else:
                    self.oscillation_stuck_counter = 0
            else:
                self.oscillation_stuck_counter = 0

            # 卡住或振盪達到閾值，則強制重新規劃
            stuck_by_single_tile = self.decision_cycle_stuck_counter >= self.stuck_threshold_decision_cycles
            stuck_by_oscillation = self.oscillation_stuck_counter >= getattr(settings, "AI_OSCILLATION_STUCK_THRESHOLD", 3)

            if stuck_by_single_tile or stuck_by_oscillation:
                if stuck_by_oscillation:
                     ai_log(f"[AI_STUCK_DETECTED] AI stuck by oscillation at {current_decision_tile}. Forcing re-plan.")
                else: # stuck_by_single_tile
                     ai_log(f"[AI_STUCK_DETECTED] AI stuck at {current_decision_tile} for {self.decision_cycle_stuck_counter} decision cycles. Forcing re-plan.")
                self.decision_cycle_stuck_counter = 0
                self.oscillation_stuck_counter = 0
                self.movement_history.clear()
                self.current_movement_sub_path = []
                self.current_movement_sub_path_index = 0
                self.change_state(AI_STATE_PLANNING_PATH_TO_PLAYER)
                # 立即處理新狀態
                if self.current_state == AI_STATE_PLANNING_PATH_TO_PLAYER: self.handle_planning_path_to_player_state(ai_current_tile)
                return # 避免後續的移動執行干擾

            # 狀態處理
            if self.current_state == AI_STATE_EVADING_DANGER: self.handle_evading_danger_state(ai_current_tile)
            elif self.current_state == AI_STATE_PLANNING_PATH_TO_PLAYER: self.handle_planning_path_to_player_state(ai_current_tile)
            elif self.current_state == AI_STATE_EXECUTING_PATH_CLEARANCE: self.handle_executing_path_clearance_state(ai_current_tile)
            elif self.current_state == AI_STATE_TACTICAL_RETREAT_AND_WAIT: self.handle_tactical_retreat_and_wait_state(ai_current_tile)
            elif self.current_state == AI_STATE_ENGAGING_PLAYER: self.handle_engaging_player_state(ai_current_tile)
            elif self.current_state == AI_STATE_CLOSE_QUARTERS_COMBAT: self.handle_close_quarters_combat_state(ai_current_tile)

        if self.ai_player.action_timer <= 0:
            sub_path_finished_or_failed = False
            if self.current_movement_sub_path:
                sub_path_finished_or_failed = self.execute_next_move_on_sub_path(ai_current_tile)
            if sub_path_finished_or_failed:
                self.last_decision_time = pygame.time.get_ticks() - self.ai_decision_interval -1
            if not self.current_movement_sub_path:
                self.ai_player.is_moving = False

        if AI_DEBUG_MODE and hasattr(self.game, 'screen') and self.game.screen:
             self.debug_draw_path(self.game.screen)

    def handle_planning_path_to_player_state(self, ai_current_tile):
        ai_log(f"[AI_HANDLER] PLANNING_PATH_TO_PLAYER at {ai_current_tile}")
        if not self.player_initial_spawn_tile:
            self.player_initial_spawn_tile = self._get_human_player_current_tile() or (1,1)
            ai_log(f"[AI_ERROR] Player initial spawn tile was not set! Fallback to: {self.player_initial_spawn_tile}")

        self.astar_planned_path = self.astar_find_path(ai_current_tile, self.player_initial_spawn_tile)
        if self.astar_planned_path:
            self.astar_path_current_segment_index = 0
            self.path_to_player_initial_spawn_clear = not any(node.is_destructible_box() for node in self.astar_planned_path)
            if self.path_to_player_initial_spawn_clear:
                human_pos = self._get_human_player_current_tile()
                is_very_close_to_human = False
                if human_pos:
                    dist_to_human = abs(ai_current_tile[0] - human_pos[0]) + abs(ai_current_tile[1] - human_pos[1])
                    if dist_to_human <= settings.AI_ENGAGE_MIN_DIST_TO_PLAYER_FOR_DIRECT_PATH:
                        is_very_close_to_human = True
                if is_very_close_to_human :
                    ai_log("  A* Path to player initial spawn is ALREADY CLEAR, and AI is very close to human. Switching to CLOSE_QUARTERS_COMBAT.")
                    self.change_state(AI_STATE_CLOSE_QUARTERS_COMBAT)
                else:
                    ai_log("  A* Path to player initial spawn is ALREADY CLEAR. Switching to ENGAGING_PLAYER.")
                    self.change_state(AI_STATE_ENGAGING_PLAYER)
            else:
                ai_log(f"  New A* path set, needs clearing. First segment: {self.astar_planned_path[0] if self.astar_planned_path else 'None'}")
                self.change_state(AI_STATE_EXECUTING_PATH_CLEARANCE)
        else:
            ai_log(f"  A* failed to find path from {ai_current_tile} to {self.player_initial_spawn_tile}. AI will wait.")

    def handle_executing_path_clearance_state(self, ai_current_tile):
        ai_log(f"  [AI_HANDLER] EXECUTING_PATH_CLEARANCE at {ai_current_tile}. Target A* node: {self.astar_planned_path[self.astar_path_current_segment_index] if self.astar_planned_path and self.astar_path_current_segment_index < len(self.astar_planned_path) else 'A* Path End/Invalid'}")
        if self.ai_just_placed_bomb:
            ai_log("    Waiting for previously placed bomb to clear before continuing path clearance.")
            return

        if not self.astar_planned_path or self.astar_path_current_segment_index >= len(self.astar_planned_path):
            ai_log("    A* path finished or invalid in EXECUTING_PATH_CLEARANCE.")
            if self.is_path_to_player_initial_spawn_clear():
                ai_log("      Path to player spawn confirmed clear after A* processing!")
                self.change_state(AI_STATE_ENGAGING_PLAYER)
            else:
                ai_log("      Path still not clear or A* path was incomplete. Re-planning.")
                self.change_state(AI_STATE_PLANNING_PATH_TO_PLAYER)
            return

        if self.current_movement_sub_path:
            ai_log("    Busy with sub-path execution. Waiting for it to complete.")
            return

        current_astar_target_node = self.astar_planned_path[self.astar_path_current_segment_index]
        ai_log(f"    Evaluating A* segment idx {self.astar_path_current_segment_index}: {current_astar_target_node} from AI tile {ai_current_tile}")

        if ai_current_tile == (current_astar_target_node.x, current_astar_target_node.y):
            ai_log(f"      AI is AT A* target node {current_astar_target_node}. Advancing A* path index.")
            self.astar_path_current_segment_index += 1
            self.last_decision_time = pygame.time.get_ticks() - self.ai_decision_interval -1
            return

        if current_astar_target_node.is_empty_for_direct_movement():
            ai_log(f"      A* segment is EMPTY: {current_astar_target_node}. Setting sub-path to move.")
            path_tuples = self.bfs_find_direct_movement_path(ai_current_tile, (current_astar_target_node.x, current_astar_target_node.y), max_depth=7)
            if path_tuples: self.set_current_movement_sub_path(path_tuples)
            else:
                ai_log(f"      Cannot BFS to A* empty node {current_astar_target_node}. Obstruction or danger? Re-planning A* path.")
                self.change_state(AI_STATE_PLANNING_PATH_TO_PLAYER)
            return

        elif current_astar_target_node.is_destructible_box():
            self.target_destructible_wall_node_in_astar = current_astar_target_node
            ai_log(f"      A* segment is DESTRUCTIBLE_BOX: {self.target_destructible_wall_node_in_astar}. Finding bombing spot.")
            bomb_spot_coord, retreat_spot_coord = self._find_optimal_bombing_and_retreat_spot(self.target_destructible_wall_node_in_astar, ai_current_tile)

            if bomb_spot_coord and retreat_spot_coord:
                self.chosen_bombing_spot_coords = bomb_spot_coord
                self.chosen_retreat_spot_coords = retreat_spot_coord
                ai_log(f"        Optimal bombing spot for wall: {self.chosen_bombing_spot_coords}, retreat to: {self.chosen_retreat_spot_coords}")
                if ai_current_tile == self.chosen_bombing_spot_coords:
                    ai_log(f"        AI is ALREADY at bombing spot {self.chosen_bombing_spot_coords}. Attempting to place bomb for wall.")
                    if self.ai_player.bombs_placed_count < self.ai_player.max_bombs:
                        self.ai_player.place_bomb()
                        retreat_path_tuples = self.bfs_find_direct_movement_path(ai_current_tile, self.chosen_retreat_spot_coords, max_depth=7)
                        if retreat_path_tuples: self.set_current_movement_sub_path(retreat_path_tuples)
                        else: ai_log(f"        [CRITICAL_BOMB_PLACE_WALL] Placed bomb for wall but cannot find path to retreat spot {self.chosen_retreat_spot_coords}! Emergency replan.")
                        self.change_state(AI_STATE_TACTICAL_RETREAT_AND_WAIT)
                    else:
                        ai_log("        AI at bombing spot for wall, but no bombs available. Re-planning.")
                        self.change_state(AI_STATE_PLANNING_PATH_TO_PLAYER)
                else:
                    path_to_bomb_spot_for_wall = self.bfs_find_direct_movement_path(ai_current_tile, self.chosen_bombing_spot_coords, max_depth=7)
                    if path_to_bomb_spot_for_wall:
                        self.set_current_movement_sub_path(path_to_bomb_spot_for_wall)
                        ai_log(f"        Setting sub-path to chosen bombing spot {self.chosen_bombing_spot_coords} for wall.")
                    else:
                        ai_log(f"        Cannot BFS to chosen bombing spot {self.chosen_bombing_spot_coords} for wall. Re-planning A*.")
                        self.target_destructible_wall_node_in_astar = None
                        self.change_state(AI_STATE_PLANNING_PATH_TO_PLAYER)
            else:
                ai_log(f"      Cannot find safe bombing/retreat for wall {self.target_destructible_wall_node_in_astar}. Re-planning A*.")
                self.target_destructible_wall_node_in_astar = None
                self.change_state(AI_STATE_PLANNING_PATH_TO_PLAYER)
            return
        else:
            ai_log(f"[AI_ERROR] A* path segment {current_astar_target_node} is invalid (not '.', not 'D'). Re-planning.")
            self.change_state(AI_STATE_PLANNING_PATH_TO_PLAYER)
            return

    def handle_tactical_retreat_and_wait_state(self, ai_current_tile):
        ai_log(f"  [AI_HANDLER] TACTICAL_RETREAT_AND_WAIT at {ai_current_tile}. Target retreat: {self.chosen_retreat_spot_coords}")
        if self.current_movement_sub_path:
            ai_log("    Still executing retreat sub-path.")
            return

        if ai_current_tile == self.chosen_retreat_spot_coords:
            ai_log(f"    AI at chosen retreat spot {self.chosen_retreat_spot_coords}. Waiting for bomb (placed at {self.last_bomb_placed_time}) to clear.")
            if not self.is_bomb_still_active(self.last_bomb_placed_time):
                ai_log(f"      Bomb (placed at {self.last_bomb_placed_time}) has cleared.")
                self.ai_just_placed_bomb = False

                wall_was_the_target = bool(self.target_destructible_wall_node_in_astar)
                if wall_was_the_target:
                    updated_wall_node = self._get_node_at_coords(self.target_destructible_wall_node_in_astar.x, self.target_destructible_wall_node_in_astar.y)
                    if updated_wall_node and updated_wall_node.is_empty_for_direct_movement():
                        ai_log(f"        Target wall {self.target_destructible_wall_node_in_astar} confirmed destroyed. Advancing A* index.")
                        self.astar_path_current_segment_index += 1
                    else:
                        ai_log(f"        Target wall {self.target_destructible_wall_node_in_astar} still exists or check failed. A* path will re-evaluate or re-plan.")
                    self.target_destructible_wall_node_in_astar = None

                self.chosen_bombing_spot_coords = None
                self.chosen_retreat_spot_coords = None

                if wall_was_the_target:
                    if self.is_path_to_player_initial_spawn_clear():
                        ai_log("        Path to player spawn is now clear after bombing wall.")
                        self.change_state(AI_STATE_ENGAGING_PLAYER)
                    elif self.astar_planned_path and self.astar_path_current_segment_index < len(self.astar_planned_path):
                        ai_log("        Path not fully clear, continuing A* path execution.")
                        self.change_state(AI_STATE_EXECUTING_PATH_CLEARANCE)
                    else:
                        ai_log("        A* path finished or became invalid after bombing wall. Re-planning.")
                        self.change_state(AI_STATE_PLANNING_PATH_TO_PLAYER)
                else:
                    ai_log("        Bomb placed for engagement has cleared. Re-evaluating engagement.")
                    self.change_state(AI_STATE_ENGAGING_PLAYER)
            else:
                ai_log(f"      Bomb still active. Waiting at {self.chosen_retreat_spot_coords}.")
        else:
            ai_log(f"    Not at chosen retreat spot {self.chosen_retreat_spot_coords} AND no sub-path. Trying to re-path to retreat spot.")
            if self.chosen_retreat_spot_coords:
                retreat_path_tuples = self.bfs_find_direct_movement_path(ai_current_tile, self.chosen_retreat_spot_coords, max_depth=7)
                if retreat_path_tuples: self.set_current_movement_sub_path(retreat_path_tuples)
                else:
                    ai_log(f"      [CRITICAL_RETREAT_FAIL] Cannot BFS to {self.chosen_retreat_spot_coords}! Bomb placed but cannot reach safety. Forcing re-plan / evasion.")
                    self.ai_just_placed_bomb = False
                    self.change_state(AI_STATE_EVADING_DANGER)
            else:
                 ai_log(f"    [CRITICAL_RETREAT_ERROR] No chosen_retreat_spot defined. Re-planning.")
                 self.ai_just_placed_bomb = False
                 self.change_state(AI_STATE_PLANNING_PATH_TO_PLAYER)

    def handle_engaging_player_state(self, ai_current_tile):
        ai_log(f"[AI_HANDLER] ENGAGING_PLAYER at {ai_current_tile}")
        ai_log(f"  ENGAGE_INFO: AI Bombs: {self.ai_player.bombs_placed_count}/{self.ai_player.max_bombs}, Range: {self.ai_player.bomb_range}")
        self.path_to_player_initial_spawn_clear = True

        human_pos = self._get_human_player_current_tile()
        if not human_pos:
            ai_log("  ENGAGE: Human player not found or not alive. Switching to PLANNING.")
            self.change_state(AI_STATE_PLANNING_PATH_TO_PLAYER)
            return

        if not self.has_made_contact_with_player:
            dist_to_human_for_contact = abs(ai_current_tile[0] - human_pos[0]) + abs(ai_current_tile[1] - human_pos[1])
            if dist_to_human_for_contact <= self.player_contact_distance_threshold:
                ai_log(f"  [AI_CONTACT] First contact made with player at distance {dist_to_human_for_contact}.")
                self.has_made_contact_with_player = True

        dist_to_human = abs(ai_current_tile[0] - human_pos[0]) + abs(ai_current_tile[1] - human_pos[1])
        if dist_to_human <= settings.AI_ENGAGE_MIN_DIST_TO_PLAYER_FOR_DIRECT_PATH:
            ai_log(f"  ENGAGE: AI at {ai_current_tile} is very close (dist: {dist_to_human}) to human at {human_pos}. Switching to CLOSE_QUARTERS_COMBAT.")
            self.change_state(AI_STATE_CLOSE_QUARTERS_COMBAT)
            return

        best_bombing_action = None
        can_attempt_bombing_check = not self.ai_just_placed_bomb and self.ai_player.bombs_placed_count < self.ai_player.max_bombs
        ai_log(f"  ENGAGE_BOMB_CHECK: Condition (not ai_just_placed_bomb AND bombs_available): {can_attempt_bombing_check} (ai_just_placed_bomb={self.ai_just_placed_bomb}, bombs_placed={self.ai_player.bombs_placed_count}, max_bombs={self.ai_player.max_bombs})")

        if can_attempt_bombing_check:
            potential_bombing_spots = [ai_current_tile]
            for dx, dy in DIRECTIONS.values():
                adj_x, adj_y = ai_current_tile[0] + dx, ai_current_tile[1] + dy
                adj_node = self._get_node_at_coords(adj_x, adj_y)
                if adj_node and adj_node.is_empty_for_direct_movement() and not self.is_tile_dangerous(adj_x, adj_y, 0.1):
                    potential_bombing_spots.append((adj_x, adj_y))
            ai_log(f"    ENGAGE: Potential bombing spots to check: {potential_bombing_spots}")

            for spot_to_bomb_from in potential_bombing_spots:
                dist_human_to_this_bomb_spot = abs(spot_to_bomb_from[0] - human_pos[0]) + abs(spot_to_bomb_from[1] - human_pos[1])
                if dist_human_to_this_bomb_spot <= self.ai_player.bomb_range:
                    ai_log(f"      ENGAGE: Checking bombing from {spot_to_bomb_from} (dist to human: {dist_human_to_this_bomb_spot}, AI range: {self.ai_player.bomb_range})")
                    is_player_in_blast = self._is_tile_in_hypothetical_blast(human_pos[0], human_pos[1], spot_to_bomb_from[0], spot_to_bomb_from[1], self.ai_player.bomb_range)
                    ai_log(f"        ENGAGE: Is player {human_pos} in blast if bombed from {spot_to_bomb_from} (range {self.ai_player.bomb_range})? {is_player_in_blast}")
                    if is_player_in_blast:
                        can_bomb_at_spot, retreat_spot = self.can_place_bomb_and_retreat(spot_to_bomb_from)
                        ai_log(f"        ENGAGE_BOMB_CHECK_RESULT: can_place_bomb_and_retreat({spot_to_bomb_from}) returned: can_bomb={can_bomb_at_spot}, retreat_to={retreat_spot}")
                        if can_bomb_at_spot:
                            path_to_this_bomb_spot = [ai_current_tile] if spot_to_bomb_from == ai_current_tile else self.bfs_find_direct_movement_path(ai_current_tile, spot_to_bomb_from, max_depth=3)
                            if path_to_this_bomb_spot:
                                num_moves_to_spot = len(path_to_this_bomb_spot) -1
                                if best_bombing_action is None or num_moves_to_spot < best_bombing_action['path_to_bomb_spot_len']:
                                    best_bombing_action = {'bomb_spot': spot_to_bomb_from, 'retreat_spot': retreat_spot, 'path_to_bomb_spot_coords': path_to_this_bomb_spot, 'path_to_bomb_spot_len': num_moves_to_spot}
                                    ai_log(f"          ENGAGE: Found a candidate bombing action: {best_bombing_action}")
            if best_bombing_action:
                ai_log(f"    ENGAGE: BEST BOMBING ACTION CHOSEN: {best_bombing_action}")
                self.chosen_bombing_spot_coords = best_bombing_action['bomb_spot']
                self.chosen_retreat_spot_coords = best_bombing_action['retreat_spot']
                if ai_current_tile == self.chosen_bombing_spot_coords:
                    ai_log(f"      AI is ALREADY at best bombing spot {self.chosen_bombing_spot_coords}. Placing bomb for engagement.")
                    self.ai_player.place_bomb()
                    retreat_path_tuples = self.bfs_find_direct_movement_path(ai_current_tile, self.chosen_retreat_spot_coords, max_depth=7)
                    if retreat_path_tuples: self.set_current_movement_sub_path(retreat_path_tuples)
                    else: ai_log(f"      [CRITICAL_BOMB_PLACE_ENGAGE] Placed bomb but CANNOT find path to chosen retreat spot {self.chosen_retreat_spot_coords}!")
                    self.change_state(AI_STATE_TACTICAL_RETREAT_AND_WAIT)
                else:
                    ai_log(f"      Setting sub-path to chosen bombing spot for engagement: {best_bombing_action['path_to_bomb_spot_coords']}")
                    self.set_current_movement_sub_path(best_bombing_action['path_to_bomb_spot_coords'])
                return

        if self.ai_player.action_timer > 0:
            ai_log("  ENGAGE: AI is currently in action_timer. Waiting.")
            return
        if not self.current_movement_sub_path:
            ai_log(f"  ENGAGE: No bomb action taken & no current sub-path. Attempting to path to human at {human_pos}.")
            path_to_human = self.bfs_find_direct_movement_path(ai_current_tile, human_pos, max_depth=10, avoid_specific_tile=human_pos if dist_to_human == 0 else None)
            if path_to_human and len(path_to_human) > 1:
                self.set_current_movement_sub_path(path_to_human)
                ai_log(f"  ENGAGE: New sub-path set to human: {path_to_human}")
            elif path_to_human and len(path_to_human) == 1:
                ai_log(f"  ENGAGE: BFS path to human is trivial. Considering CQC or waiting.")
                if dist_to_human <= settings.AI_ENGAGE_MIN_DIST_TO_PLAYER_FOR_DIRECT_PATH :
                    self.change_state(AI_STATE_CLOSE_QUARTERS_COMBAT)
            else:
                ai_log(f"  ENGAGE: Cannot find direct path to human at {human_pos}. AI may wait.")

    def handle_close_quarters_combat_state(self, ai_current_tile):
        ai_log(f"[AI_HANDLER] CLOSE_QUARTERS_COMBAT at {ai_current_tile}")
        ai_log(f"  CQC_INFO: AI Bombs: {self.ai_player.bombs_placed_count}/{self.ai_player.max_bombs}, Range: {self.ai_player.bomb_range}, ai_just_placed_bomb: {self.ai_just_placed_bomb}")

        human_pos = self._get_human_player_current_tile()
        if not human_pos:
            ai_log("  CQC: Human player not found. Switching to PLANNING.")
            self.change_state(AI_STATE_PLANNING_PATH_TO_PLAYER)
            return

        dist_to_human = abs(ai_current_tile[0] - human_pos[0]) + abs(ai_current_tile[1] - human_pos[1])
        if dist_to_human > settings.AI_ENGAGE_MIN_DIST_TO_PLAYER_FOR_DIRECT_PATH:
            ai_log(f"  CQC: Human moved away (dist: {dist_to_human}). Switching back to ENGAGING_PLAYER.")
            self.change_state(AI_STATE_ENGAGING_PLAYER)
            return

        can_attempt_bombing = not self.ai_just_placed_bomb and self.ai_player.bombs_placed_count < self.ai_player.max_bombs
        if can_attempt_bombing:
            is_player_in_blast_here = self._is_tile_in_hypothetical_blast(human_pos[0], human_pos[1], ai_current_tile[0], ai_current_tile[1], self.ai_player.bomb_range)
            if is_player_in_blast_here:
                ai_log(f"  CQC: Player {human_pos} is in blast if AI bombs at current spot {ai_current_tile}.")
                can_bomb_here, retreat_spot_here = self.can_place_bomb_and_retreat(ai_current_tile)
                if can_bomb_here:
                    ai_log(f"    CQC: Found safe retreat to {retreat_spot_here}. Placing bomb at {ai_current_tile}.")
                    self.chosen_bombing_spot_coords = ai_current_tile
                    self.chosen_retreat_spot_coords = retreat_spot_here
                    self.ai_player.place_bomb()
                    retreat_path = self.bfs_find_direct_movement_path(ai_current_tile, retreat_spot_here, max_depth=7)
                    if retreat_path: self.set_current_movement_sub_path(retreat_path)
                    else: ai_log(f"    CQC: [CRITICAL] Placed bomb but no BFS path to chosen retreat {retreat_spot_here}!")
                    self.change_state(AI_STATE_TACTICAL_RETREAT_AND_WAIT)
                    return
                else:
                    if random.random() < settings.AI_CLOSE_QUARTERS_BOMB_CHANCE:
                        ai_log(f"    CQC: No perfect retreat, but attempting AGGRESSIVE bomb at {ai_current_tile} (chance: {settings.AI_CLOSE_QUARTERS_BOMB_CHANCE}).")
                        desperate_retreat_options = []
                        for dx, dy in DIRECTIONS.values():
                            next_r_x, next_r_y = ai_current_tile[0] + dx, ai_current_tile[1] + dy
                            if not self._is_tile_in_hypothetical_blast(next_r_x, next_r_y, ai_current_tile[0], ai_current_tile[1], self.ai_player.bomb_range):
                                node = self._get_node_at_coords(next_r_x, next_r_y)
                                if node and node.is_empty_for_direct_movement() and not self.is_tile_dangerous(next_r_x, next_r_y, 0.1):
                                    desperate_retreat_options.append((next_r_x, next_r_y))
                        if desperate_retreat_options:
                            self.chosen_bombing_spot_coords = ai_current_tile
                            self.chosen_retreat_spot_coords = random.choice(desperate_retreat_options)
                            ai_log(f"      CQC: Aggressive bomb! Desperate retreat to {self.chosen_retreat_spot_coords}.")
                            self.ai_player.place_bomb()
                            self.set_current_movement_sub_path([ai_current_tile, self.chosen_retreat_spot_coords])
                            self.change_state(AI_STATE_TACTICAL_RETREAT_AND_WAIT)
                            return
                        else: ai_log(f"    CQC: Aggressive bomb considered but no desperate retreat from {ai_current_tile}.")
                    else: ai_log(f"    CQC: Did not pass aggressive bomb chance.")
            else: ai_log(f"  CQC: Bombing at current spot {ai_current_tile} would not hit player {human_pos}.")
        else: ai_log(f"  CQC: Cannot attempt bombing (no bombs or ai_just_placed_bomb is True).")

        if not self.current_movement_sub_path and self.ai_player.action_timer <= 0 :
            ai_log(f"  CQC: No bomb placed, attempting to reposition from {ai_current_tile}.")
            available_reposition_spots = []
            for dx, dy in DIRECTIONS.values():
                next_x, next_y = ai_current_tile[0] + dx, ai_current_tile[1] + dy
                next_coords = (next_x, next_y)
                if next_coords == human_pos: continue
                if self.cqc_last_reposition_target and next_coords == self.cqc_last_reposition_target: # Avoid immediate back-and-forth
                     # Allow moving back if it's the *only* option or significantly better
                    pass # For now, simple skip. Can be made more complex.
                     # ai_log(f"    CQC_REPOSITION: Skipping {next_coords} as it was the last reposition target.")
                     # continue
                node = self._get_node_at_coords(next_x, next_y)
                if node and node.is_empty_for_direct_movement() and not self.is_tile_dangerous(next_x, next_y, 0.1):
                    available_reposition_spots.append(next_coords)

            best_reposition_tile = None
            if available_reposition_spots:
                # Try to pick a spot that wasn't the one AI just came from, if possible
                preferred_spots = [s for s in available_reposition_spots if s != self.cqc_last_reposition_target]
                if preferred_spots:
                    best_reposition_tile = random.choice(preferred_spots)
                elif available_reposition_spots : # Only option is to go back
                    best_reposition_tile = random.choice(available_reposition_spots)

            if best_reposition_tile:
                ai_log(f"    CQC: Repositioning to {best_reposition_tile} from options {available_reposition_spots}. Last target: {self.cqc_last_reposition_target}")
                self.set_current_movement_sub_path([ai_current_tile, best_reposition_tile])
                self.cqc_last_reposition_target = ai_current_tile # Store where AI *was* before this move
            else:
                ai_log(f"    CQC: No immediate repositioning move found from {ai_current_tile}. AI may wait.")
                self.cqc_last_reposition_target = None


    def handle_evading_danger_state(self, ai_current_tile):
        ai_log(f"[AI_HANDLER] EVADING_DANGER at {ai_current_tile}")
        if not self.is_tile_dangerous(ai_current_tile[0], ai_current_tile[1], future_seconds=settings.AI_EVASION_SAFETY_CHECK_FUTURE_SECONDS):
            ai_log(f"  EVADE: Current tile {ai_current_tile} now considered safe (check with {settings.AI_EVASION_SAFETY_CHECK_FUTURE_SECONDS}s). Deciding next state.")
            self.current_movement_sub_path = []
            if self.is_path_to_player_initial_spawn_clear(): self.change_state(AI_STATE_ENGAGING_PLAYER)
            elif self.astar_planned_path and self.astar_path_current_segment_index < len(self.astar_planned_path): self.change_state(AI_STATE_EXECUTING_PATH_CLEARANCE)
            else: self.change_state(AI_STATE_PLANNING_PATH_TO_PLAYER)
            return

        if not self.current_movement_sub_path or \
           (self.current_movement_sub_path and ai_current_tile == self.current_movement_sub_path[-1]) or \
           (self.current_movement_sub_path and self.is_tile_dangerous(self.current_movement_sub_path[-1][0], self.current_movement_sub_path[-1][1], future_seconds=0.2)):
            ai_log("  EVADE: Finding new evasion path (current is dangerous, finished, or non-existent).")
            safe_options_coords = self.find_safe_tiles_nearby_for_retreat(ai_current_tile, ai_current_tile, 0, max_depth=7) # bomb_range 0 for general danger
            best_evasion_path_coords = []
            if safe_options_coords:
                for safe_spot_coord in safe_options_coords[:3]:
                    evasion_path_tuples = self.bfs_find_direct_movement_path(ai_current_tile, safe_spot_coord, max_depth=7)
                    if evasion_path_tuples and len(evasion_path_tuples) > 1:
                        best_evasion_path_coords = evasion_path_tuples; break
            if best_evasion_path_coords:
                self.set_current_movement_sub_path(best_evasion_path_coords)
                ai_log(f"    EVADE: New evasion sub-path set: {best_evasion_path_coords}")
            else:
                ai_log("    EVADE: Cannot find any safe evasion path! AI trapped or no valid moves.")
                self.current_movement_sub_path = []
                self.ai_player.is_moving = False

    def debug_draw_path(self, surface):
        if not self.ai_player or not self.ai_player.is_alive: return
        ai_tile_now = self._get_ai_current_tile()
        if not ai_tile_now: return

        try:
            tile_size = settings.TILE_SIZE
            half_tile = tile_size // 2
            show_long_term_strategic_elements = not self.has_made_contact_with_player or \
                                                self.current_state == AI_STATE_PLANNING_PATH_TO_PLAYER or \
                                                self.current_state == AI_STATE_EXECUTING_PATH_CLEARANCE

            if show_long_term_strategic_elements and self.astar_planned_path and \
               self.astar_path_current_segment_index < len(self.astar_planned_path):
                astar_points_to_draw = [(ai_tile_now[0] * tile_size + half_tile, ai_tile_now[1] * tile_size + half_tile)]
                current_astar_target_pixel_pos = None
                for i in range(self.astar_path_current_segment_index, len(self.astar_planned_path)):
                    node = self.astar_planned_path[i]
                    px, py = node.x * tile_size + half_tile, node.y * tile_size + half_tile
                    astar_points_to_draw.append((px, py))
                    if i == self.astar_path_current_segment_index: current_astar_target_pixel_pos = (px, py)
                if len(astar_points_to_draw) > 1:
                    for i in range(len(astar_points_to_draw) - 1):
                        if i % 2 == 0 : pygame.draw.aaline(surface, (0, 180, 220, 180), astar_points_to_draw[i], astar_points_to_draw[i+1], True)
                if current_astar_target_pixel_pos:
                    pygame.draw.circle(surface, (255, 165, 0, 200), current_astar_target_pixel_pos, tile_size // 3, 3)

            if self.current_movement_sub_path and len(self.current_movement_sub_path) > 1 and \
               self.current_movement_sub_path_index < len(self.current_movement_sub_path) -1 : # Ensure there's a next step
                sub_path_points_to_draw = [(ai_tile_now[0] * tile_size + half_tile, ai_tile_now[1] * tile_size + half_tile)]
                for i in range(self.current_movement_sub_path_index + 1, len(self.current_movement_sub_path)):
                    tile_coords = self.current_movement_sub_path[i]
                    px, py = tile_coords[0] * tile_size + half_tile, tile_coords[1] * tile_size + half_tile
                    sub_path_points_to_draw.append((px,py))
                if len(sub_path_points_to_draw) > 1:
                    pygame.draw.aalines(surface, (220, 20, 180, 230), False, sub_path_points_to_draw, True)
                    next_sub_step_coords = self.current_movement_sub_path[self.current_movement_sub_path_index + 1]
                    next_px, next_py = next_sub_step_coords[0] * tile_size + half_tile, next_sub_step_coords[1] * tile_size + half_tile
                    pulse_factor = abs(pygame.time.get_ticks() % 1000 - 500) / 500
                    radius = int(tile_size // 5 + pulse_factor * (tile_size//10))
                    pygame.draw.circle(surface, (50, 255, 255, 220), (next_px, next_py), radius, 0)

            if self.chosen_retreat_spot_coords and (self.current_state == AI_STATE_TACTICAL_RETREAT_AND_WAIT or self.ai_just_placed_bomb):
                rx, ry = self.chosen_retreat_spot_coords
                rect_retreat = pygame.Rect(rx * tile_size + 4, ry * tile_size + 4, tile_size - 8, tile_size - 8)
                s_retreat = pygame.Surface((tile_size-8, tile_size-8), pygame.SRCALPHA); s_retreat.fill((135, 206, 250, 120))
                surface.blit(s_retreat, (rect_retreat.x, rect_retreat.y))
                pygame.draw.rect(surface, (70, 130, 180, 180), rect_retreat, 2)

            if self.chosen_bombing_spot_coords and \
               (self.current_state in [AI_STATE_EXECUTING_PATH_CLEARANCE, AI_STATE_ENGAGING_PLAYER, AI_STATE_CLOSE_QUARTERS_COMBAT]) and \
               ( (self.current_movement_sub_path and self.current_movement_sub_path[-1] == self.chosen_bombing_spot_coords) or \
                 ai_tile_now == self.chosen_bombing_spot_coords or self.ai_just_placed_bomb ):
                bx, by = self.chosen_bombing_spot_coords
                center_bx, center_by = bx * tile_size + half_tile, by * tile_size + half_tile
                pygame.draw.circle(surface, (255, 0, 0, 180), (center_bx, center_by), tile_size // 3, 3)
                pygame.draw.line(surface, (255,0,0,180), (center_bx - tile_size//2.5, center_by), (center_bx + tile_size//2.5, center_by), 2)
                pygame.draw.line(surface, (255,0,0,180), (center_bx, center_by - tile_size//2.5), (center_bx, center_by + tile_size//2.5), 2)

            if show_long_term_strategic_elements and self.target_destructible_wall_node_in_astar and self.current_state == AI_STATE_EXECUTING_PATH_CLEARANCE:
                wall_node = self.target_destructible_wall_node_in_astar
                wall_rect = pygame.Rect(wall_node.x * tile_size, wall_node.y * tile_size, tile_size, tile_size)
                pulse_factor_wall = abs(pygame.time.get_ticks() % 600 - 300) / 300
                alpha_wall = int(120 + pulse_factor_wall * 100)
                thickness_wall = 2 + int(pulse_factor_wall * 2)
                s_wall = pygame.Surface((tile_size, tile_size), pygame.SRCALPHA)
                pygame.draw.rect(s_wall, (255, 255, 0, alpha_wall), (0,0,tile_size,tile_size), thickness_wall)
                surface.blit(s_wall, (wall_rect.x, wall_rect.y))
        except AttributeError as e:
            if 'TILE_SIZE' in str(e) : pass
            else: ai_log(f"Debug Draw AttributeError: {e}")
        except Exception as e: ai_log(f"Error during debug_draw_path: {e}")