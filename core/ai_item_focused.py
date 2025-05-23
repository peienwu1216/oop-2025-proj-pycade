# oop-2025-proj-pycade/core/ai_item_focused.py

import pygame
import settings
import random
from collections import deque
from .ai_controller_base import AIControllerBase, ai_log, DIRECTIONS, TileNode

class ItemFocusedAIController(AIControllerBase):
    """
    一個專注於尋找並拾取道具的 AI。
    它會優先炸開可能藏有道具的障礙物。
    此版本重點修正移動到目標過程中路徑失敗導致的卡死問題。
    """
    def __init__(self, ai_player_sprite, game_instance):
        super().__init__(ai_player_sprite, game_instance)
        
        ai_log("ItemFocusedAIController (v4 - Path Execution Fix) initialized.")
        
        self.evasion_urgency_seconds = getattr(settings, "AI_ITEM_FOCUSED_EVASION_SECONDS", 0.5) # 稍微降低一點，避免過於敏感影響尋路
        self.retreat_search_depth = getattr(settings, "AI_ITEM_FOCUSED_RETREAT_DEPTH", 7) # 稍微增加撤退搜索深度
        self.min_retreat_options_for_obstacle_bombing = 1 
        
        self.max_walls_to_consider_for_items = getattr(settings, "AI_ITEM_MAX_WALL_TARGETS", 4) # 可以考慮更多牆壁
        self.wall_scan_radius_for_items = getattr(settings, "AI_ITEM_WALL_SCAN_RADIUS", 6)      # 掃描範圍也可以大一點
        self.item_bombing_chance = getattr(settings, "AI_ITEM_BOMBING_CHANCE", 0.65) 

        self.target_item_on_ground = None 
        self.potential_wall_to_bomb_for_item = None 
        
        self.item_type_priority = {
            settings.ITEM_TYPE_BOMB_RANGE: 1,
            settings.ITEM_TYPE_BOMB_CAPACITY: 2,
            settings.ITEM_TYPE_LIFE: 3,
            settings.ITEM_TYPE_SCORE: 10 
        }
        
        self.default_planning_state_on_stuck = "PLANNING_ITEM_TARGET"
        self.default_state_after_evasion = "PLANNING_ITEM_TARGET"
        
        self.last_failed_bombing_target_wall = None
        self.last_failed_bombing_spot = None
        self.last_failed_roam_target = None # 新增：記錄上次失敗的漫遊目標
        self.roam_target_seek_depth = 10 # 漫遊目標尋找深度
        self.idle_duration_ms = 1500

        self.change_state("PLANNING_ITEM_TARGET")

    def reset_state(self):
        super().reset_state()
        self.target_item_on_ground = None
        self.potential_wall_to_bomb_for_item = None
        self.last_failed_bombing_target_wall = None
        self.last_failed_bombing_spot = None
        self.last_failed_roam_target = None
        self.change_state("PLANNING_ITEM_TARGET")
        ai_log(f"ItemFocusedAIController (v4) reset. Current state: {self.current_state}")

    # --- 狀態處理邏輯 ---

    def handle_planning_item_target_state(self, ai_current_tile):
        ai_log(f"ITEM_FOCUSED: In PLANNING_ITEM_TARGET at {ai_current_tile}.")
        # 清理舊目標，但保留 last_failed_... 以避免立即重試
        self.target_item_on_ground = None
        self.potential_wall_to_bomb_for_item = None
        self.astar_planned_path = [] 

        # 1. 尋找地圖上已有的道具
        best_item_on_ground = self._find_best_item_on_ground(ai_current_tile)
        if best_item_on_ground:
            self.target_item_on_ground = best_item_on_ground['item']
            item_coords = best_item_on_ground['coords']
            ai_log(f"ITEM_FOCUSED: Found item {self.target_item_on_ground.type} on ground at {item_coords}. Pathing...")
            
            path_to_item = self.bfs_find_direct_movement_path(ai_current_tile, item_coords, max_depth=25)
            if path_to_item and len(path_to_item) > 1:
                self.set_current_movement_sub_path(path_to_item)
                self.change_state("MOVING_TO_COLLECT_ITEM")
                return
            else: 
                self.astar_planned_path = self.astar_find_path(ai_current_tile, item_coords)
                if self.astar_planned_path:
                    self.astar_path_current_segment_index = 0
                    ai_log(f"ITEM_FOCUSED: A* path to item on ground: {[(n.x,n.y) for n in self.astar_planned_path]}")
                    self.change_state("EXECUTING_ASTAR_PATH_TO_TARGET") 
                    return
                else: 
                    ai_log(f"ITEM_FOCUSED: Cannot find any path to item {self.target_item_on_ground.type}. Giving up on this item for now.")
                    self.target_item_on_ground = None 

        # 2. 尋找值得炸的牆
        # （1）！！！PLANNING_ITEM_TARGET 尋找牆壁邏輯修改開始！！！（1）
        # 傳入上次失敗的牆壁目標，以避免重複選擇
        current_wall_target = self._find_best_wall_to_bomb_for_items(ai_current_tile, exclude_wall_node=self.last_failed_bombing_target_wall)
        if current_wall_target:
            self.potential_wall_to_bomb_for_item = current_wall_target
            if random.random() < self.item_bombing_chance:
                ai_log(f"ITEM_FOCUSED: Identified new potential wall {self.potential_wall_to_bomb_for_item} to bomb for items.")
                self.last_failed_bombing_target_wall = None # 清除失敗標記，因為我們要嘗試新的牆
                self.last_failed_bombing_spot = None      # 清除失敗的轟炸點
                self.change_state("ASSESSING_OBSTACLE_FOR_ITEM")
                return
        # （1）！！！PLANNING_ITEM_TARGET 尋找牆壁邏輯修改結束！！！（1）
        
        # 3. 攻擊玩家 (低機率)
        human_pos = self._get_human_player_current_tile()
        if human_pos and random.random() < 0.05: # 非常低的機率攻擊
            ai_log("ITEM_FOCUSED: No item targets. Very low chance to engage player.")
            self.astar_planned_path = self.astar_find_path(ai_current_tile, human_pos)
            if self.astar_planned_path:
                self.astar_path_current_segment_index = 0
                self.change_state("EXECUTING_PATH_CLEARANCE") 
                return
        
        # 4. 安全漫遊
        potential_roam_targets = self._find_safe_roaming_spots(ai_current_tile, count=1, depth=self.roam_target_seek_depth, exclude_target=self.last_failed_roam_target)
        if potential_roam_targets:
            roam_target = potential_roam_targets[0]
            if roam_target != ai_current_tile:
                path_to_roam = self.bfs_find_direct_movement_path(ai_current_tile, roam_target)
                if path_to_roam and len(path_to_roam) > 1:
                    self.set_current_movement_sub_path(path_to_roam)
                    self.roaming_target_tile = roam_target # 設定漫遊目標
                    self.change_state("ROAMING") 
                    return
        
        ai_log("ITEM_FOCUSED: No clear item, wall, or roam targets. Idling.")
        self.change_state("IDLE")

    def handle_moving_to_collect_item_state(self, ai_current_tile):
        if not self.target_item_on_ground or not self.target_item_on_ground.alive():
            self.change_state("PLANNING_ITEM_TARGET"); return

        item_coords = (self.target_item_on_ground.rect.centerx // settings.TILE_SIZE,
                       self.target_item_on_ground.rect.centery // settings.TILE_SIZE)
        ai_log(f"ITEM_FOCUSED: Moving to collect item {self.target_item_on_ground.type} at {item_coords}. Current: {ai_current_tile}")

        if self.current_movement_sub_path: return

        if ai_current_tile == item_coords: 
            self.target_item_on_ground = None 
            self.change_state("PLANNING_ITEM_TARGET")
        else: 
            ai_log(f"ITEM_FOCUSED: Sub-path to item ended or failed. Re-planning to item (A*).")
            self.astar_planned_path = self.astar_find_path(ai_current_tile, item_coords)
            if self.astar_planned_path:
                self.astar_path_current_segment_index = 0
                self.change_state("EXECUTING_ASTAR_PATH_TO_TARGET")
            else: 
                self.target_item_on_ground = None
                self.change_state("PLANNING_ITEM_TARGET")

    def handle_executing_astar_path_to_target_state(self, ai_current_tile):
        # ... (與上一版相同，確保失敗時回到 PLANNING_ITEM_TARGET) ...
        current_target_description = "UNKNOWN TARGET"
        target_coords = None

        if self.target_item_on_ground and self.target_item_on_ground.alive():
            current_target_description = f"item {self.target_item_on_ground.type}"
            target_coords = (self.target_item_on_ground.rect.centerx // settings.TILE_SIZE,
                             self.target_item_on_ground.rect.centery // settings.TILE_SIZE)
        elif self.astar_planned_path : 
            last_node = self.astar_planned_path[-1]
            target_coords = (last_node.x, last_node.y)
            human_tile = self._get_human_player_current_tile()
            if human_tile and target_coords == human_tile: current_target_description = "player"
            else: current_target_description = f"coords {target_coords}"
        else: self.change_state("PLANNING_ITEM_TARGET"); return

        ai_log(f"ITEM_FOCUSED: Executing A* path to {current_target_description}. At {ai_current_tile}.")
        if self.ai_just_placed_bomb: return

        if not self.astar_planned_path or self.astar_path_current_segment_index >= len(self.astar_planned_path):
            self.change_state("PLANNING_ITEM_TARGET"); return

        if self.current_movement_sub_path: return

        target_node_in_astar = self.astar_planned_path[self.astar_path_current_segment_index]

        if ai_current_tile == (target_node_in_astar.x, target_node_in_astar.y):
            self.astar_path_current_segment_index += 1 
            if self.astar_path_current_segment_index >= len(self.astar_planned_path):
                self.change_state("PLANNING_ITEM_TARGET") 
            else: self.last_decision_time = pygame.time.get_ticks() - self.ai_decision_interval 
            return

        if target_node_in_astar.is_empty_for_direct_movement():
            path_to_node = self.bfs_find_direct_movement_path(ai_current_tile, (target_node_in_astar.x, target_node_in_astar.y))
            if path_to_node and len(path_to_node) > 1: self.set_current_movement_sub_path(path_to_node)
            else: self.change_state("PLANNING_ITEM_TARGET")
            return
        
        elif target_node_in_astar.is_destructible_box():
            self.target_destructible_wall_node_in_astar = target_node_in_astar 
            bomb_spot, retreat_spot = self._find_optimal_bombing_spot_for_obstacle(target_node_in_astar, ai_current_tile, self.min_retreat_options_for_obstacle_bombing)
            if bomb_spot and retreat_spot:
                self.chosen_bombing_spot_coords = bomb_spot
                self.chosen_retreat_spot_coords = retreat_spot
                if ai_current_tile == bomb_spot: 
                    if self.ai_player.bombs_placed_count < self.ai_player.max_bombs:
                        self.ai_player.place_bomb()
                        path_to_retreat_immediately = self.bfs_find_direct_movement_path(ai_current_tile, retreat_spot)
                        if path_to_retreat_immediately and len(path_to_retreat_immediately) > 1:
                            self.set_current_movement_sub_path(path_to_retreat_immediately)
                        self.change_state("TACTICAL_RETREAT_AND_WAIT")
                    else: self.change_state("PLANNING_ITEM_TARGET")
                else: 
                    path_to_bomb_spot = self.bfs_find_direct_movement_path(ai_current_tile, bomb_spot)
                    if path_to_bomb_spot and len(path_to_bomb_spot) > 1: 
                        self.set_current_movement_sub_path(path_to_bomb_spot)
                        # 狀態保持 EXECUTING_ASTAR_PATH_TO_TARGET，等待移動到轟炸點
                    else: self.change_state("PLANNING_ITEM_TARGET")
            else: self.change_state("PLANNING_ITEM_TARGET")
            return
        else: self.change_state("PLANNING_ITEM_TARGET")


    def handle_assessing_obstacle_for_item_state(self, ai_current_tile):
        ai_log(f"ITEM_FOCUSED: Assessing obstacle {self.potential_wall_to_bomb_for_item} at {ai_current_tile} for items.")
        if not self.potential_wall_to_bomb_for_item or \
           not self._get_node_at_coords(self.potential_wall_to_bomb_for_item.x, self.potential_wall_to_bomb_for_item.y).is_destructible_box():
            self.potential_wall_to_bomb_for_item = None
            self.change_state("PLANNING_ITEM_TARGET"); return

        bomb_spot, retreat_spot = self._find_optimal_bombing_spot_for_obstacle(self.potential_wall_to_bomb_for_item, ai_current_tile, self.min_retreat_options_for_obstacle_bombing)

        if bomb_spot and retreat_spot:
            self.chosen_bombing_spot_coords = bomb_spot
            self.chosen_retreat_spot_coords = retreat_spot
            
            path_to_bomb_spot = self.bfs_find_direct_movement_path(ai_current_tile, self.chosen_bombing_spot_coords)
            if path_to_bomb_spot and len(path_to_bomb_spot) > 0:
                self.set_current_movement_sub_path(path_to_bomb_spot)
                self.change_state("MOVING_TO_BOMB_OBSTACLE")
            else:
                ai_log("ITEM_FOCUSED: Cannot path to chosen bombing spot for wall. Re-planning.")
                self.last_failed_bombing_target_wall = self.potential_wall_to_bomb_for_item
                self.potential_wall_to_bomb_for_item = None
                self.change_state("PLANNING_ITEM_TARGET")
        else:
            ai_log("ITEM_FOCUSED: Cannot find safe way to bomb wall for items. Re-planning.")
            self.last_failed_bombing_target_wall = self.potential_wall_to_bomb_for_item
            self.potential_wall_to_bomb_for_item = None
            self.change_state("PLANNING_ITEM_TARGET")
            
    # （2）！！！MOVING_TO_BOMB_OBSTACLE 狀態處理修改開始！！！（2）
    def handle_moving_to_bomb_obstacle_state(self, ai_current_tile):
        if not self.chosen_bombing_spot_coords:
            ai_log("ITEM_FOCUSED: ERROR - No bombing spot in MOVING_TO_BOMB_OBSTACLE. Re-planning.")
            self.change_state("PLANNING_ITEM_TARGET"); return

        ai_log(f"ITEM_FOCUSED: Moving to bomb spot {self.chosen_bombing_spot_coords} for obstacle. At {ai_current_tile}.")
        
        # 如果有路徑，則等待基底類別的 update() 執行移動
        # (基底的 update -> execute_next_move_on_sub_path 會處理移動並在完成或失敗時清空 sub_path)
        if self.current_movement_sub_path:
            ai_log(f"    Path active: {self.current_movement_sub_path}, index: {self.current_movement_sub_path_index}")
            return # 等待移動執行

        # 當 self.current_movement_sub_path 為空，表示路徑已走完，或一開始就沒有成功設定/執行路徑
        ai_log(f"    Sub-path to bomb spot is now empty. Current tile: {ai_current_tile}, Target bomb spot: {self.chosen_bombing_spot_coords}")
        if ai_current_tile == self.chosen_bombing_spot_coords: # 已成功到達轟炸點
            if self.ai_player.bombs_placed_count < self.ai_player.max_bombs:
                ai_log("ITEM_FOCUSED: At bombing spot. Placing bomb for obstacle/item.")
                self.ai_player.place_bomb() # Player 應處理 ai_just_placed_bomb 和 last_bomb_placed_time
                
                # 【關鍵】放置炸彈後，必須立即設定撤退路徑並開始撤退
                path_to_retreat = self.bfs_find_direct_movement_path(ai_current_tile, self.chosen_retreat_spot_coords, max_depth=self.retreat_search_depth + 2) # 逃跑時看得更遠
                if path_to_retreat and len(path_to_retreat) > 1:
                    self.set_current_movement_sub_path(path_to_retreat)
                else: # 即使找不到明確的撤退路徑，也要進入撤退狀態，讓EVADING_DANGER接管
                    ai_log(f"ITEM_FOCUSED: Placed bomb at {ai_current_tile}, but no direct path to chosen retreat {self.chosen_retreat_spot_coords}. Will enter TACTICAL_RETREAT and potentially EVADE.")
                self.change_state("TACTICAL_RETREAT_AND_WAIT")
            else:
                ai_log("ITEM_FOCUSED: At bombing spot, but no bombs available. Re-planning.")
                self.change_state("PLANNING_ITEM_TARGET")
        else: 
            # 如果路徑是空的，但AI又不在目標轟炸點，這意味著之前的移動嘗試失敗了
            ai_log(f"ITEM_FOCUSED: Path to bombing spot {self.chosen_bombing_spot_coords} FAILED (likely blocked). Current: {ai_current_tile}. Re-planning.")
            self.last_failed_bombing_spot = self.chosen_bombing_spot_coords 
            if self.potential_wall_to_bomb_for_item: # 如果是因為炸這個牆而來的
                 self.last_failed_bombing_target_wall = self.potential_wall_to_bomb_for_item
            elif self.target_destructible_wall_node_in_astar: # 如果是因為A*路徑上的牆
                 self.last_failed_bombing_target_wall = self.target_destructible_wall_node_in_astar

            self.chosen_bombing_spot_coords = None 
            self.chosen_retreat_spot_coords = None 
            self.potential_wall_to_bomb_for_item = None # 清除當前牆壁目標，避免重複選中
            self.target_destructible_wall_node_in_astar = None # 也清除A*路徑上的牆壁目標
            self.astar_planned_path = [] # 清除A*路徑
            self.change_state("PLANNING_ITEM_TARGET")
    # （2）！！！MOVING_TO_BOMB_OBSTACLE 狀態處理修改結束！！！（2）

    def handle_tactical_retreat_and_wait_state(self, ai_current_tile):
        if not self.chosen_retreat_spot_coords:
            ai_log("ITEM_FOCUSED: ERROR - No retreat spot in TACTICAL_RETREAT. Evading.")
            self.change_state("EVADING_DANGER"); return

        ai_log(f"ITEM_FOCUSED: Retreating/Waiting. At {ai_current_tile}. Target: {self.chosen_retreat_spot_coords}. Bomb placed: {self.ai_just_placed_bomb}")
        
        # 【關鍵】只要還在撤退狀態且炸彈剛放，就應該優先執行撤退路徑
        if self.ai_just_placed_bomb and self.current_movement_sub_path:
            ai_log(f"    Prioritizing execution of retreat sub-path: {self.current_movement_sub_path}")
            return # 等待基底 update 執行移動
        
        # 如果已到達撤退點
        if ai_current_tile == self.chosen_retreat_spot_coords:
            ai_log(f"    Arrived at retreat spot {self.chosen_retreat_spot_coords}.")
            if not self.is_bomb_still_active(self.last_bomb_placed_time):
                ai_log("    Bomb has cleared. Re-planning for items.")
                self.ai_just_placed_bomb = False
                self.potential_wall_to_bomb_for_item = None
                self.target_destructible_wall_node_in_astar = None
                self.chosen_bombing_spot_coords = None
                self.chosen_retreat_spot_coords = None
                self.change_state("PLANNING_ITEM_TARGET")
            else:
                ai_log("    Bomb still active. Waiting at retreat spot.")
            return

        # 如果未在撤退點，且沒有有效的撤退路徑 (可能是初始或中途失敗)
        # 必須確保 AI 正在向撤退點移動
        if not self.current_movement_sub_path:
            ai_log(f"    Not at retreat spot and no sub-path. Attempting to path to retreat {self.chosen_retreat_spot_coords}.")
            path_to_retreat = self.bfs_find_direct_movement_path(ai_current_tile, self.chosen_retreat_spot_coords, max_depth=self.retreat_search_depth + 2)
            if path_to_retreat and len(path_to_retreat) > 1:
                self.set_current_movement_sub_path(path_to_retreat)
                ai_log(f"    Set new retreat path: {path_to_retreat}")
            else: 
                ai_log(f"ITEM_FOCUSED: CRITICAL - Cannot path to chosen retreat spot {self.chosen_retreat_spot_coords} after bombing! Evading.")
                self.change_state("EVADING_DANGER") # 強制進入緊急躲避
            
    def handle_evading_danger_state(self, ai_current_tile):
        # 使用基底類別的逃跑邏輯，它已經比較完善
        super().handle_evading_danger_state(ai_current_tile)
        # ItemFocusedAI 的 default_state_after_evasion 是 PLANNING_ITEM_TARGET

    def handle_idle_state(self, ai_current_tile):
        ai_log(f"ITEM_FOCUSED: Briefly idling at {ai_current_tile}.")
        if pygame.time.get_ticks() - self.state_start_time > self.idle_duration_ms:
            self.change_state("PLANNING_ITEM_TARGET")
            
    def handle_executing_path_clearance_state(self, ai_current_tile):
        # 這個狀態是當PLANNING_ITEM_TARGET決定攻擊玩家時進入的
        ai_log(f"ITEM_FOCUSED: (Engage Player Mode) Executing path clearance to player at {ai_current_tile}.")
        # 以下邏輯與 AggressiveAI 的類似，但完成後回到道具規劃
        if self.ai_just_placed_bomb: return

        if not self.astar_planned_path or self.astar_path_current_segment_index >= len(self.astar_planned_path):
            self.change_state("PLANNING_ITEM_TARGET"); return 

        if self.current_movement_sub_path: return

        target_node_in_astar = self.astar_planned_path[self.astar_path_current_segment_index]

        if ai_current_tile == (target_node_in_astar.x, target_node_in_astar.y):
            self.astar_path_current_segment_index += 1
            if self.astar_path_current_segment_index >= len(self.astar_planned_path):
                self.change_state("PLANNING_ITEM_TARGET") 
            else: self.last_decision_time = pygame.time.get_ticks() - self.ai_decision_interval
            return

        if target_node_in_astar.is_empty_for_direct_movement():
            path_to_node = self.bfs_find_direct_movement_path(ai_current_tile, (target_node_in_astar.x, target_node_in_astar.y))
            if path_to_node and len(path_to_node) > 1: self.set_current_movement_sub_path(path_to_node)
            else: self.change_state("PLANNING_ITEM_TARGET")
            return
        
        elif target_node_in_astar.is_destructible_box():
            # 為了攻擊玩家而炸牆，撤退要求可以稍低
            bomb_spot, retreat_spot = self._find_optimal_bombing_spot_for_obstacle(target_node_in_astar, ai_current_tile, 1) 
            if bomb_spot and retreat_spot:
                self.chosen_bombing_spot_coords = bomb_spot
                self.chosen_retreat_spot_coords = retreat_spot
                # 【修正】確保移動到轟炸點的邏輯與為道具炸牆時一致
                if ai_current_tile == bomb_spot:
                    if self.ai_player.bombs_placed_count < self.ai_player.max_bombs:
                        self.ai_player.place_bomb()
                        path_to_retreat_immediately = self.bfs_find_direct_movement_path(ai_current_tile, retreat_spot)
                        if path_to_retreat_immediately and len(path_to_retreat_immediately) > 1:
                            self.set_current_movement_sub_path(path_to_retreat_immediately)
                        self.change_state("TACTICAL_RETREAT_AND_WAIT")
                    else: self.change_state("PLANNING_ITEM_TARGET")
                else: # 需要移動到轟炸點
                    path_to_bomb_spot = self.bfs_find_direct_movement_path(ai_current_tile, bomb_spot)
                    if path_to_bomb_spot and len(path_to_bomb_spot) > 0: # 允許原地
                        self.set_current_movement_sub_path(path_to_bomb_spot)
                        self.change_state("MOVING_TO_BOMB_OBSTACLE") # 統一使用這個狀態來移動到轟炸點
                    else: self.change_state("PLANNING_ITEM_TARGET")
            else: self.change_state("PLANNING_ITEM_TARGET") # 找不到方案就重新規劃道具
            return
        else: self.change_state("PLANNING_ITEM_TARGET")


    # --- 特定輔助函式 ---
    def _find_best_item_on_ground(self, ai_current_tile):
        if not self.game.items_group: return None
        best_item_found = None
        highest_priority_value = float('inf') 
        shortest_path_len_to_item = float('inf')

        for item_sprite in self.game.items_group:
            if not item_sprite.alive(): continue 

            priority = self.item_type_priority.get(item_sprite.type, 99)
            item_coords = (item_sprite.rect.centerx // settings.TILE_SIZE, item_sprite.rect.centery // settings.TILE_SIZE)
            
            dist_to_item_manhattan = abs(ai_current_tile[0] - item_coords[0]) + abs(ai_current_tile[1] - item_coords[1])
            
            # 只考慮比當前最佳道具優先級更高，或優先級相同但路徑更短（或估算距離更短）的
            if priority < highest_priority_value or \
               (priority == highest_priority_value and dist_to_item_manhattan < shortest_path_len_to_item) :
                
                # 為了提高性能，只對看起來有希望的道具進行 BFS
                if dist_to_item_manhattan < shortest_path_len_to_item + 5 : # 曼哈頓距離在一個合理範圍內
                    temp_path_bfs = self.bfs_find_direct_movement_path(ai_current_tile, item_coords, max_depth=15) 
                    if temp_path_bfs and len(temp_path_bfs)>1: 
                        current_path_len = len(temp_path_bfs) -1
                        if priority < highest_priority_value or (priority == highest_priority_value and current_path_len < shortest_path_len_to_item):
                            highest_priority_value = priority
                            shortest_path_len_to_item = current_path_len
                            best_item_found = {'item': item_sprite, 'coords': item_coords, 'dist_bfs': current_path_len}
                    # 如果不能直接BFS，但優先級很高，且之前沒有找到可直接到達的更高優先級道具
                    elif priority < highest_priority_value and best_item_found is None: 
                         if dist_to_item_manhattan < shortest_path_len_to_item : 
                            highest_priority_value = priority
                            shortest_path_len_to_item = dist_to_item_manhattan 
                            best_item_found = {'item': item_sprite, 'coords': item_coords, 'dist_bfs': float('inf')} 
        if best_item_found:
            ai_log(f"ITEM_FOCUSED: Found best item on ground: {best_item_found['item'].type} (Prio: {highest_priority_value}, Est.PathLen: {best_item_found.get('dist_bfs', shortest_path_len_to_item)})")
        return best_item_found

    # （3）！！！_find_best_wall_to_bomb_for_items 修改開始！！！（3）
    def _find_best_wall_to_bomb_for_items(self, ai_current_tile, exclude_wall_node=None):
        potential_walls = []
        for r in range(self.map_manager.tile_height):
            for c in range(self.map_manager.tile_width):
                node = self._get_node_at_coords(c, r)
                if node and node.is_destructible_box():
                    if exclude_wall_node and node.x == exclude_wall_node.x and node.y == exclude_wall_node.y:
                        continue 

                    dist_to_wall = abs(ai_current_tile[0] - c) + abs(ai_current_tile[1] - r)
                    if dist_to_wall == 0: continue # 不炸腳下的牆 (通常需要先移動)
                    if dist_to_wall <= self.wall_scan_radius_for_items:
                        open_sides = 0
                        can_reach_bomb_spot = False
                        # 檢查是否能找到一個可達的、用於炸這面牆的空格子作為轟炸點
                        for dx_wall_offset, dy_wall_offset in DIRECTIONS.values():
                            bomb_spot_x = node.x + dx_wall_offset
                            bomb_spot_y = node.y + dy_wall_offset
                            bomb_spot_node_check = self._get_node_at_coords(bomb_spot_x, bomb_spot_y)
                            if bomb_spot_node_check and bomb_spot_node_check.is_empty_for_direct_movement():
                                # 檢查AI是否能走到這個潛在的轟炸點
                                if self.bfs_find_direct_movement_path(ai_current_tile, (bomb_spot_x, bomb_spot_y), max_depth=7): # max_depth 可以調整
                                    can_reach_bomb_spot = True
                                    # 評估炸開後的價值
                                    for dx_check, dy_check in DIRECTIONS.values():
                                        adj_node = self._get_node_at_coords(node.x + dx_check, node.y + dy_check)
                                        if adj_node and adj_node.is_empty_for_direct_movement():
                                            open_sides +=1
                                    break # 找到一個可行的轟炸點和評估即可
                        
                        if can_reach_bomb_spot and open_sides > 0: 
                             score = (open_sides * 5) - dist_to_wall 
                             potential_walls.append({'node': node, 'dist': dist_to_wall, 'open': open_sides, 'score': score})
        
        if not potential_walls: return None
        potential_walls.sort(key=lambda w: w['score'], reverse=True) 
        
        top_walls_to_consider = [w['node'] for w in potential_walls[:self.max_walls_to_consider_for_items]]
        
        if top_walls_to_consider:
            # 從候選中隨機選一個，避免總選同一個
            # chosen_wall_info = random.choice(top_walls_to_consider) if len(top_walls_to_consider) > 1 else top_walls_to_consider[0]
            # 改為選擇評分最高的那個
            chosen_wall_node = potential_walls[0]['node']
            ai_log(f"ITEM_FOCUSED: Found {len(potential_walls)} potential walls. Chosen: {chosen_wall_node} (Score: {potential_walls[0]['score']})")
            return chosen_wall_node
        return None
    # （3）！！！_find_best_wall_to_bomb_for_items 修改結束！！！（3）

    def _find_optimal_bombing_spot_for_obstacle(self, wall_node, ai_current_tile, min_retreat_options=1):
        candidate_placements = []
        for dx_wall_offset, dy_wall_offset in DIRECTIONS.values():
            bomb_spot_x = wall_node.x + dx_wall_offset
            bomb_spot_y = wall_node.y + dy_wall_offset
            bomb_spot_coords = (bomb_spot_x, bomb_spot_y)
            
            # 【關鍵檢查】確保轟炸點不是上次失敗的轟炸點 (如果目標牆也一樣)
            if self.last_failed_bombing_spot and \
               bomb_spot_coords == self.last_failed_bombing_spot and \
               self.potential_wall_to_bomb_for_item == self.last_failed_bombing_target_wall:
                ai_log(f"ITEM_FOCUSED: Skipping previously failed bombing spot {bomb_spot_coords} for wall {wall_node}")
                continue

            bomb_spot_node = self._get_node_at_coords(bomb_spot_x, bomb_spot_y)
            if not (bomb_spot_node and bomb_spot_node.is_empty_for_direct_movement()):
                continue

            path_to_bomb_spot = self.bfs_find_direct_movement_path(ai_current_tile, bomb_spot_coords, max_depth=7) 
            if not path_to_bomb_spot : continue

            retreat_spots = self.find_safe_tiles_nearby_for_retreat(
                bomb_spot_coords, bomb_spot_coords, self.ai_player.bomb_range, 
                self.retreat_search_depth, min_retreat_options 
            )
            if retreat_spots:
                best_retreat_spot = retreat_spots[0] 
                if self.bfs_find_direct_movement_path(bomb_spot_coords, best_retreat_spot, self.retreat_search_depth):
                    candidate_placements.append({
                        'bomb_spot': bomb_spot_coords, 
                        'retreat_spot': best_retreat_spot,
                        'path_to_bomb_len': len(path_to_bomb_spot)
                    })
        
        if not candidate_placements: return None, None
        candidate_placements.sort(key=lambda p: p['path_to_bomb_len'])
        return candidate_placements[0]['bomb_spot'], candidate_placements[0]['retreat_spot']

    def _find_safe_roaming_spots(self, ai_current_tile, count=1, depth=3, exclude_target=None):
        q = deque([(ai_current_tile, 0)]) 
        visited = {ai_current_tile}
        potential_spots = []

        while q and len(potential_spots) < count * 10: # 多找些候選
            (curr_x, curr_y), d = q.popleft()

            if d > 0 and d <= depth: 
                if (curr_x, curr_y) == exclude_target: continue # 排除上次失敗的漫遊目標

                if not self.is_tile_dangerous(curr_x, curr_y, future_seconds=self.evasion_urgency_seconds * 0.3): # 漫遊時對目標點安全性要求可以略低
                    openness = self._get_tile_openness(curr_x, curr_y, radius=1)
                    if openness >= 1 : 
                        if (curr_x, curr_y) != ai_current_tile:
                           potential_spots.append(((curr_x, curr_y), openness))
            
            if d < depth: 
                shuffled_directions = list(DIRECTIONS.values()); random.shuffle(shuffled_directions) 
                for dx, dy in shuffled_directions: 
                    next_x, next_y = curr_x + dx, curr_y + dy 
                    next_coords = (next_x, next_y) 
                    if next_coords not in visited: 
                        node = self._get_node_at_coords(next_x, next_y) 
                        if node and node.is_empty_for_direct_movement(): 
                             if not self.is_tile_dangerous(next_x, next_y, future_seconds=0.05): # 路徑上的格子短期安全即可
                                visited.add(next_coords) 
                                q.append((next_coords, d + 1)) 
        
        if not potential_spots: return [] 
        potential_spots.sort(key=lambda s: s[1], reverse=True) 
        
        # 過濾掉AI當前位置（如果意外加入）
        final_choices = [spot[0] for spot in potential_spots if spot[0] != ai_current_tile]
        
        return final_choices[:count]