# oop-2025-proj-pycade/core/ai_conservative.py

import pygame
import settings # 假設 settings.py 包含 AI 行為相關參數
import random
from collections import deque
from .ai_controller_base import AIControllerBase, TileNode, DIRECTIONS, ai_base_log # 從基礎類別匯入

# 為保守型 AI 定義特定的狀態 (如果需要，可以擴展基礎類別的狀態)
# 例如，可以複用基礎類別的狀態名，但在 handle 方法中賦予不同的邏輯
AI_STATE_CONSERVATIVE_IDLE = "CONSERVATIVE_IDLE"
AI_STATE_CONSERVATIVE_EVADING = "CONSERVATIVE_EVADING"
AI_STATE_CONSERVATIVE_SAFE_BOMBING = "CONSERVATIVE_SAFE_BOMBING" # 極度謹慎的轟炸
AI_STATE_CONSERVATIVE_RETREAT = "CONSERVATIVE_RETREAT"
# ... 其他可能需要的狀態

class ConservativeAIController(AIControllerBase):
    def __init__(self, ai_player_sprite, game_instance):
        super().__init__(ai_player_sprite, game_instance)
        ai_base_log(f"ConservativeAIController __init__ for Player ID: {id(ai_player_sprite)}")

        # 保守型 AI 特有的參數或狀態初始化
        self.current_state = AI_STATE_CONSERVATIVE_IDLE # 初始狀態
        self.aggression_level = 0.3 # 非常低的攻擊意願 (0.0 - 1.0)
        self.evasion_urgency_threshold = 0.6 # 危險判斷的閾值，比通用型更敏感 (例如，更長的 future_seconds)
        self.safe_retreat_depth_conservative = getattr(settings, "AI_CONSERVATIVE_RETREAT_DEPTH", 8) # 更深的撤退搜索
        self.min_safe_bombing_retreat_options = getattr(settings, "AI_CONSERVATIVE_MIN_RETREAT_OPTIONS", 3) # 放置炸彈前需要更多安全撤退點

        # 可以覆寫或設定基礎類別中的一些與卡死檢測相關的閾值，使其更不容易卡住或更早放棄困難的路徑
        self.stuck_threshold_decision_cycles_conservative = 3 # 更快判斷為卡住
        self.oscillation_stuck_threshold_conservative = 2


    def reset_state(self): # 或者 reset_state_conservative，如果 game.py 中這樣呼叫
        super().reset_state_base() # 呼叫基礎類別的重置
        self.current_state = AI_STATE_CONSERVATIVE_IDLE
        ai_base_log(f"ConservativeAIController reset_state for Player ID: {id(self.ai_player)}.")
        # 重置保守型特有的狀態
        self.chosen_bombing_spot_coords = None # 從原始 AIController 複製
        self.chosen_retreat_spot_coords = None # 從原始 AIController 複製
        self.target_destructible_wall_node_in_astar = None # 從原始 AIController 複製

    def update(self):
        # 呼叫基礎類別的 update 來處理通用的移動子路徑執行和卡死檢測更新
        # super().update() # 注意：基礎 update 可能會執行移動，如果這裡要完全控制決策，則選擇性呼叫

        current_time = pygame.time.get_ticks()
        ai_current_tile = self._get_ai_current_tile()

        if not ai_current_tile or not self.ai_player or not self.ai_player.is_alive:
            if self.current_state != "DEAD_CONSERVATIVE": # 可以定義自己的 DEAD 狀態
                self.change_state("DEAD_CONSERVATIVE")
            return

        # --- 通用邏輯 (從父類複製或在此處重寫，以適應保守型AI的決策頻率) ---
        # 保險機制：重置 ai_just_placed_bomb 標誌 (這部分邏輯與原 AI 相同)
        if self.ai_just_placed_bomb and self.last_bomb_placed_time > 0:
            time_since_bomb_placed = current_time - self.last_bomb_placed_time
            bomb_clear_timeout = settings.BOMB_TIMER + settings.EXPLOSION_DURATION + 1000
            if time_since_bomb_placed > bomb_clear_timeout:
                ai_base_log(f"[CONSERVATIVE_AI_BOMB_FLAG_RESET_TIMEOUT] ai_just_placed_bomb was True for too long. Forcing reset.")
                self.ai_just_placed_bomb = False
                self.last_bomb_placed_time = 0
        # --- 卡死檢測更新 (與原 AI 類似) ---
        # (這部分已移至 AIControllerBase 的 update，這裡可以選擇是否再次計算或依賴父類)
        # 簡單起見，我們先假設父類的 update 會處理 is_moving 等，這裡專注決策
        if not self.current_movement_sub_path and \
           not (self.current_state == AI_STATE_CONSERVATIVE_RETREAT and self.ai_just_placed_bomb): # 注意狀態名
            if self.last_known_tile == ai_current_tile:
                self.decision_cycle_stuck_counter += 1
            else:
                self.decision_cycle_stuck_counter = 0
        else:
            self.decision_cycle_stuck_counter = 0
        self.last_known_tile = ai_current_tile

        is_oscillating = False
        if len(self.movement_history) == self.movement_history.maxlen:
            if self.movement_history[0] == self.movement_history[2] and \
               self.movement_history[1] == self.movement_history[3] and \
               self.movement_history[0] != self.movement_history[1] and \
               ai_current_tile == self.movement_history[3]:
                self.oscillation_stuck_counter += 1
                is_oscillating = True
            else:
                self.oscillation_stuck_counter = 0
        else:
            self.oscillation_stuck_counter = 0
        # --- 卡死檢測結束 ---

        # 決策時機判斷
        is_decision_time = (current_time - self.last_decision_time >= self.ai_decision_interval)
        is_urgent_evasion = self.is_tile_dangerous(ai_current_tile[0], ai_current_tile[1], future_seconds=self.evasion_urgency_threshold) # 更敏感的危險偵測

        if is_urgent_evasion and self.current_state != AI_STATE_CONSERVATIVE_EVADING:
            ai_base_log(f"[CONSERVATIVE_AI_DANGER] AI at {ai_current_tile} is in DANGER! Switching to EVADING.")
            self.change_state(AI_STATE_CONSERVATIVE_EVADING)
            self.last_decision_time = current_time # 立即重新決策
            # 在 EVADING 狀態下，決策間隔可以縮短

        if is_decision_time or self.current_state == AI_STATE_CONSERVATIVE_EVADING:
            if self.current_state != AI_STATE_CONSERVATIVE_EVADING: # 正常決策週期
                 self.last_decision_time = current_time

            # 卡住或振盪達到閾值，則強制重新規劃 (保守型可能更傾向於放棄當前目標並尋找安全)
            stuck_by_single_tile = self.decision_cycle_stuck_counter >= self.stuck_threshold_decision_cycles_conservative
            stuck_by_oscillation = self.oscillation_stuck_counter >= self.oscillation_stuck_threshold_conservative
            if stuck_by_single_tile or stuck_by_oscillation:
                log_msg = "[CONSERVATIVE_AI_STUCK]"
                if stuck_by_oscillation: log_msg += f" Oscillation at {ai_current_tile}."
                else: log_msg += f" Stuck at {ai_current_tile} for {self.decision_cycle_stuck_counter} cycles."
                ai_base_log(log_msg + " Forcing to IDLE/SAFE state.")
                self.decision_cycle_stuck_counter = 0
                self.oscillation_stuck_counter = 0
                self.movement_history.clear()
                self.current_movement_sub_path = [] # 清空子路徑
                self.change_state(AI_STATE_CONSERVATIVE_IDLE) # 卡住時，保守型 AI 可能會先回到閒置/尋找安全狀態
                # 立即處理新狀態
                # return # 避免後續的移動執行干擾 (或者讓新的狀態處理邏輯在同一個 update tick 中執行)


            # --- 狀態處理邏輯 ---
            if self.current_state == AI_STATE_CONSERVATIVE_EVADING:
                self.handle_evading_danger_state(ai_current_tile)
            elif self.current_state == AI_STATE_CONSERVATIVE_IDLE:
                self.handle_idle_state(ai_current_tile)
            elif self.current_state == AI_STATE_CONSERVATIVE_SAFE_BOMBING:
                self.handle_safe_bombing_state(ai_current_tile)
            elif self.current_state == AI_STATE_CONSERVATIVE_RETREAT:
                self.handle_retreat_state(ai_current_tile)
            # ... 其他保守型 AI 的狀態處理
            else:
                ai_base_log(f"[CONSERVATIVE_AI_WARN] Unknown state: {self.current_state}. Defaulting to IDLE.")
                self.change_state(AI_STATE_CONSERVATIVE_IDLE)

        # --- 移動子路徑執行 (如果父類的 update 不執行這個，或者你想更精細控制) ---
        # 這部分邏輯已在父類 AIControllerBase 的 update 方法中，理論上不需要重複
        # 但如果子類需要更特殊的移動處理或時機，可以在這裡覆寫或擴展
        if self.ai_player.action_timer <= 0: # 確保 AI 當前不是在執行移動動畫
            sub_path_finished_or_failed = False
            if self.current_movement_sub_path:
                sub_path_finished_or_failed = self.execute_next_move_on_sub_path(ai_current_tile)

            if sub_path_finished_or_failed: # 如果子路徑完成或失敗
                # 保守型 AI 在子路徑完成後，可能不會立即進行下一個決策，而是重新評估周圍環境
                self.last_decision_time = pygame.time.get_ticks() - self.ai_decision_interval - 1 # 允許下個 tick 重新決策

            if not self.current_movement_sub_path: # 如果沒有子路徑了
                self.ai_player.is_moving = False


    def handle_idle_state(self, ai_current_tile):
        ai_base_log(f"[CONSERVATIVE_AI_IDLE] at {ai_current_tile}. Assessing situation.")
        # 1. 檢查自身是否安全，不安全則立刻轉到 EVADING
        if self.is_tile_dangerous(ai_current_tile[0], ai_current_tile[1], future_seconds=self.evasion_urgency_threshold * 1.5): # 更長遠的預判
            self.change_state(AI_STATE_CONSERVATIVE_EVADING)
            return

        # 2. 尋找一個更安全的位置移動 (如果當前位置不夠好，例如太開闊或靠近潛在危險源)
        #    可以使用 find_safe_tiles_nearby_for_retreat 但目標是找到一個"更優"的安全點，而不僅僅是躲避特定炸彈

        # 3. 非常謹慎地考慮是否需要攻擊或炸牆
        #    只有在極端有利或必要時才行動
        human_pos = self._get_human_player_current_tile()
        if human_pos and random.random() < self.aggression_level / 5: # 極低的機率考慮攻擊
             # 檢查是否可以進行一次非常安全的攻擊 (例如玩家被困)
             # ... (這裡可以加入類似原 AI engage player 的邏輯，但條件非常苛刻)
             pass

        # 4. 如果無事可做，可以小範圍隨機安全移動，或者尋找一個角落待著
        if not self.current_movement_sub_path: # 確保沒有正在執行的移動
            safe_random_moves = []
            for dx, dy in DIRECTIONS.values():
                next_x, next_y = ai_current_tile[0] + dx, ai_current_tile[1] + dy
                node = self._get_node_at_coords(next_x, next_y)
                if node and node.is_empty_for_direct_movement() and \
                   not self.is_tile_dangerous(next_x, next_y, future_seconds=self.evasion_urgency_threshold * 2):
                    safe_random_moves.append((next_x, next_y))

            if safe_random_moves:
                target_move = random.choice(safe_random_moves)
                self.set_current_movement_sub_path([ai_current_tile, target_move])
                ai_base_log(f"    [CONSERVATIVE_IDLE] Making a safe random move to {target_move}")
            else:
                ai_base_log(f"    [CONSERVATIVE_IDLE] No safe random moves. Staying put.")
                self.ai_player.is_moving = False # 確保動畫停止

    def handle_evading_danger_state(self, ai_current_tile):
        ai_base_log(f"[CONSERVATIVE_AI_EVADE] at {ai_current_tile}")
        # 檢查是否仍然危險
        if not self.is_tile_dangerous(ai_current_tile[0], ai_current_tile[1], future_seconds=self.evasion_urgency_threshold):
            ai_base_log(f"    [CONSERVATIVE_EVADE] Tile {ai_current_tile} now considered safe. Switching to IDLE.")
            self.current_movement_sub_path = [] # 清空之前的逃跑路徑
            self.change_state(AI_STATE_CONSERVATIVE_IDLE)
            return

        # 如果沒有逃跑路徑，或者當前逃跑路徑的目標點也變得危險，則重新尋找
        path_target_is_dangerous = False
        if self.current_movement_sub_path and len(self.current_movement_sub_path) > 0 :
            final_target_in_sub_path = self.current_movement_sub_path[-1]
            if self.is_tile_dangerous(final_target_in_sub_path[0], final_target_in_sub_path[1], future_seconds=0.1): # 短期預測目標點
                 path_target_is_dangerous = True
                 ai_base_log(f"    [CONSERVATIVE_EVADE] Current sub-path target {final_target_in_sub_path} is also dangerous. Re-planning evasion.")


        if not self.current_movement_sub_path or \
           (self.current_movement_sub_path and ai_current_tile == self.current_movement_sub_path[-1]) or \
           path_target_is_dangerous:

            ai_base_log("    [CONSERVATIVE_EVADE] Finding new evasion path.")
            # 使用基礎類別的 find_safe_tiles_nearby_for_retreat，但可能使用更嚴格的參數
            # bomb_range 0 表示一般性危險，不針對特定自己放的炸彈
            safe_options_coords = self.find_safe_tiles_nearby_for_retreat_conservative(ai_current_tile, ai_current_tile, 0, max_depth=self.safe_retreat_depth_conservative)

            best_evasion_path_coords = []
            if safe_options_coords:
                # 優先選擇最近的安全點
                for safe_spot_coord in safe_options_coords: # find_safe_tiles_nearby_for_retreat 應該已經排序過
                    evasion_path_tuples = self.bfs_find_direct_movement_path(ai_current_tile, safe_spot_coord, max_depth=self.safe_retreat_depth_conservative)
                    if evasion_path_tuples and len(evasion_path_tuples) > 1: # 確保不是原地踏步
                        best_evasion_path_coords = evasion_path_tuples
                        break # 找到第一個可達的安全點路徑就用它

            if best_evasion_path_coords:
                self.set_current_movement_sub_path(best_evasion_path_coords)
                ai_base_log(f"    [CONSERVATIVE_EVADE] New evasion sub-path set: {best_evasion_path_coords}")
            else:
                ai_base_log("    [CONSERVATIVE_EVADE] CRITICAL: Cannot find ANY safe evasion path! AI may be trapped.")
                self.current_movement_sub_path = [] # 清空路徑
                self.ai_player.is_moving = False # 停止移動動畫
                # 在這種情況下，AI 可能會原地不動，等待運氣或死亡

    # (保守型 AI 可能很少進入此狀態，或者此狀態的邏輯會非常謹慎)
    def handle_safe_bombing_state(self, ai_current_tile):
        ai_base_log(f"[CONSERVATIVE_AI_SAFE_BOMBING] at {ai_current_tile}.")
        # 類似原始 AI 的 EXECUTING_PATH_CLEARANCE 或 ENGAGING_PLAYER 中的放置炸彈邏輯
        # 但條件更嚴格：
        # 1. 只有在目標 (牆壁或被困的玩家) 價值很高時才考慮
        # 2. 必須有多個非常安全的撤退點
        # 3. 放置炸彈本身不能讓自己立即陷入危險
        # ... (此處省略詳細實現，可以參考原始 AI 的 _find_optimal_bombing_and_retreat_spot 和 can_place_bomb_and_retreat，但要調整參數)

        # 如果決定放置炸彈:
        # self.ai_player.place_bomb()
        # self.ai_just_placed_bomb = True
        # self.last_bomb_placed_time = pygame.time.get_ticks()
        # # 設定撤退路徑
        # self.set_current_movement_sub_path(pathToRetreat)
        # self.change_state(AI_STATE_CONSERVATIVE_RETREAT)
        # return

        # 如果不滿足轟炸條件，則轉回 IDLE
        ai_base_log("    [CONSERVATIVE_SAFE_BOMBING] Conditions not met for safe bombing. Reverting to IDLE.")
        self.change_state(AI_STATE_CONSERVATIVE_IDLE)


    def handle_retreat_state(self, ai_current_tile):
        ai_base_log(f"[CONSERVATIVE_AI_RETREAT] at {ai_current_tile}. Target: {self.chosen_retreat_spot_coords}")
        # 此邏輯與原始 AIController 的 TACTICAL_RETREAT_AND_WAIT 非常相似
        if self.current_movement_sub_path: # 仍在執行撤退子路徑
            ai_base_log("    Still executing retreat sub-path.")
            return

        if ai_current_tile == self.chosen_retreat_spot_coords:
            ai_base_log(f"    AI at chosen retreat spot {self.chosen_retreat_spot_coords}. Waiting for bomb to clear.")
            if not self.is_bomb_still_active(self.last_bomb_placed_time):
                ai_base_log(f"      Bomb (placed at {self.last_bomb_placed_time}) has cleared.")
                self.ai_just_placed_bomb = False
                self.chosen_bombing_spot_coords = None
                self.chosen_retreat_spot_coords = None
                # 炸彈清除後，保守型 AI 會回到 IDLE 狀態重新評估
                self.change_state(AI_STATE_CONSERVATIVE_IDLE)
            else:
                ai_base_log(f"      Bomb still active. Waiting at {self.chosen_retreat_spot_coords}.")
        else: # 未到達預期撤退點，但子路徑已空 (可能被中斷或初始路徑失敗)
            ai_base_log(f"    Not at chosen retreat spot {self.chosen_retreat_spot_coords} AND no sub-path. Re-pathing to retreat spot.")
            if self.chosen_retreat_spot_coords:
                retreat_path_tuples = self.bfs_find_direct_movement_path(ai_current_tile, self.chosen_retreat_spot_coords, max_depth=self.safe_retreat_depth_conservative)
                if retreat_path_tuples and len(retreat_path_tuples) > 1:
                    self.set_current_movement_sub_path(retreat_path_tuples)
                else: # 無法路徑到預期撤退點
                    ai_base_log(f"      [CONSERVATIVE_RETREAT_CRITICAL] Cannot BFS to chosen retreat spot {self.chosen_retreat_spot_coords}! Bomb placed. Switching to EVADING.")
                    self.change_state(AI_STATE_CONSERVATIVE_EVADING) # 緊急躲避
            else: # 沒有設定撤退點，這是一個邏輯錯誤，應該轉到更安全的狀態
                ai_base_log(f"    [CONSERVATIVE_RETREAT_ERROR] No chosen_retreat_spot defined. Switching to EVADING.")
                self.change_state(AI_STATE_CONSERVATIVE_EVADING)

    # 保守型 AI 特有的尋找安全點方法，可能比基礎類別的更嚴格
    def find_safe_tiles_nearby_for_retreat_conservative(self, from_tile_coords, bomb_just_placed_at_coords, bomb_range, max_depth=8, future_seconds_multiplier=1.5):
        ai_base_log(f"    [CONSERVATIVE_RETREAT_FINDER] from_tile={from_tile_coords}, bomb_at={bomb_just_placed_at_coords}, range={bomb_range}, depth={max_depth}")
        q = deque([(from_tile_coords, [from_tile_coords], 0)])
        visited = {from_tile_coords}
        safe_retreat_spots = []

        danger_check_future_seconds = settings.AI_RETREAT_SPOT_OTHER_DANGER_FUTURE_SECONDS * future_seconds_multiplier

        while q:
            (curr_x, curr_y), path, depth = q.popleft()

            if depth > max_depth:
                continue

            is_safe_from_this_bomb = True # 如果 bomb_range 是 0 (一般躲避)，則此項為 True
            if bomb_range > 0 : # 僅當是躲避特定炸彈時才檢查
                is_safe_from_this_bomb = not self._is_tile_in_hypothetical_blast(curr_x, curr_y, bomb_just_placed_at_coords[0], bomb_just_placed_at_coords[1], bomb_range)

            is_safe_from_other_dangers = not self.is_tile_dangerous(curr_x, curr_y, future_seconds=danger_check_future_seconds)

            if is_safe_from_this_bomb and is_safe_from_other_dangers:
                safe_retreat_spots.append({'coords': (curr_x, curr_y), 'path_len': len(path) -1, 'depth': depth})
                if len(safe_retreat_spots) >= 15: # 尋找更多選項
                    break

            if depth < max_depth:
                shuffled_directions = list(DIRECTIONS.values()); random.shuffle(shuffled_directions)
                for dx, dy in shuffled_directions:
                    next_x, next_y = curr_x + dx, curr_y + dy
                    if (next_x, next_y) not in visited:
                        node = self._get_node_at_coords(next_x, next_y)
                        if node and node.is_empty_for_direct_movement():
                            # 預檢查下一步是否會立即進入危險 (短期預判)
                            if not self.is_tile_dangerous(next_x, next_y, future_seconds=0.1):
                                visited.add((next_x, next_y))
                                q.append(((next_x, next_y), path + [(next_x, next_y)], depth + 1))

        if safe_retreat_spots:
            # 保守型 AI 可能更喜歡 "更深" (更遠離起始點) 且路徑也較長的安全點
            safe_retreat_spots.sort(key=lambda x: (-x['depth'], x['path_len'])) # 優先深度，其次路徑長度
            return [spot['coords'] for spot in safe_retreat_spots]
        return []
    
    def debug_draw_path(self, surface):
        # 首先，呼叫父類別的 debug_draw_path (如果它包含了通用的繪圖邏輯)
        # 如果父類別的 debug_draw_path 是空的，或者您想完全自訂，則可以不呼叫 super()
        # 假設 AIControllerBase 已經繪製了 astar_planned_path, current_movement_sub_path 等基礎路徑
        # 我們可以調整其繪製的顏色，或者在這裡重新繪製以使用保守型特定的顏色
        
        ai_tile_now = self._get_ai_current_tile()
        if not ai_tile_now or not self.ai_player or not self.ai_player.is_alive:
            return

        try:
            tile_size = settings.TILE_SIZE
            half_tile = tile_size // 2

            # --- 1. 重新繪製或調整基礎路徑的視覺效果 (可選) ---
            # 如果希望保守型的路徑顏色不同，可以在這裡覆蓋父類的繪製
            # 或者在父類中提供顏色參數

            # 繪製 A* 規劃路徑 (如果存在且需要顯示)
            # (這段邏輯與您原始 AIController 中的 debug_draw_path 相似)
            show_long_term_strategic_elements_conservative = (
                self.current_state == AI_STATE_CONSERVATIVE_IDLE or
                (hasattr(self, 'target_destructible_wall_node_in_astar') and self.target_destructible_wall_node_in_astar is not None) or # 如果保守型有炸牆目標
                (hasattr(self, 'player_initial_spawn_tile') and self.astar_planned_path and len(self.astar_planned_path) > 0 and self.astar_planned_path[-1].x == self.player_initial_spawn_tile[0] and self.astar_planned_path[-1].y == self.player_initial_spawn_tile[1]) # 如果目標是玩家出生點
            )

            if show_long_term_strategic_elements_conservative and self.astar_planned_path and \
               self.astar_path_current_segment_index < len(self.astar_planned_path):
                astar_points_to_draw = [(ai_tile_now[0] * tile_size + half_tile, ai_tile_now[1] * tile_size + half_tile)]
                current_astar_target_pixel_pos = None
                for i in range(self.astar_path_current_segment_index, len(self.astar_planned_path)):
                    node = self.astar_planned_path[i]
                    px, py = node.x * tile_size + half_tile, node.y * tile_size + half_tile
                    astar_points_to_draw.append((px, py))
                    if i == self.astar_path_current_segment_index:
                        current_astar_target_pixel_pos = (px, py)
                
                if len(astar_points_to_draw) > 1:
                    # 保守型 A* 路徑用不同顏色，例如深藍色
                    for i in range(len(astar_points_to_draw) - 1):
                        # 虛線效果
                        if i % 2 == 0 : pygame.draw.aaline(surface, (0, 0, 139, 180), astar_points_to_draw[i], astar_points_to_draw[i+1], True) # 深藍色
                
                if current_astar_target_pixel_pos:
                    pygame.draw.circle(surface, (0, 100, 200, 200), current_astar_target_pixel_pos, tile_size // 3, 2) # 標記 A* 的下一個主要目標點


            # 繪製當前移動子路徑 (如果存在)
            # (這段邏輯與您原始 AIController 中的 debug_draw_path 相似)
            if self.current_movement_sub_path and len(self.current_movement_sub_path) > 1 and \
               self.current_movement_sub_path_index < len(self.current_movement_sub_path) -1 :
                sub_path_points_to_draw = [(ai_tile_now[0] * tile_size + half_tile, ai_tile_now[1] * tile_size + half_tile)]
                for i in range(self.current_movement_sub_path_index + 1, len(self.current_movement_sub_path)):
                    tile_coords = self.current_movement_sub_path[i]
                    px, py = tile_coords[0] * tile_size + half_tile, tile_coords[1] * tile_size + half_tile
                    sub_path_points_to_draw.append((px,py))
                
                if len(sub_path_points_to_draw) > 1:
                    # 保守型子路徑用不同顏色，例如綠色 (代表安全移動)
                    color_sub_path = (0, 180, 0, 200) # 綠色
                    if self.current_state == AI_STATE_CONSERVATIVE_EVADING:
                        color_sub_path = (255,165,0, 220) # 逃跑時用橙色
                    pygame.draw.aalines(surface, color_sub_path, False, sub_path_points_to_draw, True)
                    
                    next_sub_step_coords = self.current_movement_sub_path[self.current_movement_sub_path_index + 1]
                    next_px, next_py = next_sub_step_coords[0] * tile_size + half_tile, next_sub_step_coords[1] * tile_size + half_tile
                    pulse_factor = abs(pygame.time.get_ticks() % 800 - 400) / 400 # 脈衝慢一點
                    radius = int(tile_size // 6 + pulse_factor * (tile_size//12))
                    pygame.draw.circle(surface, color_sub_path, (next_px, next_py), radius, 0)


            # --- 2. 保守型 AI 特有的視覺化元素 ---

            # 標記感知到的"高度"危險格子 (比 is_tile_dangerous 更敏感或更長遠的預判)
            # 這部分可以根據 ConservativeAIController 內部的危險評估邏輯來繪製
            # 例如，如果它有一個 "imminent_danger_tiles" 列表
            if hasattr(self, 'evasion_urgency_threshold'): # 假設保守型有此屬性
                for r_offset in range(-4, 5): # 檢查更大範圍
                    for c_offset in range(-4, 5):
                        check_x, check_y = ai_tile_now[0] + c_offset, ai_tile_now[1] + r_offset
                        if 0 <= check_x < self.map_manager.tile_width and 0 <= check_y < self.map_manager.tile_height:
                            # 使用保守型AI更敏感的危險判斷標準
                            if self.is_tile_dangerous(check_x, check_y, future_seconds=self.evasion_urgency_threshold):
                                rect_high_danger = pygame.Rect(check_x * tile_size, check_y * tile_size, tile_size, tile_size)
                                s_high_danger = pygame.Surface((tile_size, tile_size), pygame.SRCALPHA)
                                s_high_danger.fill((255, 0, 0, 70)) # 更深的紅色半透明
                                surface.blit(s_high_danger, rect_high_danger.topleft)
                                # 可以在格子中間畫一個小叉叉
                                pygame.draw.line(surface, (139,0,0, 100), rect_high_danger.topleft, rect_high_danger.bottomright, 1)
                                pygame.draw.line(surface, (139,0,0, 100), rect_high_danger.topright, rect_high_danger.bottomleft, 1)


            # 標記選擇的撤退點 (如果正在撤退或剛放置炸彈)
            # (這段邏輯與您原始 AIController 中的 debug_draw_path 相似，但顏色可以調整)
            if hasattr(self, 'chosen_retreat_spot_coords') and self.chosen_retreat_spot_coords and \
               (self.current_state == AI_STATE_CONSERVATIVE_RETREAT or (hasattr(self,'ai_just_placed_bomb') and self.ai_just_placed_bomb)):
                rx, ry = self.chosen_retreat_spot_coords
                rect_retreat = pygame.Rect(rx * tile_size + 2, ry * tile_size + 2, tile_size - 4, tile_size - 4) # 稍微小一點的框
                s_retreat_conservative = pygame.Surface((tile_size-4, tile_size-4), pygame.SRCALPHA)
                s_retreat_conservative.fill((0, 255, 0, 100)) # 淺綠色半透明代表安全目標
                surface.blit(s_retreat_conservative, (rect_retreat.x, rect_retreat.y))
                pygame.draw.rect(surface, (0, 128, 0, 180), rect_retreat, 2) # 深綠色邊框


            # 標記選擇的轟炸點 (如果保守型 AI 罕見地決定轟炸)
            # (這段邏輯與您原始 AIController 中的 debug_draw_path 相似)
            if hasattr(self, 'chosen_bombing_spot_coords') and self.chosen_bombing_spot_coords and \
               (self.current_state == AI_STATE_CONSERVATIVE_SAFE_BOMBING or \
                ( (self.current_movement_sub_path and self.current_movement_sub_path[-1] == self.chosen_bombing_spot_coords) or \
                  ai_tile_now == self.chosen_bombing_spot_coords ) ) : # 確保目標是這個轟炸點
                bx, by = self.chosen_bombing_spot_coords
                center_bx, center_by = bx * tile_size + half_tile, by * tile_size + half_tile
                # 保守型的轟炸點標記可以不那麼顯眼
                pygame.draw.circle(surface, (255, 100, 0, 150), (center_bx, center_by), tile_size // 4, 2) # 橙色細圓圈
                # 可以畫一個小標靶圖案
                pygame.draw.line(surface, (200,80,0,150), (center_bx - tile_size//3, center_by), (center_bx + tile_size//3, center_by), 1)
                pygame.draw.line(surface, (200,80,0,150), (center_bx, center_by - tile_size//3), (center_bx, center_by + tile_size//3), 1)

            # 標記目標可破壞牆壁 (如果保守型 AI 決定炸牆)
            # (這段邏輯與您原始 AIController 中的 debug_draw_path 相似)
            if hasattr(self, 'target_destructible_wall_node_in_astar') and self.target_destructible_wall_node_in_astar and \
               self.current_state == AI_STATE_CONSERVATIVE_SAFE_BOMBING: # 假設炸牆也在這個狀態下
                wall_node = self.target_destructible_wall_node_in_astar
                wall_rect = pygame.Rect(wall_node.x * tile_size, wall_node.y * tile_size, tile_size, tile_size)
                pulse_factor_wall = abs(pygame.time.get_ticks() % 700 - 350) / 350 # 脈衝更慢
                alpha_wall = int(100 + pulse_factor_wall * 80)
                thickness_wall = 1 + int(pulse_factor_wall * 1) # 更細的框
                s_wall_conservative = pygame.Surface((tile_size, tile_size), pygame.SRCALPHA)
                pygame.draw.rect(s_wall_conservative, (200, 200, 0, alpha_wall), (0,0,tile_size,tile_size), thickness_wall) # 暗黃色
                surface.blit(s_wall_conservative, (wall_rect.x, wall_rect.y))

        except AttributeError as e:
            # 避免因為 settings.TILE_SIZE 還沒準備好等問題導致崩潰
            if 'TILE_SIZE' in str(e) or 'game' in str(e) or 'map_manager' in str(e): # 常見的初始化問題
                pass # 在遊戲剛開始，資源尚未完全加載時，可以忽略
            else:
                ai_base_log(f"ConservativeAI Debug Draw AttributeError: {e}")
        except Exception as e:
            ai_base_log(f"Error during ConservativeAI debug_draw_path: {e}")