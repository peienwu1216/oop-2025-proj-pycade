# oop-2025-proj-pycade/core/ai_controller_conservative.py

import pygame
import settings #
import random #
from collections import deque #
from .ai_controller_base import AIControllerBase, ai_log, DIRECTIONS #

class ConservativeAIController(AIControllerBase):
    """
    一個謹慎的 AI，主要行為是隨機安全漫遊，並伺機炸開障礙物以獲取道具。
    它會極力避免與玩家直接衝突，並優先確保自身安全。
    此版本強化了其環境感知、躲避機動性和決策智能。
    """
    def __init__(self, ai_player_sprite, game_instance): #
        super().__init__(ai_player_sprite, game_instance) #
        
        ai_log("ConservativeAIController (Enhanced Roaming & Opportunistic v2) initialized.") #
        
        # 行為參數
        self.obstacle_bombing_chance = 0.15 #
        # 【調整】讓躲避更靈敏，預判時間可以稍短，但逃跑路徑的選擇更重要
        self.evasion_urgency_seconds = getattr(settings, "AI_CONSERVATIVE_EVASION_SECONDS", 0.6) #
        self.min_retreat_options_for_obstacle = 2 #
        self.retreat_search_depth = getattr(settings, "AI_CONSERVATIVE_RETREAT_DEPTH", 7) #
        self.roam_target_seek_depth = 4     #
        self.idle_duration_ms = 1200        # # 減少閒置時間，保持一定的活躍度

        # 內部狀態
        self.roaming_target_tile = None #
        self.target_obstacle_to_bomb = None #
        
        # 設定此 AI 在卡住時，預設回到哪個規劃狀態
        self.default_planning_state_on_stuck = "PLANNING_ROAM"
        # 設定此 AI 在成功躲避後，預設回到哪個狀態
        self.default_state_after_evasion = "PLANNING_ROAM"

        self.change_state("PLANNING_ROAM") # 初始狀態為規劃漫遊 #

    def reset_state(self): #
        super().reset_state() #
        self.roaming_target_tile = None #
        self.target_obstacle_to_bomb = None #
        self.change_state("PLANNING_ROAM") #
        ai_log(f"ConservativeAI (Enhanced v2) reset. Current state: {self.current_state}") #

    # --- 狀態處理邏輯 ---

    def handle_planning_roam_state(self, ai_current_tile): #
        ai_log(f"CONSERVATIVE: In PLANNING_ROAM at {ai_current_tile}.") #
        self.roaming_target_tile = None 

        # 1. 檢查是否有值得炸的牆壁 (如果AI當前沒有移動任務)
        if not self.current_movement_sub_path and random.random() < self.obstacle_bombing_chance: #
            self.target_obstacle_to_bomb = self._find_nearby_worthwhile_obstacle(ai_current_tile, search_radius=3) #
            if self.target_obstacle_to_bomb: #
                ai_log(f"CONSERVATIVE: Found obstacle {self.target_obstacle_to_bomb} to consider bombing.") #
                self.change_state("ASSESSING_OBSTACLE") #
                return

        # 2. 如果不炸牆，則尋找新的漫遊目標點
        potential_roam_targets = self._find_safe_roaming_spots(ai_current_tile, count=3, depth=self.roam_target_seek_depth) #
        if potential_roam_targets: #
            self.roaming_target_tile = random.choice(potential_roam_targets) #
            
            if self.roaming_target_tile == ai_current_tile: #
                ai_log("CONSERVATIVE: Roam target is current tile. Idling briefly.")
                self.roaming_target_tile = None
                self.change_state("IDLE") 
                return

            path_to_roam_target = self.bfs_find_direct_movement_path(ai_current_tile, self.roaming_target_tile) #
            
            if path_to_roam_target and len(path_to_roam_target) > 1: #
                ai_log(f"CONSERVATIVE: New roam target {self.roaming_target_tile}. Path: {path_to_roam_target}") #
                self.set_current_movement_sub_path(path_to_roam_target) #
                self.change_state("ROAMING") 
            else:
                ai_log("CONSERVATIVE: Could not find valid path to roam target. Idling.") #
                self.roaming_target_tile = None #
                self.change_state("IDLE") #
        else:
            ai_log("CONSERVATIVE: No safe roaming spots found. Idling.") #
            self.change_state("IDLE") #

    def handle_roaming_state(self, ai_current_tile): #
        if not self.roaming_target_tile: 
            # 如果漫遊目標丟失，重新規劃
            ai_log("CONSERVATIVE: Roaming target lost. Re-planning roam.")
            self.change_state("PLANNING_ROAM"); return

        ai_log(f"CONSERVATIVE: Roaming. At {ai_current_tile}, target: {self.roaming_target_tile}, sub_path: {'Yes' if self.current_movement_sub_path else 'No'}") #

        # 如果當前沒有移動子路徑 (表示之前的路徑已完成，或一開始就沒有)
        if not self.current_movement_sub_path: #
            if ai_current_tile == self.roaming_target_tile: 
                ai_log("CONSERVATIVE: Reached roam target. Re-planning next roam.") #
                self.change_state("PLANNING_ROAM") #
            else: # 還沒到目標，但沒有路徑 (可能是路徑失敗或初始就沒有)
                ai_log(f"CONSERVATIVE: Attempting to path to roam target {self.roaming_target_tile}.")
                path_to_roam_target = self.bfs_find_direct_movement_path(ai_current_tile, self.roaming_target_tile) #
                if path_to_roam_target and len(path_to_roam_target) > 1: #
                    self.set_current_movement_sub_path(path_to_roam_target) #
                    # 狀態保持在 ROAMING，等待基底的 update 執行移動
                else: 
                    ai_log(f"CONSERVATIVE: Cannot reach roam target {self.roaming_target_tile}. Re-planning roam.") #
                    self.change_state("PLANNING_ROAM") #
        # 如果有 current_movement_sub_path，則基底的 update() 中的 execute_next_move_on_sub_path 會處理它。
        # 當 sub_path 執行完畢 (execute_next_move_on_sub_path 返回 True)，
        # 基底的 update() 會觸發下一次決策 (因為 self.last_decision_time 被重置了)，
        # AI 會再次進入此 handle_roaming_state，然後上面的 if not self.current_movement_sub_path 分支會被執行。

    def handle_assessing_obstacle_state(self, ai_current_tile): #
        ai_log(f"CONSERVATIVE: Assessing obstacle {self.target_obstacle_to_bomb} at {ai_current_tile}.") #
        if not self.target_obstacle_to_bomb or \
           not self._get_node_at_coords(self.target_obstacle_to_bomb.x, self.target_obstacle_to_bomb.y).is_destructible_box(): #
            ai_log("CONSERVATIVE: Target obstacle no longer valid or already destroyed. Returning to planning.")
            self.target_obstacle_to_bomb = None #
            self.change_state("PLANNING_ROAM"); return

        bomb_spot, retreat_spot = self._find_optimal_bombing_spot_for_obstacle(self.target_obstacle_to_bomb, ai_current_tile) #

        if bomb_spot and retreat_spot: #
            ai_log(f"CONSERVATIVE: Plan to bomb obstacle: Bomb at {bomb_spot}, retreat to {retreat_spot}.") #
            self.chosen_bombing_spot_coords = bomb_spot #
            self.chosen_retreat_spot_coords = retreat_spot #
            
            # 【修正】在移動到轟炸點之前，先設定路徑
            path_to_bomb_spot = self.bfs_find_direct_movement_path(ai_current_tile, self.chosen_bombing_spot_coords)
            if path_to_bomb_spot and len(path_to_bomb_spot) > 0 : # 允許原地不動 (長度為1，set_current_movement_sub_path 會處理)
                self.set_current_movement_sub_path(path_to_bomb_spot)
                self.change_state("MOVING_TO_BOMB_OBSTACLE") #
            else:
                ai_log("CONSERVATIVE: Cannot path to chosen bombing spot. Re-planning.")
                self.change_state("PLANNING_ROAM")
        else:
            ai_log("CONSERVATIVE: Cannot find safe way to bomb obstacle. Returning to roaming.") #
            self.target_obstacle_to_bomb = None #
            self.change_state("PLANNING_ROAM") #
            
    def handle_moving_to_bomb_obstacle_state(self, ai_current_tile): #
        # 【修正】確保 chosen_bombing_spot_coords 有效
        if not self.chosen_bombing_spot_coords: 
            ai_log("CONSERVATIVE: ERROR - No bombing spot in MOVING_TO_BOMB_OBSTACLE. Re-planning.")
            self.change_state("PLANNING_ROAM"); return

        ai_log(f"CONSERVATIVE: Moving to bomb spot {self.chosen_bombing_spot_coords}. At {ai_current_tile}.") #
        if self.current_movement_sub_path: return # 正在移動 #

        # 當 current_movement_sub_path 為空，表示路徑已走完或失敗
        if ai_current_tile == self.chosen_bombing_spot_coords: #
            if self.ai_player.bombs_placed_count < self.ai_player.max_bombs: #
                ai_log("CONSERVATIVE: At bombing spot. Placing bomb for obstacle.") #
                self.ai_player.place_bomb() #
                
                path_to_retreat = self.bfs_find_direct_movement_path(ai_current_tile, self.chosen_retreat_spot_coords) #
                if path_to_retreat and len(path_to_retreat) > 1: #
                    self.set_current_movement_sub_path(path_to_retreat) #
                # 即使找不到撤退路徑，也必須進入撤退狀態，讓EVADING_DANGER接管
                self.change_state("TACTICAL_RETREAT_AND_WAIT") #
            else:
                ai_log("CONSERVATIVE: At bombing spot, but no bombs available. Returning to roaming.") #
                self.change_state("PLANNING_ROAM") #
        else: 
            ai_log(f"CONSERVATIVE: Path to bombing spot {self.chosen_bombing_spot_coords} failed or ended before arrival. Current: {ai_current_tile}. Re-planning.") #
            self.change_state("PLANNING_ROAM") #

    def handle_tactical_retreat_and_wait_state(self, ai_current_tile): #
        if not self.chosen_retreat_spot_coords: 
            ai_log("CONSERVATIVE: ERROR - No retreat spot in TACTICAL_RETREAT. Evading.")
            self.change_state("EVADING_DANGER"); return

        ai_log(f"CONSERVATIVE: Retreating/Waiting. At {ai_current_tile}. Target: {self.chosen_retreat_spot_coords}.") #
        if self.current_movement_sub_path: return #
        
        if ai_current_tile == self.chosen_retreat_spot_coords: #
            if not self.is_bomb_still_active(self.last_bomb_placed_time): #
                self.ai_just_placed_bomb = False #
                self.target_obstacle_to_bomb = None #
                self.chosen_bombing_spot_coords = None # 清理轟炸點
                self.chosen_retreat_spot_coords = None # 清理撤退點
                self.change_state("PLANNING_ROAM") #
            return #

        path_to_retreat = self.bfs_find_direct_movement_path(ai_current_tile, self.chosen_retreat_spot_coords) #
        if path_to_retreat and len(path_to_retreat) > 1: #
            self.set_current_movement_sub_path(path_to_retreat) #
        else: 
            ai_log("CONSERVATIVE: CRITICAL - Cannot reach chosen retreat spot. Evading.") #
            self.change_state("EVADING_DANGER") #
            
    def handle_evading_danger_state(self, ai_current_tile): #
        """優化後的逃跑邏輯：更積極尋找並選擇最佳逃生路徑。"""
        ai_log(f"CONSERVATIVE: EVADING DANGER at {ai_current_tile} with urgency: {self.evasion_urgency_seconds}s.") #
        
        # 【修正】基底類別的 is_tile_dangerous 已經考慮了 future_seconds，這裡直接使用 evasion_urgency_seconds
        if not self.is_tile_dangerous(ai_current_tile[0], ai_current_tile[1], future_seconds=self.evasion_urgency_seconds): #
            ai_log("CONSERVATIVE: Danger seems to have passed. Returning to roaming.") #
            self.change_state("PLANNING_ROAM") #
            return

        if self.current_movement_sub_path: 
            target_of_current_path = self.current_movement_sub_path[-1] #
            # 檢查目標點是否「立即」危險，或者路徑只剩一步但那一步是危險的
            if self.is_tile_dangerous(target_of_current_path[0], target_of_current_path[1], 0.05) or \
               (len(self.current_movement_sub_path) <= 2 and self.is_tile_dangerous(target_of_current_path[0], target_of_current_path[1], 0.2)):
                ai_log("CONSERVATIVE: Current evasion path target became dangerous or path too short/risky. Re-planning evasion.") #
                self.current_movement_sub_path = [] 

        if not self.current_movement_sub_path: 
            ai_log("CONSERVATIVE: Finding new evasion path.") #
            safe_spots = self.find_safe_tiles_nearby_for_retreat(
                from_coords=ai_current_tile,
                bomb_coords_as_danger_source=ai_current_tile, 
                bomb_range_of_danger_source=0, 
                max_depth=self.retreat_search_depth + 1, # 逃跑時看得更遠
                min_options_needed=3 
            ) #
            
            best_path_to_safety = None
            if safe_spots: #
                candidate_paths = []
                for spot in safe_spots: #
                    path = self.bfs_find_direct_movement_path(ai_current_tile, spot, max_depth=self.retreat_search_depth + 1) #
                    if path and len(path) > 1: #
                        openness = self._get_tile_openness(spot[0], spot[1]) #
                        candidate_paths.append({'path': path, 'openness': openness, 'len': len(path)})
                
                if candidate_paths:
                    candidate_paths.sort(key=lambda p: (-p['openness'], p['len'])) # 優先空曠，其次路徑短
                    best_path_to_safety = candidate_paths[0]['path']
            
            if best_path_to_safety: #
                ai_log(f"CONSERVATIVE: Found best evasion path to {best_path_to_safety[-1]}. Path: {best_path_to_safety}") #
                self.set_current_movement_sub_path(best_path_to_safety) #
            else: 
                ai_log("CONSERVATIVE: CRITICAL - No valid evasion path found! Attempting desperate move.") #
                self._attempt_desperate_move(ai_current_tile)

    def _attempt_desperate_move(self, ai_current_tile): #
        """在無路可逃時，嘗試向最不壞的相鄰格子移動一步。"""
        possible_moves = []
        for dx, dy in DIRECTIONS.values(): #
            next_x, next_y = ai_current_tile[0] + dx, ai_current_tile[1] + dy #
            node = self._get_node_at_coords(next_x, next_y) #
            if node and node.is_empty_for_direct_movement(): #
                danger_score = 0
                if self.is_tile_dangerous(next_x, next_y, 0.05): danger_score += 20 # 極度即時危險
                elif self.is_tile_dangerous(next_x, next_y, 0.15): danger_score += 10 # 即將爆炸
                elif self.is_tile_dangerous(next_x, next_y, 0.3): danger_score += 5  # 短期危險
                possible_moves.append(((next_x, next_y), danger_score))
        
        if possible_moves:
            possible_moves.sort(key=lambda m: m[1]) # 按危險評分排序，選最不危險的
            desperate_target = possible_moves[0][0]
            ai_log(f"CONSERVATIVE: Making a desperate random move to {desperate_target}.") #
            self.set_current_movement_sub_path([ai_current_tile, desperate_target]) #
        else:
            ai_log("CONSERVATIVE: No desperate moves available. Stuck in danger.") #

    def handle_idle_state(self, ai_current_tile): #
        ai_log(f"CONSERVATIVE: Briefly idling at {ai_current_tile}.") #
        if pygame.time.get_ticks() - self.state_start_time > self.idle_duration_ms: #
            self.change_state("PLANNING_ROAM") #

    # --- 特定輔助函式 ---
    def _find_nearby_worthwhile_obstacle(self, ai_current_tile, search_radius=3): #
        potential_targets = []
        for r_offset in range(-search_radius, search_radius + 1): #
            for c_offset in range(-search_radius, search_radius + 1): #
                if abs(r_offset) + abs(c_offset) > search_radius : continue #
                if r_offset == 0 and c_offset == 0: continue #
                check_x, check_y = ai_current_tile[0] + c_offset, ai_current_tile[1] + r_offset #
                node = self._get_node_at_coords(check_x, check_y) #
                if node and node.is_destructible_box(): #
                    # 簡單價值判斷：如果牆的另一邊是空格，或能打通到更開闊的地方
                    for dr, dc in DIRECTIONS.values(): #
                        next_to_wall_x, next_to_wall_y = node.x + dr, node.y + dc
                        if (next_to_wall_x, next_to_wall_y) != ai_current_tile and \
                           (next_to_wall_x, next_to_wall_y) != (node.x, node.y) :
                            next_node = self._get_node_at_coords(next_to_wall_x, next_to_wall_y) #
                            if next_node and next_node.is_empty_for_direct_movement(): #
                                potential_targets.append(node) #
                                break 
                    # if node in potential_targets: continue # 避免重複加入，但上面的 break 已經處理
        if potential_targets: #
            return random.choice(potential_targets) #
        return None #

    def _find_optimal_bombing_spot_for_obstacle(self, wall_node, ai_current_tile): #
        candidate_placements = []
        for dx_wall_offset, dy_wall_offset in DIRECTIONS.values(): #
            bomb_spot_x = wall_node.x + dx_wall_offset #
            bomb_spot_y = wall_node.y + dy_wall_offset #
            bomb_spot_coords = (bomb_spot_x, bomb_spot_y) #
            
            bomb_spot_node = self._get_node_at_coords(bomb_spot_x, bomb_spot_y) #
            if not (bomb_spot_node and bomb_spot_node.is_empty_for_direct_movement()): continue #

            path_to_bomb_spot = self.bfs_find_direct_movement_path(ai_current_tile, bomb_spot_coords, max_depth=5) #
            if not path_to_bomb_spot : continue # 

            retreat_spots = self.find_safe_tiles_nearby_for_retreat(
                bomb_spot_coords, bomb_spot_coords, self.ai_player.bomb_range, 
                self.retreat_search_depth, self.min_retreat_options_for_obstacle
            ) #
            if retreat_spots: #
                best_retreat_spot = retreat_spots[0]  #
                if self.bfs_find_direct_movement_path(bomb_spot_coords, best_retreat_spot, self.retreat_search_depth): #
                    candidate_placements.append({ #
                        'bomb_spot': bomb_spot_coords,  #
                        'retreat_spot': best_retreat_spot, #
                        'path_to_bomb_len': len(path_to_bomb_spot) #
                    })
        
        if not candidate_placements: return None, None #
        candidate_placements.sort(key=lambda p: p['path_to_bomb_len']) #
        return candidate_placements[0]['bomb_spot'], candidate_placements[0]['retreat_spot'] #

    def _find_safe_roaming_spots(self, ai_current_tile, count=1, depth=3): #
        q = deque([(ai_current_tile, 0)]) # (coords, current_depth) #
        visited = {ai_current_tile} #
        potential_spots = [] #

        while q and len(potential_spots) < count * 5: # 找多一點候選 #
            (curr_x, curr_y), d = q.popleft() #

            if d > 0 and d <= depth: #
                # 漫遊時，對目標點的安全性要求可以略微放寬一點點，主要確保路徑安全
                if not self.is_tile_dangerous(curr_x, curr_y, future_seconds=self.evasion_urgency_seconds * 0.7): #
                    openness = self._get_tile_openness(curr_x, curr_y, radius=1) #
                    if openness >= 1 : # 至少有一個方向是空的，避免選到死角
                        potential_spots.append(((curr_x, curr_y), openness))
            
            if d < depth: #
                shuffled_directions = list(DIRECTIONS.values()); random.shuffle(shuffled_directions) #
                for dx, dy in shuffled_directions: #
                    next_x, next_y = curr_x + dx, curr_y + dy #
                    next_coords = (next_x, next_y) #
                    if next_coords not in visited: #
                        node = self._get_node_at_coords(next_x, next_y) #
                        if node and node.is_empty_for_direct_movement(): #
                             if not self.is_tile_dangerous(next_x, next_y, future_seconds=0.1): # # 路徑上的格子短期安全即可
                                visited.add(next_coords) #
                                q.append((next_coords, d + 1)) #
        
        if not potential_spots: return [] #
        potential_spots.sort(key=lambda s: s[1], reverse=True) #
        return [spot[0] for spot in potential_spots[:count]] #

    # ConservativeAI 不覆寫 debug_draw_path，直接使用基底類別的精美版