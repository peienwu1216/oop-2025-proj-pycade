# oop-2025-proj-pycade/core/ai_controller_base.py

import pygame
import settings
import random
from collections import deque
import heapq

AI_DEBUG_MODE_BASE = True
def ai_base_log(message):
    if AI_DEBUG_MODE_BASE:
        print(f"[AI_BASE] {message}")

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
        ai_base_log(f"AIControllerBase __init__ for Player ID: {id(ai_player_sprite)}")
        self.ai_player = ai_player_sprite
        self.game = game_instance
        self.map_manager = self.game.map_manager
        self.human_player_sprite = getattr(self.game, 'player1', None)
        self.current_state = "BASE_IDLE" 
        self.state_start_time = pygame.time.get_ticks()
        self.ai_decision_interval = settings.AI_MOVE_DELAY
        self.last_decision_time = pygame.time.get_ticks() - self.ai_decision_interval
        self.astar_planned_path = []
        self.astar_path_current_segment_index = 0
        self.current_movement_sub_path = []
        self.current_movement_sub_path_index = 0
        self.last_bomb_placed_time = 0
        self.ai_just_placed_bomb = False
        self.movement_history = deque(maxlen=4)
        self.oscillation_stuck_counter = 0
        self.decision_cycle_stuck_counter = 0
        self.last_known_tile = (-1,-1)

    def _update_and_check_stuck_conditions(self, ai_current_tile, stuck_threshold, oscillation_threshold):
        is_waiting_after_bomb_for_stuck_check = False
        if self.ai_just_placed_bomb:
            if self.current_movement_sub_path and hasattr(self, 'chosen_retreat_spot_coords') and self.chosen_retreat_spot_coords and self.current_movement_sub_path[-1] == self.chosen_retreat_spot_coords:
                 is_waiting_after_bomb_for_stuck_check = True
            elif not self.current_movement_sub_path and hasattr(self, 'chosen_retreat_spot_coords') and self.chosen_retreat_spot_coords and ai_current_tile == self.chosen_retreat_spot_coords: 
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
                ai_base_log(f"[STUCK_BASE_OSCILLATION] Oscillation detected. Count: {self.oscillation_stuck_counter}. History: {history}")
            else:
                self.oscillation_stuck_counter = 0
        else:
            self.oscillation_stuck_counter = 0
        stuck = self.decision_cycle_stuck_counter >= stuck_threshold
        oscillating = self.oscillation_stuck_counter >= oscillation_threshold
        if stuck and not is_oscillating : 
            ai_base_log(f"[STUCK_BASE_TILE] AI stuck at {ai_current_tile} for {self.decision_cycle_stuck_counter} cycles (threshold: {stuck_threshold}).")
        return stuck or oscillating

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
                ai_base_log(f"[ERROR_BASE] Map data access out of bounds for y={y}, x={x}"); return None
            except TypeError: 
                 ai_base_log(f"[ERROR_BASE] Map data not subscriptable for y={y}, x={x}. map_data type: {type(self.map_manager.map_data)}"); return None
        return None

    def _get_node_neighbors(self, node: TileNode, for_astar_planning=True):
        neighbors = []
        for dx, dy in DIRECTIONS.values():
            nx, ny = node.x + dx, node.y + dy
            neighbor_node = self._get_node_at_coords(nx, ny)
            if neighbor_node:
                if for_astar_planning:
                    if neighbor_node.is_walkable_for_astar_planning(): neighbors.append(neighbor_node)
                else: 
                    if neighbor_node.is_empty_for_direct_movement(): neighbors.append(neighbor_node)
        return neighbors

    def _is_tile_in_hypothetical_blast(self, check_tile_x, check_tile_y, bomb_placed_at_x, bomb_placed_at_y, bomb_range):
        if not (0 <= check_tile_x < self.map_manager.tile_width and 0 <= check_tile_y < self.map_manager.tile_height): return False
        if check_tile_x == bomb_placed_at_x and check_tile_y == bomb_placed_at_y: return True
        if check_tile_y == bomb_placed_at_y and abs(check_tile_x - bomb_placed_at_x) <= bomb_range:
            blocked = False; step = 1 if check_tile_x > bomb_placed_at_x else -1
            for i in range(1, abs(check_tile_x - bomb_placed_at_x)):
                current_check_x = bomb_placed_at_x + i * step
                if self.map_manager.is_solid_wall_at(current_check_x, bomb_placed_at_y): blocked = True; break
                node_between = self._get_node_at_coords(current_check_x, bomb_placed_at_y) 
                if node_between and node_between.is_destructible_box(): blocked = True; break 
            if not blocked: return True
        if check_tile_x == bomb_placed_at_x and abs(check_tile_y - bomb_placed_at_y) <= bomb_range:
            blocked = False; step = 1 if check_tile_y > bomb_placed_at_y else -1
            for i in range(1, abs(check_tile_y - bomb_placed_at_y)):
                current_check_y = bomb_placed_at_y + i * step
                if self.map_manager.is_solid_wall_at(bomb_placed_at_x, current_check_y): blocked = True; break
                node_between = self._get_node_at_coords(bomb_placed_at_x, current_check_y)
                if node_between and node_between.is_destructible_box(): blocked = True; break
            if not blocked: return True
        return False

    def is_tile_dangerous(self, tile_x, tile_y, future_seconds=0.3):
        tile_rect = pygame.Rect(tile_x * settings.TILE_SIZE, tile_y * settings.TILE_SIZE, settings.TILE_SIZE, settings.TILE_SIZE)
        if hasattr(self.game, 'explosions_group'):
            for exp_sprite in self.game.explosions_group:
                if exp_sprite.rect.colliderect(tile_rect): return True
        if hasattr(self.game, 'bombs_group'):
            for bomb in self.game.bombs_group:
                if bomb.exploded: continue
                time_to_explosion_ms = (bomb.spawn_time + bomb.timer) - pygame.time.get_ticks()
                if 0 < time_to_explosion_ms < future_seconds * 1000:
                    range_to_check = bomb.placed_by_player.bomb_range if hasattr(bomb.placed_by_player, 'bomb_range') else 1
                    if self._is_tile_in_hypothetical_blast(tile_x, tile_y, bomb.current_tile_x, bomb.current_tile_y, range_to_check): return True
        return False
    
    def astar_find_path(self, start_coords, target_coords):
        ai_base_log(f"[ASTAR_BASE] Planning path from {start_coords} to {target_coords}...")
        start_node = self._get_node_at_coords(start_coords[0], start_coords[1])
        target_node = self._get_node_at_coords(target_coords[0], target_coords[1])
        if not start_node or not target_node:
            ai_base_log(f"[ASTAR_BASE_ERROR] Invalid start ({start_node}) or target ({target_node}) node."); return []
        open_set = []; closed_set = set(); open_set_dict = {}
        start_node.g_cost = 0
        start_node.h_cost = abs(start_node.x - target_node.x) + abs(start_node.y - target_node.y)
        start_node.parent = None
        heapq.heappush(open_set, start_node)
        open_set_dict[(start_node.x, start_node.y)] = start_node
        path_found = False; final_node = None
        while open_set:
            current_node = heapq.heappop(open_set)
            if (current_node.x, current_node.y) not in open_set_dict or open_set_dict[(current_node.x, current_node.y)] is not current_node:
                continue 
            open_set_dict.pop((current_node.x, current_node.y), None)
            if current_node == target_node:
                final_node = current_node; path_found = True; break
            if (current_node.x, current_node.y) in closed_set: continue
            closed_set.add((current_node.x, current_node.y))
            for neighbor_node_template in self._get_node_neighbors(current_node, for_astar_planning=True):
                if (neighbor_node_template.x, neighbor_node_template.y) in closed_set: continue
                move_cost_to_neighbor = neighbor_node_template.get_astar_move_cost_to_here()
                tentative_g_cost = current_node.g_cost + move_cost_to_neighbor
                neighbor_coords = (neighbor_node_template.x, neighbor_node_template.y)
                if neighbor_coords in open_set_dict:
                    neighbor_node = open_set_dict[neighbor_coords]
                else: 
                    neighbor_node = TileNode(neighbor_coords[0], neighbor_coords[1], neighbor_node_template.tile_char)
                    neighbor_node.g_cost = float('inf') 
                    neighbor_node.h_cost = abs(neighbor_node.x - target_node.x) + abs(neighbor_node.y - target_node.y)
                if tentative_g_cost < neighbor_node.g_cost:
                    neighbor_node.parent = current_node
                    neighbor_node.g_cost = tentative_g_cost
                    if neighbor_coords not in open_set_dict or open_set_dict[neighbor_coords].get_f_cost() > neighbor_node.get_f_cost() :
                        heapq.heappush(open_set, neighbor_node)
                        open_set_dict[neighbor_coords] = neighbor_node
        path = []
        if path_found and final_node:
            temp = final_node
            while temp: path.append(temp); temp = temp.parent
            path.reverse()
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
        
    def can_place_bomb_and_retreat(self, bomb_placement_coords):
        if self.is_tile_dangerous(bomb_placement_coords[0], bomb_placement_coords[1], future_seconds=0.1):
            return False, None
        bomb_range_to_use = self.ai_player.bomb_range
        retreat_spots = self.find_safe_tiles_nearby_for_retreat(bomb_placement_coords, bomb_placement_coords, bomb_range_to_use)
        if retreat_spots:
            best_retreat_spot = retreat_spots[0]
            path_to_retreat = self.bfs_find_direct_movement_path(bomb_placement_coords, best_retreat_spot, max_depth=7)
            if path_to_retreat and len(path_to_retreat) > 1 :
                return True, best_retreat_spot
        return False, None

    def find_safe_tiles_nearby_for_retreat(self, from_tile_coords, bomb_just_placed_at_coords, bomb_range, max_depth=6):
        q = deque([(from_tile_coords, [from_tile_coords], 0)]); visited = {from_tile_coords}
        safe_retreat_spots = []
        future_check = getattr(settings, "AI_RETREAT_SPOT_OTHER_DANGER_FUTURE_SECONDS", 1.5)
        while q:
            (curr_x, curr_y), path, depth = q.popleft()
            if depth > max_depth: continue
            is_safe_from_this_bomb = True
            if bomb_range > 0 :
                is_safe_from_this_bomb = not self._is_tile_in_hypothetical_blast(curr_x, curr_y, bomb_just_placed_at_coords[0], bomb_just_placed_at_coords[1], bomb_range)
            is_safe_from_other_dangers = not self.is_tile_dangerous(curr_x, curr_y, future_seconds=future_check)
            if is_safe_from_this_bomb and is_safe_from_other_dangers:
                safe_retreat_spots.append({'coords': (curr_x, curr_y), 'path_len': len(path) -1 })
                if len(safe_retreat_spots) >= 5: break 
            if depth < max_depth:
                shuffled_directions = list(DIRECTIONS.values()); random.shuffle(shuffled_directions)
                for dx, dy in shuffled_directions:
                    next_x, next_y = curr_x + dx, curr_y + dy
                    if (next_x, next_y) not in visited:
                        node = self._get_node_at_coords(next_x, next_y)
                        if node and node.is_empty_for_direct_movement() and not self.is_tile_dangerous(next_x, next_y, future_seconds=0.1):
                            visited.add((next_x, next_y)); q.append(((next_x, next_y), path + [(next_x, next_y)], depth + 1))
        if safe_retreat_spots:
            safe_retreat_spots.sort(key=lambda x: x['path_len'])
            return [spot['coords'] for spot in safe_retreat_spots]
        return []
        
    def set_current_movement_sub_path(self, path_coords_list):
        if path_coords_list and len(path_coords_list) >= 1:
            self.current_movement_sub_path = path_coords_list
            self.current_movement_sub_path_index = 0
            ai_base_log(f"    Set new sub-path: {self.current_movement_sub_path}")
        else:
            self.current_movement_sub_path = []; self.current_movement_sub_path_index = 0
            ai_base_log(f"    Cleared sub-path (attempted to set empty or invalid path_coords_list).")

    def execute_next_move_on_sub_path(self, ai_current_tile):
        if not self.current_movement_sub_path: return True
        if ai_current_tile == self.current_movement_sub_path[-1]:
            self.movement_history.append(ai_current_tile)
            self.current_movement_sub_path = []; self.current_movement_sub_path_index = 0
            if hasattr(self.ai_player, 'is_moving'): self.ai_player.is_moving = False
            return True
        if self.current_movement_sub_path_index >= len(self.current_movement_sub_path):
            self.current_movement_sub_path = []; self.current_movement_sub_path_index = 0; return True
        expected_current_sub_path_tile = self.current_movement_sub_path[self.current_movement_sub_path_index]
        if ai_current_tile != expected_current_sub_path_tile:
            ai_base_log(f"    Sub-path desync: AI at {ai_current_tile}, expected {expected_current_sub_path_tile}. Path: {self.current_movement_sub_path}. Clearing.")
            self.current_movement_sub_path = []; self.current_movement_sub_path_index = 0; return True
        if self.current_movement_sub_path_index + 1 >= len(self.current_movement_sub_path): 
            ai_base_log(f"    Sub-path logic error: trying to get next beyond end. Path: {self.current_movement_sub_path}. Clearing.")
            self.current_movement_sub_path = []; self.current_movement_sub_path_index = 0; return True
        next_target_tile_in_sub_path = self.current_movement_sub_path[self.current_movement_sub_path_index + 1]
        dx = next_target_tile_in_sub_path[0] - ai_current_tile[0]; dy = next_target_tile_in_sub_path[1] - ai_current_tile[1]
        if not (abs(dx) <= 1 and abs(dy) <= 1 and (dx != 0 or dy != 0) and (dx == 0 or dy == 0)):
            ai_base_log(f"    Invalid step in sub-path from {ai_current_tile} to {next_target_tile_in_sub_path}. Clearing.")
            self.current_movement_sub_path = []; self.current_movement_sub_path_index = 0; return True
        moved = self.ai_player.attempt_move_to_tile(dx, dy)
        if moved:
            moved_to_tile = (self.ai_player.tile_x, self.ai_player.tile_y)
            self.movement_history.append(moved_to_tile)
            self.current_movement_sub_path_index += 1
            if moved_to_tile == self.current_movement_sub_path[-1]: 
                self.current_movement_sub_path = []; self.current_movement_sub_path_index = 0
                if hasattr(self.ai_player, 'is_moving'): self.ai_player.is_moving = False
                return True
            return False
        else:
            ai_base_log(f"    Sub-path move from {ai_current_tile} to {next_target_tile_in_sub_path} FAILED (blocked). Clearing.")
            self.current_movement_sub_path = []; self.current_movement_sub_path_index = 0; return True

    def is_bomb_still_active(self, bomb_placed_timestamp):
        if bomb_placed_timestamp == 0: return False
        elapsed_time = pygame.time.get_ticks() - bomb_placed_timestamp
        bomb_timer_duration = getattr(settings, 'BOMB_TIMER', 3000)
        explosion_effect_duration = getattr(settings, 'EXPLOSION_DURATION', 300)
        buffer_time = 200
        return elapsed_time < (bomb_timer_duration + explosion_effect_duration + buffer_time)

    def reset_state_base(self): 
        ai_base_log(f"AIControllerBase reset_state_base for Player ID: {id(self.ai_player)}.")
        self.current_state = "BASE_IDLE" 
        self.state_start_time = pygame.time.get_ticks()
        self.astar_planned_path = []
        self.astar_path_current_segment_index = 0
        self.current_movement_sub_path = []
        self.current_movement_sub_path_index = 0
        self.last_bomb_placed_time = 0
        self.ai_just_placed_bomb = False
        self.last_decision_time = pygame.time.get_ticks() - self.ai_decision_interval 
        current_ai_tile_tuple = self._get_ai_current_tile()
        self.last_known_tile = current_ai_tile_tuple if current_ai_tile_tuple else (-1,-1)
        self.movement_history.clear()
        self.oscillation_stuck_counter = 0
        self.decision_cycle_stuck_counter = 0
    
    def update(self):
        pass

    def change_state(self, new_state):
        if self.current_state != new_state:
            ai_base_log(f"[STATE_CHANGE_BASE] ID: {id(self.ai_player)} From {self.current_state} -> {new_state}")
            # （1）！！！移除特定於 ItemFocusedAIController 的清理邏輯！！！
            # old_state = self.current_state # 儲存舊狀態是好的，但特定清理不在此處
            self.current_state = new_state
            self.state_start_time = pygame.time.get_ticks()
            
            # 通用的狀態改變清理
            self.current_movement_sub_path = []
            self.current_movement_sub_path_index = 0
            # （1）！！！移除結束！！！

    def debug_draw_path(self, surface):
        ai_tile_now = self._get_ai_current_tile()
        if ai_tile_now and hasattr(settings, 'TILE_SIZE'):
            try:
                s = pygame.Surface((settings.TILE_SIZE, settings.TILE_SIZE), pygame.SRCALPHA)
                s.fill((0, 0, 255, 30)) # 更淡一點的基礎標記
                surface.blit(s, (ai_tile_now[0] * settings.TILE_SIZE, ai_tile_now[1] * settings.TILE_SIZE))
            except Exception as e:
                ai_base_log(f"Error in base debug_draw_path: {e}")