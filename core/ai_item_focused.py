# oop-2025-proj-pycade/core/ai_item_focused.py

import pygame
import settings # 假設 settings.py 包含 AI 行為相關參數
import random
from .ai_controller_base import AIControllerBase, TileNode, DIRECTIONS, ai_base_log # 從基礎類別匯入
# 假設 Item 類別可以從 sprites.item 匯入，用於判斷道具類型等
from sprites.item import Item # 根據您的專案結構調整

# 道具優先型 AI 的狀態
AI_STATE_ITEM_SCANNING = "ITEM_SCANNING" # 掃描地圖尋找道具
AI_STATE_ITEM_PLANNING_PATH = "ITEM_PLANNING_PATH" # 規劃到目標道具的路徑
AI_STATE_ITEM_MOVING_TO_TARGET = "ITEM_MOVING_TO_TARGET" # 正在前往道具
AI_STATE_ITEM_NO_TARGET_IDLE = "ITEM_NO_TARGET_IDLE" # 沒有道具目標時的閒置/安全巡邏
AI_STATE_ITEM_EVADING = "ITEM_EVADING" # 躲避危險 (與其他 AI 類似，但可能因道具目標而調整)
AI_STATE_ITEM_RETREAT_AFTER_BOMB = "ITEM_RETREAT_AFTER_BOMB" # 如果為了拿道具而放炸彈後的撤退

class ItemFocusedAIController(AIControllerBase):
    def __init__(self, ai_player_sprite, game_instance):
        super().__init__(ai_player_sprite, game_instance)
        ai_base_log(f"ItemFocusedAIController __init__ for Player ID: {id(ai_player_sprite)}")

        self.current_state = AI_STATE_ITEM_SCANNING
        self.item_priority_threshold = getattr(settings, "AI_ITEM_PRIORITY_THRESHOLD", 0.5) # 道具吸引力閾值
        self.max_item_search_depth_astar = getattr(settings, "AI_ITEM_ASTAR_DEPTH", 20) # A*搜索道具的最大深度
        self.max_item_search_depth_bfs = getattr(settings, "AI_ITEM_BFS_DEPTH", 10) # BFS 搜索道具的最大深度

        self.current_target_item = None # (item_sprite, item_tile_coords)
        self.last_scan_time = 0
        self.scan_interval = getattr(settings, "AI_ITEM_SCAN_INTERVAL", 2000) # 每隔多久重新掃描一次道具 (毫秒)

        # 卡死檢測參數可以有自己的設定
        self.stuck_threshold_decision_cycles_item = getattr(settings, "AI_ITEM_STUCK_CYCLES", 5)
        self.oscillation_stuck_threshold_item = getattr(settings, "AI_ITEM_OSCILLATION_CYCLES", 3)


    def reset_state(self): # 或 reset_state_item_focused
        super().reset_state_base()
        self.current_state = AI_STATE_ITEM_SCANNING
        ai_base_log(f"ItemFocusedAIController reset_state for Player ID: {id(self.ai_player)}.")
        self.current_target_item = None
        self.last_scan_time = 0 # 確保重置後立即掃描
        self.chosen_bombing_spot_coords = None
        self.chosen_retreat_spot_coords = None
        self.target_destructible_wall_node_in_astar = None


    def update(self):
        current_time = pygame.time.get_ticks()
        ai_current_tile = self._get_ai_current_tile()

        if not ai_current_tile or not self.ai_player or not self.ai_player.is_alive:
            if self.current_state != "DEAD_ITEM_FOCUSED":
                self.change_state("DEAD_ITEM_FOCUSED")
            return

        # --- 卡死檢測更新 (與其他 AI 類似) ---
        if not self.current_movement_sub_path and \
           not (self.current_state == AI_STATE_ITEM_RETREAT_AFTER_BOMB and self.ai_just_placed_bomb):
            if self.last_known_tile == ai_current_tile:
                self.decision_cycle_stuck_counter += 1
            else:
                self.decision_cycle_stuck_counter = 0
        else:
            self.decision_cycle_stuck_counter = 0
        self.last_known_tile = ai_current_tile
        # (振盪檢測邏輯...)
        is_oscillating = False # 假設的振盪檢測結果
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

        is_decision_time = (current_time - self.last_decision_time >= self.ai_decision_interval)
        is_immediately_dangerous = self.is_tile_dangerous(ai_current_tile[0], ai_current_tile[1], future_seconds=0.25) # 道具型也需要快速反應危險

        if is_immediately_dangerous and self.current_state != AI_STATE_ITEM_EVADING:
            ai_base_log(f"[ITEM_AI_DANGER] AI at {ai_current_tile} is in IMMEDIATE DANGER! Switching to EVADING.")
            # 如果正在追逐道具，可能需要暫時放棄
            # self.current_target_item = None # 或者不清空，等安全了再繼續
            # self.astar_planned_path = []
            self.change_state(AI_STATE_ITEM_EVADING)
            self.last_decision_time = current_time

        if is_decision_time or self.current_state == AI_STATE_ITEM_EVADING or \
           (self.current_state == AI_STATE_ITEM_SCANNING and current_time - self.last_scan_time > self.scan_interval): # 定期掃描

            if self.current_state != AI_STATE_ITEM_EVADING:
                self.last_decision_time = current_time

            if self.current_state == AI_STATE_ITEM_SCANNING and current_time - self.last_scan_time > self.scan_interval:
                self.last_scan_time = current_time # 更新掃描時間

            stuck_by_single_tile = self.decision_cycle_stuck_counter >= self.stuck_threshold_decision_cycles_item
            stuck_by_oscillation = self.oscillation_stuck_counter >= self.oscillation_stuck_threshold_item
            if stuck_by_single_tile or stuck_by_oscillation:
                log_msg = "[ITEM_AI_STUCK]"
                # (與其他AI類似的卡死日誌和處理)
                ai_base_log(log_msg + " Clearing target item and re-scanning.")
                self.decision_cycle_stuck_counter = 0; self.oscillation_stuck_counter = 0
                self.movement_history.clear(); self.current_movement_sub_path = []
                self.current_target_item = None; self.astar_planned_path = []
                self.change_state(AI_STATE_ITEM_SCANNING) # 卡住時，重新掃描道具

            # --- 狀態處理邏輯 ---
            if self.current_state == AI_STATE_ITEM_EVADING:
                self.handle_evading_danger_state(ai_current_tile)
            elif self.current_state == AI_STATE_ITEM_SCANNING:
                self.handle_scanning_state(ai_current_tile)
            elif self.current_state == AI_STATE_ITEM_PLANNING_PATH:
                self.handle_planning_path_state(ai_current_tile)
            elif self.current_state == AI_STATE_ITEM_MOVING_TO_TARGET:
                self.handle_moving_to_target_state(ai_current_tile)
            elif self.current_state == AI_STATE_ITEM_NO_TARGET_IDLE:
                self.handle_no_target_idle_state(ai_current_tile)
            elif self.current_state == AI_STATE_ITEM_RETREAT_AFTER_BOMB:
                self.handle_retreat_after_bomb_state(ai_current_tile)
            # ... 其他可能需要的狀態
            else:
                ai_base_log(f"[ITEM_AI_WARN] Unknown state: {self.current_state}. Defaulting to SCANNING.")
                self.change_state(AI_STATE_ITEM_SCANNING)

        # --- 移動子路徑執行 ---
        if self.ai_player.action_timer <= 0:
            sub_path_finished_or_failed = False
            if self.current_movement_sub_path:
                sub_path_finished_or_failed = self.execute_next_move_on_sub_path(ai_current_tile)

            if sub_path_finished_or_failed:
                self.last_decision_time = pygame.time.get_ticks() - self.ai_decision_interval - 1
                # 如果子路徑完成（例如到達道具前一格，或炸牆點），需要根據當前狀態決定下一步
                if self.current_state == AI_STATE_ITEM_MOVING_TO_TARGET and self.current_target_item:
                    if ai_current_tile == self.current_target_item[1]: # 已到達道具位置
                        ai_base_log(f"    Reached item target {self.current_target_item[0].type} at {ai_current_tile}. Item should be collected by game logic.")
                        self.current_target_item = None # 清除目標
                        self.astar_planned_path = []
                        self.change_state(AI_STATE_ITEM_SCANNING) # 重新掃描
                    # else: # 可能子路徑是到某個中間點，例如炸牆點
                      # handle_moving_to_target_state 內部會處理
                elif self.current_state == AI_STATE_ITEM_RETREAT_AFTER_BOMB:
                    # 撤退完成後，檢查炸彈是否清除，然後重新掃描
                    if ai_current_tile == self.chosen_retreat_spot_coords:
                         self.handle_retreat_after_bomb_state(ai_current_tile) # 讓狀態處理函式決定下一步
                    else: # 撤退路徑中斷
                         self.change_state(AI_STATE_ITEM_EVADING)


            if not self.current_movement_sub_path:
                self.ai_player.is_moving = False

    def _evaluate_item_value(self, item_sprite):
        # 根據道具類型和 AI 當前狀態給道具評分
        # 這是核心的道具優先邏輯
        if not item_sprite or not hasattr(item_sprite, 'type'):
            return 0

        item_type = item_sprite.type
        base_value = 0
        # 假設 settings.py 有 ITEM_TYPE_* 的定義
        if item_type == settings.ITEM_TYPE_BOMB_CAPACITY:
            # 如果炸彈容量未滿，則價值較高
            if self.ai_player.max_bombs < getattr(settings, "MAX_POSSIBLE_BOMBS", 5): # 假設有個最大上限
                base_value = 80
            else:
                base_value = 10 # 已經滿了，價值不高
        elif item_type == settings.ITEM_TYPE_BOMB_RANGE:
            if self.ai_player.bomb_range < getattr(settings, "MAX_POSSIBLE_RANGE", 5):
                base_value = 75
            else:
                base_value = 10
        elif item_type == settings.ITEM_TYPE_LIFE:
            if self.ai_player.lives < settings.MAX_LIVES: # 假設 MAX_LIVES 在 settings 中
                base_value = 100 # 生命最重要
            else:
                base_value = 5 # 命滿了
        elif item_type == settings.ITEM_TYPE_SCORE:
            base_value = 20 # 分數道具價值一般
        # ... 其他道具類型 ...
        else:
            base_value = 15 # 未知或一般道具

        # 可以根據距離、危險程度等調整價值
        # 此處簡化，只返回基礎價值
        return base_value

    def _find_best_item(self, ai_current_tile):
        best_item_found = None
        highest_value = -1
        shortest_path_len = float('inf')

        if not hasattr(self.game, 'items_group'): #
            return None

        visible_items = []
        for item_sprite in self.game.items_group:
            if item_sprite.alive(): # 確保道具還存在
                 # 假設 item sprite 有 rect 屬性用於獲取格子座標
                item_tile_x = item_sprite.rect.centerx // settings.TILE_SIZE
                item_tile_y = item_sprite.rect.centery // settings.TILE_SIZE
                item_tile_coords = (item_tile_x, item_tile_y)

                # 評估道具價值
                value = self._evaluate_item_value(item_sprite)
                if value < self.item_priority_threshold * 20: # 忽略價值太低的 (乘以一個因子)
                    continue

                # 評估路徑可達性和距離 (初步用BFS，如果太遠或中間有牆再考慮A*)
                # 這裡只考慮直接可達性，不考慮炸牆拿道具 (除非後續狀態處理中加入)
                path_to_item = self.bfs_find_direct_movement_path(ai_current_tile, item_tile_coords, max_depth=self.max_item_search_depth_bfs)
                if path_to_item:
                    path_len = len(path_to_item) - 1
                    # 綜合考慮價值和距離 (例如: value / (path_len + 1))
                    effective_value = value / (path_len + 0.1) # 避免除以0

                    if effective_value > highest_value :
                        highest_value = effective_value
                        best_item_found = (item_sprite, item_tile_coords, path_to_item)
                    elif effective_value == highest_value and path_len < shortest_path_len: # 同樣價值，選近的
                        shortest_path_len = path_len
                        best_item_found = (item_sprite, item_tile_coords, path_to_item)

        if best_item_found:
            ai_base_log(f"    [ITEM_SCAN] Best item found: {best_item_found[0].type} at {best_item_found[1]} with effective_value {highest_value:.2f}")
            return best_item_found
        else:
            ai_base_log("    [ITEM_SCAN] No suitable items found.")
            return None

    def handle_scanning_state(self, ai_current_tile):
        ai_base_log(f"[ITEM_AI_SCANNING] at {ai_current_tile}.")
        found_item_data = self._find_best_item(ai_current_tile)
        if found_item_data:
            self.current_target_item = (found_item_data[0], found_item_data[1]) # sprite, coords
            # A* 路徑規劃到道具 (如果 BFS 路徑太長或不可靠，或者 _find_best_item 中只做了初步可達性)
            # 為了簡化，如果 _find_best_item 返回了 BFS 路徑，可以直接用它
            if len(found_item_data) > 2 and found_item_data[2]: # 如果返回了 BFS 路徑
                self.astar_planned_path = [] # 清空 A* 路徑，因為我們用 BFS
                self.set_current_movement_sub_path(found_item_data[2])
                self.change_state(AI_STATE_ITEM_MOVING_TO_TARGET)
            else: # 否則，需要 A* 規劃
                self.change_state(AI_STATE_ITEM_PLANNING_PATH)
        else:
            self.change_state(AI_STATE_ITEM_NO_TARGET_IDLE) # 沒有道具目標，進入閒置


    def handle_planning_path_state(self, ai_current_tile):
        ai_base_log(f"[ITEM_AI_PLANNING_PATH] to target item at {self.current_target_item[1] if self.current_target_item else 'None'}.")
        if not self.current_target_item:
            self.change_state(AI_STATE_ITEM_SCANNING); return

        target_item_coords = self.current_target_item[1]
        # 使用 A* 規劃路徑到道具 (這裡假設道具本身是可穿越的，目標是道具所在的格子)
        # 注意：如果道具被牆擋住，此處的 A* 可能無法直接到達
        # 需要更複雜的邏輯：先 A* 到牆邊，然後炸牆，然後再去撿道具
        # 為了簡化此階段，我們先假設 A* 的目標是道具格子，如果路徑上有可破壞牆，則轉到炸牆邏輯

        self.astar_planned_path = self.astar_find_path(ai_current_tile, target_item_coords) # max_depth?
        if self.astar_planned_path:
            self.astar_path_current_segment_index = 0
            # 檢查路徑上是否有可破壞的牆需要清除
            # (這部分邏輯可以從 AggressiveAIController 或原始 AIController 借鑒)
            # ...
            # 如果需要炸牆：
            #   self.target_destructible_wall_node_in_astar = first_destructible_wall_on_path
            #   self.change_state(AI_STATE_ITEM_CLEARING_FOR_ITEM) # 需要新狀態
            #   return
            # 如果路徑直接可達 (或只有空格):
            self.set_current_movement_sub_path(self._convert_astar_nodes_to_coords(self.astar_planned_path))
            self.change_state(AI_STATE_ITEM_MOVING_TO_TARGET)
        else:
            ai_base_log(f"    Cannot A* path to item {self.current_target_item[0].type} at {target_item_coords}. Re-scanning.")
            self.current_target_item = None # 放棄當前目標
            self.change_state(AI_STATE_ITEM_SCANNING)

    def _convert_astar_nodes_to_coords(self, astar_node_path):
        if not astar_node_path: return []
        return [(node.x, node.y) for node in astar_node_path]

    def handle_moving_to_target_state(self, ai_current_tile):
        ai_base_log(f"[ITEM_AI_MOVING_TO_TARGET] at {ai_current_tile}. Target: {self.current_target_item[1] if self.current_target_item else 'None'}.")
        if not self.current_target_item or not self.current_target_item[0].alive(): # 道具消失或已被拾取
            ai_base_log("    Target item no longer available. Re-scanning.")
            self.current_target_item = None
            self.astar_planned_path = []
            self.current_movement_sub_path = []
            self.change_state(AI_STATE_ITEM_SCANNING)
            return

        target_item_coords = self.current_target_item[1]
        if ai_current_tile == target_item_coords: # 已經到達
            # 遊戲邏輯會處理拾取，這裡AI任務完成
            ai_base_log(f"    Successfully arrived at item {self.current_target_item[0].type}. Re-scanning.")
            self.current_target_item = None
            self.astar_planned_path = []
            self.current_movement_sub_path = []
            self.change_state(AI_STATE_ITEM_SCANNING)
            return

        # 如果沒有子路徑了 (例如A*路徑執行完但未到達，或路徑中斷)，重新規劃或放棄
        if not self.current_movement_sub_path:
            ai_base_log("    Sub-path ended before reaching item. Re-planning or re-scanning.")
            # 可以嘗試重新規劃一次BFS，如果不行就重新掃描
            path_to_item_bfs = self.bfs_find_direct_movement_path(ai_current_tile, target_item_coords, max_depth=self.max_item_search_depth_bfs // 2)
            if path_to_item_bfs and len(path_to_item_bfs) > 1:
                self.set_current_movement_sub_path(path_to_item_bfs)
            else:
                self.current_target_item = None
                self.astar_planned_path = []
                self.change_state(AI_STATE_ITEM_SCANNING)

    def handle_no_target_idle_state(self, ai_current_tile):
        ai_base_log(f"[ITEM_AI_NO_TARGET_IDLE] at {ai_current_tile}.")
        # 類似 ConservativeAI 的 IDLE 狀態，進行安全巡邏
        # 定期嘗試重新掃描道具 (由主 update 迴圈的 scan_interval 控制)
        if not self.current_movement_sub_path:
            safe_random_moves = []
            for dx, dy in DIRECTIONS.values():
                next_x, next_y = ai_current_tile[0] + dx, ai_current_tile[1] + dy
                node = self._get_node_at_coords(next_x, next_y)
                if node and node.is_empty_for_direct_movement() and \
                   not self.is_tile_dangerous(next_x, next_y, future_seconds=0.5): # 安全巡邏
                    safe_random_moves.append((next_x, next_y))
            if safe_random_moves:
                self.set_current_movement_sub_path([ai_current_tile, random.choice(safe_random_moves)])
            else: # 無處可去
                self.ai_player.is_moving = False


    def handle_retreat_after_bomb_state(self, ai_current_tile):
        ai_base_log(f"[ITEM_AI_RETREAT_AFTER_BOMB] at {ai_current_tile}. Target: {self.chosen_retreat_spot_coords}")
        # 與其他AI的撤退邏輯類似
        if self.current_movement_sub_path: return

        if ai_current_tile == self.chosen_retreat_spot_coords or not self.chosen_retreat_spot_coords:
            if not self.is_bomb_still_active(self.last_bomb_placed_time):
                ai_base_log(f"      Bomb cleared (for item). Re-scanning.")
                self.ai_just_placed_bomb = False
                self.chosen_bombing_spot_coords = None
                self.chosen_retreat_spot_coords = None
                self.target_destructible_wall_node_in_astar = None # 清除炸牆目標
                self.change_state(AI_STATE_ITEM_SCANNING) # 重新掃描，看是否能拿到道具或有新道具
            # else: # 炸彈還在，繼續等待
        else: # 未到達撤退點
            # (重新規劃到撤退點的邏輯，或轉入 EVADING)
            if self.chosen_retreat_spot_coords:
                retreat_path = self.bfs_find_direct_movement_path(ai_current_tile, self.chosen_retreat_spot_coords, max_depth=7)
                if retreat_path and len(retreat_path)>1: self.set_current_movement_sub_path(retreat_path)
                else: self.change_state(AI_STATE_ITEM_EVADING)
            else: self.change_state(AI_STATE_ITEM_EVADING)


    def handle_evading_danger_state(self, ai_current_tile):
        ai_base_log(f"[ITEM_AI_EVADING] at {ai_current_tile}")
        # 與其他AI的躲避邏輯類似
        if not self.is_tile_dangerous(ai_current_tile[0], ai_current_tile[1], future_seconds=0.3):
            ai_base_log(f"    Tile {ai_current_tile} now safe. Re-scanning for items.")
            self.current_movement_sub_path = []
            self.change_state(AI_STATE_ITEM_SCANNING) # 躲避完後，重新掃描道具
            return

        path_target_is_dangerous = False
        # (檢查子路徑目標是否危險的邏輯)
        # (尋找並設定逃跑路徑的邏輯)
        # ... (與 ConservativeAIController 或 AggressiveAIController 類似的實現) ...
        if not self.current_movement_sub_path or \
           (self.current_movement_sub_path and ai_current_tile == self.current_movement_sub_path[-1]) or \
           path_target_is_dangerous: # path_target_is_dangerous 需要計算
            # 尋找安全點，這裡可以使用基礎類別的，或者道具型有自己的偏好
            safe_options_coords = self.find_safe_tiles_nearby_for_retreat(ai_current_tile, ai_current_tile, 0, max_depth=6) # 基礎的躲避
            best_evasion_path_coords = []
            if safe_options_coords:
                for safe_spot_coord in safe_options_coords:
                    evasion_path_tuples = self.bfs_find_direct_movement_path(ai_current_tile, safe_spot_coord, max_depth=6)
                    if evasion_path_tuples and len(evasion_path_tuples) > 1:
                        best_evasion_path_coords = evasion_path_tuples; break
            if best_evasion_path_coords:
                self.set_current_movement_sub_path(best_evasion_path_coords)
            else:
                self.current_movement_sub_path = []
                self.ai_player.is_moving = False


    # debug_draw_path 可以擴展以標記目標道具和路徑
    def debug_draw_path(self, surface):
        # 首先，呼叫父類別的 debug_draw_path 來繪製通用的路徑訊息
        # 如果 AIControllerBase 中的 debug_draw_path 繪製了 A* 和 sub_path，這裡可以不用重複
        # super().debug_draw_path(surface)
        # 但為了更精細地控制道具優先型 AI 的路徑顏色，我們可以在這裡重新繪製或調整

        ai_tile_now = self._get_ai_current_tile()
        if not ai_tile_now or not self.ai_player or not self.ai_player.is_alive:
            return

        try:
            tile_size = settings.TILE_SIZE
            half_tile = tile_size // 2

            # --- 1. 繪製 A* 規劃路徑 (如果目標是道具，使用特殊顏色) ---
            is_targeting_item_with_astar = (
                self.astar_planned_path and
                self.current_target_item and
                self.current_target_item[0].alive() and # 確保道具還存在
                len(self.astar_planned_path) > 0 and
                self.astar_planned_path[-1].x == self.current_target_item[1][0] and
                self.astar_planned_path[-1].y == self.current_target_item[1][1]
            )

            if self.astar_planned_path and self.astar_path_current_segment_index < len(self.astar_planned_path):
                astar_points_to_draw = [(ai_tile_now[0] * tile_size + half_tile, ai_tile_now[1] * tile_size + half_tile)]
                current_astar_target_pixel_pos = None
                for i in range(self.astar_path_current_segment_index, len(self.astar_planned_path)):
                    node = self.astar_planned_path[i]
                    px, py = node.x * tile_size + half_tile, node.y * tile_size + half_tile
                    astar_points_to_draw.append((px, py))
                    if i == self.astar_path_current_segment_index:
                        current_astar_target_pixel_pos = (px, py)
                
                if len(astar_points_to_draw) > 1:
                    astar_line_color = (128, 0, 128, 180) # 紫色，預設給道具的 A* 路徑
                    if not is_targeting_item_with_astar: # 如果 A* 目標不是道具（例如，逃跑時）
                        astar_line_color = (0, 0, 139, 180) # 深藍色 (與保守型類似或自訂)
                    
                    for i in range(len(astar_points_to_draw) - 1):
                        if i % 2 == 0: # 虛線效果
                            pygame.draw.aaline(surface, astar_line_color, astar_points_to_draw[i], astar_points_to_draw[i+1], True)
                
                if current_astar_target_pixel_pos:
                    pygame.draw.circle(surface, astar_line_color, current_astar_target_pixel_pos, tile_size // 3, 2)

            # --- 2. 繪製當前移動子路徑 (如果目標是道具，使用特殊顏色) ---
            if self.current_movement_sub_path and len(self.current_movement_sub_path) > 1 and \
               self.current_movement_sub_path_index < len(self.current_movement_sub_path) -1 :
                sub_path_points_to_draw = [(ai_tile_now[0] * tile_size + half_tile, ai_tile_now[1] * tile_size + half_tile)]
                for i in range(self.current_movement_sub_path_index + 1, len(self.current_movement_sub_path)):
                    tile_coords = self.current_movement_sub_path[i]
                    px, py = tile_coords[0] * tile_size + half_tile, tile_coords[1] * tile_size + half_tile
                    sub_path_points_to_draw.append((px,py))
                
                if len(sub_path_points_to_draw) > 1:
                    sub_path_color = (218, 112, 214, 200) # 蘭花紫，預設給道具的子路徑
                    if self.current_state == AI_STATE_ITEM_EVADING:
                        sub_path_color = (255, 165, 0, 220) # 逃跑時用橙色
                    elif not (self.current_target_item and self.current_movement_sub_path[-1] == self.current_target_item[1]):
                        # 如果子路徑的最終目標不是當前道具（例如，是去炸牆點，或安全巡邏）
                        sub_path_color = (0, 200, 0, 180) # 綠色代表其他移動
                    
                    pygame.draw.aalines(surface, sub_path_color, False, sub_path_points_to_draw, True)
                    
                    next_sub_step_coords = self.current_movement_sub_path[self.current_movement_sub_path_index + 1]
                    next_px, next_py = next_sub_step_coords[0] * tile_size + half_tile, next_sub_step_coords[1] * tile_size + half_tile
                    pulse_factor = abs(pygame.time.get_ticks() % 1000 - 500) / 500
                    radius = int(tile_size // 5 + pulse_factor * (tile_size//10))
                    pygame.draw.circle(surface, sub_path_color, (next_px, next_py), radius, 0)

            # --- 3. 道具優先型 AI 特有的視覺化元素 ---

            # 標記當前目標道具 (如果存在)
            if self.current_target_item and self.current_target_item[0].alive():
                item_sprite, item_coords = self.current_target_item
                ix, iy = item_coords
                center_ix, center_iy = ix * tile_size + half_tile, iy * tile_size + half_tile
                
                # 根據道具類型使用不同顏色和樣式標記目標道具
                item_value = self._evaluate_item_value(item_sprite) # 獲取道具評估價值
                target_color = (255, 215, 0, 220) # 金色，高價值道具
                target_radius = tile_size // 2 - 2
                target_thickness = 3

                if item_value < 40: # 中等價值
                    target_color = (173, 216, 230, 200) # 淺藍色
                    target_radius = tile_size // 3
                    target_thickness = 2
                elif item_value < 15: # 低價值 (理論上不會被選為目標，但以防萬一)
                    target_color = (211, 211, 211, 180) #淺灰色
                    target_radius = tile_size // 4
                    target_thickness = 1

                # 繪製目標道具外框
                pygame.draw.circle(surface, target_color, (center_ix, center_iy), target_radius, target_thickness)
                
                # 畫一條從 AI 指向目標道具的指示線 (如果 AI 正在前往該道具)
                if self.current_state == AI_STATE_ITEM_MOVING_TO_TARGET or self.current_state == AI_STATE_ITEM_PLANNING_PATH:
                    pygame.draw.aaline(surface, target_color,
                                       (ai_tile_now[0]*tile_size+half_tile, ai_tile_now[1]*tile_size+half_tile),
                                       (center_ix, center_iy), True)
                
                # 在目標道具旁顯示其類型或價值 (可選，需要字體)
                if hasattr(self, 'hud_font') and self.hud_font: # 假設有 self.hud_font
                    try:
                        item_info_text = f"{item_sprite.type[:3]}:{int(item_value)}" # 簡短類型和價值
                        text_surf = self.hud_font.render(item_info_text, True, target_color)
                        text_rect = text_surf.get_rect(center=(center_ix, center_iy - tile_size // 2 - 5))
                        surface.blit(text_surf, text_rect)
                    except Exception as e:
                        ai_base_log(f"Error rendering item info text: {e}")


            # 標記為了獲取道具而選擇的轟炸點或目標牆壁
            # (這部分邏輯與您原始 AIController 中的 debug_draw_path 相似)
            # 但顏色或標記可以特化，例如用道具相關的顏色 (如果目標是炸牆拿道具)
            if hasattr(self, 'chosen_bombing_spot_coords') and self.chosen_bombing_spot_coords and \
               self.current_state == AI_STATE_ITEM_RETREAT_AFTER_BOMB: # 假設這是炸牆取物後的撤退
                # (繪製轟炸點的邏輯，顏色可自訂)
                bx, by = self.chosen_bombing_spot_coords
                center_bx, center_by = bx * tile_size + half_tile, by * tile_size + half_tile
                pygame.draw.circle(surface, (255, 140, 0, 180), (center_bx, center_by), tile_size // 3, 2) # 暗橙色


            if hasattr(self, 'target_destructible_wall_node_in_astar') and self.target_destructible_wall_node_in_astar and \
               (self.current_state == AI_STATE_ITEM_PLANNING_PATH or \
                (self.current_movement_sub_path and len(self.current_movement_sub_path) > 1 and self.current_movement_sub_path[-1] == (self.target_destructible_wall_node_in_astar.x, self.target_destructible_wall_node_in_astar.y))): # 如果正在前往炸這個牆
                # (繪製目標牆壁的邏輯，顏色可自訂)
                wall_node = self.target_destructible_wall_node_in_astar
                wall_rect = pygame.Rect(wall_node.x * tile_size, wall_node.y * tile_size, tile_size, tile_size)
                s_wall_item = pygame.Surface((tile_size, tile_size), pygame.SRCALPHA)
                s_wall_item.fill((255,255,0, 70)) # 黃色半透明表示為了道具要炸的牆
                surface.blit(s_wall_item, (wall_rect.x, wall_rect.y))
                pygame.draw.rect(surface, (200,200,0,150), wall_rect, 2)


            # 標記撤退點 (如果因為放炸彈拿道具而撤退)
            if hasattr(self, 'chosen_retreat_spot_coords') and self.chosen_retreat_spot_coords and \
               self.current_state == AI_STATE_ITEM_RETREAT_AFTER_BOMB:
                # (繪製撤退點的邏輯，顏色可自訂)
                rx, ry = self.chosen_retreat_spot_coords
                rect_retreat_item = pygame.Rect(rx * tile_size + 3, ry * tile_size + 3, tile_size - 6, tile_size - 6)
                s_retreat_item = pygame.Surface((tile_size-6, tile_size-6), pygame.SRCALPHA)
                s_retreat_item.fill((0,220,0, 100)) # 亮綠色
                surface.blit(s_retreat_item, (rect_retreat_item.x, rect_retreat_item.y))
                pygame.draw.rect(surface, (0,150,0, 180), rect_retreat_item, 2)


        except AttributeError as e:
            if 'TILE_SIZE' in str(e) or 'game' in str(e) or 'map_manager' in str(e):
                pass
            else:
                ai_base_log(f"ItemFocusedAI Debug Draw AttributeError: {e}")
        except Exception as e:
            ai_base_log(f"Error during ItemFocusedAI debug_draw_path: {e}")