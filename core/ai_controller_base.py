# oop-2025-proj-pycade/core/ai_controller_base.py

import pygame
import settings # 您可能需要從 settings_rl.py 或主 settings.py 匯入
import random
from collections import deque
import heapq

# 從您原始 ai_controller.py 複製過來的 AI_DEBUG_MODE 和 ai_log (如果新的 AI 也需要)
AI_DEBUG_MODE_BASE = True # 可以獨立控制 Base AI 的日誌

def ai_base_log(message):
    if AI_DEBUG_MODE_BASE:
        print(f"[AI_BASE] {message}")

# 從您原始 ai_controller.py 複製過來的 DIRECTIONS 和 TileNode (或者考慮將 TileNode 移到更通用的地方)
DIRECTIONS = {"UP": (0, -1), "DOWN": (0, 1), "LEFT": (-1, 0), "RIGHT": (1, 0)} #

class TileNode: #
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
        # 從原始 ai_controller.py 複製 COST_MOVE_EMPTY 和 COST_BOMB_BOX 的定義，或者從 settings 匯入
        COST_MOVE_EMPTY_BASE = 1 # 範例值
        COST_BOMB_BOX_BASE = 3   # 範例值
        if self.tile_char == '.': return COST_MOVE_EMPTY_BASE
        elif self.tile_char == 'D': return COST_BOMB_BOX_BASE
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
        return f"N_Base({self.x},{self.y},'{self.tile_char}',g={g_str},h={h_str})"


class AIControllerBase:
    def __init__(self, ai_player_sprite, game_instance):
        ai_base_log(f"AIControllerBase __init__ for Player ID: {id(ai_player_sprite)}")
        self.ai_player = ai_player_sprite
        self.game = game_instance
        self.map_manager = self.game.map_manager # 假設 game_instance 有 map_manager 屬性
        self.human_player_sprite = getattr(self.game, 'player1', None) # 假設 game_instance 有 player1 屬性

        # 通用屬性 (從原始 AIController 複製並調整)
        self.current_state = "BASE_IDLE" # 基礎類別可以有一個預設的閒置狀態
        self.state_start_time = pygame.time.get_ticks()
        self.ai_decision_interval = settings.AI_MOVE_DELAY # 假設 settings.py 可用
        self.last_decision_time = pygame.time.get_ticks() - self.ai_decision_interval

        self.astar_planned_path = []
        self.astar_path_current_segment_index = 0
        self.current_movement_sub_path = []
        self.current_movement_sub_path_index = 0

        self.last_bomb_placed_time = 0
        self.ai_just_placed_bomb = False # 子類可能會用到

        self.movement_history = deque(maxlen=4) # 卡死檢測相關
        self.oscillation_stuck_counter = 0
        self.decision_cycle_stuck_counter = 0
        self.last_known_tile = (-1,-1)
        # 注意：stuck_threshold_decision_cycles 等特定於行為的參數可以放在子類

    def _get_ai_current_tile(self): #
        if self.ai_player and self.ai_player.is_alive:
            return (self.ai_player.tile_x, self.ai_player.tile_y)
        return None

    def _get_human_player_current_tile(self): #
        if self.human_player_sprite and self.human_player_sprite.is_alive:
            return (self.human_player_sprite.tile_x, self.human_player_sprite.tile_y)
        return None

    def _get_node_at_coords(self, x, y): #
        if self.map_manager and 0 <= y < self.map_manager.tile_height and 0 <= x < self.map_manager.tile_width:
            tile_char = self.map_manager.map_data[y][x]
            return TileNode(x, y, tile_char) # 使用上面定義的 TileNode
        return None

    def _get_node_neighbors(self, node: TileNode, for_astar_planning=True): #
        neighbors = []
        # 使用上面定義的 DIRECTIONS
        for dx, dy in DIRECTIONS.values():
            nx, ny = node.x + dx, node.y + dy
            neighbor_node = self._get_node_at_coords(nx, ny)
            if neighbor_node:
                if for_astar_planning:
                    if neighbor_node.is_walkable_for_astar_planning():
                        neighbors.append(neighbor_node)
                else: # for direct movement (BFS)
                    if neighbor_node.is_empty_for_direct_movement():
                        neighbors.append(neighbor_node)
        return neighbors

    def _is_tile_in_hypothetical_blast(self, check_tile_x, check_tile_y, bomb_placed_at_x, bomb_placed_at_y, bomb_range): #
        if not (0 <= check_tile_x < self.map_manager.tile_width and \
                0 <= check_tile_y < self.map_manager.tile_height):
            return False

        if check_tile_x == bomb_placed_at_x and check_tile_y == bomb_placed_at_y: return True

        # 水平方向檢查
        if check_tile_y == bomb_placed_at_y and abs(check_tile_x - bomb_placed_at_x) <= bomb_range:
            blocked = False
            step = 1 if check_tile_x > bomb_placed_at_x else -1
            for i in range(1, abs(check_tile_x - bomb_placed_at_x)): # 不檢查起點和終點之間是否有牆
                current_check_x = bomb_placed_at_x + i * step
                if self.map_manager.is_solid_wall_at(current_check_x, bomb_placed_at_y): # 檢查固定牆
                    blocked = True; break
                # 在基礎類別中，我們可以先不檢查可破壞牆壁，除非子類需要此精細度
                # node_between = self._get_node_at_coords(current_check_x, bomb_placed_at_y)
                # if node_between and node_between.is_destructible_box():
                #     blocked = True; break
            if not blocked: return True

        # 垂直方向檢查
        if check_tile_x == bomb_placed_at_x and abs(check_tile_y - bomb_placed_at_y) <= bomb_range:
            blocked = False
            step = 1 if check_tile_y > bomb_placed_at_y else -1
            for i in range(1, abs(check_tile_y - bomb_placed_at_y)): # 不檢查起點和終點之間是否有牆
                current_check_y = bomb_placed_at_y + i * step
                if self.map_manager.is_solid_wall_at(bomb_placed_at_x, current_check_y): # 檢查固定牆
                    blocked = True; break
                # node_between = self._get_node_at_coords(bomb_placed_at_x, current_check_y)
                # if node_between and node_between.is_destructible_box():
                #     blocked = True; break
            if not blocked: return True
        return False

    def is_tile_dangerous(self, tile_x, tile_y, future_seconds=0.3): #
        # 檢查現有爆炸
        tile_rect = pygame.Rect(tile_x * settings.TILE_SIZE, tile_y * settings.TILE_SIZE, settings.TILE_SIZE, settings.TILE_SIZE)
        if hasattr(self.game, 'explosions_group'):
            for exp_sprite in self.game.explosions_group:
                if exp_sprite.rect.colliderect(tile_rect):
                    return True

        # 檢查即將爆炸的炸彈
        if hasattr(self.game, 'bombs_group'):
            for bomb in self.game.bombs_group:
                if bomb.exploded: continue
                time_to_explosion_ms = (bomb.spawn_time + bomb.timer) - pygame.time.get_ticks()
                # 確保 future_seconds 來自 settings 或作為參數傳遞
                effective_future_seconds = getattr(settings, 'AI_EVASION_SAFETY_CHECK_FUTURE_SECONDS', future_seconds)

                if 0 < time_to_explosion_ms < effective_future_seconds * 1000:
                    range_to_check = bomb.placed_by_player.bomb_range if hasattr(bomb.placed_by_player, 'bomb_range') else 1
                    if self._is_tile_in_hypothetical_blast(tile_x, tile_y, bomb.current_tile_x, bomb.current_tile_y, range_to_check):
                        return True
        return False

    def astar_find_path(self, start_coords, target_coords): #
        # (從原始 AIController 複製 A* 演算法的完整實現)
        # ...
        ai_base_log(f"[ASTAR_BASE] Planning path from {start_coords} to {target_coords}...")
        start_node = self._get_node_at_coords(start_coords[0], start_coords[1])
        target_node = self._get_node_at_coords(target_coords[0], target_coords[1])
        if not start_node or not target_node:
            ai_base_log(f"[ASTAR_BASE_ERROR] Invalid start ({start_node}) or target ({target_node}) node."); return []

        open_set = []; closed_set = set(); open_set_dict = {}
        start_node.g_cost = 0
        start_node.h_cost = abs(start_node.x - target_node.x) + abs(start_node.y - target_node.y)
        start_node.parent = None
        heapq.heappush(open_set, (start_node.get_f_cost(), start_node.h_cost, start_node)) # 使用 TileNode 的 __lt__
        open_set_dict[(start_node.x, start_node.y)] = start_node
        path_found = False; final_node = None

        while open_set:
            _, _, current_node = heapq.heappop(open_set) # 取 f_cost 最小的
            open_set_dict.pop((current_node.x, current_node.y), None) # 從字典中移除

            if current_node == target_node:
                final_node = current_node; path_found = True; break

            if (current_node.x, current_node.y) in closed_set: # 避免重複處理
                continue
            closed_set.add((current_node.x, current_node.y))

            for neighbor_node_template in self._get_node_neighbors(current_node, for_astar_planning=True):
                if (neighbor_node_template.x, neighbor_node_template.y) in closed_set:
                    continue

                move_cost_to_neighbor = neighbor_node_template.get_astar_move_cost_to_here()
                tentative_g_cost = current_node.g_cost + move_cost_to_neighbor

                # 獲取 open_set 中已存在的鄰居節點 (如果有的話) 或使用模板
                neighbor_node = open_set_dict.get((neighbor_node_template.x, neighbor_node_template.y), neighbor_node_template)

                if tentative_g_cost < neighbor_node.g_cost:
                    neighbor_node.parent = current_node
                    neighbor_node.g_cost = tentative_g_cost
                    neighbor_node.h_cost = abs(neighbor_node.x - target_node.x) + abs(neighbor_node.y - target_node.y)
                    # 如果節點已在 open_set (透過 open_set_dict 檢查)，理論上 heapq 會處理更新 (如果 Python 的 heapq 支援 decrease-key)
                    # Python 的 heapq 不直接支援 decrease-key，但重複添加帶有更新成本的節點，並依賴於 heapq 總是彈出成本最小的那個，
                    # 加上 closed_set 的檢查，可以達到類似效果。
                    # 或者，更嚴格的 A* 實現會移除舊節點或標記為無效。
                    # 簡單起見，我們先依賴 heapq 和 closed_set。
                    if (neighbor_node.x, neighbor_node.y) not in open_set_dict or open_set_dict[(neighbor_node.x, neighbor_node.y)].get_f_cost() > neighbor_node.get_f_cost():
                        heapq.heappush(open_set, (neighbor_node.get_f_cost(), neighbor_node.h_cost, neighbor_node))
                        open_set_dict[(neighbor_node.x, neighbor_node.y)] = neighbor_node
        path = []
        if path_found and final_node:
            temp = final_node
            while temp:
                path.append(temp) # TileNode 物件
                temp = temp.parent
            path.reverse()
            ai_base_log(f"[ASTAR_BASE_SUCCESS] Path found ({len(path)} segments). Example segment: {path[0] if path else 'N/A'}")
        else:
            ai_base_log(f"[ASTAR_BASE_FAIL] No path found from {start_coords} to {target_coords}.")
        return path # 返回 TileNode 物件列表

    def bfs_find_direct_movement_path(self, start_coords, target_coords, max_depth=15, avoid_specific_tile=None): #
        # (從原始 AIController 複製 BFS 演算法的完整實現)
        # ...
        ai_base_log(f"[BFS_BASE] Finding direct path from {start_coords} to {target_coords} (max_depth={max_depth})")
        q = deque([(start_coords, [start_coords])]) # path 存儲的是座標元組
        visited = {start_coords}

        while q:
            (curr_x, curr_y), path = q.popleft()

            if len(path) - 1 > max_depth: # path 長度是節點數，移動步數是 len(path)-1
                continue

            if (curr_x, curr_y) == target_coords:
                ai_base_log(f"[BFS_BASE_SUCCESS] Path found: {path}")
                return path # 返回座標元組列表

            # 隨機化方向的順序，避免 AI 出現固定偏好
            shuffled_directions = list(DIRECTIONS.values())
            random.shuffle(shuffled_directions)

            for dx, dy in shuffled_directions:
                next_x, next_y = curr_x + dx, curr_y + dy
                next_coords = (next_x, next_y)

                if next_coords not in visited:
                    if avoid_specific_tile and next_coords == avoid_specific_tile:
                        continue

                    node = self._get_node_at_coords(next_x, next_y)
                    # 這裡的 is_tile_dangerous 檢查的 future_seconds 應該較小，因為是即時移動
                    if node and node.is_empty_for_direct_movement() and \
                       not self.is_tile_dangerous(next_x, next_y, future_seconds=0.15): # 假設 settings.BFS_MOVE_DANGER_CHECK_SECONDS
                        visited.add(next_coords)
                        q.append((next_coords, path + [next_coords]))
        ai_base_log(f"[BFS_BASE_FAIL] No direct path found from {start_coords} to {target_coords}")
        return [] # 返回空列表


    def set_current_movement_sub_path(self, path_coords_list): #
        # path_coords_list 應該是一個座標元組的列表
        if path_coords_list and len(path_coords_list) >= 1: # 至少包含當前位置
            self.current_movement_sub_path = path_coords_list
            self.current_movement_sub_path_index = 0 # 總是從路徑的第一個點開始（即AI當前位置）
            if len(path_coords_list) == 1 and path_coords_list[0] == self._get_ai_current_tile():
                ai_base_log(f"    Set sub-path of length 1 (AI already at target): {self.current_movement_sub_path}")
            else:
                ai_base_log(f"    Set new movement sub-path: {self.current_movement_sub_path}")
        else:
            self.current_movement_sub_path = []
            self.current_movement_sub_path_index = 0
            ai_base_log("    Cleared sub-path (attempted to set empty or invalid path_coords_list).")


    def execute_next_move_on_sub_path(self, ai_current_tile): #
        # (從原始 AIController 複製此方法的邏輯)
        # ...
        if not self.current_movement_sub_path:
            # ai_base_log("Execute_next_move: No sub-path to execute.")
            return True # 表示子路徑已完成（或不存在）

        # 檢查是否已到達子路徑的最終目標
        if ai_current_tile == self.current_movement_sub_path[-1]:
            ai_base_log(f"    Sub-path target {self.current_movement_sub_path[-1]} reached. Path: {self.current_movement_sub_path}. AI at: {ai_current_tile}")
            self.movement_history.append(ai_current_tile) # 記錄到達目標點
            self.current_movement_sub_path = []
            self.current_movement_sub_path_index = 0
            if hasattr(self.ai_player, 'is_moving'): self.ai_player.is_moving = False # 確保停止動畫
            return True # 子路徑完成

        # 檢查當前索引是否有效
        if self.current_movement_sub_path_index >= len(self.current_movement_sub_path):
            ai_base_log(f"[MOVE_SUB_PATH_ERROR_BASE] Index out of bounds. Path: {self.current_movement_sub_path}, Index: {self.current_movement_sub_path_index}. Clearing.")
            self.current_movement_sub_path = []
            self.current_movement_sub_path_index = 0
            return True # 標記為完成以觸發重新決策

        # 驗證 AI 當前位置是否與子路徑期望的位置一致
        expected_current_sub_path_tile = self.current_movement_sub_path[self.current_movement_sub_path_index]
        if ai_current_tile != expected_current_sub_path_tile:
            ai_base_log(f"[MOVE_SUB_PATH_WARN_BASE] AI at {ai_current_tile} but sub-path expected {expected_current_sub_path_tile} at index {self.current_movement_sub_path_index}. Sub_path: {self.current_movement_sub_path}. Resetting sub-path.")
            self.current_movement_sub_path = []
            self.current_movement_sub_path_index = 0
            return True # 標記為完成以觸發重新決策

        # 如果這是路徑的最後一步（即 AI 已在倒數第二個點，下一步是目標點）
        if self.current_movement_sub_path_index + 1 >= len(self.current_movement_sub_path):
            # 這種情況理論上應該被上面的 `ai_current_tile == self.current_movement_sub_path[-1]` 捕獲
            # 但為了保險起見，如果到了這裡，說明AI還未移動到最後一個點
            ai_base_log(f"[MOVE_SUB_PATH_LOGIC_BASE] AI at {ai_current_tile}, next is final target {self.current_movement_sub_path[-1]}. Path: {self.current_movement_sub_path}")
            # 繼續執行移動到最後一點的邏輯
            pass

        # 獲取子路徑中的下一個目標瓦片
        next_target_tile_in_sub_path = self.current_movement_sub_path[self.current_movement_sub_path_index + 1]
        dx = next_target_tile_in_sub_path[0] - ai_current_tile[0]
        dy = next_target_tile_in_sub_path[1] - ai_current_tile[1]

        # 驗證移動是否是有效的單步移動
        if not (abs(dx) <= 1 and abs(dy) <= 1 and (dx != 0 or dy != 0) and (dx == 0 or dy == 0)):
            ai_base_log(f"[MOVE_SUB_PATH_ERROR_BASE] Invalid step in sub-path from {ai_current_tile} to {next_target_tile_in_sub_path}. Dx={dx}, Dy={dy}. Path: {self.current_movement_sub_path}. Clearing.")
            self.current_movement_sub_path = []
            self.current_movement_sub_path_index = 0
            return True # 標記為完成以觸發重新決策

        # 嘗試移動
        moved = self.ai_player.attempt_move_to_tile(dx, dy) # 假設 Player 有此方法
        if moved:
            moved_to_tile = (self.ai_player.tile_x, self.ai_player.tile_y) # 獲取移動後的實際位置
            self.movement_history.append(moved_to_tile)
            ai_base_log(f"    Sub-path: Moved from {ai_current_tile} to {moved_to_tile}. New index: {self.current_movement_sub_path_index + 1}")
            self.current_movement_sub_path_index += 1
            # 如果移動後到達了子路徑的最終目標
            if moved_to_tile == self.current_movement_sub_path[-1]:
                ai_base_log(f"    Sub-path target {moved_to_tile} reached by move. Path: {self.current_movement_sub_path}.")
                self.current_movement_sub_path = []
                self.current_movement_sub_path_index = 0
                if hasattr(self.ai_player, 'is_moving'): self.ai_player.is_moving = False
                return True # 子路徑完成
            return False # 子路徑仍在執行
        else:
            ai_base_log(f"    Sub-path Move from {ai_current_tile} to {next_target_tile_in_sub_path} FAILED (blocked). Path: {self.current_movement_sub_path}. Clearing sub-path.")
            self.current_movement_sub_path = []
            self.current_movement_sub_path_index = 0
            return True # 標記為完成以觸發重新決策

    def is_bomb_still_active(self, bomb_placed_timestamp): #
        if bomb_placed_timestamp == 0: return False # 從未放置或已重置
        elapsed_time = pygame.time.get_ticks() - bomb_placed_timestamp
        # 確保 BOMB_TIMER 和 EXPLOSION_DURATION 從 settings 獲取
        bomb_timer_duration = getattr(settings, 'BOMB_TIMER', 3000)
        explosion_effect_duration = getattr(settings, 'EXPLOSION_DURATION', 300)
        buffer_time = 200 # 給爆炸效果消失的額外緩衝
        return elapsed_time < (bomb_timer_duration + explosion_effect_duration + buffer_time)

    def reset_state_base(self): # 基礎的重置邏輯
        ai_base_log(f"AIControllerBase reset_state_base for Player ID: {id(self.ai_player)}.")
        self.current_state = "BASE_IDLE" # 或者子類可以覆寫此初始狀態
        self.state_start_time = pygame.time.get_ticks()
        self.astar_planned_path = []
        self.astar_path_current_segment_index = 0
        self.current_movement_sub_path = []
        self.current_movement_sub_path_index = 0
        self.last_bomb_placed_time = 0
        self.ai_just_placed_bomb = False
        self.last_decision_time = pygame.time.get_ticks() - self.ai_decision_interval # 允許立即決策

        current_ai_tile_tuple = self._get_ai_current_tile()
        self.last_known_tile = current_ai_tile_tuple if current_ai_tile_tuple else (-1,-1)
        self.movement_history.clear()
        self.oscillation_stuck_counter = 0
        self.decision_cycle_stuck_counter = 0

    # update 方法留給子類實現具體的狀態機邏輯
    def update(self):
        # 基本的存活檢查和決策時機判斷
        current_time = pygame.time.get_ticks()
        ai_current_tile = self._get_ai_current_tile()

        if not ai_current_tile or not self.ai_player or not self.ai_player.is_alive:
            # self.change_state("BASE_DEAD") # 子類可以定義自己的 DEAD 狀態
            return

        # 通用的卡死檢測邏輯 (可以被子類使用)
        if not self.current_movement_sub_path and \
           not (self.current_state == "TACTICAL_RETREAT_AND_WAIT_OVERRIDE" and self.ai_just_placed_bomb): # 子類需要提供確切的等待狀態名
            if self.last_known_tile == ai_current_tile:
                self.decision_cycle_stuck_counter += 1
            else:
                self.decision_cycle_stuck_counter = 0
        else:
            self.decision_cycle_stuck_counter = 0
        self.last_known_tile = ai_current_tile

        is_oscillating = False
        if len(self.movement_history) == self.movement_history.maxlen:
            # (振盪檢測邏輯複製自原始 AIController)
            # ...
            if self.movement_history[0] == self.movement_history[2] and \
               self.movement_history[1] == self.movement_history[3] and \
               self.movement_history[0] != self.movement_history[1] and \
               ai_current_tile == self.movement_history[3]: # 確保當前位置是振盪模式的最後一個位置
                self.oscillation_stuck_counter += 1
                is_oscillating = True
                ai_base_log(f"[OSCILLATION_DETECT_BASE] Oscillation detected. Count: {self.oscillation_stuck_counter}. History: {list(self.movement_history)}")
            else:
                self.oscillation_stuck_counter = 0 # 只要不符合振盪模式就重置
        else: # 歷史記錄不足以判斷振盪
            self.oscillation_stuck_counter = 0

        # 子類需要在其 update 方法中決定如何使用這些卡死計數器，以及如何觸發重新規劃
        # 例如:
        # stuck_threshold = getattr(settings, "AI_STUCK_THRESHOLD", 5)
        # if self.decision_cycle_stuck_counter >= stuck_threshold or \
        #    self.oscillation_stuck_counter >= getattr(settings, "AI_OSCILLATION_STUCK_THRESHOLD", 3):
        #      self.handle_stuck_situation() # 子類實現此方法

        # 基礎 update 主要處理移動子路徑
        if self.ai_player and hasattr(self.ai_player, 'action_timer') and self.ai_player.action_timer <= 0:
            sub_path_finished_or_failed = False
            if self.current_movement_sub_path:
                sub_path_finished_or_failed = self.execute_next_move_on_sub_path(ai_current_tile)

            if sub_path_finished_or_failed: # 如果子路徑完成或失敗，可能需要立即重新決策
                self.last_decision_time = pygame.time.get_ticks() - self.ai_decision_interval - 1 # 讓決策時鐘立即觸發

            if not self.current_movement_sub_path and hasattr(self.ai_player, 'is_moving'):
                self.ai_player.is_moving = False

        # 實際的狀態處理和決策邏輯由子類覆寫和實現
        pass

    def change_state(self, new_state): # 基礎的狀態改變，子類可以擴展
        if self.current_state != new_state:
            ai_base_log(f"[STATE_CHANGE_BASE] ID: {id(self.ai_player)} From {self.current_state} -> {new_state}")
            self.current_state = new_state
            self.state_start_time = pygame.time.get_ticks()
            # 通用清理：清空當前移動子路徑
            self.current_movement_sub_path = []
            self.current_movement_sub_path_index = 0

    # debug_draw_path 可以先留空，或者只畫最基本的 AI 位置
    def debug_draw_path(self, surface):
        # ai_tile_now = self._get_ai_current_tile()
        # if ai_tile_now and hasattr(settings, 'TILE_SIZE'):
        #     try:
        #         pygame.draw.circle(surface, (0,0,255,100), 
        #                            (ai_tile_now[0] * settings.TILE_SIZE + settings.TILE_SIZE // 2,
        #                             ai_tile_now[1] * settings.TILE_SIZE + settings.TILE_SIZE // 2),
        #                             settings.TILE_SIZE // 4)
        #     except Exception as e:
        #         ai_base_log(f"Error in base debug_draw_path: {e}")
        pass