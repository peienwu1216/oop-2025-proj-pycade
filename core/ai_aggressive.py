# oop-2025-proj-pycade/core/ai_aggressive.py

import pygame
import settings # 假設 settings.py 包含 AI 行為相關參數
import random
from collections import deque
from .ai_controller_base import AIControllerBase, TileNode, DIRECTIONS, ai_base_log # 從基礎類別匯入

# 攻擊型 AI 可能會更頻繁地使用或直接進入這些從原始 AIController 借鑒的狀態
# 這些狀態名稱來自您原始的 ai_controller.py
AI_STATE_AGGRESSIVE_PLANNING_PLAYER = "AGGRESSIVE_PLANNING_PLAYER" # 專門規劃攻擊玩家路徑
AI_STATE_AGGRESSIVE_EXECUTE_CLEARANCE = "AGGRESSIVE_EXECUTE_CLEARANCE" # 積極清除通往玩家的障礙
AI_STATE_AGGRESSIVE_ENGAGE = "AGGRESSIVE_ENGAGE"
AI_STATE_AGGRESSIVE_CQC = "AGGRESSIVE_CQC" # Close Quarters Combat
AI_STATE_AGGRESSIVE_RETREAT_SHORT = "AGGRESSIVE_RETREAT_SHORT" # 攻擊後的短暫必要撤退
AI_STATE_AGGRESSIVE_EVADING = "AGGRESSIVE_EVADING" # 仍然需要躲避，但可能更快反擊
AI_STATE_AGGRESSIVE_IDLE_SCAN = "AGGRESSIVE_IDLE_SCAN" # 短暫停留並掃描玩家


class AggressiveAIController(AIControllerBase):
    def __init__(self, ai_player_sprite, game_instance):
        super().__init__(ai_player_sprite, game_instance)
        ai_base_log(f"AggressiveAIController __init__ for Player ID: {id(ai_player_sprite)}")

        self.current_state = AI_STATE_AGGRESSIVE_IDLE_SCAN # 初始狀態，掃描玩家
        self.aggression_factor = getattr(settings, "AI_AGGRESSIVE_FACTOR", 0.8) # 攻擊性因子 (0.0-1.0)
        self.retreat_risk_tolerance = getattr(settings, "AI_AGGRESSIVE_RETREAT_RISK", 0.3) # 撤退時可接受的風險 (0-1, 越高風險承受能力越強)
        self.path_clearance_urgency = getattr(settings, "AI_AGGRESSIVE_CLEARANCE_URGENCY", 0.7) # 炸牆的急迫性

        # 攻擊型AI的卡死檢測閾值可以與保守型不同，例如它可能更願意嘗試，即使卡住一下
        self.stuck_threshold_decision_cycles_aggressive = getattr(settings, "AI_AGGRESSIVE_STUCK_CYCLES", 7)
        self.oscillation_stuck_threshold_aggressive = getattr(settings, "AI_AGGRESSIVE_OSCILLATION_CYCLES", 4)

        self.target_player_last_seen_tile = None # 記錄玩家最後出現的位置

    def reset_state(self): # 或 reset_state_aggressive
        super().reset_state_base()
        self.current_state = AI_STATE_AGGRESSIVE_IDLE_SCAN
        ai_base_log(f"AggressiveAIController reset_state for Player ID: {id(self.ai_player)}.")
        self.chosen_bombing_spot_coords = None
        self.chosen_retreat_spot_coords = None
        self.target_destructible_wall_node_in_astar = None
        self.target_player_last_seen_tile = None
        self.has_made_contact_with_player = False # 從原始AIController借鑒
        self.player_contact_distance_threshold = getattr(settings, "AI_PLAYER_CONTACT_DISTANCE", 2) # 從原始AIController借鑒


    def update(self):
        current_time = pygame.time.get_ticks()
        ai_current_tile = self._get_ai_current_tile()
        human_player_tile = self._get_human_player_current_tile()

        if not ai_current_tile or not self.ai_player or not self.ai_player.is_alive:
            if self.current_state != "DEAD_AGGRESSIVE":
                self.change_state("DEAD_AGGRESSIVE")
            return

        if human_player_tile:
            self.target_player_last_seen_tile = human_player_tile
            # 更新接觸狀態
            if not self.has_made_contact_with_player:
                dist_to_human = abs(ai_current_tile[0] - human_player_tile[0]) + abs(ai_current_tile[1] - human_player_tile[1])
                if dist_to_human <= self.player_contact_distance_threshold:
                    self.has_made_contact_with_player = True
                    ai_base_log(f"[AGGRESSIVE_AI_CONTACT] Made contact with player at {human_player_tile}")

        # --- 卡死檢測更新 (與原 AI 類似, 可考慮使用父類方法) ---
        # (與 ConservativeAIController 類似的卡死檢測邏輯，但使用 aggressive 的閾值)
        if not self.current_movement_sub_path and \
           not (self.current_state == AI_STATE_AGGRESSIVE_RETREAT_SHORT and self.ai_just_placed_bomb):
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

        is_decision_time = (current_time - self.last_decision_time >= self.ai_decision_interval)
        is_immediately_dangerous = self.is_tile_dangerous(ai_current_tile[0], ai_current_tile[1], future_seconds=0.2) # 攻擊型AI對自身危險的反應要快

        if is_immediately_dangerous and self.current_state != AI_STATE_AGGRESSIVE_EVADING:
            ai_base_log(f"[AGGRESSIVE_AI_DANGER] AI at {ai_current_tile} is in IMMEDIATE DANGER! Switching to EVADING.")
            self.change_state(AI_STATE_AGGRESSIVE_EVADING)
            self.last_decision_time = current_time # 立即重新決策

        if is_decision_time or self.current_state == AI_STATE_AGGRESSIVE_EVADING:
            if self.current_state != AI_STATE_AGGRESSIVE_EVADING:
                 self.last_decision_time = current_time

            stuck_by_single_tile = self.decision_cycle_stuck_counter >= self.stuck_threshold_decision_cycles_aggressive
            stuck_by_oscillation = self.oscillation_stuck_counter >= self.oscillation_stuck_threshold_aggressive
            if stuck_by_single_tile or stuck_by_oscillation:
                # 攻擊型AI卡住時，可能會更激進地嘗試炸開一條路，或者直接衝向玩家最後位置
                log_msg = "[AGGRESSIVE_AI_STUCK]"
                if stuck_by_oscillation: log_msg += f" Oscillation at {ai_current_tile}."
                else: log_msg += f" Stuck at {ai_current_tile} for {self.decision_cycle_stuck_counter} cycles."
                ai_base_log(log_msg + " Attempting aggressive re-plan or action.")
                self.decision_cycle_stuck_counter = 0
                self.oscillation_stuck_counter = 0
                self.movement_history.clear()
                self.current_movement_sub_path = []
                # 卡住時，攻擊型AI的備選方案：
                # 1. 嘗試炸開周圍的牆 (如果有的話)
                # 2. 強行規劃到玩家最後位置
                # 3. 如果也在危險中，則還是先逃跑
                if is_immediately_dangerous:
                    self.change_state(AI_STATE_AGGRESSIVE_EVADING)
                elif self.target_player_last_seen_tile:
                    self.change_state(AI_STATE_AGGRESSIVE_PLANNING_PLAYER) # 強制重新規劃到玩家
                else:
                    self.change_state(AI_STATE_AGGRESSIVE_IDLE_SCAN) # 回到掃描

            # --- 狀態處理邏輯 ---
            if self.current_state == AI_STATE_AGGRESSIVE_EVADING:
                self.handle_evading_danger_state(ai_current_tile)
            elif self.current_state == AI_STATE_AGGRESSIVE_IDLE_SCAN:
                self.handle_idle_scan_state(ai_current_tile)
            elif self.current_state == AI_STATE_AGGRESSIVE_PLANNING_PLAYER:
                self.handle_planning_player_state(ai_current_tile)
            elif self.current_state == AI_STATE_AGGRESSIVE_EXECUTE_CLEARANCE:
                self.handle_execute_clearance_state(ai_current_tile)
            elif self.current_state == AI_STATE_AGGRESSIVE_ENGAGE:
                self.handle_engage_state(ai_current_tile)
            elif self.current_state == AI_STATE_AGGRESSIVE_CQC:
                self.handle_cqc_state(ai_current_tile)
            elif self.current_state == AI_STATE_AGGRESSIVE_RETREAT_SHORT:
                self.handle_retreat_short_state(ai_current_tile)
            else:
                ai_base_log(f"[AGGRESSIVE_AI_WARN] Unknown state: {self.current_state}. Defaulting to IDLE_SCAN.")
                self.change_state(AI_STATE_AGGRESSIVE_IDLE_SCAN)

        # --- 移動子路徑執行 ---
        # (與 ConservativeAIController 和父類中的邏輯類似)
        if self.ai_player.action_timer <= 0:
            sub_path_finished_or_failed = False
            if self.current_movement_sub_path:
                sub_path_finished_or_failed = self.execute_next_move_on_sub_path(ai_current_tile)

            if sub_path_finished_or_failed:
                self.last_decision_time = pygame.time.get_ticks() - self.ai_decision_interval - 1

            if not self.current_movement_sub_path:
                self.ai_player.is_moving = False


    def handle_idle_scan_state(self, ai_current_tile):
        ai_base_log(f"[AGGRESSIVE_AI_IDLE_SCAN] at {ai_current_tile}.")
        if self.target_player_last_seen_tile:
            self.change_state(AI_STATE_AGGRESSIVE_PLANNING_PLAYER)
        else: # 沒有玩家目標，原地隨機小範圍移動或等待 (攻擊型AI不應長時間閒置)
            if not self.current_movement_sub_path:
                safe_random_moves = []
                for dx, dy in DIRECTIONS.values():
                    next_x, next_y = ai_current_tile[0] + dx, ai_current_tile[1] + dy
                    node = self._get_node_at_coords(next_x, next_y)
                    if node and node.is_empty_for_direct_movement() and \
                       not self.is_tile_dangerous(next_x, next_y, future_seconds=0.3):
                        safe_random_moves.append((next_x, next_y))
                if safe_random_moves:
                    self.set_current_movement_sub_path([ai_current_tile, random.choice(safe_random_moves)])

    def handle_planning_player_state(self, ai_current_tile):
        ai_base_log(f"[AGGRESSIVE_AI_PLANNING_PLAYER] at {ai_current_tile}.")
        target_coords = self.target_player_last_seen_tile
        if not target_coords and self.human_player_sprite: # 如果沒有最後位置，但玩家還活著，用初始位置
            target_coords = getattr(self.game, 'player1_start_tile', (1,1)) # 從原始AIController借鑒

        if not target_coords:
            ai_base_log("    No target player coords. Switching to IDLE_SCAN.")
            self.change_state(AI_STATE_AGGRESSIVE_IDLE_SCAN)
            return

        self.astar_planned_path = self.astar_find_path(ai_current_tile, target_coords)
        if self.astar_planned_path:
            self.astar_path_current_segment_index = 0
            # 檢查路徑是否需要清除障礙物
            needs_clearance = any(node.is_destructible_box() for node in self.astar_planned_path)
            if needs_clearance:
                if random.random() < self.path_clearance_urgency: # 攻擊型AI更願意炸牆
                    ai_base_log(f"    A* path to player needs clearance. Switching to EXECUTE_CLEARANCE.")
                    self.change_state(AI_STATE_AGGRESSIVE_EXECUTE_CLEARANCE)
                else: # 有一定機率直接嘗試接近，即使有牆 (可能想引誘玩家)
                    ai_base_log(f"    A* path to player needs clearance, but attempting direct approach/engagement.")
                    self.change_state(AI_STATE_AGGRESSIVE_ENGAGE) # 或者直接進入交戰，嘗試在牆邊戰鬥
            else:
                ai_base_log(f"    A* path to player is clear. Switching to ENGAGE.")
                self.change_state(AI_STATE_AGGRESSIVE_ENGAGE)
        else:
            ai_base_log(f"    A* failed to find path to player at {target_coords}. Switching to IDLE_SCAN.")
            self.change_state(AI_STATE_AGGRESSIVE_IDLE_SCAN)


    def handle_execute_clearance_state(self, ai_current_tile):
        ai_base_log(f"[AGGRESSIVE_AI_EXECUTE_CLEARANCE] at {ai_current_tile}.")
        # 這部分邏輯與原始 AIController 的 EXECUTING_PATH_CLEARANCE 非常相似
        # 主要區別在於，攻擊型 AI 在無法找到完美炸牆點時，可能會採取風險稍高的策略
        # 或者更快地放棄炸牆，轉而嘗試其他接近玩家的方式

        if self.ai_just_placed_bomb: # 如果剛放了炸彈，必須先撤退
            ai_base_log("    Waiting for previously placed bomb to clear.")
            # 確保進入撤退狀態，如果還沒的話
            if self.current_state != AI_STATE_AGGRESSIVE_RETREAT_SHORT and self.chosen_retreat_spot_coords:
                if ai_current_tile != self.chosen_retreat_spot_coords:
                    path_to_retreat = self.bfs_find_direct_movement_path(ai_current_tile, self.chosen_retreat_spot_coords, max_depth=7)
                    if path_to_retreat: self.set_current_movement_sub_path(path_to_retreat)
                self.change_state(AI_STATE_AGGRESSIVE_RETREAT_SHORT)
            elif not self.chosen_retreat_spot_coords: # 沒有撤退點，緊急逃跑
                self.change_state(AI_STATE_AGGRESSIVE_EVADING)
            return

        if not self.astar_planned_path or self.astar_path_current_segment_index >= len(self.astar_planned_path):
            ai_base_log("    A* path finished or invalid. Re-planning to player.")
            self.change_state(AI_STATE_AGGRESSIVE_PLANNING_PLAYER)
            return

        if self.current_movement_sub_path: # 正在移動中
            return

        current_astar_target_node = self.astar_planned_path[self.astar_path_current_segment_index]

        if ai_current_tile == (current_astar_target_node.x, current_astar_target_node.y):
            self.astar_path_current_segment_index += 1
            self.last_decision_time = pygame.time.get_ticks() - self.ai_decision_interval -1 # Force re-eval
            return

        if current_astar_target_node.is_empty_for_direct_movement():
            path_tuples = self.bfs_find_direct_movement_path(ai_current_tile, (current_astar_target_node.x, current_astar_target_node.y), max_depth=7)
            if path_tuples: self.set_current_movement_sub_path(path_tuples)
            else: self.change_state(AI_STATE_AGGRESSIVE_PLANNING_PLAYER) # 路徑不通，重新規劃
            return

        elif current_astar_target_node.is_destructible_box():
            self.target_destructible_wall_node_in_astar = current_astar_target_node
            # 使用基礎類別的 _find_optimal_bombing_and_retreat_spot
            # 但攻擊型 AI 可能對撤退點的要求較低
            bomb_spot_coord, retreat_spot_coord = self._find_optimal_bombing_and_retreat_spot_aggressive(self.target_destructible_wall_node_in_astar, ai_current_tile)

            if bomb_spot_coord and retreat_spot_coord:
                self.chosen_bombing_spot_coords = bomb_spot_coord
                self.chosen_retreat_spot_coords = retreat_spot_coord
                if ai_current_tile == self.chosen_bombing_spot_coords:
                    if self.ai_player.bombs_placed_count < self.ai_player.max_bombs:
                        self.ai_player.place_bomb() # Player 類別的方法
                        # ai_just_placed_bomb 和 last_bomb_placed_time 應該在 place_bomb 中由 Player 通知 Controller，或在此處設定
                        self.ai_just_placed_bomb = True
                        self.last_bomb_placed_time = pygame.time.get_ticks()
                        # 立即設定撤退路徑並切換狀態
                        path_to_retreat = self.bfs_find_direct_movement_path(ai_current_tile, self.chosen_retreat_spot_coords, max_depth=7)
                        if path_to_retreat: self.set_current_movement_sub_path(path_to_retreat)
                        self.change_state(AI_STATE_AGGRESSIVE_RETREAT_SHORT)
                    else: # 沒炸彈了
                        self.change_state(AI_STATE_AGGRESSIVE_PLANNING_PLAYER)
                else: # 前往轟炸點
                    path_to_bomb_spot = self.bfs_find_direct_movement_path(ai_current_tile, self.chosen_bombing_spot_coords, max_depth=7)
                    if path_to_bomb_spot: self.set_current_movement_sub_path(path_to_bomb_spot)
                    else: self.change_state(AI_STATE_AGGRESSIVE_PLANNING_PLAYER)
            else: # 找不到好的炸牆方案，攻擊型 AI 可能會選擇強行 Engage 或重新規劃
                ai_base_log("    Cannot find optimal bombing spot for clearance. Re-evaluating.")
                self.change_state(AI_STATE_AGGRESSIVE_ENGAGE) # 嘗試直接交戰
                # 或者 self.change_state(AI_STATE_AGGRESSIVE_PLANNING_PLAYER)
        else: # A* 路徑上有不可處理的障礙 (例如固定牆，這不應該發生在 A* 的可達路徑上)
            self.change_state(AI_STATE_AGGRESSIVE_PLANNING_PLAYER)


    def handle_engage_state(self, ai_current_tile):
        ai_base_log(f"[AGGRESSIVE_AI_ENGAGE] at {ai_current_tile}.")
        # 與原始 AIController 的 ENGAGING_PLAYER 狀態非常相似
        # 主要調整：更積極地尋找攻擊機會，對撤退點的要求可以略微降低
        human_pos = self._get_human_player_current_tile()
        if not human_pos:
            self.change_state(AI_STATE_AGGRESSIVE_IDLE_SCAN); return

        dist_to_human = abs(ai_current_tile[0] - human_pos[0]) + abs(ai_current_tile[1] - human_pos[1])
        engage_min_dist = getattr(settings, "AI_ENGAGE_MIN_DIST_TO_PLAYER_FOR_DIRECT_PATH", 2) # 從原始AIController借鑒
        if dist_to_human <= engage_min_dist:
            self.change_state(AI_STATE_AGGRESSIVE_CQC); return

        if self.ai_just_placed_bomb: # 剛放完炸彈，應該在撤退狀態
            if self.current_state != AI_STATE_AGGRESSIVE_RETREAT_SHORT:
                 self.change_state(AI_STATE_AGGRESSIVE_RETREAT_SHORT)
            return

        # 嘗試放置攻擊性炸彈
        if self.ai_player.bombs_placed_count < self.ai_player.max_bombs:
            # 檢查當前位置或鄰近位置是否適合攻擊玩家
            # (這部分邏輯可以大量參考原始 AIController 的 ENGAGING_PLAYER 中的炸彈決策)
            # 但 _find_optimal_bombing_and_retreat_spot_aggressive 應該用攻擊型的標準
            # ...
            # 假設找到了 best_bombing_action = {'bomb_spot': ..., 'retreat_spot': ..., 'path_to_bomb_spot_coords': ...}
            # best_bombing_action = self._evaluate_potential_bombing_actions_aggressive(ai_current_tile, human_pos)
            # if best_bombing_action:
            #    self.chosen_bombing_spot_coords = best_bombing_action['bomb_spot']
            #    self.chosen_retreat_spot_coords = best_bombing_action['retreat_spot']
            #    if ai_current_tile == self.chosen_bombing_spot_coords:
            #        self.ai_player.place_bomb()
            #        self.ai_just_placed_bomb = True; self.last_bomb_placed_time = pygame.time.get_ticks()
            #        path_to_retreat = self.bfs_find_direct_movement_path(ai_current_tile, self.chosen_retreat_spot_coords, max_depth=7)
            #        if path_to_retreat: self.set_current_movement_sub_path(path_to_retreat)
            #        self.change_state(AI_STATE_AGGRESSIVE_RETREAT_SHORT)
            #    else:
            #        self.set_current_movement_sub_path(best_bombing_action['path_to_bomb_spot_coords'])
            #    return
            pass # 佔位符，需要詳細實現攻擊評估

        # 如果不放炸彈，則移動向玩家
        if not self.current_movement_sub_path:
            path_to_human = self.bfs_find_direct_movement_path(ai_current_tile, human_pos, max_depth=10, avoid_specific_tile=human_pos) # 避免直接踩到玩家身上
            if path_to_human and len(path_to_human) > 1:
                self.set_current_movement_sub_path(path_to_human)
            elif path_to_human and len(path_to_human) == 1 : # 已經在旁邊了
                self.change_state(AI_STATE_AGGRESSIVE_CQC)
            else: # 路徑不通
                 # 如果路徑不通，攻擊型AI可能會嘗試炸牆 (如果A*路徑建議如此)
                if self.astar_planned_path and any(node.is_destructible_box() for node in self.astar_planned_path):
                    self.change_state(AI_STATE_AGGRESSIVE_EXECUTE_CLEARANCE)
                else: # 真的沒路了
                    ai_base_log("    ENGAGE: Cannot find path to human, trying to re-plan A*")
                    self.change_state(AI_STATE_AGGRESSIVE_PLANNING_PLAYER)


    def handle_cqc_state(self, ai_current_tile):
        ai_base_log(f"[AGGRESSIVE_AI_CQC] at {ai_current_tile}.")
        # 與原始 AIController 的 CLOSE_QUARTERS_COMBAT 狀態非常相似
        # 主要調整：更高的機率進行侵略性放置炸彈
        human_pos = self._get_human_player_current_tile()
        if not human_pos:
            self.change_state(AI_STATE_AGGRESSIVE_IDLE_SCAN); return

        dist_to_human = abs(ai_current_tile[0] - human_pos[0]) + abs(ai_current_tile[1] - human_pos[1])
        engage_min_dist = getattr(settings, "AI_ENGAGE_MIN_DIST_TO_PLAYER_FOR_DIRECT_PATH", 2)
        if dist_to_human > engage_min_dist: # 玩家跑遠了
            self.change_state(AI_STATE_AGGRESSIVE_ENGAGE); return

        if self.ai_just_placed_bomb:
            if self.current_state != AI_STATE_AGGRESSIVE_RETREAT_SHORT: self.change_state(AI_STATE_AGGRESSIVE_RETREAT_SHORT)
            return

        can_attempt_bombing = self.ai_player.bombs_placed_count < self.ai_player.max_bombs
        if can_attempt_bombing:
            # (參考原始 CQC 中的炸彈放置邏輯，但 aggressive_bomb_chance 可以更高)
            # aggressive_bomb_chance = getattr(settings, "AI_AGGRESSIVE_CQC_BOMB_CHANCE", 0.8) # 比原始的 0.6 更高
            # if random.random() < aggressive_bomb_chance:
            #    # 嘗試放置炸彈並找到任何一個非爆炸點作為撤退點
            #    ...
            #    self.ai_player.place_bomb()
            #    self.ai_just_placed_bomb = True; self.last_bomb_placed_time = pygame.time.get_ticks()
            #    # 尋找一個"還行"的撤退點
            #    desperate_retreat_options = self._find_desperate_retreat_cqc(ai_current_tile)
            #    if desperate_retreat_options:
            #        self.chosen_retreat_spot_coords = random.choice(desperate_retreat_options)
            #        self.set_current_movement_sub_path([ai_current_tile, self.chosen_retreat_spot_coords])
            #    self.change_state(AI_STATE_AGGRESSIVE_RETREAT_SHORT)
            #    return
            pass # 佔位符，需要詳細實現 CQC 炸彈邏輯

        # 如果不放炸彈，則嘗試重新定位以獲得更好攻擊角度，或緊逼玩家
        if not self.current_movement_sub_path and self.ai_player.action_timer <= 0:
            # (參考原始 CQC 中的 reposition 邏輯，但更傾向於靠近玩家或有攻擊機會的位置)
            # ...
            pass # 佔位符


    def handle_retreat_short_state(self, ai_current_tile):
        ai_base_log(f"[AGGRESSIVE_AI_RETREAT_SHORT] at {ai_current_tile}. Target: {self.chosen_retreat_spot_coords}")
        # 與 ConservativeAIController 的 handle_retreat_state 類似，但撤退後可能更快轉回攻擊狀態
        if self.current_movement_sub_path:
            return

        if ai_current_tile == self.chosen_retreat_spot_coords or not self.chosen_retreat_spot_coords: # 到達撤退點或沒有指定撤退點
            if not self.is_bomb_still_active(self.last_bomb_placed_time):
                ai_base_log(f"      Bomb cleared. Aggressive AI re-evaluating engagement.")
                self.ai_just_placed_bomb = False
                self.chosen_bombing_spot_coords = None
                self.chosen_retreat_spot_coords = None
                # 攻擊型 AI 可能會立即重新掃描或規劃攻擊玩家
                self.change_state(AI_STATE_AGGRESSIVE_IDLE_SCAN)
            else: # 炸彈還在
                # 攻擊型 AI 在等待時也可能尋找新的攻擊機會，如果撤退點本身可以攻擊的話
                pass
        else: # 未到達預期撤退點
            retreat_path_tuples = self.bfs_find_direct_movement_path(ai_current_tile, self.chosen_retreat_spot_coords, max_depth=7)
            if retreat_path_tuples and len(retreat_path_tuples) > 1:
                self.set_current_movement_sub_path(retreat_path_tuples)
            else: # 路徑不通，緊急躲避
                self.change_state(AI_STATE_AGGRESSIVE_EVADING)


    def handle_evading_danger_state(self, ai_current_tile):
        ai_base_log(f"[AGGRESSIVE_AI_EVADING] at {ai_current_tile}")
        # 與 ConservativeAIController 的 handle_evading_danger_state 類似
        # 但逃脫後，攻擊型 AI 會更快嘗試反擊或重新尋找玩家
        if not self.is_tile_dangerous(ai_current_tile[0], ai_current_tile[1], future_seconds=0.3): # 檢查標準可以略寬鬆
            ai_base_log(f"    Tile {ai_current_tile} now considered safe. Aggressive AI switching to IDLE_SCAN.")
            self.current_movement_sub_path = []
            self.change_state(AI_STATE_AGGRESSIVE_IDLE_SCAN)
            return

        # (尋找逃跑路徑的邏輯，與 ConservativeAIController 類似，但 max_depth 和其他參數可以不同)
        # ...
        path_target_is_dangerous = False # 與保守型類似的檢查
        if self.current_movement_sub_path and len(self.current_movement_sub_path) > 0 :
            final_target_in_sub_path = self.current_movement_sub_path[-1]
            if self.is_tile_dangerous(final_target_in_sub_path[0], final_target_in_sub_path[1], future_seconds=0.1):
                 path_target_is_dangerous = True

        if not self.current_movement_sub_path or \
           (self.current_movement_sub_path and ai_current_tile == self.current_movement_sub_path[-1]) or \
           path_target_is_dangerous:
            safe_options_coords = self.find_safe_tiles_nearby_for_retreat_aggressive(ai_current_tile, ai_current_tile, 0, max_depth=5) # 攻擊型可能不會跑太遠
            # ... (選擇路徑並設定的邏輯)
            best_evasion_path_coords = []
            if safe_options_coords:
                for safe_spot_coord in safe_options_coords:
                    evasion_path_tuples = self.bfs_find_direct_movement_path(ai_current_tile, safe_spot_coord, max_depth=5)
                    if evasion_path_tuples and len(evasion_path_tuples) > 1:
                        best_evasion_path_coords = evasion_path_tuples; break
            if best_evasion_path_coords:
                self.set_current_movement_sub_path(best_evasion_path_coords)
            else: # 沒地方跑了
                self.current_movement_sub_path = []
                self.ai_player.is_moving = False


    # --- 攻擊型特有的輔助方法 ---
    def _find_optimal_bombing_and_retreat_spot_aggressive(self, target_node: TileNode, ai_current_tile):
        # 這個方法會被 EXECUTE_CLEARANCE 或 ENGAGE 狀態呼叫
        # 與基礎類別的類似，但可能對撤退點的數量/質量要求較低
        # 或者，如果找不到完美的，它可能會選擇一個「還行」的方案
        ai_base_log(f"    [AGGRESSIVE_BOMB_SPOT_FINDER] For target {target_node} from AI at {ai_current_tile}")
        candidate_placements = []
        # (參考原始 _find_optimal_bombing_and_retreat_spot 的邏輯)
        # 但在呼叫 self.can_place_bomb_and_retreat_aggressive 時使用攻擊型的標準
        for dx_wall_offset, dy_wall_offset in DIRECTIONS.values():
            bomb_spot_x = target_node.x + dx_wall_offset
            bomb_spot_y = target_node.y + dy_wall_offset
            # 攻擊型AI炸牆時，bomb_spot 可能是牆本身，或者牆旁邊
            # 如果是炸玩家，target_node 就是玩家，bomb_spot 就是AI當前或鄰近
            # 這裡假設 target_node 是牆

            # 確保轟炸點本身是空的且安全 (短期內)
            bomb_spot_node_check = self._get_node_at_coords(bomb_spot_x, bomb_spot_y)
            if not (bomb_spot_node_check and bomb_spot_node_check.is_empty_for_direct_movement() and \
                    not self.is_tile_dangerous(bomb_spot_x, bomb_spot_y, 0.1)):
                # 如果目標是牆，而這個潛在轟炸點不佳，檢查牆的另一側作為轟炸點
                # 這裡的邏輯需要根據 target_node 是牆還是玩家來調整
                if target_node.is_destructible_box(): # 如果目標是牆
                     # 嘗試以牆本身作為"假想"轟炸點，然後找鄰近的空格子放炸彈
                     # 或者遍歷牆的四周作為可能的放置點
                     pass # 這部分需要更詳細的邏輯
                else: # 如果目標是玩家或其他，則此潛在轟炸點不佳
                    continue

            # ... (path_to_bomb_spot 的計算)
            # ... (can_bomb, retreat_spot_coords = self.can_place_bomb_and_retreat_aggressive(...))
            # ... (添加到 candidate_placements)
            pass # 佔位符

        if not candidate_placements: return None, None
        # 攻擊型可能選擇路徑最短的，即使撤退點質量稍差
        candidate_placements.sort(key=lambda p: p['path_to_bomb_spot_len'])
        return candidate_placements[0]['bomb_spot'], candidate_placements[0]['retreat_spot']

    def can_place_bomb_and_retreat_aggressive(self, bomb_placement_coords):
        # 與基礎類別的類似，但對 retreat_spots 的要求可能更低
        # 例如，只要有一個還算安全的撤退點就行
        if self.is_tile_dangerous(bomb_placement_coords[0], bomb_placement_coords[1], future_seconds=0.05): # 極短期檢查
            return False, None
        bomb_range_to_use = self.ai_player.bomb_range
        # 使用攻擊型的撤退點尋找邏輯，它可能接受風險稍高的點
        retreat_spots = self.find_safe_tiles_nearby_for_retreat_aggressive(bomb_placement_coords, bomb_placement_coords, bomb_range_to_use, max_depth=5) # 深度較淺
        if retreat_spots:
            best_retreat_spot = retreat_spots[0] # 取第一個（可能是最近的）
            path_to_retreat = self.bfs_find_direct_movement_path(bomb_placement_coords, best_retreat_spot, max_depth=5)
            if path_to_retreat and len(path_to_retreat) > 1 :
                return True, best_retreat_spot
        return False, None

    def find_safe_tiles_nearby_for_retreat_aggressive(self, from_tile_coords, bomb_just_placed_at_coords, bomb_range, max_depth=5, future_seconds_multiplier=0.8):
        # 與保守型的類似，但 max_depth 更小，future_seconds_multiplier 更小 (表示對未來危險的預判時間更短，更能容忍風險)
        # 並且可能只尋找少量 (例如1-2個) 撤退點就夠了
        # ... (具體實現參考 ConservativeAIController 的版本，但調整參數和排序邏輯)
        # 攻擊型可能優先選擇"最近的"安全點，即使它不是"最安全的"
        # sort_key=lambda x: x['path_len']
        # ...
        # 返回的列表可以更短
        ai_base_log(f"    [AGGRESSIVE_RETREAT_FINDER] from_tile={from_tile_coords}, bomb_at={bomb_just_placed_at_coords}, range={bomb_range}, depth={max_depth}")
        q = deque([(from_tile_coords, [from_tile_coords], 0)])
        visited = {from_tile_coords}
        safe_retreat_spots = []
        danger_check_future_seconds = settings.AI_RETREAT_SPOT_OTHER_DANGER_FUTURE_SECONDS * future_seconds_multiplier

        while q:
            (curr_x, curr_y), path, depth = q.popleft()
            if depth > max_depth: continue

            is_safe_from_this_bomb = True
            if bomb_range > 0 :
                is_safe_from_this_bomb = not self._is_tile_in_hypothetical_blast(curr_x, curr_y, bomb_just_placed_at_coords[0], bomb_just_placed_at_coords[1], bomb_range)
            is_safe_from_other_dangers = not self.is_tile_dangerous(curr_x, curr_y, future_seconds=danger_check_future_seconds)

            if is_safe_from_this_bomb and is_safe_from_other_dangers:
                safe_retreat_spots.append({'coords': (curr_x, curr_y), 'path_len': len(path) -1, 'depth': depth})
                if len(safe_retreat_spots) >= 3: # 攻擊型找到少量幾個就夠了
                    break 

            if depth < max_depth:
                # (BFS 鄰居擴展邏輯)
                shuffled_directions = list(DIRECTIONS.values()); random.shuffle(shuffled_directions)
                for dx, dy in shuffled_directions:
                    next_x, next_y = curr_x + dx, curr_y + dy
                    if (next_x, next_y) not in visited:
                        node = self._get_node_at_coords(next_x, next_y)
                        if node and node.is_empty_for_direct_movement():
                            if not self.is_tile_dangerous(next_x, next_y, future_seconds=0.05): # 極短期檢查
                                visited.add((next_x, next_y))
                                q.append(((next_x, next_y), path + [(next_x, next_y)], depth + 1))
        if safe_retreat_spots:
            safe_retreat_spots.sort(key=lambda x: x['path_len']) # 優先最近的
            return [spot['coords'] for spot in safe_retreat_spots]
        return []

    # debug_draw_path 可以繼承基礎類別的，然後再添加攻擊型特有的標記
    # 例如，用鮮豔的紅色表示其攻擊目標或路徑
    def debug_draw_path(self, surface):
        super().debug_draw_path(surface) # 呼叫父類繪製基礎路徑

        ai_tile_now = self._get_ai_current_tile()
        if not ai_tile_now or not hasattr(settings, 'TILE_SIZE'): return
        tile_size = settings.TILE_SIZE
        half_tile = tile_size // 2

        # 標記攻擊目標 (玩家的最後位置)
        if self.target_player_last_seen_tile and \
           (self.current_state == AI_STATE_AGGRESSIVE_PLANNING_PLAYER or \
            self.current_state == AI_STATE_AGGRESSIVE_ENGAGE or \
            self.current_state == AI_STATE_AGGRESSIVE_CQC):
            px, py = self.target_player_last_seen_tile
            center_tx, center_ty = px * tile_size + half_tile, py * tile_size + half_tile
            pygame.draw.circle(surface, (255, 0, 0, 180), (center_tx, center_ty), tile_size // 2, 2) # 大紅圈
            pygame.draw.line(surface, (255,0,0,180), (center_tx - tile_size//3, center_ty - tile_size//3), (center_tx + tile_size//3, center_ty + tile_size//3), 2)
            pygame.draw.line(surface, (255,0,0,180), (center_tx - tile_size//3, center_ty + tile_size//3), (center_tx + tile_size//3, center_ty - tile_size//3), 2)

        # 如果 A* 路徑是直接指向玩家，可以用紅色線條
        if self.astar_planned_path and self.target_player_last_seen_tile and \
           len(self.astar_planned_path) > 0 and \
           (self.astar_planned_path[-1].x == self.target_player_last_seen_tile[0] and \
            self.astar_planned_path[-1].y == self.target_player_last_seen_tile[1]):

            astar_points_to_draw_agg = [(ai_tile_now[0] * tile_size + half_tile, ai_tile_now[1] * tile_size + half_tile)]
            for i in range(self.astar_path_current_segment_index, len(self.astar_planned_path)):
                node = self.astar_planned_path[i]
                px_node, py_node = node.x * tile_size + half_tile, node.y * tile_size + half_tile
                astar_points_to_draw_agg.append((px_node, py_node))

            if len(astar_points_to_draw_agg) > 1:
                pygame.draw.lines(surface, (200, 0, 0, 150), False, astar_points_to_draw_agg, 2) # 粗紅線