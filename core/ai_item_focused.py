# oop-2025-proj-pycade/core/ai_item_focused.py

import pygame
import settings
import random
from collections import deque
from .ai_controller_base import AIControllerBase, ai_log, DIRECTIONS, TileNode

class ItemFocusedAIController(AIControllerBase):
    """
    An AI that focuses on items, becomes aggressive with power, and switches
    to a chain-bombing hunting strategy in the endgame.
    v7 - Chain Bombing Endgame: Attempts to place multiple bombs in sequence
    during endgame hunt by moving to temporary safe spots.
    """
    def __init__(self, ai_player_sprite, game_instance):
        super().__init__(ai_player_sprite, game_instance)
        
        ai_log("ItemFocusedAIController (v7.1 - Attribute Fix) initialized.") 
        
        self.evasion_urgency_seconds = getattr(settings, "AI_ITEM_FOCUSED_EVASION_SECONDS", 0.5)
        self.retreat_search_depth = getattr(settings, "AI_ITEM_FOCUSED_RETREAT_DEPTH", 7)
        self.min_retreat_options_for_obstacle_bombing = 1
        
        self.max_walls_to_consider_for_items = getattr(settings, "AI_ITEM_MAX_WALL_TARGETS", 4)
        self.wall_scan_radius_for_items = getattr(settings, "AI_ITEM_WALL_SCAN_RADIUS", 6)
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
        self.last_failed_roam_target = None 
        self.roam_target_seek_depth = 10 
        self.idle_duration_ms = 1500 

        self.cqc_engagement_distance = getattr(settings, "AI_AGGRESSIVE_CQC_ENGAGE_DISTANCE", 2) 
        self.cqc_bomb_chance = getattr(settings, "AI_AGGRESSIVE_CQC_BOMB_CHANCE", 0.75) 
        
        # 新增：用於連環轟炸的狀態
        self.is_chain_bombing_active = False 
        self.chain_bombs_placed_in_sequence = 0 
        self.max_bombs_per_chain = 2  
        
        # *** BUG FIX: 初始化遺漏的屬性 ***
        self.last_placed_bomb_for_chain_coords = None 
        
        self.current_chain_target_stand_tile = None 
        self.current_chain_retreat_tile = None    
        self.final_retreat_spot_after_chain = None 

        self.change_state("PLANNING_ITEM_TARGET") 

    @property
    def aggression_level(self):
        base_bombs = settings.INITIAL_BOMBS #
        base_range = settings.INITIAL_BOMB_RANGE #
        bomb_power = (self.ai_player.max_bombs - base_bombs) * 0.4  #
        range_power = (self.ai_player.bomb_range - base_range) * 0.6 #
        level = bomb_power + range_power #
        return min(1.0, level / 4.0) #

    def _is_endgame(self): # 判斷是否進入終局
        no_destructible_walls = not self.game.map_manager.destructible_walls_group #
        no_items_on_ground = not self.game.items_group #
        return no_destructible_walls and no_items_on_ground #

    def reset_state(self): #
        super().reset_state() #
        self.target_item_on_ground = None #
        self.potential_wall_to_bomb_for_item = None #
        self.last_failed_bombing_target_wall = None #
        self.last_failed_bombing_spot = None #
        self.last_failed_roam_target = None #
        
        self._reset_chain_bombing_state() # 重置連環轟炸狀態

        self.change_state("PLANNING_ITEM_TARGET") #
        ai_log(f"ItemFocusedAIController (v7) reset. Current state: {self.current_state}") #

    def _reset_chain_bombing_state(self): #
        """Helper to reset chain bombing specific attributes."""
        ai_log("    Resetting chain bombing state variables.") #
        self.is_chain_bombing_active = False #
        self.chain_bombs_placed_in_sequence = 0 #
        
        # *** BUG FIX: 加入遺漏的屬性重置 ***
        self.last_placed_bomb_for_chain_coords = None #
        
        self.current_chain_target_stand_tile = None #
        self.current_chain_retreat_tile = None #
        self.final_retreat_spot_after_chain = None #


    def change_state(self, new_state): #
        if self.current_state != new_state: #
            # 如果從 ENDGAME_HUNT 或 TACTICAL_RETREAT_AND_WAIT (可能因連鎖而進入) 離開
            # 並且新的狀態不是這兩者之一，則重置連鎖狀態
            if self.current_state in ["ENDGAME_HUNT", "TACTICAL_RETREAT_AND_WAIT"] and \
               new_state not in ["ENDGAME_HUNT", "TACTICAL_RETREAT_AND_WAIT"]:
                if self.is_chain_bombing_active: # 只有當確實執行過連鎖才打印日誌
                    ai_log(f"    Leaving chain-bombing related state ({self.current_state}) for {new_state}. Resetting chain state.")
                self._reset_chain_bombing_state()
        super().change_state(new_state) #


    # --- State Handling ---

    def handle_planning_item_target_state(self, ai_current_tile): #
        ai_log(f"ITEM_FOCUSED: In PLANNING_ITEM_TARGET at {ai_current_tile}. Aggression: {self.aggression_level:.2f}") #

        if self._is_endgame(): #
            ai_log("ITEM_FOCUSED: Endgame condition met. Switching to ENDGAME_HUNT.") #
            self._reset_chain_bombing_state() # 確保開始新的 endgame hunt 時重置
            self.change_state("ENDGAME_HUNT") #
            return

        # ... (找道具、攻擊性檢測、找牆、漫遊的邏輯與 v6 版本相同) ...
        self.target_item_on_ground = None #
        self.potential_wall_to_bomb_for_item = None #
        self.astar_planned_path = [] #

        best_item_on_ground = self._find_best_item_on_ground(ai_current_tile) #
        if best_item_on_ground: #
            self.target_item_on_ground = best_item_on_ground['item'] #
            item_coords = best_item_on_ground['coords'] #
            path_to_item = self.bfs_find_direct_movement_path(ai_current_tile, item_coords, max_depth=25) #
            if path_to_item and len(path_to_item) > 1: #
                self.set_current_movement_sub_path(path_to_item) #
                self.change_state("MOVING_TO_COLLECT_ITEM") #
                return
            self.astar_planned_path = self.astar_find_path(ai_current_tile, item_coords) #
            if self.astar_planned_path: #
                self.astar_path_current_segment_index = 0 #
                self.change_state("EXECUTING_ASTAR_PATH_TO_TARGET") #
                return
            self.target_item_on_ground = None #

        human_pos = self._get_human_player_current_tile() #
        attack_chance = 0.05 + (self.aggression_level * 0.7) #
        if human_pos and random.random() < attack_chance: #
            ai_log(f"ITEM_FOCUSED: Aggression check passed (chance: {attack_chance:.2f}). Engaging player.") #
            dist_to_human = abs(ai_current_tile[0] - human_pos[0]) + abs(ai_current_tile[1] - human_pos[1]) #
            if dist_to_human <= self.cqc_engagement_distance: #
                self.change_state("CLOSE_QUARTERS_COMBAT") #
            else:
                self.change_state("ENGAGING_PLAYER") #
            return

        current_wall_target = self._find_best_wall_to_bomb_for_items(ai_current_tile, exclude_wall_node=self.last_failed_bombing_target_wall) #
        if current_wall_target: #
            self.potential_wall_to_bomb_for_item = current_wall_target #
            if random.random() < self.item_bombing_chance: #
                self.change_state("ASSESSING_OBSTACLE_FOR_ITEM") #
                return
        
        potential_roam_targets = self._find_safe_roaming_spots(ai_current_tile, count=1, depth=self.roam_target_seek_depth, exclude_target=self.last_failed_roam_target) #
        if potential_roam_targets: #
            roam_target = potential_roam_targets[0] #
            path_to_roam = self.bfs_find_direct_movement_path(ai_current_tile, roam_target) #
            if path_to_roam and len(path_to_roam) > 1: #
                self.set_current_movement_sub_path(path_to_roam) #
                self.roaming_target_tile = roam_target #
                self.change_state("ROAMING") #
                return
        
        self.change_state("IDLE") #
    
    def handle_endgame_hunt_state(self, ai_current_tile): #
        ai_log(f"ITEM_FOCUSED: In ENDGAME_HUNT at {ai_current_tile}. ChainBombing: {self.is_chain_bombing_active}, Count: {self.chain_bombs_placed_in_sequence}/{self.max_bombs_per_chain}") #
        human_pos = self._get_human_player_current_tile() #
        if not human_pos: #
            self._reset_chain_bombing_state()
            self.change_state("IDLE"); return #

        if self.ai_player.action_timer > 0: return # AI 正在執行上一個動作
        if self.current_movement_sub_path: return # AI 正在移動到某處

        # 如果剛放完一顆炸彈 (ai_just_placed_bomb 會由 Player.place_bomb 設定)
        # 並且正在執行連鎖轟炸, 且已到達為躲避該炸彈的臨時點 (current_movement_sub_path is empty)
        if self.is_chain_bombing_active and self.ai_just_placed_bomb:
            # 此時 ai_just_placed_bomb 為 True, 表示 Player.place_bomb() 剛被調用
            # 通常Player.place_bomb()後，AI控制器會立即規劃撤退
            # 我們在這裡的邏輯是：如果剛放完一顆，並且還能繼續連鎖，就規劃下一顆
            ai_log(f"    Chain bomb #{self.chain_bombs_placed_in_sequence} placed. AI at {ai_current_tile}. Considering next chain bomb.")
            self.ai_just_placed_bomb = False # 清除標誌，準備下一次放置判斷

            if self.ai_player.bombs_placed_count < self.ai_player.max_bombs and \
               self.chain_bombs_placed_in_sequence < self.max_bombs_per_chain:
                # 從當前（剛躲開上一顆炸彈的臨時點）尋找下一個陷阱點
                next_bombing_plan = self._find_trapping_bomb_spot(ai_current_tile, human_pos, is_chaining=True)
                if next_bombing_plan:
                    next_stand_tile, next_temp_retreat, next_path_to_stand = next_bombing_plan
                    # 確保新的放置點與上一個不同，避免原地重複放（除非特殊策略）
                    if next_stand_tile == self.current_chain_target_stand_tile:
                         ai_log(f"    Next chain stand tile {next_stand_tile} is same as current. Stopping chain to avoid loop.")
                         self._execute_final_retreat_after_chain(ai_current_tile)
                         return

                    ai_log(f"    Found next chain bomb plan: Stand at {next_stand_tile}, temp retreat {next_temp_retreat}.")
                    self.current_chain_target_stand_tile = next_stand_tile
                    self.current_chain_retreat_tile = next_temp_retreat # 針對下一顆的臨時撤退
                    self.set_current_movement_sub_path(next_path_to_stand)
                    # AI 將移動到 next_stand_tile, 然後下個週期再次進入此 state handler,
                    # is_chain_bombing_active 仍為 True, 但 ai_just_placed_bomb 為 False, 會觸發下面的放置邏輯
                    return 
            
            # 無法繼續連鎖 (沒炸彈 / 達到上限 / 找不到好點)
            ai_log(f"    Cannot continue chain bombing (Bombs left: {self.ai_player.max_bombs - self.ai_player.bombs_placed_count}, Chain count: {self.chain_bombs_placed_in_sequence}). Executing final retreat.")
            self._execute_final_retreat_after_chain(ai_current_tile)
            return

        # --- 主要的 ENDGAME_HUNT 邏輯 (開始一個轟炸序列，或放置序列中的下一顆) ---
        target_stand_tile_for_this_bomb = self.current_chain_target_stand_tile if self.is_chain_bombing_active else None
        
        if target_stand_tile_for_this_bomb and ai_current_tile == target_stand_tile_for_this_bomb: # 已到達預計的（連鎖）放置點
            ai_log(f"    At designated chain stand tile {ai_current_tile}. Placing bomb #{self.chain_bombs_placed_in_sequence + 1}.")
            if self.ai_player.bombs_placed_count < self.ai_player.max_bombs:
                self.ai_player.place_bomb() # Player.place_bomb() 會設定 self.ai_just_placed_bomb = True
                self.chain_bombs_placed_in_sequence += 1
                # 找到躲避這顆剛放的炸彈的臨時位置
                temp_retreat_path_after_this_bomb = None
                safe_spots = self.find_safe_tiles_nearby_for_retreat(ai_current_tile, ai_current_tile, self.ai_player.bomb_range, max_depth=3, min_options_needed=1)
                if safe_spots:
                    temp_retreat_path_after_this_bomb = self.bfs_find_direct_movement_path(ai_current_tile, safe_spots[0], max_depth=3)
                
                if temp_retreat_path_after_this_bomb:
                    self.set_current_movement_sub_path(temp_retreat_path_after_this_bomb)
                    ai_log(f"    Chain bomb #{self.chain_bombs_placed_in_sequence} placed. Moving to temp retreat {safe_spots[0]}.")
                    # is_chain_bombing_active 保持 True, ai_just_placed_bomb 會是 True
                    # 下一輪 update, current_movement_sub_path 會被執行。
                    # 再下一輪, is_chain_bombing_active and self.ai_just_placed_bomb 分支會被觸發
                else: # 連臨時躲避點都找不到
                    ai_log(f"    Chain bomb #{self.chain_bombs_placed_in_sequence} placed, but NO TEMP RETREAT. Executing final retreat.")
                    self._execute_final_retreat_after_chain(ai_current_tile)
            else: # 沒炸彈了
                ai_log("    Reached chain stand tile, but no bombs left.")
                self._execute_final_retreat_after_chain(ai_current_tile)

        else: # 需要尋找一個（新的）轟炸計劃，或者移動到已規劃的 current_chain_target_stand_tile
            if self.is_chain_bombing_active and self.current_chain_target_stand_tile and ai_current_tile != self.current_chain_target_stand_tile:
                 # 正在去往下一個連鎖轟炸點的路上，但路徑已走完（所以 current_movement_sub_path 為空）
                 # 這種情況理論上不應頻繁發生，因為上面 current_movement_sub_path 的檢查會先攔截
                 ai_log(f"    Unexpected: In chain, target stand {self.current_chain_target_stand_tile}, AI at {ai_current_tile}, no sub-path. Re-evaluating.")
                 # Fall through to find a new plan / path to current target

            if not self.is_chain_bombing_active or not self.current_chain_target_stand_tile: # 開始新的轟炸序列 或 中斷後重新規劃
                self._reset_chain_bombing_state() # 確保是全新的開始
                bombing_plan = self._find_trapping_bomb_spot(ai_current_tile, human_pos, is_chaining=False)
                if bombing_plan:
                    stand_on_tile, retreat_spot, path_to_stand_on_tile = bombing_plan
                    ai_log(f"    New hunt plan: Stand at {stand_on_tile}, final retreat to {retreat_spot}.")
                    self.is_chain_bombing_active = True # 標記開始連鎖
                    self.chain_bombs_placed_in_sequence = 0
                    self.current_chain_target_stand_tile = stand_on_tile
                    self.current_chain_retreat_tile = retreat_spot # 這個是針對第一顆的臨時/最終撤退
                    self.final_retreat_spot_after_chain = retreat_spot # 也作為整個序列的最終撤退點 (可被後續更新)
                    self.set_current_movement_sub_path(path_to_stand_on_tile)
                else:
                    ai_log("    No initial trapping plan found. Fallback to ENGAGING_PLAYER.")
                    self.change_state("ENGAGING_PLAYER")
            elif self.is_chain_bombing_active and self.current_chain_target_stand_tile and ai_current_tile != self.current_chain_target_stand_tile:
                # 如果正在去往下一個連鎖點的途中，但路徑丟失了，重新規劃路徑
                ai_log(f"    Re-pathing to current chain target stand tile {self.current_chain_target_stand_tile}.")
                path_to_target = self.bfs_find_direct_movement_path(ai_current_tile, self.current_chain_target_stand_tile)
                if path_to_target:
                    self.set_current_movement_sub_path(path_to_target)
                else: # 到不了目標了
                    ai_log(f"    Cannot re-path to {self.current_chain_target_stand_tile}. Stopping chain.")
                    self._execute_final_retreat_after_chain(ai_current_tile)


    def _execute_final_retreat_after_chain(self, ai_current_tile):
        """Helper to execute retreat after a chain bombing sequence ends."""
        ai_log(f"    Executing final retreat from {ai_current_tile}. Target: {self.final_retreat_spot_after_chain}")
        self._reset_chain_bombing_state() # 清理連鎖狀態

        # 找到一個能躲避所有剛才放置的炸彈的安全點 (這一步是理想情況，但較難實現)
        # 簡化：先用 self.final_retreat_spot_after_chain，如果沒有，就用通用的
        retreat_target = self.final_retreat_spot_after_chain
        if not retreat_target:
            # 如果沒有特別為連鎖設定的最終撤退點，就用一個通用的安全點
            safe_spots = self.find_safe_tiles_nearby_for_retreat(ai_current_tile, ai_current_tile, 0, self.retreat_search_depth, 1)
            if safe_spots:
                retreat_target = safe_spots[0]
        
        if retreat_target:
            path = self.bfs_find_direct_movement_path(ai_current_tile, retreat_target, self.retreat_search_depth)
            if path:
                self.set_current_movement_sub_path(path)
        self.change_state("TACTICAL_RETREAT_AND_WAIT")


    # ... (其他 handle_... state 方法，如 _find_trapping_bomb_spot 等，與 v6 基本一致或稍作調整) ...
    def handle_moving_to_collect_item_state(self, ai_current_tile): #
        if not self.target_item_on_ground or not self.target_item_on_ground.alive(): #
            self.change_state("PLANNING_ITEM_TARGET"); return #
        item_coords = (self.target_item_on_ground.rect.centerx // settings.TILE_SIZE, self.target_item_on_ground.rect.centery // settings.TILE_SIZE) #
        if self.current_movement_sub_path: return #
        if ai_current_tile == item_coords: self.change_state("PLANNING_ITEM_TARGET") #
        else: 
            self.astar_planned_path = self.astar_find_path(ai_current_tile, item_coords) #
            if self.astar_planned_path: self.astar_path_current_segment_index = 0; self.change_state("EXECUTING_ASTAR_PATH_TO_TARGET") #
            else: self.change_state("PLANNING_ITEM_TARGET") #

    def handle_executing_astar_path_to_target_state(self, ai_current_tile): #
        if self.ai_just_placed_bomb: return #
        if not self.astar_planned_path or self.astar_path_current_segment_index >= len(self.astar_planned_path): self.change_state("PLANNING_ITEM_TARGET"); return #
        if self.current_movement_sub_path: return #
        target_node_in_astar = self.astar_planned_path[self.astar_path_current_segment_index] #
        if ai_current_tile == (target_node_in_astar.x, target_node_in_astar.y): #
            self.astar_path_current_segment_index += 1; self.last_decision_time = pygame.time.get_ticks() - self.ai_decision_interval; return #
        if target_node_in_astar.is_empty_for_direct_movement(): #
            path_to_node = self.bfs_find_direct_movement_path(ai_current_tile, (target_node_in_astar.x, target_node_in_astar.y)) #
            if path_to_node: self.set_current_movement_sub_path(path_to_node) #
            else: self.change_state("PLANNING_ITEM_TARGET") #
        elif target_node_in_astar.is_destructible_box(): #
            self.target_destructible_wall_node_in_astar = target_node_in_astar #
            bomb_spot, retreat_spot = self._find_optimal_bombing_spot_for_obstacle(target_node_in_astar, ai_current_tile, 1) #
            if bomb_spot and retreat_spot: self.chosen_bombing_spot_coords = bomb_spot; self.chosen_retreat_spot_coords = retreat_spot; self.change_state("MOVING_TO_BOMB_OBSTACLE") #
            else: self.change_state("PLANNING_ITEM_TARGET") #
        else: self.change_state("PLANNING_ITEM_TARGET") #

    def handle_assessing_obstacle_for_item_state(self, ai_current_tile): #
        if not self.potential_wall_to_bomb_for_item or not self._get_node_at_coords(self.potential_wall_to_bomb_for_item.x, self.potential_wall_to_bomb_for_item.y).is_destructible_box(): #
            self.change_state("PLANNING_ITEM_TARGET"); return #
        bomb_spot, retreat_spot = self._find_optimal_bombing_spot_for_obstacle(self.potential_wall_to_bomb_for_item, ai_current_tile, self.min_retreat_options_for_obstacle_bombing) #
        if bomb_spot and retreat_spot: #
            self.chosen_bombing_spot_coords = bomb_spot; self.chosen_retreat_spot_coords = retreat_spot #
            path_to_bomb_spot = self.bfs_find_direct_movement_path(ai_current_tile, self.chosen_bombing_spot_coords) #
            if path_to_bomb_spot: self.set_current_movement_sub_path(path_to_bomb_spot); self.change_state("MOVING_TO_BOMB_OBSTACLE") #
            else: self.change_state("PLANNING_ITEM_TARGET") #
        else: self.change_state("PLANNING_ITEM_TARGET") #

    def handle_moving_to_bomb_obstacle_state(self, ai_current_tile): #
        if not self.chosen_bombing_spot_coords: self.change_state("PLANNING_ITEM_TARGET"); return #
        if self.current_movement_sub_path: return #
        if ai_current_tile == self.chosen_bombing_spot_coords: #
            if self.ai_player.bombs_placed_count < self.ai_player.max_bombs: #
                self.ai_player.place_bomb() #
                path_to_retreat = self.bfs_find_direct_movement_path(ai_current_tile, self.chosen_retreat_spot_coords, self.retreat_search_depth) #
                if path_to_retreat: self.set_current_movement_sub_path(path_to_retreat) #
                self.change_state("TACTICAL_RETREAT_AND_WAIT") #
            else: self.change_state("PLANNING_ITEM_TARGET") #
        else: self.change_state("PLANNING_ITEM_TARGET") #

    def handle_tactical_retreat_and_wait_state(self, ai_current_tile): #
        if not self.chosen_retreat_spot_coords and not self.final_retreat_spot_after_chain: # 如果連最終撤退點都沒有
            ai_log(f"ITEM_FOCUSED (Retreat): No retreat spot defined. Switching to EVADING_DANGER.")
            self.change_state("EVADING_DANGER"); return

        retreat_target_for_this_wait = self.final_retreat_spot_after_chain if self.final_retreat_spot_after_chain else self.chosen_retreat_spot_coords

        if self.current_movement_sub_path: return #

        if ai_current_tile == retreat_target_for_this_wait: #
            all_my_bombs_cleared = True # 假設所有炸彈都清了
            # 在更複雜的實現中，這裡應該檢查 self.game.bombs_group 中由該AI放置且未爆炸的炸彈
            # 但 self.is_bomb_still_active(self.last_bomb_placed_time) 只看最後一顆
            # 為了簡化，我們假設如果最後一顆清了，可能其他的也差不多了 (或者依賴 stuck detection)
            if not self.is_bomb_still_active(self.last_bomb_placed_time): #
                self.ai_just_placed_bomb = False #
                self.potential_wall_to_bomb_for_item = None 
                self.target_destructible_wall_node_in_astar = None
                self.chosen_bombing_spot_coords = None
                # self.chosen_retreat_spot_coords = None # 保留這個，可能還有用
                
                is_currently_endgame = self._is_endgame()
                ai_has_bombs = self.ai_player.bombs_placed_count < self.ai_player.max_bombs

                # 只有在清場後，才重置連鎖狀態，準備下一次可能的序列
                was_chaining = self.is_chain_bombing_active
                self._reset_chain_bombing_state()


                if is_currently_endgame: #
                    if ai_has_bombs: #
                        ai_log("ITEM_FOCUSED (Retreat): Endgame, bomb(s) cleared, has bombs. Re-entering ENDGAME_HUNT.")
                        self.change_state("ENDGAME_HUNT") #
                    else: # 終局但沒炸彈了
                        ai_log("ITEM_FOCUSED (Retreat): Endgame, bomb(s) cleared, NO bombs left. Engaging.")
                        self.change_state("ENGAGING_PLAYER")
                else: # 不是終局，回到常規規劃
                    ai_log("ITEM_FOCUSED (Retreat): Bomb(s) cleared. Re-planning for items/aggression.")
                    self.change_state("PLANNING_ITEM_TARGET") #
            return #
        
        path_to_retreat = self.bfs_find_direct_movement_path(ai_current_tile, retreat_target_for_this_wait, self.retreat_search_depth) #
        if path_to_retreat: self.set_current_movement_sub_path(path_to_retreat) #
        else: self.change_state("EVADING_DANGER") #
            
    def handle_evading_danger_state(self, ai_current_tile): #
        super().handle_evading_danger_state(ai_current_tile) #

    def handle_idle_state(self, ai_current_tile): #
        if pygame.time.get_ticks() - self.state_start_time > self.idle_duration_ms: #
            self.change_state("PLANNING_ITEM_TARGET") #

    def handle_engaging_player_state(self, ai_current_tile): #
        human_pos = self._get_human_player_current_tile() #
        if not human_pos: self.change_state("PLANNING_ITEM_TARGET"); return #
        dist_to_human = abs(ai_current_tile[0] - human_pos[0]) + abs(ai_current_tile[1] - human_pos[1]) #
        if dist_to_human <= self.cqc_engagement_distance: self.change_state("CLOSE_QUARTERS_COMBAT"); return #
        if self.current_movement_sub_path: return #
        if not self.ai_just_placed_bomb and self.ai_player.bombs_placed_count < self.ai_player.max_bombs: #
            if self._is_tile_in_hypothetical_blast(human_pos[0], human_pos[1], ai_current_tile[0], ai_current_tile[1], self.ai_player.bomb_range): #
                can_bomb, retreat_spot = self.can_place_bomb_and_retreat(ai_current_tile) #
                if can_bomb or random.random() < self.aggression_level * 0.5: #
                    self.chosen_retreat_spot_coords = retreat_spot #
                    self.ai_player.place_bomb() #
                    if retreat_spot: self.set_current_movement_sub_path(self.bfs_find_direct_movement_path(ai_current_tile, retreat_spot)) #
                    self.change_state("TACTICAL_RETREAT_AND_WAIT") #
                    return
        if not self.current_movement_sub_path: #
            path_to_human = self.bfs_find_direct_movement_path(ai_current_tile, human_pos, max_depth=10) #
            if path_to_human: self.set_current_movement_sub_path(path_to_human) #
            else: self.change_state("PLANNING_ITEM_TARGET") #

    def handle_close_quarters_combat_state(self, ai_current_tile): #
        human_pos = self._get_human_player_current_tile() #
        if not human_pos: self.change_state("PLANNING_ITEM_TARGET"); return #
        dist_to_human = abs(ai_current_tile[0] - human_pos[0]) + abs(ai_current_tile[1] - human_pos[1]) #
        if dist_to_human > self.cqc_engagement_distance + 1: self.change_state("ENGAGING_PLAYER"); return #
        if self.current_movement_sub_path: return #
        if not self.ai_just_placed_bomb and self.ai_player.bombs_placed_count < self.ai_player.max_bombs: #
            if self._is_tile_in_hypothetical_blast(human_pos[0], human_pos[1], ai_current_tile[0], ai_current_tile[1], self.ai_player.bomb_range): #
                if random.random() < (self.cqc_bomb_chance * (0.5 + self.aggression_level)): #
                    can_bomb, retreat_spot = self.can_place_bomb_and_retreat(ai_current_tile) #
                    self.chosen_retreat_spot_coords = retreat_spot #
                    self.ai_player.place_bomb() #
                    if retreat_spot: self.set_current_movement_sub_path(self.bfs_find_direct_movement_path(ai_current_tile, retreat_spot)) #
                    self.change_state("TACTICAL_RETREAT_AND_WAIT") #
                    return
        if not self.current_movement_sub_path: #
            available_spots = [c for c in self._get_adjacent_empty_tiles(ai_current_tile) if c != human_pos] #
            if available_spots: self.set_current_movement_sub_path([ai_current_tile, random.choice(available_spots)]) #

    # --- Helper Functions (許多與 v6 相同) ---
    def _find_trapping_bomb_spot(self, ai_current_tile, player_tile, is_chaining=False): #
        ai_log(f"    TRAP SEARCH (Chain:{is_chaining}): AI at {ai_current_tile}, Player at {player_tile}") #
        candidate_plans = [] 
        initial_player_safe_area = self._get_safe_area_size(player_tile, {}) #
        ai_log(f"      Initial player safe area: {initial_player_safe_area}") #

        # 考慮的站立點：AI 當前位置，以及 AI 周圍一格的安全空地
        potential_stand_tiles_with_paths = {ai_current_tile: [ai_current_tile]} # 路徑是 [ai_current_tile] 表示不需移動
        for dx, dy in DIRECTIONS.values(): #
            next_tile = (ai_current_tile[0] + dx, ai_current_tile[1] + dy)
            node = self._get_node_at_coords(next_tile[0], next_tile[1]) #
            if node and node.is_empty_for_direct_movement() and not self.is_tile_dangerous(next_tile[0], next_tile[1], 0.05): #
                if next_tile not in potential_stand_tiles_with_paths:
                     potential_stand_tiles_with_paths[next_tile] = [ai_current_tile, next_tile]
        
        ai_log(f"      Trap search: Potential stand tiles for AI: {list(potential_stand_tiles_with_paths.keys())}")

        for stand_tile, path_to_stand_tile in potential_stand_tiles_with_paths.items():
            # 如果是連鎖轟炸，並且這個站立點是上一顆炸彈的位置，則跳過 (避免在同一個點連續放)
            if is_chaining and stand_tile == self.last_placed_bomb_for_chain_coords:
                ai_log(f"      Skipping stand_tile {stand_tile} as it's where the last chain bomb was placed.")
                continue

            # 檢查從這個站立點放炸彈是否能炸到玩家
            if self._is_tile_in_hypothetical_blast(player_tile[0], player_tile[1], stand_tile[0], stand_tile[1], self.ai_player.bomb_range): #
                # 檢查AI是否能從 stand_tile 安全地放置並撤退
                # 注意: can_place_bomb_and_retreat 內部會檢查 stand_tile 是否可放置
                can_bomb_at_stand, retreat_spot_from_stand = self.can_place_bomb_and_retreat(stand_tile) #
                
                if can_bomb_at_stand and retreat_spot_from_stand: #
                    blast_tiles = self._get_hypothetical_blast_tiles(stand_tile, self.ai_player.bomb_range) #
                    player_safe_after = self._get_safe_area_size(player_tile, blast_tiles) #
                    
                    # 評分：玩家安全區越小越好，AI移動成本越低越好
                    # 優先考慮直接命中，然後是限制程度，最後是移動成本
                    score = player_safe_after
                    if player_tile in blast_tiles: # 直接命中玩家的權重最高
                        score -= 1000 
                    score += (len(path_to_stand_tile) -1) * 2 # 每移動一步增加成本

                    candidate_plans.append( (score, stand_tile, retreat_spot_from_stand, path_to_stand_tile) ) #
                    ai_log(f"      TRAP OPTION (Stand Tile {stand_tile}): Hits player: {player_tile in blast_tiles}. Retreat: {retreat_spot_from_stand}. Player Safe Area After: {player_safe_after}. Path len: {len(path_to_stand_tile)-1}. Score: {score}") #

        if not candidate_plans: #
            ai_log("    TRAP SEARCH: No viable trapping plans found.") #
            return None

        candidate_plans.sort(key=lambda x: x[0]) # 按評分排序 (越小越好) #
        
        best_score, best_stand_tile, best_retreat_spot, best_path_to_stand = candidate_plans[0] #
        
        # 只有當這個計劃確實能困住玩家或造成傷害時才採納
        meaningful_trap_threshold = initial_player_safe_area -1 # 至少減少一個安全格
        if best_score < initial_player_safe_area or (player_tile in self._get_hypothetical_blast_tiles(best_stand_tile, self.ai_player.bomb_range)):
             if player_tile not in self._get_hypothetical_blast_tiles(best_stand_tile, self.ai_player.bomb_range) and best_score >= meaningful_trap_threshold:
                ai_log(f"    TRAP SEARCH: Best plan (score {best_score}) does not hit player directly and doesn't trap enough (initial: {initial_player_safe_area}, after: {best_score}). Discarding.")
                return None

             ai_log(f"    TRAP SEARCH: Best plan chosen with score {best_score}: Stand at {best_stand_tile}, Retreat to {best_retreat_spot}, Path: {best_path_to_stand}") #
             return best_stand_tile, best_retreat_spot, best_path_to_stand #
        
        ai_log(f"    TRAP SEARCH: No plan met trapping effectiveness criteria. Best score: {best_score}, Initial safe: {initial_player_safe_area}") #
        return None #

    # ... (_find_best_item_on_ground, _find_best_wall_to_bomb_for_items, _find_optimal_bombing_spot_for_obstacle, _find_safe_roaming_spots)
    # ... (_get_safe_area_size, _get_hypothetical_blast_tiles, _get_adjacent_empty_tiles)
    # 這些輔助函式與 v6 版本基本一致，此處省略以保持簡潔。確保它們在您的類別中仍然存在。
    def _find_best_item_on_ground(self, ai_current_tile): #
        if not self.game.items_group: return None #
        best_item_found = None; highest_priority_value = float('inf'); shortest_path_len_to_item = float('inf') #
        for item_sprite in self.game.items_group: #
            if not item_sprite.alive(): continue #
            priority = self.item_type_priority.get(item_sprite.type, 99) #
            item_coords = (item_sprite.rect.centerx // settings.TILE_SIZE, item_sprite.rect.centery // settings.TILE_SIZE) #
            dist_to_item_manhattan = abs(ai_current_tile[0] - item_coords[0]) + abs(ai_current_tile[1] - item_coords[1]) #
            if priority < highest_priority_value or (priority == highest_priority_value and dist_to_item_manhattan < shortest_path_len_to_item) : #
                if dist_to_item_manhattan < shortest_path_len_to_item + 5 : #
                    temp_path_bfs = self.bfs_find_direct_movement_path(ai_current_tile, item_coords, max_depth=15) #
                    if temp_path_bfs and len(temp_path_bfs)>1: #
                        current_path_len = len(temp_path_bfs) -1 #
                        if priority < highest_priority_value or (priority == highest_priority_value and current_path_len < shortest_path_len_to_item): #
                            highest_priority_value = priority; shortest_path_len_to_item = current_path_len #
                            best_item_found = {'item': item_sprite, 'coords': item_coords, 'dist_bfs': current_path_len} #
                    elif priority < highest_priority_value and best_item_found is None and dist_to_item_manhattan < shortest_path_len_to_item : #
                        highest_priority_value = priority; shortest_path_len_to_item = dist_to_item_manhattan #
                        best_item_found = {'item': item_sprite, 'coords': item_coords, 'dist_bfs': float('inf')} #
        return best_item_found #

    def _find_best_wall_to_bomb_for_items(self, ai_current_tile, exclude_wall_node=None): #
        potential_walls = []; tile_height = self.map_manager.tile_height; tile_width = self.map_manager.tile_width #
        for r in range(tile_height): #
            for c in range(tile_width): #
                node = self._get_node_at_coords(c, r) #
                if not (node and node.is_destructible_box()): continue #
                if exclude_wall_node and node.x == exclude_wall_node.x and node.y == exclude_wall_node.y : continue #
                dist_to_wall = abs(ai_current_tile[0] - c) + abs(ai_current_tile[1] - r) #
                if dist_to_wall == 0 or dist_to_wall > self.wall_scan_radius_for_items: continue #
                can_reach_bomb_spot = False #
                for dx_wall_offset, dy_wall_offset in DIRECTIONS.values(): #
                    bomb_spot_x, bomb_spot_y = node.x + dx_wall_offset, node.y + dy_wall_offset #
                    bomb_spot_node_check = self._get_node_at_coords(bomb_spot_x, bomb_spot_y) #
                    if bomb_spot_node_check and bomb_spot_node_check.is_empty_for_direct_movement(): #
                        if self.bfs_find_direct_movement_path(ai_current_tile, (bomb_spot_x, bomb_spot_y), max_depth=7): #
                            can_reach_bomb_spot = True; break #
                if can_reach_bomb_spot: potential_walls.append({'node': node, 'dist': dist_to_wall, 'score': -dist_to_wall }) #
        if not potential_walls: return None #
        potential_walls.sort(key=lambda w: w['score'], reverse=True) #
        return potential_walls[0]['node'] #

    def _find_optimal_bombing_spot_for_obstacle(self, wall_node, ai_current_tile, min_retreat_options=1): #
        candidate_placements = [] #
        for dx_wall_offset, dy_wall_offset in DIRECTIONS.values(): #
            bomb_spot_coords = (wall_node.x + dx_wall_offset, wall_node.y + dy_wall_offset) #
            if self.last_failed_bombing_spot and bomb_spot_coords == self.last_failed_bombing_spot and self.potential_wall_to_bomb_for_item == self.last_failed_bombing_target_wall: continue #
            bomb_spot_node = self._get_node_at_coords(bomb_spot_coords[0], bomb_spot_coords[1]) #
            if not (bomb_spot_node and bomb_spot_node.is_empty_for_direct_movement()): continue #
            path_to_bomb_spot = self.bfs_find_direct_movement_path(ai_current_tile, bomb_spot_coords, max_depth=7) #
            if not path_to_bomb_spot : continue #
            retreat_spots = self.find_safe_tiles_nearby_for_retreat(bomb_spot_coords, bomb_spot_coords, self.ai_player.bomb_range, self.retreat_search_depth, min_retreat_options) #
            if retreat_spots: #
                best_retreat_spot = retreat_spots[0] #
                if self.bfs_find_direct_movement_path(bomb_spot_coords, best_retreat_spot, self.retreat_search_depth): #
                    candidate_placements.append({'bomb_spot': bomb_spot_coords, 'retreat_spot': best_retreat_spot, 'path_to_bomb_len': len(path_to_bomb_spot)}) #
        if not candidate_placements: return None, None #
        candidate_placements.sort(key=lambda p: p['path_to_bomb_len']) #
        return candidate_placements[0]['bomb_spot'], candidate_placements[0]['retreat_spot'] #

    def _find_safe_roaming_spots(self, ai_current_tile, count=1, depth=3, exclude_target=None): #
        q = deque([(ai_current_tile, 0)]); visited = {ai_current_tile}; potential_spots = [] #
        while q and len(potential_spots) < count * 10: #
            (curr_x, curr_y), d = q.popleft() #
            if d > 0 and d <= depth: #
                if (curr_x, curr_y) == exclude_target: continue #
                if not self.is_tile_dangerous(curr_x, curr_y, future_seconds=self.evasion_urgency_seconds * 0.3): #
                    openness = self._get_tile_openness(curr_x, curr_y, radius=1) #
                    if openness >= 1 and (curr_x, curr_y) != ai_current_tile: potential_spots.append(((curr_x, curr_y), openness)) #
            if d < depth: #
                shuffled_directions = list(DIRECTIONS.values()); random.shuffle(shuffled_directions) #
                for dx, dy in shuffled_directions: #
                    next_x, next_y = curr_x + dx, curr_y + dy; next_coords = (next_x, next_y) #
                    if next_coords not in visited: #
                        node = self._get_node_at_coords(next_x, next_y) #
                        if node and node.is_empty_for_direct_movement() and not self.is_tile_dangerous(next_x, next_y, future_seconds=0.05): #
                            visited.add(next_coords); q.append((next_coords, d + 1)) #
        if not potential_spots: return [] #
        potential_spots.sort(key=lambda s: s[1], reverse=True) #
        final_choices = [spot[0] for spot in potential_spots if spot[0] != ai_current_tile] #
        return final_choices[:count] #

    def _get_safe_area_size(self, start_tile, blocked_tiles): #
        q = deque([start_tile]); visited = {start_tile}; count = 0 #
        if start_tile in blocked_tiles: return 0 #
        while q: #
            tile = q.popleft(); count += 1 #
            for neighbor in self._get_adjacent_empty_tiles(tile): #
                if neighbor not in visited and neighbor not in blocked_tiles: #
                    visited.add(neighbor); q.append(neighbor) #
        return count #

    def _get_hypothetical_blast_tiles(self, bomb_coords, bomb_range): #
        blast_tiles = {bomb_coords} #
        for dx, dy in DIRECTIONS.values(): #
            for i in range(1, bomb_range + 1): #
                nx, ny = bomb_coords[0] + dx * i, bomb_coords[1] + dy * i #
                if not (0 <= nx < self.map_manager.tile_width and 0 <= ny < self.map_manager.tile_height): break #
                if self.map_manager.is_solid_wall_at(nx, ny): break #
                blast_tiles.add((nx, ny)) #
                node = self._get_node_at_coords(nx, ny) #
                if node and node.is_destructible_box(): break #
        return blast_tiles #
        
    def _get_adjacent_empty_tiles(self, tile): #
        x, y = tile; empty_tiles = [] #
        for dx, dy in DIRECTIONS.values(): #
            nx, ny = x + dx, y + dy #
            node = self._get_node_at_coords(nx, ny) #
            if node and node.is_empty_for_direct_movement(): empty_tiles.append((nx, ny)) #
        return empty_tiles #