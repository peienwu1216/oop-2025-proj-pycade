# oop-2025-proj-pycade/core/ai_item_focused.py

import pygame
import settings
import random
from collections import deque
from .ai_controller_base import AIControllerBase, TileNode, DIRECTIONS, ai_base_log

# 道具優先型 AI 的狀態
AI_STATE_ITEM_SCANNING = "ITEM_SCANNING"
AI_STATE_ITEM_MOVING_TO_ACCESSIBLE_ITEM = "ITEM_MOVING_TO_ACCESSIBLE_ITEM"
AI_STATE_ITEM_PLANNING_BOMB_FOR_ITEM = "ITEM_PLANNING_BOMB_FOR_ITEM"
AI_STATE_ITEM_MOVING_TO_BOMB_SPOT_FOR_ITEM = "ITEM_MOVING_TO_BOMB_SPOT_FOR_ITEM"
AI_STATE_ITEM_BOMBING_FOR_ITEM = "ITEM_BOMBING_FOR_ITEM"
AI_STATE_ITEM_RETREAT_AFTER_BOMBING_FOR_ITEM = "ITEM_RETREAT_AFTER_BOMBING_FOR_ITEM"
AI_STATE_ITEM_NO_VIABLE_TARGET_IDLE = "ITEM_NO_VIABLE_TARGET_IDLE"
AI_STATE_ITEM_EVADING_DANGER = "ITEM_EVADING_DANGER"
AI_STATE_ITEM_DEAD = "DEAD_ITEM_FOCUSED"

class ItemFocusedAIController(AIControllerBase):
    def __init__(self, ai_player_sprite, game_instance):
        super().__init__(ai_player_sprite, game_instance)
        ai_base_log(f"ItemFocusedAIController __init__ for Player ID: {id(ai_player_sprite)}")

        # （1）！！！確保所有 AI_STATE_ITEM_... 常數在此檔案開頭已定義！！！
        # （已經在檔案開頭定義了）

        self.current_state = AI_STATE_ITEM_SCANNING
        
        self.item_value_threshold = getattr(settings, "AI_ITEM_VALUE_THRESHOLD", 10) 
        self.item_scan_interval = getattr(settings, "AI_ITEM_SCAN_INTERVAL", 1200) 
        self.bfs_max_depth_direct_item = getattr(settings, "AI_ITEM_BFS_MAX_DEPTH_DIRECT", 18) 
        self.astar_max_depth_item = getattr(settings, "AI_ITEM_ASTAR_MAX_DEPTH", 35)
        self.bombing_cost_for_item = getattr(settings, "AI_ITEM_BOMBING_COST", 20) 
        self.danger_avoidance_for_item_future = getattr(settings, "AI_ITEM_DANGER_FUTURE_SEC", 0.7)

        self.stuck_threshold_decision_cycles_item = getattr(settings, "AI_ITEM_STUCK_CYCLES", 10) 
        self.oscillation_stuck_threshold_item = getattr(settings, "AI_ITEM_OSCILLATION_CYCLES", 5)

        self.current_target_item_info = None
        self.chosen_bombing_spot_coords = None
        self.chosen_retreat_spot_coords = None
        self.wall_to_clear_for_item = None
        
        self.last_scan_time = 0
        try:
            self.hud_font = pygame.font.Font(None, 18) 
        except Exception:
            self.hud_font = pygame.font.SysFont("arial", 18)
        self.reset_state()

    def reset_state(self):
        super().reset_state_base()
        self.current_state = AI_STATE_ITEM_SCANNING
        ai_base_log(f"ItemFocusedAIController reset_state for Player ID: {id(self.ai_player)}.")
        self._reset_item_specific_targets()
        self.last_scan_time = pygame.time.get_ticks() - self.item_scan_interval 

    def _reset_item_specific_targets(self):
        ai_base_log("    Resettings item-specific targets.")
        self.current_target_item_info = None
        self.astar_planned_path = [] 
        self.current_movement_sub_path = [] 
        self.chosen_bombing_spot_coords = None
        self.chosen_retreat_spot_coords = None
        self.wall_to_clear_for_item = None

    def update(self):
        current_time = pygame.time.get_ticks()
        ai_current_tile = self._get_ai_current_tile()

        if not ai_current_tile or not self.ai_player or not self.ai_player.is_alive:
            if self.current_state != AI_STATE_ITEM_DEAD: self.change_state(AI_STATE_ITEM_DEAD)
            return

        if self.ai_just_placed_bomb and self.last_bomb_placed_time > 0:
            if current_time - self.last_bomb_placed_time > (settings.BOMB_TIMER + settings.EXPLOSION_DURATION + 1000):
                self.ai_just_placed_bomb = False; self.last_bomb_placed_time = 0
        
        stuck_or_oscillating = self._update_and_check_stuck_conditions(ai_current_tile, self.stuck_threshold_decision_cycles_item, self.oscillation_stuck_threshold_item)

        is_decision_time = (current_time - self.last_decision_time >= self.ai_decision_interval)
        is_immediately_dangerous = self.is_tile_dangerous(ai_current_tile[0], ai_current_tile[1], future_seconds=self.danger_avoidance_for_item_future / 2.5) 

        if is_immediately_dangerous and self.current_state != AI_STATE_ITEM_EVADING_DANGER:
            ai_base_log(f"[ITEM_AI_DANGER] at {ai_current_tile}! Switching to EVADING.")
            self.change_state(AI_STATE_ITEM_EVADING_DANGER) 
            self.last_decision_time = current_time 

        if stuck_or_oscillating and self.current_state != AI_STATE_ITEM_EVADING_DANGER :
            ai_base_log(f"[ITEM_AI_STUCK_RESET] Stuck/Oscillating ({self.decision_cycle_stuck_counter}/{self.oscillation_stuck_counter}). Clearing targets and re-scanning.")
            self.change_state(AI_STATE_ITEM_SCANNING) 
            self.last_decision_time = current_time 

        elif is_decision_time or self.current_state == AI_STATE_ITEM_EVADING_DANGER or \
            (self.current_state == AI_STATE_ITEM_SCANNING and current_time - self.last_scan_time >= self.item_scan_interval):
            
            if self.current_state != AI_STATE_ITEM_EVADING_DANGER: self.last_decision_time = current_time
            if self.current_state == AI_STATE_ITEM_SCANNING and (current_time - self.last_scan_time >= self.item_scan_interval):
                 self.last_scan_time = current_time

            if self.current_state == AI_STATE_ITEM_EVADING_DANGER:
                self.handle_evading_danger_state(ai_current_tile)
            elif self.current_state == AI_STATE_ITEM_SCANNING:
                self.handle_scanning_state(ai_current_tile)
            elif self.current_state == AI_STATE_ITEM_MOVING_TO_ACCESSIBLE_ITEM:
                self.handle_moving_to_accessible_item_state(ai_current_tile)
            elif self.current_state == AI_STATE_ITEM_PLANNING_BOMB_FOR_ITEM: 
                self.handle_planning_bomb_for_item_state(ai_current_tile)
            elif self.current_state == AI_STATE_ITEM_MOVING_TO_BOMB_SPOT_FOR_ITEM:
                self.handle_moving_to_bomb_spot_for_item_state(ai_current_tile)
            elif self.current_state == AI_STATE_ITEM_BOMBING_FOR_ITEM:
                self.handle_bombing_for_item_state(ai_current_tile)
            elif self.current_state == AI_STATE_ITEM_RETREAT_AFTER_BOMBING_FOR_ITEM:
                self.handle_retreat_after_bombing_for_item_state(ai_current_tile)
            elif self.current_state == AI_STATE_ITEM_NO_VIABLE_TARGET_IDLE:
                self.handle_no_viable_target_idle_state(ai_current_tile)
            elif self.current_state == AI_STATE_ITEM_DEAD:
                pass
            else: 
                ai_base_log(f"[ITEM_AI_WARN] Unknown state: {self.current_state}. Reverting to SCANNING.")
                self.change_state(AI_STATE_ITEM_SCANNING)
        
        if self.ai_player.action_timer <= 0: 
            if self.current_movement_sub_path:
                sub_path_finished_or_failed = self.execute_next_move_on_sub_path(ai_current_tile)
                if sub_path_finished_or_failed:
                    self.last_decision_time = pygame.time.get_ticks() - self.ai_decision_interval - 1 
                    if self.current_state == AI_STATE_ITEM_MOVING_TO_ACCESSIBLE_ITEM and self.current_target_item_info and ai_current_tile == self.current_target_item_info['coords']:
                        self._target_item_reached_or_gone()
                    elif self.current_state == AI_STATE_ITEM_MOVING_TO_BOMB_SPOT_FOR_ITEM and self.current_target_item_info and ai_current_tile == self.current_target_item_info.get('bomb_spot'):
                        self.change_state(AI_STATE_ITEM_BOMBING_FOR_ITEM) 
                    elif self.current_state == AI_STATE_ITEM_RETREAT_AFTER_BOMBING_FOR_ITEM and self.chosen_retreat_spot_coords and ai_current_tile == self.chosen_retreat_spot_coords:
                        self.handle_retreat_after_bombing_for_item_state(ai_current_tile) 
            
            if not self.current_movement_sub_path:
                self.ai_player.is_moving = False

    # （1）！！！新增 ItemFocusedAIController 特有的 change_state 方法！！！
    def change_state(self, new_state):
        old_state = self.current_state
        # 呼叫父類的通用狀態轉換邏輯 (這會設定 self.current_state, self.state_start_time 並清空路徑)
        super().change_state(new_state) 

        # 特定於道具 AI 的清理邏輯
        # 如果從一個與道具追蹤相關的狀態離開，並且新的狀態不是另一個道具追蹤/處理狀態，則清理道具目標
        item_pursuit_states = [ # 這些狀態下，AI 有一個明確的 current_target_item_info
            AI_STATE_ITEM_MOVING_TO_ACCESSIBLE_ITEM,
            AI_STATE_ITEM_PLANNING_BOMB_FOR_ITEM, # 雖然此狀態可能較少直接使用
            AI_STATE_ITEM_MOVING_TO_BOMB_SPOT_FOR_ITEM,
            AI_STATE_ITEM_BOMBING_FOR_ITEM
            # RETREAT_AFTER_BOMBING_FOR_ITEM 也與之前的道具目標相關，但不一定是主動追蹤狀態
        ]
        # 這些狀態是道具相關的，但不一定表示正在“追逐”一個舊目標，所以不在此處觸發重置
        safe_new_item_states = [
            AI_STATE_ITEM_SCANNING, # 掃描會自己找新目標
            AI_STATE_ITEM_EVADING_DANGER, # 躲避優先
            AI_STATE_ITEM_NO_VIABLE_TARGET_IDLE, # 沒有目標
            AI_STATE_ITEM_RETREAT_AFTER_BOMBING_FOR_ITEM, # 正在處理炸彈後續
            AI_STATE_ITEM_DEAD
        ]

        if old_state in item_pursuit_states and new_state not in item_pursuit_states:
            # 只有當舊狀態是追蹤道具，而新狀態不是繼續追蹤或處理該道具的後續時，才重置
            # 例如，從 MOVING_TO_ITEM -> EVADING，或者 MOVING_TO_ITEM -> SCANNING (因卡住)
            if new_state not in [AI_STATE_ITEM_RETREAT_AFTER_BOMBING_FOR_ITEM]: # 如果不是轉到炸後撤退
                ai_base_log(f"    ItemFocusedAI: Clearing item targets due to state change from {old_state} to {new_state}")
                self._reset_item_specific_targets()
    # （1）！！！新增結束！！！
    
    def _evaluate_item_value(self, item_sprite, path_len_to_item):
        # (與上一版本相同的實現)
        if not item_sprite or not hasattr(item_sprite, 'type'): return -1
        item_type = item_sprite.type; base_value = 0
        if item_type == settings.ITEM_TYPE_BOMB_CAPACITY: base_value = 90 if self.ai_player.max_bombs < getattr(settings, "MAX_POSSIBLE_BOMBS", 5) else 5
        elif item_type == settings.ITEM_TYPE_BOMB_RANGE: base_value = 85 if self.ai_player.bomb_range < getattr(settings, "MAX_POSSIBLE_RANGE", 6) else 5
        elif item_type == settings.ITEM_TYPE_LIFE: base_value = 120 if self.ai_player.lives < settings.MAX_LIVES else 2
        elif item_type == settings.ITEM_TYPE_SCORE: base_value = 10
        else: base_value = 15
        if base_value <= 0: return -1
        value_after_distance = base_value / (path_len_to_item / 3.0 + 1.0)
        item_tile_x = item_sprite.rect.centerx // settings.TILE_SIZE; item_tile_y = item_sprite.rect.centery // settings.TILE_SIZE
        if self.is_tile_dangerous(item_tile_x, item_tile_y, future_seconds=self.danger_avoidance_for_item_future):
            value_after_distance *= 0.1 
            ai_base_log(f"    Item {item_type} at dangerous spot ({item_tile_x},{item_tile_y}), value heavily reduced.")
        ai_base_log(f"    Evaluating item: {item_type}, base_val: {base_value}, path_len: {path_len:.1f}, final_val: {value_after_distance:.2f}")
        return value_after_distance

    def _find_best_item_target(self, ai_current_tile):
        # (與上一版本相同的實現)
        best_target_info = None; highest_score = -1 
        if not hasattr(self.game, 'items_group') or not self.game.items_group:
            ai_base_log("    _find_best_item_target: No items_group attribute or items_group is empty."); return None
        active_items = [s for s in self.game.items_group if s.alive()]
        if not active_items:
            ai_base_log("    _find_best_item_target: items_group contains no alive items."); return None
        ai_base_log(f"    _find_best_item_target: Scanning {len(active_items)} alive items.")
        for item_sprite in active_items:
            item_coords = (item_sprite.rect.centerx // settings.TILE_SIZE, item_sprite.rect.centery // settings.TILE_SIZE)
            ai_base_log(f"        Considering item: {getattr(item_sprite, 'type', 'UnknownType')} at {item_coords}")
            direct_path_to_item = self.bfs_find_direct_movement_path(ai_current_tile, item_coords, max_depth=self.bfs_max_depth_direct_item)
            path_len = len(direct_path_to_item) - 1 if direct_path_to_item else float('inf')
            current_item_value = self._evaluate_item_value(item_sprite, path_len)
            ai_base_log(f"            BFS path len: {path_len if direct_path_to_item else 'N/A'}. Evaluated value: {current_item_value:.2f}. Threshold: {self.item_value_threshold}")
            if current_item_value < self.item_value_threshold:
                ai_base_log(f"            Item {getattr(item_sprite, 'type', 'UnknownType')} value too low. Skipping."); continue
            if direct_path_to_item:
                ai_base_log(f"            Direct path found for {getattr(item_sprite, 'type', 'UnknownType')}. Length: {path_len}.")
                if current_item_value > highest_score:
                    highest_score = current_item_value
                    best_target_info = {'sprite': item_sprite, 'coords': item_coords, 'value': current_item_value,'path': direct_path_to_item, 'type': 'direct','wall_to_bomb': None, 'bomb_spot': None, 'retreat_spot': None}
                    ai_base_log(f"                New best direct target: {getattr(item_sprite, 'type', 'UnknownType')}, score: {highest_score:.2f}")
                continue 
            ai_base_log(f"            No direct BFS to {getattr(item_sprite, 'type', 'UnknownType')}. Trying A* and bombing logic.")
            astar_path_nodes = self.astar_find_path(ai_current_tile, item_coords) 
            if not astar_path_nodes:
                ai_base_log(f"                A* path to {getattr(item_sprite, 'type', 'UnknownType')} FAILED."); continue 
            wall_to_bomb_node = None; path_to_wall_is_clear = True
            for node_idx, node in enumerate(astar_path_nodes):
                if node_idx == 0 and (node.x, node.y) == ai_current_tile: continue 
                if node.is_destructible_box(): wall_to_bomb_node = node; break 
                elif not node.is_empty_for_direct_movement(): path_to_wall_is_clear = False; break
            if not path_to_wall_is_clear:
                ai_base_log(f"                A* path to {getattr(item_sprite, 'type', 'UnknownType')} blocked by indestructible wall."); continue
            if not wall_to_bomb_node:
                astar_path_coords = self._convert_astar_nodes_to_coords(astar_path_nodes)
                astar_path_len = len(astar_path_coords) -1
                value_via_astar_direct = self._evaluate_item_value(item_sprite, astar_path_len)
                if value_via_astar_direct > self.item_value_threshold and value_via_astar_direct > highest_score:
                    highest_score = value_via_astar_direct
                    best_target_info = {'sprite': item_sprite, 'coords': item_coords, 'value': value_via_astar_direct, 'path': astar_path_coords, 'type': 'astar_direct', 'wall_to_bomb': None, 'bomb_spot': None, 'retreat_spot': None}
                    ai_base_log(f"                Found A* direct path for {getattr(item_sprite, 'type', 'UnknownType')}, score: {highest_score:.2f}")
                continue
            ai_base_log(f"            A* to {getattr(item_sprite, 'type', 'UnknownType')} requires bombing wall: {wall_to_bomb_node}")
            bomb_spot, retreat_spot = self._find_optimal_bombing_and_retreat_spot_for_item(wall_to_bomb_node, ai_current_tile, for_item=True)
            if bomb_spot and retreat_spot:
                path_to_bomb_spot = self.bfs_find_direct_movement_path(ai_current_tile, bomb_spot, max_depth=self.bfs_max_depth_direct_item)
                if not path_to_bomb_spot:
                    ai_base_log(f"                Cannot BFS to bomb_spot {bomb_spot} for wall {wall_to_bomb_node}."); continue 
                cost_to_reach_bomb_spot = len(path_to_bomb_spot) - 1
                item_base_value = self._evaluate_item_value(item_sprite, 0) 
                value_after_bombing = item_base_value - self.bombing_cost_for_item - (cost_to_reach_bomb_spot * 0.3)
                ai_base_log(f"                Bombing for {getattr(item_sprite, 'type', 'UnknownType')}: val_after_bomb_cost={value_after_bombing:.2f} (item_base_val={item_base_value:.2f}, reach_cost={cost_to_reach_bomb_spot*0.3}, bomb_cost={self.bombing_cost_for_item})")
                if value_after_bombing > self.item_value_threshold and value_after_bombing > highest_score:
                    highest_score = value_after_bombing
                    best_target_info = {'sprite': item_sprite, 'coords': item_coords, 'value': value_after_bombing, 'path': path_to_bomb_spot, 'type': 'via_bombing', 'wall_to_bomb': wall_to_bomb_node, 'bomb_spot': bomb_spot, 'retreat_spot': retreat_spot}
                    ai_base_log(f"                New best via_bombing target: {getattr(item_sprite, 'type', 'UnknownType')}, score: {highest_score:.2f}")
            else:
                ai_base_log(f"                Cannot find optimal bombing/retreat for wall {wall_to_bomb_node} for item {getattr(item_sprite, 'type', 'UnknownType')}")
        if best_target_info:
             target_sprite_type = getattr(best_target_info.get('sprite'), 'type', 'UnknownType')
             ai_base_log(f"    [FINAL_ITEM_CHOICE] Target: {target_sprite_type} at {best_target_info.get('coords')}, Type: {best_target_info.get('type')}, Score: {highest_score:.2f}, Path: {best_target_info.get('path')}")
        else:
            ai_base_log(f"    [FINAL_ITEM_CHOICE] No viable item target found.")
        return best_target_info

    def handle_scanning_state(self, ai_current_tile):
        ai_base_log(f"[ITEM_AI_State] SCANNING at {ai_current_tile}")
        self.current_target_item_info = self._find_best_item_target(ai_current_tile)
        if self.current_target_item_info:
            target_type = self.current_target_item_info['type']
            path_to_next_point = self.current_target_item_info['path']
            if path_to_next_point and len(path_to_next_point) > 0 :
                self.set_current_movement_sub_path(path_to_next_point)
                if target_type == 'direct' or target_type == 'astar_direct':
                    self.change_state(AI_STATE_ITEM_MOVING_TO_ACCESSIBLE_ITEM)
                elif target_type == 'via_bombing':
                    self.chosen_bombing_spot_coords = self.current_target_item_info.get('bomb_spot') 
                    self.chosen_retreat_spot_coords = self.current_target_item_info.get('retreat_spot')
                    self.wall_to_clear_for_item = self.current_target_item_info.get('wall_to_bomb')
                    if not (self.chosen_bombing_spot_coords and self.chosen_retreat_spot_coords and self.wall_to_clear_for_item):
                        self._reset_item_specific_targets(); self.change_state(AI_STATE_ITEM_NO_VIABLE_TARGET_IDLE)
                    else: self.change_state(AI_STATE_ITEM_MOVING_TO_BOMB_SPOT_FOR_ITEM)
                else: self.change_state(AI_STATE_ITEM_NO_VIABLE_TARGET_IDLE)
            else: self._reset_item_specific_targets(); self.change_state(AI_STATE_ITEM_NO_VIABLE_TARGET_IDLE)
        else: self.change_state(AI_STATE_ITEM_NO_VIABLE_TARGET_IDLE)

    def handle_moving_to_accessible_item_state(self, ai_current_tile): 
        ai_base_log(f"[ITEM_AI_State] MOVING_TO_ACCESSIBLE_ITEM to {self.current_target_item_info.get('coords') if self.current_target_item_info else 'None'}")
        if not self.current_target_item_info or not self.current_target_item_info.get('sprite') or not self.current_target_item_info['sprite'].alive():
            self._target_item_reached_or_gone(); return
        target_coords = self.current_target_item_info['coords']
        if ai_current_tile == target_coords: 
            self._target_item_reached_or_gone(); return
        if not self.current_movement_sub_path:
            new_path = self.bfs_find_direct_movement_path(ai_current_tile, target_coords, max_depth=self.bfs_max_depth_direct_item // 2)
            if new_path and len(new_path) > 1: self.set_current_movement_sub_path(new_path)
            else: self._reset_item_specific_targets(); self.change_state(AI_STATE_ITEM_SCANNING)

    def handle_planning_bomb_for_item_state(self, ai_current_tile):
        ai_base_log(f"[ITEM_AI_State] PLANNING_BOMB_FOR_ITEM (type: {self.current_target_item_info.get('type') if self.current_target_item_info else 'None'})")
        if not self.current_target_item_info or self.current_target_item_info.get('type') != 'via_bombing':
            self._reset_item_specific_targets(); self.change_state(AI_STATE_ITEM_SCANNING); return
        bomb_spot = self.current_target_item_info.get('bomb_spot'); retreat_spot = self.current_target_item_info.get('retreat_spot')
        wall_target = self.current_target_item_info.get('wall_to_bomb'); path_to_bomb_spot = self.current_target_item_info.get('path')
        if not (bomb_spot and retreat_spot and wall_target and path_to_bomb_spot):
            self._reset_item_specific_targets(); self.change_state(AI_STATE_ITEM_SCANNING); return
        self.set_current_movement_sub_path(path_to_bomb_spot)
        self.chosen_bombing_spot_coords = bomb_spot; self.chosen_retreat_spot_coords = retreat_spot
        self.wall_to_clear_for_item = wall_target
        self.change_state(AI_STATE_ITEM_MOVING_TO_BOMB_SPOT_FOR_ITEM)

    def handle_moving_to_bomb_spot_for_item_state(self, ai_current_tile):
        target_bomb_spot = self.current_target_item_info.get('bomb_spot') if self.current_target_item_info else None
        ai_base_log(f"[ITEM_AI_State] MOVING_TO_BOMB_SPOT to {target_bomb_spot}")
        if not self.current_target_item_info or not target_bomb_spot or \
           not self.current_target_item_info.get('sprite') or not self.current_target_item_info['sprite'].alive():
            self._reset_item_specific_targets(); self.change_state(AI_STATE_ITEM_SCANNING); return
        if ai_current_tile == target_bomb_spot:
            self.change_state(AI_STATE_ITEM_BOMBING_FOR_ITEM); return
        if not self.current_movement_sub_path: 
            new_path_to_bomb_spot = self.bfs_find_direct_movement_path(ai_current_tile, target_bomb_spot, max_depth=self.bfs_max_depth_direct_item // 2)
            if new_path_to_bomb_spot and len(new_path_to_bomb_spot) > 1: self.set_current_movement_sub_path(new_path_to_bomb_spot)
            else: self._reset_item_specific_targets(); self.change_state(AI_STATE_ITEM_SCANNING)
    
    def handle_bombing_for_item_state(self, ai_current_tile):
        ai_base_log(f"[ITEM_AI_State] BOMBING_FOR_ITEM at {ai_current_tile}")
        if not self.current_target_item_info or \
           not self.current_target_item_info.get('bomb_spot') or \
           not self.current_target_item_info.get('retreat_spot') or \
           not self.current_target_item_info.get('wall_to_bomb'):
            self._reset_item_specific_targets(); self.change_state(AI_STATE_ITEM_SCANNING); return
        bomb_spot = self.current_target_item_info['bomb_spot']; retreat_spot = self.current_target_item_info['retreat_spot']
        wall_to_bomb = self.current_target_item_info['wall_to_bomb']
        if ai_current_tile != bomb_spot: 
            path_to_it = self.bfs_find_direct_movement_path(ai_current_tile, bomb_spot, max_depth=3)
            if path_to_it: self.set_current_movement_sub_path(path_to_it)
            self.change_state(AI_STATE_ITEM_MOVING_TO_BOMB_SPOT_FOR_ITEM); return
        current_wall_node = self._get_node_at_coords(wall_to_bomb.x, wall_to_bomb.y)
        if not current_wall_node or not current_wall_node.is_destructible_box():
            self.current_target_item_info['type'] = 'direct'; self.current_target_item_info['wall_to_bomb'] = None
            self.current_target_item_info['bomb_spot'] = None; self.current_target_item_info['retreat_spot'] = None
            direct_path = self.bfs_find_direct_movement_path(ai_current_tile, self.current_target_item_info['coords'], max_depth=self.bfs_max_depth_direct_item)
            if direct_path: self.current_target_item_info['path'] = direct_path; self.set_current_movement_sub_path(direct_path); self.change_state(AI_STATE_ITEM_MOVING_TO_ACCESSIBLE_ITEM)
            else: self._reset_item_specific_targets(); self.change_state(AI_STATE_ITEM_SCANNING)
            return
        if self.ai_player.bombs_placed_count < self.ai_player.max_bombs:
            self.ai_player.place_bomb(); self.ai_just_placed_bomb = True; self.last_bomb_placed_time = pygame.time.get_ticks()
            self.chosen_retreat_spot_coords = retreat_spot 
            path_to_retreat_coords = self.bfs_find_direct_movement_path(ai_current_tile, retreat_spot, max_depth=self.bfs_max_depth_direct_item)
            if path_to_retreat_coords and len(path_to_retreat_coords) > 1: self.set_current_movement_sub_path(path_to_retreat_coords)
            self.change_state(AI_STATE_ITEM_RETREAT_AFTER_BOMBING_FOR_ITEM)
        else: self._reset_item_specific_targets(); self.change_state(AI_STATE_ITEM_SCANNING)

    def handle_retreat_after_bombing_for_item_state(self, ai_current_tile):
        ai_base_log(f"[ITEM_AI_State] RETREAT_AFTER_BOMBING_FOR_ITEM to {self.chosen_retreat_spot_coords}")
        if self.current_movement_sub_path and ai_current_tile != self.current_movement_sub_path[-1]: return
        if not self.chosen_retreat_spot_coords: self.change_state(AI_STATE_ITEM_EVADING_DANGER); return
        if ai_current_tile == self.chosen_retreat_spot_coords or not self.current_movement_sub_path:
            if not self.is_bomb_still_active(self.last_bomb_placed_time): 
                self.ai_just_placed_bomb = False; wall_was_cleared = True
                original_target_item_sprite = self.current_target_item_info.get('sprite') if self.current_target_item_info else None
                original_target_item_coords = self.current_target_item_info.get('coords') if self.current_target_item_info else None
                if self.current_target_item_info and self.current_target_item_info.get('wall_to_bomb'): 
                    wall_node = self.current_target_item_info['wall_to_bomb']
                    current_wall_state = self._get_node_at_coords(wall_node.x, wall_node.y)
                    if current_wall_state and current_wall_state.is_destructible_box(): wall_was_cleared = False
                self.chosen_bombing_spot_coords = None; self.chosen_retreat_spot_coords = None
                if wall_was_cleared and original_target_item_sprite and original_target_item_sprite.alive():
                    path_to_item_now = self.bfs_find_direct_movement_path(ai_current_tile, original_target_item_coords, max_depth=self.bfs_max_depth_direct_item)
                    if path_to_item_now:
                        self.current_target_item_info = {'sprite': original_target_item_sprite, 'coords': original_target_item_coords, 'value': self._evaluate_item_value(original_target_item_sprite, len(path_to_item_now)-1),'path': path_to_item_now, 'type': 'direct','wall_to_bomb': None, 'bomb_spot': None, 'retreat_spot': None}
                        self.set_current_movement_sub_path(path_to_item_now); self.change_state(AI_STATE_ITEM_MOVING_TO_ACCESSIBLE_ITEM)
                    else: self._reset_item_specific_targets(); self.change_state(AI_STATE_ITEM_SCANNING)
                else: self._reset_item_specific_targets(); self.change_state(AI_STATE_ITEM_SCANNING)
        else: self.change_state(AI_STATE_ITEM_EVADING_DANGER)

    def handle_evading_danger_state(self, ai_current_tile):
        ai_base_log(f"[ITEM_AI_State] EVADING_DANGER at {ai_current_tile}")
        if not self.is_tile_dangerous(ai_current_tile[0], ai_current_tile[1], future_seconds=self.danger_avoidance_for_item_future / 2.0):
            self._reset_item_specific_targets(); self.change_state(AI_STATE_ITEM_SCANNING); return
        path_target_is_dangerous = False
        if self.current_movement_sub_path and len(self.current_movement_sub_path) > 0 :
            final_target_in_sub_path = self.current_movement_sub_path[-1]
            if self.is_tile_dangerous(final_target_in_sub_path[0], final_target_in_sub_path[1], future_seconds=0.1): path_target_is_dangerous = True
        if not self.current_movement_sub_path or \
            (self.current_movement_sub_path and ai_current_tile == self.current_movement_sub_path[-1]) or \
            path_target_is_dangerous:
            safe_options_coords = self.find_safe_tiles_nearby_for_retreat(ai_current_tile, ai_current_tile, 0, max_depth=7) 
            best_evasion_path_coords = []
            if safe_options_coords:
                for safe_spot_coord in safe_options_coords:
                    evasion_path_tuples = self.bfs_find_direct_movement_path(ai_current_tile, safe_spot_coord, max_depth=7)
                    if evasion_path_tuples and len(evasion_path_tuples) > 1: best_evasion_path_coords = evasion_path_tuples; break
            if best_evasion_path_coords: self.set_current_movement_sub_path(best_evasion_path_coords)
            else: self.current_movement_sub_path = []; self.ai_player.is_moving = False

    def _target_item_reached_or_gone(self):
        item_type_str = "Unknown"
        if self.current_target_item_info and self.current_target_item_info.get('sprite') and hasattr(self.current_target_item_info['sprite'], 'type'):
            item_type_str = self.current_target_item_info['sprite'].type
        ai_base_log(f"    Target item {item_type_str} reached or gone. Re-scanning.")
        self._reset_item_specific_targets()
        self.change_state(AI_STATE_ITEM_SCANNING)

    def debug_draw_path(self, surface):
        super().debug_draw_path(surface) 
        ai_tile_now = self._get_ai_current_tile()
        if not ai_tile_now or not hasattr(settings, 'TILE_SIZE'): return
        tile_size = settings.TILE_SIZE; half_tile = tile_size // 2
        astar_line_color_item = (150, 50, 200, 180); sub_path_color_item = (200, 100, 220, 200) 
        if self.astar_planned_path and self.astar_path_current_segment_index < len(self.astar_planned_path):
            astar_points = [(ai_tile_now[0] * tile_size + half_tile, ai_tile_now[1] * tile_size + half_tile)]
            for i in range(self.astar_path_current_segment_index, len(self.astar_planned_path)):
                node = self.astar_planned_path[i]; astar_points.append((node.x * tile_size + half_tile, node.y * tile_size + half_tile))
            if len(astar_points) > 1:
                for i in range(len(astar_points) - 1):
                    if i % 2 == 0: pygame.draw.aaline(surface, astar_line_color_item, astar_points[i], astar_points[i+1], True)
            if len(self.astar_planned_path) > self.astar_path_current_segment_index :
                next_astar_node = self.astar_planned_path[self.astar_path_current_segment_index]
                pygame.draw.circle(surface, astar_line_color_item, (next_astar_node.x *tile_size + half_tile, next_astar_node.y*tile_size+half_tile), tile_size//3, 2)
        if self.current_movement_sub_path and len(self.current_movement_sub_path) > 1 and self.current_movement_sub_path_index < len(self.current_movement_sub_path) -1 :
            sub_points = [(ai_tile_now[0] * tile_size + half_tile, ai_tile_now[1] * tile_size + half_tile)]
            for i in range(self.current_movement_sub_path_index + 1, len(self.current_movement_sub_path)):
                coords = self.current_movement_sub_path[i]; sub_points.append((coords[0] * tile_size + half_tile, coords[1] * tile_size + half_tile))
            if len(sub_points) > 1: pygame.draw.aalines(surface, sub_path_color_item, False, sub_points, True)
            next_sub_coords = self.current_movement_sub_path[self.current_movement_sub_path_index+1]
            pulse_factor = abs(pygame.time.get_ticks() % 1000 - 500) / 500
            radius = int(tile_size // 5 + pulse_factor * (tile_size//10))
            pygame.draw.circle(surface, sub_path_color_item, (next_sub_coords[0]*tile_size+half_tile, next_sub_coords[1]*tile_size+half_tile), radius,0)
        if self.current_target_item_info and self.current_target_item_info.get('sprite') and self.current_target_item_info['sprite'].alive():
            item_sprite = self.current_target_item_info['sprite']; item_coords = self.current_target_item_info['coords']
            item_value_score = self.current_target_item_info['value']; path_type_to_item = self.current_target_item_info['type']
            ix, iy = item_coords; center_ix, center_iy = ix * tile_size + half_tile, iy * tile_size + half_tile
            item_color = (255, 215, 0, 220) 
            if item_value_score < 50 : item_color = (173, 216, 230, 200)
            if item_value_score < self.item_value_threshold : item_color = (192, 192, 192, 180)
            pygame.draw.circle(surface, item_color, (center_ix, center_iy), tile_size // 2 - 1, 3)
            if self.current_state in [AI_STATE_ITEM_MOVING_TO_ACCESSIBLE_ITEM, AI_STATE_ITEM_MOVING_TO_BOMB_SPOT_FOR_ITEM, AI_STATE_ITEM_PLANNING_BOMB_FOR_ITEM] or \
               (self.astar_planned_path and len(self.astar_planned_path) > 0 and self.astar_planned_path[-1].x == ix and self.astar_planned_path[-1].y == iy): 
                pygame.draw.aaline(surface, item_color, (ai_tile_now[0]*tile_size+half_tile, ai_tile_now[1]*tile_size+half_tile), (center_ix, center_iy), True)
            if self.hud_font and hasattr(item_sprite, 'type'):
                try:
                    type_abbr = item_sprite.type[:4].upper(); val_text = f"{int(item_value_score)}"
                    info_str = f"{type_abbr}:{val_text}"; 
                    if path_type_to_item == 'via_bombing': info_str += "(B!)"
                    text_surf = self.hud_font.render(info_str, True, (0,0,0))
                    text_rect = text_surf.get_rect(center=(center_ix, center_iy - tile_size // 2 - 8)); surface.blit(text_surf, text_rect)
                except Exception: pass
        if self.current_target_item_info and self.current_target_item_info['type'] == 'via_bombing' and self.current_target_item_info.get('wall_to_bomb'):
            wall_node = self.current_target_item_info['wall_to_bomb']
            wall_rect = pygame.Rect(wall_node.x * tile_size, wall_node.y * tile_size, tile_size, tile_size)
            s_wall_item_clear = pygame.Surface((tile_size, tile_size), pygame.SRCALPHA); s_wall_item_clear.fill((255,165,0, 90)) 
            surface.blit(s_wall_item_clear, (wall_rect.x, wall_rect.y)); pygame.draw.rect(surface, (255,140,0,180), wall_rect, 2)
            bomb_spot_for_wall = self.current_target_item_info.get('bomb_spot')
            if bomb_spot_for_wall and (self.current_state == AI_STATE_ITEM_MOVING_TO_BOMB_SPOT_FOR_ITEM or self.current_state == AI_STATE_ITEM_BOMBING_FOR_ITEM):
                 bx, by = bomb_spot_for_wall; center_bx, center_by = bx * tile_size + half_tile, by * tile_size + half_tile
                 pygame.draw.circle(surface, (200, 0, 0, 150), (center_bx, center_by), tile_size // 4, 3)
                 pygame.draw.aaline(surface, (200,0,0,100), (center_bx, center_by), (wall_node.x*tile_size+half_tile, wall_node.y*tile_size+half_tile))
        if self.chosen_retreat_spot_coords and self.current_state == AI_STATE_ITEM_RETREAT_AFTER_BOMBING_FOR_ITEM:
            rx, ry = self.chosen_retreat_spot_coords
            rect_retreat_item_bomb = pygame.Rect(rx * tile_size + 1, ry * tile_size + 1, tile_size - 2, tile_size - 2)
            s_retreat_item_bomb = pygame.Surface((tile_size-2, tile_size-2), pygame.SRCALPHA); s_retreat_item_bomb.fill((144,238,144, 120)) 
            surface.blit(s_retreat_item_bomb, (rect_retreat_item_bomb.x, rect_retreat_item_bomb.y)); pygame.draw.rect(surface, (34,139,34, 180), rect_retreat_item_bomb, 2)