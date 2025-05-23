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

# --- 常數與節點定義 ---
DIRECTIONS = {"UP": (0, -1), "DOWN": (0, 1), "LEFT": (-1, 0), "RIGHT": (1, 0)}

class TileNode:
    """代表地圖上的一個格子，用於路徑規劃。"""
    def __init__(self, x, y, tile_char):
        self.x, self.y, self.tile_char = x, y, tile_char
        self.parent = None
        self.g_cost, self.h_cost = float('inf'), float('inf')

    def get_f_cost(self): return self.g_cost + self.h_cost
    def is_walkable_for_astar_planning(self): return self.tile_char in ['.', 'D']
    def is_empty_for_direct_movement(self): return self.tile_char == '.'
    def is_destructible_box(self): return self.tile_char == 'D'
    def get_astar_move_cost_to_here(self):
        if self.tile_char == '.': return 1
        if self.tile_char == 'D': return 3
        return float('inf')

    def __lt__(self, other):
        if not isinstance(other, TileNode): return NotImplemented
        f1, f2 = self.get_f_cost(), other.get_f_cost()
        return (f1, self.h_cost) < (f2, other.h_cost)
    def __eq__(self, other):
        return isinstance(other, TileNode) and self.x == other.x and self.y == other.y
    def __hash__(self): return hash((self.x, self.y))
    def __repr__(self): return f"N({self.x},{self.y},'{self.tile_char}',f={self.get_f_cost():.1f})"

class AIControllerBase:
    """
    所有 AI 行為模式的基底類別。
    提供通用的狀態管理、路徑規劃和輔助函式。
    """
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

        self.reset_state()

    def reset_state(self):
        """重置 AI 的所有狀態，以便在新遊戲或死亡後重新開始。"""
        ai_log(f"Resetting AI state for Player ID: {id(self.ai_player)}.")
        self.current_state = "PLANNING_PATH" # 初始狀態
        self.state_start_time = pygame.time.get_ticks()
        self.astar_planned_path = []
        self.astar_path_current_segment_index = 0
        self.current_movement_sub_path = []
        self.current_movement_sub_path_index = 0
        self.last_bomb_placed_time = 0
        self.ai_just_placed_bomb = False
        self.chosen_bombing_spot_coords = None
        self.chosen_retreat_spot_coords = None
        self.last_decision_time = pygame.time.get_ticks() - self.ai_decision_interval
        current_ai_tile_tuple = self._get_ai_current_tile()
        self.last_known_tile = current_ai_tile_tuple if current_ai_tile_tuple else (-1,-1)
        self.movement_history.clear()
        self.oscillation_stuck_counter = 0
        self.decision_cycle_stuck_counter = 0

    def change_state(self, new_state):
        """切換 AI 的有限狀態機 (FSM) 狀態，並進行必要的清理。"""
        if self.current_state != new_state:
            ai_log(f"[STATE_CHANGE] ID: {id(self.ai_player)} From {self.current_state} -> {new_state}")
            self.current_state = new_state
            self.state_start_time = pygame.time.get_ticks()
            self.current_movement_sub_path = []
            self.current_movement_sub_path_index = 0
            
            # 清理特定狀態的過時資訊
            if new_state not in ["EXECUTING_PATH_CLEARANCE", "TACTICAL_RETREAT_AND_WAIT"] and hasattr(self, 'target_destructible_wall_node_in_astar'):
                self.target_destructible_wall_node_in_astar = None
            if new_state not in ["TACTICAL_RETREAT_AND_WAIT", "CLOSE_QUARTERS_COMBAT", "ENGAGING_PLAYER"]:
                self.chosen_bombing_spot_coords = None
                self.chosen_retreat_spot_coords = None
            if new_state == "PLANNING_PATH":
                 self.astar_planned_path = []
                 self.astar_path_current_segment_index = 0

    # --- 核心 Update 迴圈 ---
    def update(self):
        """
        AI 的主驅動函式，每個遊戲迴圈都會呼叫。
        負責管理決策時機、處理緊急情況（如躲避危險）和執行當前狀態的邏輯。
        """
        current_time = pygame.time.get_ticks()
        ai_current_tile = self._get_ai_current_tile()

        if not ai_current_tile or not self.ai_player.is_alive:
            if self.current_state != "DEAD": self.change_state("DEAD")
            return

        # 保險機制：自動清理過時的炸彈旗標
        if self.ai_just_placed_bomb and not self.is_bomb_still_active(self.last_bomb_placed_time):
             ai_log("Bomb flag auto-cleared as bomb effect has ended.")
             self.ai_just_placed_bomb = False

        # 最高優先級：檢查是否處於危險中，是則立即切換到逃跑狀態
        if self.is_tile_dangerous(ai_current_tile[0], ai_current_tile[1], future_seconds=0.4):
            if self.current_state != "EVADING_DANGER":
                self.change_state("EVADING_DANGER")
                self.last_decision_time = current_time # 讓 AI 立即做一次逃跑決策

        # 根據計時器觸發一個新的決策週期
        if current_time - self.last_decision_time >= self.ai_decision_interval:
            self.last_decision_time = current_time

            # 卡死檢測
            if self._update_and_check_stuck_conditions(ai_current_tile):
                ai_log("Stuck detected! Forcing a re-plan.")
                self.movement_history.clear()
                self.decision_cycle_stuck_counter = 0
                self.oscillation_stuck_counter = 0
                self.change_state("PLANNING_PATH") # 強制重新規劃
                self.handle_state(ai_current_tile) # 立即處理新狀態
                return

            # 正常執行當前狀態的邏輯
            self.handle_state(ai_current_tile)

        # 根據決策結果，執行移動
        if self.ai_player.action_timer <= 0:
            if self.current_movement_sub_path:
                if self.execute_next_move_on_sub_path(ai_current_tile):
                    # 如果子路徑走完了，立即觸發下一次決策，無需等待計時器
                    self.last_decision_time = pygame.time.get_ticks()
            else:
                self.ai_player.is_moving = False

    def handle_state(self, ai_current_tile):
        """
        狀態分派器。根據 self.current_state 呼叫對應的 handle_..._state 方法。
        子類別應覆寫各個 handle_..._state 方法來實現特定行為。
        """
        state_handler_method_name = f"handle_{self.current_state.lower()}_state"
        handler = getattr(self, state_handler_method_name, self.handle_unknown_state)
        handler(ai_current_tile)

    def handle_unknown_state(self, ai_current_tile):
        """如果找不到狀態對應的處理函式，則執行此預設行為，防止程式崩潰。"""
        ai_log(f"Warning: Unknown state '{self.current_state}'. Reverting to PLANNING_PATH.")
        self.change_state("PLANNING_PATH")
        
    # --- 狀態處理函式的預設實作 (供子類別覆寫) ---
    
    def handle_planning_path_state(self, ai_current_tile):
        ai_log("Base class handle_planning_path_state called. No specific goal. Idling.")
        # 子類別必須覆寫此方法來決定要去哪裡
        
    def handle_evading_danger_state(self, ai_current_tile):
        """
        使用更敏感的參數進行逃跑，並嘗試找到最佳的逃生路徑。
        """
        ai_log(f"CONSERVATIVE (Roaming): EVADING DANGER at {ai_current_tile} with high urgency.")
        
        # 1. 檢查當前位置是否已經安全
        if not self.is_tile_dangerous(ai_current_tile[0], ai_current_tile[1], self.evasion_urgency_seconds):
            ai_log("CONSERVATIVE (Roaming): Danger evaded. Returning to roaming.")
            self.change_state("ROAMING")
            return

        # 2. 如果正在執行的逃跑路徑的目標點也變得危險，則清空當前路徑，重新尋找
        if self.current_movement_sub_path:
            target_of_current_path = self.current_movement_sub_path[-1]
            if self.is_tile_dangerous(target_of_current_path[0], target_of_current_path[1], future_seconds=0.2):
                ai_log("CONSERVATIVE (Roaming): Current evasion path target has become dangerous. Re-planning evasion.")
                self.current_movement_sub_path = [] # 清空路徑，強制重新尋找

        # 3. 如果沒有有效的逃跑路徑，則尋找新的
        if not self.current_movement_sub_path:
            ai_log("CONSERVATIVE (Roaming): Finding new evasion path.")
            # 增加搜索深度和候選點數量
            safe_spots = self.find_safe_tiles_nearby_for_retreat(
                from_coords=ai_current_tile,
                bomb_coords=ai_current_tile, # 這裡的 bomb_coords 其實是指危險源中心，對於一般危險用AI當前位置即可
                bomb_range=0, # bomb_range 0 表示一般性危險，不是躲避特定自己放的炸彈
                max_depth=self.retreat_search_depth + 2, # 比平時看得更遠一點
                min_options_needed=3 # 嘗試找到至少3個選項
            )
            
            if safe_spots:
                best_path_to_safety = None
                # 從找到的安全點中，選擇一個路徑最短的
                # （find_safe_tiles_nearby_for_retreat 內部可以增加排序邏輯，例如優先選擇「空曠度」高的點）
                for spot in safe_spots:
                    path = self.bfs_find_direct_movement_path(ai_current_tile, spot, max_depth=self.retreat_search_depth + 2)
                    if path and len(path) > 1:
                        if best_path_to_safety is None or len(path) < len(best_path_to_safety):
                            best_path_to_safety = path
                
                if best_path_to_safety:
                    ai_log(f"CONSERVATIVE (Roaming): Found best evasion path to {best_path_to_safety[-1]}. Path: {best_path_to_safety}")
                    self.set_current_movement_sub_path(best_path_to_safety)
                    return # 找到路徑就立刻返回，等待下一幀執行移動

            # 如果真的找不到任何安全路徑
            ai_log("CONSERVATIVE (Roaming): CRITICAL - No valid evasion path found! Trying a short random move.")
            # 作為最後手段，嘗試隨機向一個相鄰的、不是立即致命的格子移動一步
            possible_random_moves = []
            for dx, dy in DIRECTIONS.values():
                next_x, next_y = ai_current_tile[0] + dx, ai_current_tile[1] + dy
                node = self._get_node_at_coords(next_x, next_y)
                if node and node.is_empty_for_direct_movement() and not self.is_tile_dangerous(next_x, next_y, 0.1): # 極短期預判
                    possible_random_moves.append((next_x, next_y))
            
            if possible_random_moves:
                desperate_move_target = random.choice(possible_random_moves)
                ai_log(f"CONSERVATIVE (Roaming): Making a desperate random move to {desperate_move_target}.")
                self.set_current_movement_sub_path([ai_current_tile, desperate_move_target])
            else:
                ai_log("CONSERVATIVE (Roaming): No desperate moves available either. Stuck in danger.")
                # AI 卡在危險中，等待 stuck detection 或情況改變

    def handle_tactical_retreat_and_wait_state(self, ai_current_tile):
        ai_log("Base class handle_tactical_retreat_and_wait_state called. No logic. Idling.")

    def handle_engaging_player_state(self, ai_current_tile):
        ai_log("Base class handle_engaging_player_state called. No logic. Idling.")

    def handle_close_quarters_combat_state(self, ai_current_tile):
        ai_log("Base class handle_close_quarters_combat_state called. No logic. Idling.")
        
    def handle_evading_danger_state(self, ai_current_tile):
        """提供一個通用的逃生邏輯。"""
        ai_log(f"EVADING_DANGER at {ai_current_tile}")
        # 如果當前位置已經安全，則重新規劃
        if not self.is_tile_dangerous(ai_current_tile[0], ai_current_tile[1], settings.AI_EVASION_SAFETY_CHECK_FUTURE_SECONDS):
            self.change_state("PLANNING_PATH")
            return
        
        # 尋找新的逃生路徑
        safe_options = self.find_safe_tiles_nearby_for_retreat(ai_current_tile, ai_current_tile, 0)
        if safe_options:
            path_to_safety = self.bfs_find_direct_movement_path(ai_current_tile, safe_options[0])
            if path_to_safety:
                self.set_current_movement_sub_path(path_to_safety)
                return
        ai_log("Cannot find any safe evasion path! Trapped.")

    # --- 工具與輔助函式 ---

    def _get_ai_current_tile(self):
        return (self.ai_player.tile_x, self.ai_player.tile_y) if self.ai_player and self.ai_player.is_alive else None

    def _get_human_player_current_tile(self):
        return (self.human_player_sprite.tile_x, self.human_player_sprite.tile_y) if self.human_player_sprite and self.human_player_sprite.is_alive else None

    def _get_node_at_coords(self, x, y):
        if self.map_manager and 0 <= y < self.map_manager.tile_height and 0 <= x < self.map_manager.tile_width:
            return TileNode(x, y, self.map_manager.map_data[y][x])
        return None
        
    def _update_and_check_stuck_conditions(self, ai_current_tile):
        """檢查 AI 是否卡在原地或在兩點間振盪。"""
        is_waiting_for_bomb = self.ai_just_placed_bomb and self.is_bomb_still_active(self.last_bomb_placed_time)
        
        if not self.current_movement_sub_path and not is_waiting_for_bomb:
            if self.last_known_tile == ai_current_tile: self.decision_cycle_stuck_counter += 1
            else: self.decision_cycle_stuck_counter = 0
        else: self.decision_cycle_stuck_counter = 0
        self.last_known_tile = ai_current_tile

        if len(self.movement_history) == 4 and self.movement_history[0] == self.movement_history[2] and self.movement_history[1] == self.movement_history[3] and self.movement_history[0] != self.movement_history[1]:
            self.oscillation_stuck_counter += 1
        else: self.oscillation_stuck_counter = 0
        
        return self.decision_cycle_stuck_counter >= 5 or self.oscillation_stuck_counter >= 2

    def astar_find_path(self, start_coords, target_coords):
        """使用 A* 演算法尋找成本最低的路徑（考慮到需要炸開的牆壁）。"""
        start_node = self._get_node_at_coords(start_coords[0], start_coords[1])
        target_node = self._get_node_at_coords(target_coords[0], target_coords[1])
        if not start_node or not target_node: return []

        open_set = []
        heapq.heappush(open_set, (0, 0, start_node))
        open_set_dict = {(start_node.x, start_node.y): start_node}
        closed_set = set()

        start_node.g_cost = 0
        start_node.h_cost = abs(start_node.x - target_node.x) + abs(start_node.y - target_node.y)

        while open_set:
            _, _, current_node = heapq.heappop(open_set)
            if (current_node.x, current_node.y) not in open_set_dict: continue
            
            if current_node == target_node:
                path = []
                temp = current_node
                while temp:
                    path.append(temp)
                    temp = temp.parent
                return path[::-1]

            closed_set.add((current_node.x, current_node.y))

            for neighbor_template in self._get_node_neighbors(current_node):
                if (neighbor_template.x, neighbor_template.y) in closed_set:
                    continue

                tentative_g_cost = current_node.g_cost + neighbor_template.get_astar_move_cost_to_here()
                neighbor_node = open_set_dict.get((neighbor_template.x, neighbor_template.y))
                
                if neighbor_node is None or tentative_g_cost < neighbor_node.g_cost:
                    if neighbor_node is None:
                        neighbor_node = neighbor_template
                        open_set_dict[(neighbor_node.x, neighbor_node.y)] = neighbor_node
                    
                    neighbor_node.parent = current_node
                    neighbor_node.g_cost = tentative_g_cost
                    neighbor_node.h_cost = abs(neighbor_node.x - target_node.x) + abs(neighbor_node.y - target_node.y)
                    heapq.heappush(open_set, (neighbor_node.get_f_cost(), neighbor_node.h_cost, neighbor_node))
        return []

    def bfs_find_direct_movement_path(self, start_coords, target_coords, max_depth=20, avoid_specific_tile=None):
        """使用廣度優先搜尋尋找兩個空格之間的最短路徑。"""
        q = deque([(start_coords, [start_coords])])
        visited = {start_coords}
        while q:
            (curr_x, curr_y), path = q.popleft()
            if len(path) - 1 > max_depth: continue
            if (curr_x, curr_y) == target_coords: return path
            
            shuffled_dirs = list(DIRECTIONS.values()); random.shuffle(shuffled_dirs)
            for dx, dy in shuffled_dirs:
                next_coords = (curr_x + dx, curr_y + dy)
                if next_coords not in visited and next_coords != avoid_specific_tile:
                    node = self._get_node_at_coords(next_coords[0], next_coords[1])
                    if node and node.is_empty_for_direct_movement() and not self.is_tile_dangerous(next_coords[0], next_coords[1], 0.15):
                        visited.add(next_coords)
                        q.append((next_coords, path + [next_coords]))
        return []

    def execute_next_move_on_sub_path(self, ai_current_tile):
        """執行短路徑 (sub_path) 中的下一步移動。"""
        if not self.current_movement_sub_path: return True
        if ai_current_tile == self.current_movement_sub_path[-1]:
            self.movement_history.append(ai_current_tile); self.current_movement_sub_path = []; return True
        
        if self.current_movement_sub_path_index >= len(self.current_movement_sub_path) or ai_current_tile != self.current_movement_sub_path[self.current_movement_sub_path_index]:
            ai_log("Sub-path desynced. Clearing path.")
            self.current_movement_sub_path = []; return True
            
        if self.current_movement_sub_path_index + 1 >= len(self.current_movement_sub_path):
            ai_log("Sub-path logic error: index out of bounds for next step. Clearing path.")
            self.current_movement_sub_path = []; return True

        next_target = self.current_movement_sub_path[self.current_movement_sub_path_index + 1]
        dx, dy = next_target[0] - ai_current_tile[0], next_target[1] - ai_current_tile[1]
        
        if self.ai_player.attempt_move_to_tile(dx, dy):
            self.movement_history.append((self.ai_player.tile_x, self.ai_player.tile_y))
            self.current_movement_sub_path_index += 1
            return False # 移動成功，路徑尚未走完
        else:
            ai_log("Move failed (blocked). Clearing path.")
            self.current_movement_sub_path = []; return True # 移動失敗，路徑作廢

    def set_current_movement_sub_path(self, path_coords_list):
        if path_coords_list and len(path_coords_list) > 1:
            self.current_movement_sub_path = path_coords_list
            self.current_movement_sub_path_index = 0
        else:
            self.current_movement_sub_path = []
            self.current_movement_sub_path_index = 0

    def is_bomb_still_active(self, bomb_placed_timestamp):
        if bomb_placed_timestamp == 0: return False
        elapsed = pygame.time.get_ticks() - bomb_placed_timestamp
        total_duration = settings.BOMB_TIMER + settings.EXPLOSION_DURATION + 200 # 200ms buffer
        return elapsed < total_duration
        
    def _is_tile_in_hypothetical_blast(self, check_x, check_y, bomb_x, bomb_y, bomb_range):
        # 判斷一個格子是否在指定炸彈的爆炸範圍內
        if not (0 <= check_x < self.map_manager.tile_width and 0 <= check_y < self.map_manager.tile_height): return False
        if check_x == bomb_x and abs(check_y - bomb_y) <= bomb_range:
            for i in range(1, abs(check_y - bomb_y) + 1):
                y = bomb_y + i * (1 if check_y > bomb_y else -1)
                if self.map_manager.is_solid_wall_at(bomb_x, y): return False
                if y == check_y: return True
                if self._get_node_at_coords(bomb_x,y).is_destructible_box(): return False
        if check_y == bomb_y and abs(check_x - bomb_x) <= bomb_range:
            for i in range(1, abs(check_x - bomb_x) + 1):
                x = bomb_x + i * (1 if check_x > bomb_x else -1)
                if self.map_manager.is_solid_wall_at(x, bomb_y): return False
                if x == check_x: return True
                if self._get_node_at_coords(x,bomb_y).is_destructible_box(): return False
        return False
        
    def is_tile_dangerous(self, tile_x, tile_y, future_seconds=0.3):
        # 判斷一個格子在未來幾秒內是否會被爆炸波及
        tile_rect = pygame.Rect(tile_x * settings.TILE_SIZE, tile_y * settings.TILE_SIZE, settings.TILE_SIZE, settings.TILE_SIZE)
        for explosion in self.game.explosions_group:
            if explosion.rect.colliderect(tile_rect): return True
        for bomb in self.game.bombs_group:
            time_left = (bomb.spawn_time + bomb.timer) - pygame.time.get_ticks()
            if 0 < time_left < future_seconds * 1000:
                if self._is_tile_in_hypothetical_blast(tile_x, tile_y, bomb.current_tile_x, bomb.current_tile_y, bomb.placed_by_player.bomb_range):
                    return True
        return False

    def find_safe_tiles_nearby_for_retreat(self, from_coords, bomb_coords, bomb_range, max_depth=6):
        # 尋找附近的安全撤退點
        q = deque([(from_coords, 0)])
        visited = {from_coords}
        safe_spots = []
        while q:
            (curr_x, curr_y), depth = q.popleft()
            if depth > max_depth: continue
            
            is_safe_from_this_bomb = not self._is_tile_in_hypothetical_blast(curr_x, curr_y, bomb_coords[0], bomb_coords[1], bomb_range)
            is_safe_from_others = not self.is_tile_dangerous(curr_x, curr_y, settings.AI_RETREAT_SPOT_OTHER_DANGER_FUTURE_SECONDS)

            if is_safe_from_this_bomb and is_safe_from_others:
                safe_spots.append((curr_x, curr_y))
                if len(safe_spots) >= 5: break # 找到5個就夠了
            
            if depth < max_depth:
                for dx, dy in DIRECTIONS.values():
                    next_coords = (curr_x + dx, curr_y + dy)
                    if next_coords not in visited:
                        node = self._get_node_at_coords(next_coords[0], next_coords[1])
                        if node and node.is_empty_for_direct_movement():
                            visited.add(next_coords)
                            q.append((next_coords, depth + 1))
        return safe_spots

    def debug_draw_path(self, surface):
        """在螢幕上繪製 AI 的除錯資訊，如當前路徑。"""
        # 為避免程式碼過於冗長，這裡提供一個簡單的繪製邏輯
        # 你可以從原版 ai_controller.py 中複製更詳細的繪圖程式碼
        if self.current_movement_sub_path and len(self.current_movement_sub_path) > 1:
            try:
                points = [(c[0] * settings.TILE_SIZE + settings.TILE_SIZE // 2, 
                           c[1] * settings.TILE_SIZE + settings.TILE_SIZE // 2) 
                          for c in self.current_movement_sub_path]
                pygame.draw.lines(surface, (255, 0, 255), False, points, 3)
            except Exception as e:
                ai_log(f"Error in debug_draw_path: {e}")