# oop-2025-proj-pycade/core/ai_aggressive.py

import pygame
import settings
import random
from collections import deque
from .ai_controller_base import AIControllerBase, ai_log, DIRECTIONS

class AggressiveAIController(AIControllerBase):
    """
    一個攻擊性極強的 AI，首要目標是追擊並消滅人類玩家。
    它會更頻繁地放置炸彈，並在近距離戰鬥中表現得更為魯莽。
    此版本修正了放置炸彈後的撤退邏輯和路徑處理。
    """
    def __init__(self, ai_player_sprite, game_instance):
        super().__init__(ai_player_sprite, game_instance)
        
        ai_log("AggressiveAIController (v3 - Retreat Fix) initialized.")
        
        self.evasion_urgency_seconds = getattr(settings, "AI_AGGRESSIVE_EVASION_SECONDS", 0.3) 
        self.retreat_search_depth = getattr(settings, "AI_AGGRESSIVE_RETREAT_DEPTH", 6) # 逃跑時看得可以遠一點      
        self.min_retreat_options_for_bombing = 1 
        
        self.cqc_bomb_chance = getattr(settings, "AI_AGGRESSIVE_CQC_BOMB_CHANCE", 0.85) # 近身時極大概率放炸彈
        self.cqc_engagement_distance = getattr(settings, "AI_AGGRESSIVE_CQC_ENGAGE_DISTANCE", 2) 

        self.idle_duration_ms = 400 # 攻擊型AI不應閒置太久

        self.default_planning_state_on_stuck = "PLANNING_PATH_TO_PLAYER" 
        self.default_state_after_evasion = "PLANNING_PATH_TO_PLAYER"   
        self.change_state("PLANNING_PATH_TO_PLAYER")

    def reset_state(self):
        super().reset_state()
        self.change_state("PLANNING_PATH_TO_PLAYER")
        ai_log(f"AggressiveAIController (v3) reset. Current state: {self.current_state}")

    # --- 狀態處理邏輯 ---

    # （1）！！！PLANNING_PATH_TO_PLAYER 狀態處理修改開始！！！（1）
    def handle_planning_path_to_player_state(self, ai_current_tile):
        ai_log(f"AGGRESSIVE: In PLANNING_PATH_TO_PLAYER at {ai_current_tile}.")
        
        human_pos = self._get_human_player_current_tile()
        if not human_pos:
            ai_log("AGGRESSIVE: Human player not found. Idling briefly.")
            self.change_state("IDLE")
            return

        ai_log(f"AGGRESSIVE: Planning path from {ai_current_tile} to human at {human_pos}.")
        self.astar_planned_path = self.astar_find_path(ai_current_tile, human_pos)
        
        if self.astar_planned_path:
            self.astar_path_current_segment_index = 0
            needs_clearing = any(node.is_destructible_box() for node in self.astar_planned_path)
            if needs_clearing:
                ai_log("AGGRESSIVE: Path to player requires clearing obstacles.")
                self.change_state("EXECUTING_PATH_CLEARANCE")
            else:
                ai_log("AGGRESSIVE: Path to player is clear. Engaging.")
                # 【修改】將A*路徑直接設定為子路徑以開始移動
                path_tuples = [(node.x, node.y) for node in self.astar_planned_path]
                if path_tuples and len(path_tuples) > 1:
                    self.set_current_movement_sub_path(path_tuples)
                    self.change_state("ENGAGING_PLAYER")
                elif path_tuples and len(path_tuples) == 1 and path_tuples[0] == ai_current_tile : # A*目標就是當前位置
                     self.change_state("ENGAGING_PLAYER") # 或者 CQC
                else: # A*路徑無效
                    ai_log("AGGRESSIVE: A* path to player is too short or invalid after planning. Idling.")
                    self.change_state("IDLE")
        else:
            ai_log(f"AGGRESSIVE: A* failed to find path to player at {human_pos}. Idling briefly.")
            self.change_state("IDLE")
    # （1）！！！PLANNING_PATH_TO_PLAYER 狀態處理修改結束！！！（1）


    # （2）！！！EXECUTING_PATH_CLEARANCE 狀態處理修改開始！！！（2）
    def handle_executing_path_clearance_state(self, ai_current_tile):
        ai_log(f"AGGRESSIVE: In EXECUTING_PATH_CLEARANCE at {ai_current_tile}.")
        if self.ai_just_placed_bomb: return 

        if not self.astar_planned_path or self.astar_path_current_segment_index >= len(self.astar_planned_path):
            ai_log("AGGRESSIVE: A* path finished or invalid. Re-planning to player.")
            self.change_state("PLANNING_PATH_TO_PLAYER")
            return

        # 【新增】如果正在執行子路徑（例如，移動到炸彈點），則等待其完成
        if self.current_movement_sub_path:
            ai_log("AGGRESSIVE: Waiting for sub-path to bombing spot/obstacle to complete.")
            return

        target_node_in_astar = self.astar_planned_path[self.astar_path_current_segment_index]

        if ai_current_tile == (target_node_in_astar.x, target_node_in_astar.y):
            self.astar_path_current_segment_index += 1
            if self.astar_path_current_segment_index >= len(self.astar_planned_path):
                self.change_state("PLANNING_PATH_TO_PLAYER") # A*路徑上的點都處理完了
            else:
                # 強制立即重新評估下一個A*節點，而不是等待下一個決策週期
                self.last_decision_time = pygame.time.get_ticks() - self.ai_decision_interval 
            return

        if target_node_in_astar.is_empty_for_direct_movement():
            path_to_node = self.bfs_find_direct_movement_path(ai_current_tile, (target_node_in_astar.x, target_node_in_astar.y))
            if path_to_node and len(path_to_node) > 1:
                self.set_current_movement_sub_path(path_to_node)
                # 狀態保持，等待移動
            else: 
                ai_log("AGGRESSIVE: Cannot BFS to next empty A* node. Re-planning path to player.")
                self.change_state("PLANNING_PATH_TO_PLAYER")
            return
        
        elif target_node_in_astar.is_destructible_box():
            self.target_destructible_wall_node_in_astar = target_node_in_astar
            bomb_spot, retreat_spot = self._find_optimal_bombing_spot_aggressive(target_node_in_astar, ai_current_tile)

            if bomb_spot and retreat_spot:
                self.chosen_bombing_spot_coords = bomb_spot
                self.chosen_retreat_spot_coords = retreat_spot
                
                # 【修正】如果AI已經在轟炸點，直接放置炸彈並切換到撤退
                if ai_current_tile == bomb_spot:
                    if self.ai_player.bombs_placed_count < self.ai_player.max_bombs:
                        ai_log("AGGRESSIVE: Already at bombing spot for obstacle. Placing bomb.")
                        self.ai_player.place_bomb()
                        path_to_retreat_immediately = self.bfs_find_direct_movement_path(ai_current_tile, retreat_spot)
                        if path_to_retreat_immediately and len(path_to_retreat_immediately) > 1:
                            self.set_current_movement_sub_path(path_to_retreat_immediately)
                        self.change_state("TACTICAL_RETREAT_AND_WAIT")
                    else:
                        ai_log("AGGRESSIVE: At bombing spot, but no bombs. Re-planning.")
                        self.change_state("PLANNING_PATH_TO_PLAYER")
                else: # 需要移動到轟炸點
                    path_to_bomb_spot = self.bfs_find_direct_movement_path(ai_current_tile, bomb_spot)
                    if path_to_bomb_spot and len(path_to_bomb_spot) > 1:
                        self.set_current_movement_sub_path(path_to_bomb_spot)
                        # 狀態保持在 EXECUTING_PATH_CLEARANCE，但子路徑會被執行
                        # 當子路徑執行完畢，下一次進入此 state handler 時，current_movement_sub_path 會是空的
                        # 然後會進入上面的 ai_current_tile == bomb_spot 分支
                    else: 
                        ai_log("AGGRESSIVE: Cannot path to bombing spot for obstacle. Re-planning path to player.")
                        self.change_state("PLANNING_PATH_TO_PLAYER")
            else: 
                ai_log("AGGRESSIVE: No safe way to bomb obstacle to reach player. Re-planning path to player.")
                self.change_state("PLANNING_PATH_TO_PLAYER")
            return
        else: 
            ai_log(f"AGGRESSIVE: Invalid node {target_node_in_astar} in A* path. Re-planning.")
            self.change_state("PLANNING_PATH_TO_PLAYER")
    # （2）！！！EXECUTING_PATH_CLEARANCE 狀態處理修改結束！！！（2）

    # （3）！！！ENGAGING_PLAYER 和 CLOSE_QUARTERS_COMBAT 狀態處理修改開始！！！（3）
    def handle_engaging_player_state(self, ai_current_tile):
        human_pos = self._get_human_player_current_tile()
        if not human_pos:
            self.change_state("PLANNING_PATH_TO_PLAYER"); return

        dist_to_human = abs(ai_current_tile[0] - human_pos[0]) + abs(ai_current_tile[1] - human_pos[1])

        if dist_to_human <= self.cqc_engagement_distance:
            self.change_state("CLOSE_QUARTERS_COMBAT"); return
        
        # 如果正在移動，等待移動完成
        if self.current_movement_sub_path: return

        # 嘗試放置炸彈攻擊玩家
        if not self.ai_just_placed_bomb and self.ai_player.bombs_placed_count < self.ai_player.max_bombs:
            if self._is_tile_in_hypothetical_blast(human_pos[0], human_pos[1], ai_current_tile[0], ai_current_tile[1], self.ai_player.bomb_range):
                can_bomb, retreat_spot = self.can_place_bomb_and_retreat(ai_current_tile)
                if can_bomb or random.random() < 0.4: 
                    self.chosen_bombing_spot_coords = ai_current_tile
                    self.chosen_retreat_spot_coords = retreat_spot 
                    self.ai_player.place_bomb()
                    # 【關鍵修正】放置炸彈後，必須立即設定撤退路徑並切換狀態
                    if retreat_spot:
                        path_to_retreat = self.bfs_find_direct_movement_path(ai_current_tile, retreat_spot)
                        if path_to_retreat and len(path_to_retreat) > 1:
                            self.set_current_movement_sub_path(path_to_retreat)
                        else: # 即使找不到路徑，也要嘗試進入撤退狀態，讓EVADING接手
                            ai_log("AGGRESSIVE ENGAGE: Placed bomb, but no clear path to chosen retreat. Entering TACTICAL_RETREAT anyway.")
                    else: # 沒有找到安全撤退點，但還是炸了
                         ai_log("AGGRESSIVE ENGAGE: Placed bomb without a safe retreat spot. Good luck!")
                    self.change_state("TACTICAL_RETREAT_AND_WAIT")
                    return

        # 如果不放炸彈，則移動向玩家 (使用BFS追擊)
        if not self.current_movement_sub_path: # 確保不是因為剛設定完撤退路徑又來追擊
            path_to_human = self.bfs_find_direct_movement_path(ai_current_tile, human_pos, max_depth=10)
            if path_to_human and len(path_to_human) > 1:
                self.set_current_movement_sub_path(path_to_human)
            else: # 追不上，或者BFS找不到路，重新規劃 A*
                self.change_state("PLANNING_PATH_TO_PLAYER")

    def handle_close_quarters_combat_state(self, ai_current_tile):
        human_pos = self._get_human_player_current_tile()
        if not human_pos:
            self.change_state("PLANNING_PATH_TO_PLAYER"); return

        dist_to_human = abs(ai_current_tile[0] - human_pos[0]) + abs(ai_current_tile[1] - human_pos[1])
        if dist_to_human > self.cqc_engagement_distance + 1: 
            self.change_state("ENGAGING_PLAYER"); return
            
        if self.current_movement_sub_path: return 

        if not self.ai_just_placed_bomb and self.ai_player.bombs_placed_count < self.ai_player.max_bombs:
            if self._is_tile_in_hypothetical_blast(human_pos[0], human_pos[1], ai_current_tile[0], ai_current_tile[1], self.ai_player.bomb_range):
                if random.random() < self.cqc_bomb_chance:
                    ai_log("AGGRESSIVE CQC: High chance bomb!")
                    can_bomb, retreat_spot = self.can_place_bomb_and_retreat(ai_current_tile) 
                    
                    self.chosen_bombing_spot_coords = ai_current_tile
                    self.chosen_retreat_spot_coords = retreat_spot 

                    if not retreat_spot: 
                        desperate_options = self.find_safe_tiles_nearby_for_retreat(ai_current_tile, ai_current_tile, self.ai_player.bomb_range, max_depth=3, min_options_needed=1)
                        if desperate_options:
                            self.chosen_retreat_spot_coords = random.choice(desperate_options)
                            ai_log(f"AGGRESSIVE CQC: No perfect retreat, chose desperate: {self.chosen_retreat_spot_coords}")
                        else: 
                            ai_log("AGGRESSIVE CQC: No retreat found at all, bombing anyway!")

                    self.ai_player.place_bomb()
                    
                    # 【關鍵修正】放置炸彈後，必須立即設定撤退路徑並切換狀態
                    if self.chosen_retreat_spot_coords:
                        path_to_retreat = self.bfs_find_direct_movement_path(ai_current_tile, self.chosen_retreat_spot_coords)
                        if path_to_retreat and len(path_to_retreat) > 1:
                            self.set_current_movement_sub_path(path_to_retreat)
                        else:
                             ai_log("AGGRESSIVE CQC: Placed bomb, but no clear path to chosen retreat. Entering TACTICAL_RETREAT anyway.")
                    else: # 連 desperate retreat 都沒有
                        ai_log("AGGRESSIVE CQC: Placed bomb with no retreat spot. Brace for impact!")
                    
                    self.change_state("TACTICAL_RETREAT_AND_WAIT")
                    return

        # 如果不放炸彈，嘗試近距離調整位置
        available_reposition_spots = []
        for dx, dy in DIRECTIONS.values():
            next_x, next_y = ai_current_tile[0] + dx, ai_current_tile[1] + dy
            if (next_x, next_y) == human_pos: continue 
            node = self._get_node_at_coords(next_x, next_y)
            if node and node.is_empty_for_direct_movement() and not self.is_tile_dangerous(next_x, next_y, 0.1):
                available_reposition_spots.append((next_x, next_y))
        
        if available_reposition_spots:
            reposition_target = random.choice(available_reposition_spots)
            self.set_current_movement_sub_path([ai_current_tile, reposition_target])
    # （3）！！！ENGAGING_PLAYER 和 CLOSE_QUARTERS_COMBAT 狀態處理修改結束！！！（3）


    # （4）！！！TACTICAL_RETREAT_AND_WAIT 狀態處理修改開始！！！（4）
    def handle_tactical_retreat_and_wait_state(self, ai_current_tile):
        ai_log(f"AGGRESSIVE: In TACTICAL_RETREAT_AND_WAIT at {ai_current_tile}. Retreat target: {self.chosen_retreat_spot_coords}, Bomb placed: {self.ai_just_placed_bomb}")

        # 【新增】如果沒有設定有效的撤退點，或者已經沒有炸彈威脅了，就重新規劃攻擊
        if not self.chosen_retreat_spot_coords or not self.ai_just_placed_bomb:
            if not self.is_bomb_still_active(self.last_bomb_placed_time): # 額外檢查，確保炸彈真的清了
                self.ai_just_placed_bomb = False 
            ai_log("AGGRESSIVE: No valid retreat spot or bomb not active. Re-planning attack.")
            self.change_state("PLANNING_PATH_TO_PLAYER")
            return

        # 如果正在執行撤退路徑，則等待其完成
        if self.current_movement_sub_path:
            ai_log(f"AGGRESSIVE: Executing retreat sub-path to {self.current_movement_sub_path[-1]}.")
            return 
        
        # 如果已到達撤退點
        if ai_current_tile == self.chosen_retreat_spot_coords:
            ai_log(f"AGGRESSIVE: Arrived at retreat spot {self.chosen_retreat_spot_coords}. Waiting for bomb to clear.")
            if not self.is_bomb_still_active(self.last_bomb_placed_time):
                ai_log("AGGRESSIVE: Bomb has cleared. Re-planning attack.")
                self.ai_just_placed_bomb = False
                self.target_destructible_wall_node_in_astar = None 
                self.chosen_bombing_spot_coords = None
                self.chosen_retreat_spot_coords = None
                self.change_state("PLANNING_PATH_TO_PLAYER") 
            # else: 炸彈還沒清，繼續等待
            return

        # 如果未在撤退點且沒有路徑（可能是路徑執行失敗或初始就沒有）
        # 【關鍵修正】確保這裡會設定路徑讓 AI 逃跑
        ai_log(f"AGGRESSIVE: Not at retreat spot {self.chosen_retreat_spot_coords} and no sub-path. Attempting to path to retreat.")
        path_to_retreat = self.bfs_find_direct_movement_path(ai_current_tile, self.chosen_retreat_spot_coords, max_depth=self.retreat_search_depth + 2) # 逃跑時看得更遠
        if path_to_retreat and len(path_to_retreat) > 1:
            self.set_current_movement_sub_path(path_to_retreat)
            ai_log(f"AGGRESSIVE: Set new retreat path: {path_to_retreat}")
        else: 
            ai_log(f"AGGRESSIVE: CRITICAL - Cannot path to chosen retreat spot {self.chosen_retreat_spot_coords}! Entering EVADING_DANGER.")
            # 即使規劃的撤退點到不了，也要強制進入躲避狀態，嘗試找其他安全點
            self.change_state("EVADING_DANGER")
    # （4）！！！TACTICAL_RETREAT_AND_WAIT 狀態處理修改結束！！！（4）
            
    def handle_evading_danger_state(self, ai_current_tile):
        super().handle_evading_danger_state(ai_current_tile)
        # 基底的 evading state 在安全後會根據 self.default_state_after_evasion 切換
        # AggressiveAI 的 default_state_after_evasion 是 PLANNING_PATH_TO_PLAYER

    def handle_idle_state(self, ai_current_tile):
        ai_log(f"AGGRESSIVE: Idling at {ai_current_tile}. Will re-plan to player soon.")
        if pygame.time.get_ticks() - self.state_start_time > self.idle_duration_ms: 
            self.change_state("PLANNING_PATH_TO_PLAYER")

    # --- 特定輔助函式 ---
    def _find_optimal_bombing_spot_aggressive(self, wall_node, ai_current_tile):
        candidate_placements = []
        # 優先考慮與牆壁相鄰的四個格子作為放置點
        for dx_wall_offset, dy_wall_offset in DIRECTIONS.values():
            bomb_spot_x = wall_node.x + dx_wall_offset
            bomb_spot_y = wall_node.y + dy_wall_offset
            bomb_spot_coords = (bomb_spot_x, bomb_spot_y)
            
            bomb_spot_node = self._get_node_at_coords(bomb_spot_x, bomb_spot_y)
            if not (bomb_spot_node and bomb_spot_node.is_empty_for_direct_movement()):
                continue

            # 【修正】確保能從當前位置走到放置點 (除非當前位置就是放置點)
            path_to_bomb_spot = []
            if ai_current_tile == bomb_spot_coords:
                path_to_bomb_spot = [ai_current_tile] # 表示原地放炸彈
            else:
                path_to_bomb_spot = self.bfs_find_direct_movement_path(ai_current_tile, bomb_spot_coords, max_depth=5)
            
            if not path_to_bomb_spot : continue # 如果找不到路徑到轟炸點，則跳過

            retreat_spots = self.find_safe_tiles_nearby_for_retreat(
                bomb_spot_coords, bomb_spot_coords, self.ai_player.bomb_range, 
                self.retreat_search_depth, self.min_retreat_options_for_bombing 
            )
            if retreat_spots: # 攻擊型AI只要有一個撤退點就行
                best_retreat_spot = retreat_spots[0] 
                # 攻擊型AI可以不那麼嚴格檢查到撤退點的路徑是否完美，有總比沒有好
                candidate_placements.append({
                    'bomb_spot': bomb_spot_coords, 
                    'retreat_spot': best_retreat_spot,
                    'path_to_bomb_len': len(path_to_bomb_spot)
                })
        
        if not candidate_placements: 
            # 如果找不到任何帶撤退路線的方案，但AI非常想炸，可以考慮一個沒有撤退的方案（極端情況）
            # 此處簡化：找不到安全方案就放棄
            return None, None
            
        candidate_placements.sort(key=lambda p: p['path_to_bomb_len'])
        return candidate_placements[0]['bomb_spot'], candidate_placements[0]['retreat_spot']