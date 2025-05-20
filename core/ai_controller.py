# oop-2025-proj-pycade/core/ai_controller.py

import pygame
import settings #
import random
from collections import deque

# --- AI 狀態定義 ---
AI_STATE_EVALUATE_SITUATION = "EVALUATE_SITUATION" 
AI_STATE_CRITICAL_ESCAPE = "CRITICAL_ESCAPE"       
AI_STATE_TACTICAL_RETREAT = "TACTICAL_RETREAT"    
AI_STATE_ENGAGE_TARGET = "ENGAGE_TARGET"          
AI_STATE_COLLECT_POWERUP = "COLLECT_POWERUP"      
AI_STATE_STRATEGIC_BOMBING_FOR_PATH = "STRATEGIC_BOMBING_FOR_PATH"
AI_STATE_AWAIT_OPPORTUNITY = "AWAIT_OPPORTUNITY"  
AI_STATE_PATROL = "PATROL"                        

DIRECTIONS = {"UP": (0, -1), "DOWN": (0, 1), "LEFT": (-1, 0), "RIGHT": (1, 0)}
POWERUP_VALUES = {
    settings.ITEM_TYPE_LIFE: 100, #
    settings.ITEM_TYPE_BOMB_CAPACITY: 85, #
    settings.ITEM_TYPE_BOMB_RANGE: 75, #
    settings.ITEM_TYPE_SCORE: 5, #
}

class AIController:
    def __init__(self, ai_player_sprite, game_instance):
        self.ai_player = ai_player_sprite
        self.game = game_instance
        self.current_state = AI_STATE_EVALUATE_SITUATION 
        self.state_start_time = pygame.time.get_ticks()
        self.current_path = []
        self.current_path_index = 0 # 指向AI當前在路徑中的格子 (已到達的)
        self.ai_decision_interval = settings.AI_MOVE_DELAY #
        self.last_decision_time = pygame.time.get_ticks() - self.ai_decision_interval - 1 # 確保第一次決策發生
        
        self.human_player_sprite = self.game.player1 #
        
        self.current_target_player_sprite = None
        self.current_target_item_sprite = None 
        self.current_escape_target_tile = None      
        self.current_action_target_tile = None 
        self.current_bombing_target_wall_sprite = None
        self.bombing_spot_for_wall = None

        self.last_bomb_placed_time = 0          
        self.ai_just_placed_bomb = False 
        self.player_unreachable_start_time = 0 
        self.stuck_in_patrol_start_time = 0 

        self.bfs_visited_visual = []
        self.aggression = 0.7  
        self.caution_level = 0.5 
        self.powerup_priority_factor = 0.8 
        # print(f"AIController V2.4 (Full) initialized for Player ID: {id(self.ai_player)}.") # DEBUG

    def change_state(self, new_state, **kwargs):
        # ！！！ 如果狀態未變且沒有新的路徑或特定目標傳入，則可能不需要重置state_start_time ！！！
        # ！！！ 但為了簡化，目前只要change_state被調用，就重置計時器和路徑相關 ！！！
        # if self.current_state == new_state and not kwargs.get('force_reset', False) and not kwargs.get('path'):
        #     # print(f"AI ({id(self.ai_player)}) staying in state: {self.current_state}") # DEBUG
        #     return

        # print(f"AI ({id(self.ai_player)}) state: {self.current_state} -> {new_state}") # DEBUG
        self.current_state = new_state
        self.state_start_time = pygame.time.get_ticks()
        
        # ！！！ 只有在 kwargs 中明確提供了 path 時才更新 path ！！！
        # ！！！ 否則，在 handle 方法中根據新狀態決定是否及如何計算路徑 ！！！
        if 'path' in kwargs:
            self.current_path = kwargs.get('path', [])
        elif new_state != self.current_state : # 如果是真正的狀態切換（非EVALUATE->EVALUATE），則清空舊路徑
            self.current_path = []

        self.current_path_index = 0 # 路徑改變，索引歸零
        
        self.current_target_player_sprite = kwargs.get('target_player_sprite', None)
        self.current_target_item_sprite = kwargs.get('target_item_sprite', None)
        self.current_escape_target_tile = kwargs.get('escape_target_tile', None)
        self.current_action_target_tile = kwargs.get('action_target_tile', None)
        self.current_bombing_target_wall_sprite = kwargs.get('target_wall_sprite', None)
        self.bombing_spot_for_wall = kwargs.get('bombing_spot', None)

        if new_state == AI_STATE_PATROL and not self.current_path:
            if self.stuck_in_patrol_start_time == 0: 
                 self.stuck_in_patrol_start_time = pygame.time.get_ticks()
        elif new_state != AI_STATE_PATROL: 
            self.stuck_in_patrol_start_time = 0

    def _get_ai_current_tile(self):
        return (self.ai_player.hitbox.centerx // settings.TILE_SIZE, #
                self.ai_player.hitbox.centery // settings.TILE_SIZE) #

    def _is_tile_in_hypothetical_blast(self, check_tile_x, check_tile_y,
                                       bomb_placed_at_x, bomb_placed_at_y,
                                       bomb_range):
        if check_tile_x == bomb_placed_at_x and check_tile_y == bomb_placed_at_y: return True
        if check_tile_y == bomb_placed_at_y and abs(check_tile_x - bomb_placed_at_x) <= bomb_range:
            blocked = False; step = 1 if check_tile_x > bomb_placed_at_x else -1
            for i in range(1, abs(check_tile_x - bomb_placed_at_x)):
                if self.game.map_manager.is_solid_wall_at(bomb_placed_at_x + i * step, bomb_placed_at_y): blocked = True; break #
            if not blocked: return True
        if check_tile_x == bomb_placed_at_x and abs(check_tile_y - bomb_placed_at_y) <= bomb_range:
            blocked = False; step = 1 if check_tile_y > bomb_placed_at_y else -1
            for i in range(1, abs(check_tile_y - bomb_placed_at_y)):
                if self.game.map_manager.is_solid_wall_at(bomb_placed_at_x, bomb_placed_at_y + i * step): blocked = True; break #
            if not blocked: return True
        return False
    
    def is_tile_dangerous(self, tile_x, tile_y, check_bombs=True, check_explosions=True, future_seconds=None):
        if future_seconds is None: 
            future_seconds = (settings.BOMB_TIMER / 1000.0) + (settings.EXPLOSION_DURATION / 1000.0) + 0.3 #
        target_px = tile_x * settings.TILE_SIZE + settings.TILE_SIZE // 2 #
        target_py = tile_y * settings.TILE_SIZE + settings.TILE_SIZE // 2 #
        if check_explosions:
            for exp in self.game.explosions_group: #
                if exp.rect.collidepoint(target_px, target_py): return True #
        if check_bombs:
            for bomb in self.game.bombs_group: #
                if bomb.exploded: continue #
                time_to_exp_ms = (bomb.spawn_time + bomb.timer) - pygame.time.get_ticks() #
                if 0 < time_to_exp_ms < future_seconds * 1000:
                    if self._is_tile_in_hypothetical_blast(tile_x, tile_y,
                                                           bomb.current_tile_x, bomb.current_tile_y, #
                                                           bomb.placed_by_player.bomb_range): return True #
        return False

    def can_place_bomb_safely_at(self, bomb_placement_x, bomb_placement_y):
        ai_bomb_range = self.ai_player.bomb_range #
        for dx_fs, dy_fs in DIRECTIONS.values():
            first_step_x, first_step_y = bomb_placement_x + dx_fs, bomb_placement_y + dy_fs
            if not self.game.map_manager.is_walkable(first_step_x, first_step_y): continue #
            if self._is_tile_in_hypothetical_blast(first_step_x, first_step_y, bomb_placement_x, bomb_placement_y, ai_bomb_range): continue
            if self.is_tile_dangerous(first_step_x, first_step_y, True, True, 0.3): continue
            
            q = deque([((first_step_x, first_step_y), 0)]); visited = {(first_step_x, first_step_y)}
            max_depth = ai_bomb_range + 3 
            while q:
                (cx, cy), depth = q.popleft()
                if depth > max_depth: continue
                safe_from_hypo = not self._is_tile_in_hypothetical_blast(cx, cy, bomb_placement_x, bomb_placement_y, ai_bomb_range)
                if safe_from_hypo:
                    safe_from_others = not self.is_tile_dangerous(cx, cy, True, True, (settings.BOMB_TIMER / 1000.0) + (settings.EXPLOSION_DURATION / 1000.0) + 0.3) #
                    if safe_from_others: return True 
                if depth < max_depth:
                    for dx_bfs, dy_bfs in DIRECTIONS.values():
                        nx, ny = cx + dx_bfs, cy + dy_bfs
                        if (nx,ny) not in visited and self.game.map_manager.is_walkable(nx,ny): #
                            if self._is_tile_in_hypothetical_blast(nx,ny,bomb_placement_x,bomb_placement_y,ai_bomb_range): continue
                            if self.is_tile_dangerous(nx,ny,True,True,0.3): continue
                            visited.add((nx,ny)); q.append(((nx,ny),depth+1))
        return False

    def bfs_find_path(self, start_tile, end_tile, avoid_danger_from_bombs=True, avoid_current_explosions=True, max_depth=float('inf')):
        if not end_tile: return [] 
        if start_tile == end_tile : return [start_tile] # 如果起點就是終點，路徑就是該點
        
        self.bfs_visited_visual = [] 
        queue = deque([(start_tile, [start_tile])]) 
        visited = {start_tile}
        map_mgr = self.game.map_manager
        
        while queue:
            (current_x, current_y), path_to_current = queue.popleft()
            self.bfs_visited_visual.append((current_x, current_y)) 

            if (current_x, current_y) == end_tile: return path_to_current
            
            if len(path_to_current) -1 >= max_depth: continue

            for _, (dx, dy) in DIRECTIONS.items(): 
                next_x, next_y = current_x + dx, current_y + dy
                if (next_x, next_y) not in visited:
                    if map_mgr.is_walkable(next_x, next_y): #
                        # ！！！路徑上的下一步是否危險，使用較短的 future_seconds ！！！
                        is_next_step_dangerous = self.is_tile_dangerous(next_x, next_y, 
                                                                      check_bombs=avoid_danger_from_bombs, 
                                                                      check_explosions=avoid_current_explosions,
                                                                      future_seconds=0.15) # 非常短的預測，確保路徑可行性
                        if is_next_step_dangerous: continue 
                        visited.add((next_x, next_y))
                        new_path = list(path_to_current); new_path.append((next_x, next_y))
                        queue.append(((next_x, next_y), new_path))
        return [] 

    def find_safe_tiles_nearby(self, start_tile, max_search_depth=5, avoid_specific_bomb_data=None):
        queue = deque([(start_tile, 0)]) 
        visited = {start_tile}      
        safe_tiles_found = []       
        map_mgr = self.game.map_manager 
        while queue:
            (current_x, current_y), depth = queue.popleft()
            if depth > max_search_depth: continue
            
            # ！！！ 判斷目標格子本身的安全性時，可以使用稍長的預測時間 ！！！
            is_safe_from_general_danger = not self.is_tile_dangerous(current_x, current_y, True, True, 0.3) 
            is_safe_from_specific_bomb = True
            if avoid_specific_bomb_data:
                bomb_tile, bomb_range = avoid_specific_bomb_data
                if self._is_tile_in_hypothetical_blast(current_x, current_y, bomb_tile[0], bomb_tile[1], bomb_range):
                    is_safe_from_specific_bomb = False
            
            if is_safe_from_general_danger and is_safe_from_specific_bomb:
                safe_tiles_found.append((current_x, current_y))
                if len(safe_tiles_found) >= 3 + depth: break 
            
            if depth < max_search_depth:
                for dx, dy in DIRECTIONS.values(): 
                    next_x, next_y = current_x + dx, current_y + dy
                    if (next_x, next_y) not in visited and map_mgr.is_walkable(next_x, next_y): #
                        path_next_safe = True
                        if avoid_specific_bomb_data:
                            bomb_tile, bomb_range = avoid_specific_bomb_data
                            if self._is_tile_in_hypothetical_blast(next_x, next_y, bomb_tile[0], bomb_tile[1], bomb_range):
                                path_next_safe = False
                        if self.is_tile_dangerous(next_x,next_y,True,True,0.15): # 路徑上的下一步用較短預測
                            path_next_safe = False
                        if not path_next_safe: continue
                        visited.add((next_x, next_y))
                        queue.append(((next_x, next_y), depth + 1))
        return safe_tiles_found

    def find_best_powerup(self):
        ai_tile = self._get_ai_current_tile()
        best_item = None
        best_path_to_item = None
        highest_weighted_value = -float('inf')

        sorted_items = sorted(list(self.game.items_group), key=lambda item: POWERUP_VALUES.get(item.type, 0), reverse=True) #
        
        # print(f"[AI DEBUG] find_best_powerup: Checking {len(sorted_items)} items.") # DEBUG
        for item_sprite in sorted_items:
            if not item_sprite.alive: continue #
            item_tile = (item_sprite.rect.centerx // settings.TILE_SIZE, item_sprite.rect.centery // settings.TILE_SIZE) #
            
            # print(f"[AI DEBUG] Checking item {item_sprite.type} at {item_tile}") # DEBUG
            path = self.bfs_find_path(ai_tile, item_tile, True, True) 
            # print(f"[AI DEBUG] Path to item {item_sprite.type}: {'Found' if path else 'None'}") # DEBUG

            if path:
                raw_value = POWERUP_VALUES.get(item_sprite.type, 0) * self.powerup_priority_factor #
                path_penalty = len(path) * 0.5 
                weighted_value = raw_value - path_penalty
                
                if weighted_value > highest_weighted_value:
                    # ！！！ 確保目標道具格子本身在短期內是安全的 ！！！
                    if not self.is_tile_dangerous(item_tile[0], item_tile[1], True, True, 0.2): # 短期檢查
                        highest_weighted_value = weighted_value
                        best_item = item_sprite
                        best_path_to_item = path
                        # ！！！找到一個道具和路徑後，就可以先返回，讓狀態機決定是否採用！！！
                        # ！！！而不是遍歷完所有道具才返回最佳的。這樣可以更快反應。！！！
                        # ！！！但如果想選“絕對最佳”，則需要遍歷完。目前邏輯是選加權最高的。！！！
        
        # print(f"[AI DEBUG] find_best_powerup result: Item: {best_item.type if best_item else 'None'}, Path: {'Yes' if best_path_to_item else 'No'}") # DEBUG
        if best_item and best_path_to_item:
            return best_item, best_path_to_item
        return None, None

    def find_strategic_wall_to_bomb(self, ultimate_target_tile=None):
        # (與之前版本類似，但確保路徑搜尋不被過度限制)
        ai_tile = self._get_ai_current_tile()
        candidate_walls_data = []
        if not self.game.map_manager.destructible_walls_group: return None #

        for wall in self.game.map_manager.destructible_walls_group: #
            if wall.is_destroyed: continue #
            wall_tile = (wall.tile_x, wall.tile_y) #
            for dx, dy in DIRECTIONS.values(): 
                bomb_spot_candidate = (wall_tile[0] - dx, wall_tile[1] - dy) 
                if not self.game.map_manager.is_walkable(bomb_spot_candidate[0], bomb_spot_candidate[1]): continue #
                if self.is_tile_dangerous(bomb_spot_candidate[0], bomb_spot_candidate[1], True, True, 0.5): continue
                
                path_to_bomb_spot = self.bfs_find_path(ai_tile, bomb_spot_candidate, True, True) 
                if path_to_bomb_spot:
                    if self.can_place_bomb_safely_at(bomb_spot_candidate[0], bomb_spot_candidate[1]):
                        value = len(path_to_bomb_spot) 
                        if ultimate_target_tile: 
                            vec_ai_to_wall = (wall_tile[0] - ai_tile[0], wall_tile[1] - ai_tile[1])
                            vec_wall_to_target = (ultimate_target_tile[0] - wall_tile[0], ultimate_target_tile[1] - wall_tile[1])
                            dot_product_direction = vec_ai_to_wall[0] * vec_wall_to_target[0] + vec_ai_to_wall[1] * vec_wall_to_target[1]
                            if dot_product_direction > 0 : value -= 5 
                            other_side_x, other_side_y = wall_tile[0] + dx, wall_tile[1] + dy
                            if not self.game.map_manager.is_walkable(other_side_x, other_side_y): #
                                if (self.game.map_manager.is_solid_wall_at(other_side_x, other_side_y) or \
                                     any(d_wall.tile_x == other_side_x and d_wall.tile_y == other_side_y for d_wall in self.game.map_manager.destructible_walls_group if not d_wall.is_destroyed and d_wall != wall)): #
                                     value += 10
                        candidate_walls_data.append({'wall_sprite': wall, 'path_to_bomb_spot': path_to_bomb_spot, 'bomb_spot': bomb_spot_candidate, 'value': value })
                        break 
        if not candidate_walls_data: return None
        candidate_walls_data.sort(key=lambda x: x['value'])
        return candidate_walls_data[0]

    # --- 主要決策與狀態處理 ---
    def update_state_machine(self):
        ai_current_tile = self._get_ai_current_tile()
        
        # ！！！ 1. 最高優先級：立即危險逃生 ！！！
        if self.is_tile_dangerous(ai_current_tile[0], ai_current_tile[1], True, True, future_seconds=0.6):
            # print(f"[AI FSM] DANGER at {ai_current_tile}! Entering CRITICAL_ESCAPE.") # DEBUG
            safe_spots = self.find_safe_tiles_nearby(ai_current_tile, max_search_depth=7)
            if safe_spots:
                escape_tile = random.choice(safe_spots)
                path = self.bfs_find_path(ai_current_tile, escape_tile, True, True)
                if path:
                    self.change_state(AI_STATE_CRITICAL_ESCAPE, escape_target_tile=escape_tile, path=path)
                    return
            # print(f"[AI FSM] CRITICAL_ESCAPE: No safe escape path! Defaulting to PATROL.") # DEBUG
            self.change_state(AI_STATE_PATROL) 
            return

        # ！！！ 2. 處理自己剛放的炸彈：必須戰術性撤退 ！！！
        if self.ai_just_placed_bomb:
            # print(f"[AI FSM] Just placed bomb. Entering TACTICAL_RETREAT.") # DEBUG
            self.change_state(AI_STATE_TACTICAL_RETREAT) # TACTICAL_RETREAT的handle會計算路徑
            return

        # --- 根據優先級進行其他決策 ---
        path_to_player = None
        player_tile_target = None
        can_reach_player = False

        if self.human_player_sprite and self.human_player_sprite.is_alive: #
            player_tile_target = (self.human_player_sprite.hitbox.centerx // settings.TILE_SIZE, self.human_player_sprite.hitbox.centery // settings.TILE_SIZE) #
            path_to_player = self.bfs_find_path(ai_current_tile, player_tile_target, True, True) 
            can_reach_player = bool(path_to_player) # path_to_player可能是空列表

        # 3. 攻擊玩家 (如果可達)
        if can_reach_player:
            self.player_unreachable_start_time = 0 
            self.change_state(AI_STATE_ENGAGE_TARGET, target_player_sprite=self.human_player_sprite, path=path_to_player)
            # print(f"[AI FSM] Player reachable at {player_tile_target}. Path len {len(path_to_player)}. Engaging.") # DEBUG
            return
        elif player_tile_target : 
            if self.player_unreachable_start_time == 0: self.player_unreachable_start_time = pygame.time.get_ticks()
        else: self.player_unreachable_start_time = 0

        # 4. 拾取道具
        powerup_data = self.find_best_powerup()
        if powerup_data:
            item_sprite, path_to_item = powerup_data
            if path_to_item: # ！！！確保 find_best_powerup 返回了有效的路徑！！！
                self.change_state(AI_STATE_COLLECT_POWERUP, target_item_sprite=item_sprite, path=path_to_item)
                # print(f"[AI FSM] Found powerup {item_sprite.type} at {item_sprite.rect.centerx//settings.TILE_SIZE, item_sprite.rect.centery//settings.TILE_SIZE}. Path len {len(path_to_item)}. Collecting.") # DEBUG
                return
            # else:
                # print(f"[AI FSM] Found powerup {item_sprite.type} but no path to it.") # DEBUG
        
        # 5. 策略性轟炸開路
        if self.ai_player.bombs_placed_count < self.ai_player.max_bombs: #
            should_try_bombing_wall = False
            current_time = pygame.time.get_ticks()
            if player_tile_target and not can_reach_player and self.player_unreachable_start_time > 0 and \
               (current_time - self.player_unreachable_start_time > 3000): # 嘗試3秒後
                should_try_bombing_wall = True
                # print(f"[AI FSM] Player unreachable for >3s. Considering bombing wall.") # DEBUG
            elif not player_tile_target and not powerup_data: 
                if self.current_state == AI_STATE_PATROL and not self.current_path and \
                   self.stuck_in_patrol_start_time > 0 and \
                   (current_time - self.stuck_in_patrol_start_time > 4000): # 卡在巡邏超過4秒
                    should_try_bombing_wall = True
                    # print(f"[AI FSM] Stuck in PATROL with no path for >4s. Considering bombing wall.") # DEBUG
            
            if should_try_bombing_wall:
                ultimate_target_for_bombing = player_tile_target if player_tile_target and not can_reach_player else None
                wall_data = self.find_strategic_wall_to_bomb(ultimate_target_tile=ultimate_target_for_bombing)
                if wall_data:
                    self.change_state(AI_STATE_STRATEGIC_BOMBING_FOR_PATH, 
                                      target_wall_sprite=wall_data['wall_sprite'], 
                                      bombing_spot=wall_data['bomb_spot'],
                                      path=wall_data['path_to_bomb_spot'])
                    # print(f"[AI FSM] Decided to break wall: {wall_data['wall_sprite'].tile_x},{wall_data['wall_sprite'].tile_y}") # DEBUG
                    return
        
        # 6. 等待時機 (通常是躲完自己炸彈後)
        time_since_ai_bomb = pygame.time.get_ticks() - self.last_bomb_placed_time
        if self.ai_just_placed_bomb and \
           not self.is_tile_dangerous(ai_current_tile[0], ai_current_tile[1], True, True, 0.1) and \
           (time_since_ai_bomb < settings.BOMB_TIMER + settings.EXPLOSION_DURATION + 300): # 稍長一點的等待
            # print(f"[AI FSM] Retreat from own bomb likely complete, awaiting explosion.") # DEBUG
            self.change_state(AI_STATE_AWAIT_OPPORTUNITY)
            return
        elif self.ai_just_placed_bomb and \
             (time_since_ai_bomb >= settings.BOMB_TIMER + settings.EXPLOSION_DURATION + 300): #
            # print(f"[AI FSM] Own bomb should have finished. Resetting flag.") # DEBUG
            self.ai_just_placed_bomb = False 
            # 繼續到下一個決策（很可能是 PATROL）

        # 7. 巡邏 (預設行為)
        # ！！！ 只有在 AI 當前不是 PATROL 或者 PATROL 狀態下沒有路徑時才強制切換/重新處理 PATROL ！！！
        if self.current_state != AI_STATE_PATROL or not self.current_path:
            # print(f"[AI FSM] No other actions. Defaulting/Re-evaluating PATROL.") # DEBUG
            self.change_state(AI_STATE_PATROL) # PATROL的handle會計算路徑
            # 注意：如果handle_patrol_state再次失敗，AI仍可能不動，但stuck_in_patrol_start_time會計時

    def perform_current_state_action(self):
        if not self.ai_player.is_alive: return #
        # print(f"[AI ACTION] State: {self.current_state}, Path len: {len(self.current_path)}") # DEBUG
        if self.current_state == AI_STATE_EVALUATE_SITUATION: pass # 主要由 update_state_machine 處理
        elif self.current_state == AI_STATE_CRITICAL_ESCAPE: self.handle_critical_escape_state()
        elif self.current_state == AI_STATE_TACTICAL_RETREAT: self.handle_tactical_retreat_state()
        elif self.current_state == AI_STATE_ENGAGE_TARGET: self.handle_engage_target_state()
        elif self.current_state == AI_STATE_COLLECT_POWERUP: self.handle_collect_powerup_state()
        elif self.current_state == AI_STATE_STRATEGIC_BOMBING_FOR_PATH: self.handle_strategic_bombing_for_path_state()
        elif self.current_state == AI_STATE_AWAIT_OPPORTUNITY: self.handle_await_opportunity_state()
        elif self.current_state == AI_STATE_PATROL: self.handle_patrol_state()
    
    def handle_critical_escape_state(self):
        ai_tile = self._get_ai_current_tile()
        # 路徑應該已在 update_state_machine 中設定
        if not self.current_path: 
            # 如果意外沒有路徑，嘗試最後的努力
            safe_spots = self.find_safe_tiles_nearby(ai_tile, max_search_depth=5)
            if safe_spots:
                escape_tile = random.choice(safe_spots)
                path = self.bfs_find_path(ai_tile, escape_tile, True, True)
                if path: self.change_state(AI_STATE_CRITICAL_ESCAPE, escape_target_tile=escape_tile, path=path)
                else: self.change_state(AI_STATE_PATROL) # 緊急情況下找不到路就先亂動一下
            else: self.change_state(AI_STATE_PATROL)
            return

        if self.current_escape_target_tile:
            if ai_tile == self.current_escape_target_tile and not self.is_tile_dangerous(ai_tile[0], ai_tile[1], True, True, 0.1):
                self.change_state(AI_STATE_EVALUATE_SITUATION)
            elif self.is_tile_dangerous(self.current_escape_target_tile[0], self.current_escape_target_tile[1], True, True, 0.3):
                self.current_path = []; self.change_state(AI_STATE_EVALUATE_SITUATION) 
        elif not self.current_path : 
            self.change_state(AI_STATE_EVALUATE_SITUATION)

    def handle_tactical_retreat_state(self):
        ai_tile = self._get_ai_current_tile()
        if self.ai_just_placed_bomb: 
            if not self.current_path: 
                my_bomb_sprite = None
                for bomb in self.game.bombs_group: #
                    if bomb.placed_by_player == self.ai_player and not bomb.exploded and \
                       (pygame.time.get_ticks() - bomb.spawn_time < 1000) : #
                        my_bomb_sprite = bomb; break
                if my_bomb_sprite:
                    bomb_data = ((my_bomb_sprite.current_tile_x, my_bomb_sprite.current_tile_y), self.ai_player.bomb_range) #
                    safe_spots = self.find_safe_tiles_nearby(ai_tile, max_search_depth=self.ai_player.bomb_range + 4, avoid_specific_bomb_data=bomb_data) #
                    if safe_spots:
                        retreat_target = random.choice(safe_spots) 
                        path = self.bfs_find_path(ai_tile, retreat_target, True, True)
                        # ！！！ 在 change_state 中設定 path ！！！
                        if path: self.change_state(AI_STATE_TACTICAL_RETREAT, escape_target_tile=retreat_target, path=path) 
                        else: self.change_state(AI_STATE_CRITICAL_ESCAPE) 
                    else: self.change_state(AI_STATE_CRITICAL_ESCAPE) 
                else: 
                    self.ai_just_placed_bomb = False 
                    self.change_state(AI_STATE_EVALUATE_SITUATION)
        
        if self.current_escape_target_tile and ai_tile == self.current_escape_target_tile and \
           not self.is_tile_dangerous(ai_tile[0], ai_tile[1], True, True, 0.1):
            if self.ai_just_placed_bomb : self.change_state(AI_STATE_AWAIT_OPPORTUNITY)
            else: self.change_state(AI_STATE_EVALUATE_SITUATION)
        elif not self.current_path and self.ai_just_placed_bomb : 
            self.change_state(AI_STATE_EVALUATE_SITUATION)

    def handle_engage_target_state(self):
        # (路徑已由 update_state_machine 設定)
        ai_tile = self._get_ai_current_tile()
        if not self.current_target_player_sprite or not self.current_target_player_sprite.is_alive: #
            self.change_state(AI_STATE_EVALUATE_SITUATION); return

        player_tile = (self.current_target_player_sprite.hitbox.centerx // settings.TILE_SIZE, self.current_target_player_sprite.hitbox.centery // settings.TILE_SIZE) #
        
        # 如果路徑失效或目標移動，update_state_machine 會重新評估並設定新路徑
        if not self.current_path: # 理論上進入此 handle 時應該有路徑
            # print("[AI ENGAGE] Entered handle_engage_target without a path. Re-evaluating.") # DEBUG
            self.change_state(AI_STATE_EVALUATE_SITUATION); return

        # 判斷是否放置炸彈
        steps_to_player = (len(self.current_path) - 1) - self.current_path_index
        is_at_current_path_pos = (ai_tile == self.current_path[self.current_path_index])
        
        # ！！！更精確的判斷：AI 是否在路徑的當前點，並且離玩家夠近可以放炸彈！！！
        if is_at_current_path_pos and steps_to_player <= (self.ai_player.bomb_range + 1): #
             if self.ai_player.bombs_placed_count < self.ai_player.max_bombs: #
                if self.can_place_bomb_safely_at(ai_tile[0], ai_tile[1]):
                    # print(f"[AI ENGAGE] Placing bomb at {ai_tile} to attack player at {player_tile}") # DEBUG
                    self.ai_player.place_bomb() #
                    # Player.place_bomb 應已設定 ai_just_placed_bomb 和 last_bomb_placed_time
                    self.change_state(AI_STATE_TACTICAL_RETREAT) 
                    return
        elif ai_tile == player_tile : # 如果AI剛好在玩家格子上
             if self.ai_player.bombs_placed_count < self.ai_player.max_bombs and self.can_place_bomb_safely_at(ai_tile[0], ai_tile[1]): #
                self.ai_player.place_bomb(); self.change_state(AI_STATE_TACTICAL_RETREAT); return #


    def handle_collect_powerup_state(self):
        # (路徑已由 update_state_machine 設定)
        ai_tile = self._get_ai_current_tile()
        if not self.current_target_item_sprite or not self.current_target_item_sprite.alive: #
            self.change_state(AI_STATE_EVALUATE_SITUATION); return
        
        item_tile = (self.current_target_item_sprite.rect.centerx // settings.TILE_SIZE, self.current_target_item_sprite.rect.centery // settings.TILE_SIZE) #
        if not self.current_path: # 如果沒有路徑 (可能 update_state_machine 中的 path 失效了)
            path = self.bfs_find_path(ai_tile, item_tile, True, True)
            if path: self.current_path = path; self.current_path_index = 0
            else: self.change_state(AI_STATE_EVALUATE_SITUATION); return # 還是找不到路
        
        if ai_tile == item_tile and not self.current_target_item_sprite.alive: #
             self.change_state(AI_STATE_EVALUATE_SITUATION)

    def handle_strategic_bombing_for_path_state(self):
        # (路徑已由 update_state_machine 設定)
        ai_tile = self._get_ai_current_tile()
        if not self.current_bombing_target_wall_sprite or \
           self.current_bombing_target_wall_sprite.is_destroyed or \
           not self.bombing_spot_for_wall: #
            self.change_state(AI_STATE_EVALUATE_SITUATION); return
        
        if not self.current_path : # 如果沒有路徑到轟炸點
            # print(f"[AI STRATEGIC_BOMBING] No path to bombing spot {self.bombing_spot_for_wall}. Re-evaluating.") # DEBUG
            self.change_state(AI_STATE_EVALUATE_SITUATION); return

        if ai_tile == self.bombing_spot_for_wall:
            if self.ai_player.bombs_placed_count < self.ai_player.max_bombs: #
                if self.can_place_bomb_safely_at(ai_tile[0], ai_tile[1]):
                    # print(f"[AI STRATEGIC_BOMBING] At bombing spot {ai_tile}. Placing bomb.") # DEBUG
                    self.ai_player.place_bomb() #
                    self.change_state(AI_STATE_TACTICAL_RETREAT); return
                else: 
                    # print(f"[AI STRATEGIC_BOMBING] At spot {ai_tile}, but now unsafe. Re-evaluating.") # DEBUG
                    self.change_state(AI_STATE_EVALUATE_SITUATION); return
            else: self.change_state(AI_STATE_EVALUATE_SITUATION); return

    def handle_await_opportunity_state(self):
        self.ai_player.set_ai_movement_intent(0,0) #
        if self.ai_just_placed_bomb and \
            (pygame.time.get_ticks() - self.last_bomb_placed_time > settings.BOMB_TIMER + settings.EXPLOSION_DURATION + 500): #
            self.ai_just_placed_bomb = False 
            self.change_state(AI_STATE_EVALUATE_SITUATION)
        elif not self.ai_just_placed_bomb and pygame.time.get_ticks() - self.state_start_time > 2000: 
            self.change_state(AI_STATE_EVALUATE_SITUATION)

    def handle_patrol_state(self):
        if not self.current_path: 
            ai_tile = self._get_ai_current_tile()
            possible_targets = []
            # ！！！巡邏點選擇邏輯，如果找不到遠的，就找近的！！！
            for distance_tier in [( (self.game.map_manager.tile_width + self.game.map_manager.tile_height) // 5, #
                                    (self.game.map_manager.tile_width + self.game.map_manager.tile_height) // 3), #
                                  (1, 2) # 近距離的後備選擇
                                 ]:
                min_dist, max_dist = distance_tier
                for r_idx in range(self.game.map_manager.tile_height): #
                    for c_idx in range(self.game.map_manager.tile_width): #
                        if self.game.map_manager.is_walkable(c_idx, r_idx) and \
                           not self.is_tile_dangerous(c_idx, r_idx, True, True, 1.0): #
                            distance = abs(c_idx - ai_tile[0]) + abs(r_idx - ai_tile[1])
                            if min_dist < distance < max_dist : 
                                possible_targets.append((c_idx, r_idx))
                if possible_targets: break # 找到一批就用這批

            if possible_targets:
                self.stuck_in_patrol_start_time = 0 
                target_patrol_tile = random.choice(possible_targets)
                path = self.bfs_find_path(ai_tile, target_patrol_tile, True, True)
                if path: 
                    # ！！！ 在 change_state 中設定路徑和目標！！！
                    self.change_state(AI_STATE_PATROL, action_target_tile=target_patrol_tile, path=path)
                else: # 找不到路徑去任何巡邏點
                    self.ai_player.set_ai_movement_intent(0,0) #
                    if self.stuck_in_patrol_start_time == 0: self.stuck_in_patrol_start_time = pygame.time.get_ticks()
            else: 
                self.ai_player.set_ai_movement_intent(0,0) #
                if self.stuck_in_patrol_start_time == 0: self.stuck_in_patrol_start_time = pygame.time.get_ticks()
        elif self.current_action_target_tile and self._get_ai_current_tile() == self.current_action_target_tile:
            self.change_state(AI_STATE_EVALUATE_SITUATION) # 到達巡邏點，重新評估

    def move_along_path(self):
        # ！！！ 重寫 move_along_path 以修正索引錯誤和路徑結束邏輯 ！！！
        if not self.current_path: # 路徑為空
            self.ai_player.set_ai_movement_intent(0, 0) #
            return True # 表示路徑已“處理”完畢 (空路徑)

        current_ai_tile_on_path = self.current_path[self.current_path_index]
        ai_current_map_tile = self._get_ai_current_tile()

        # 確保AI的邏輯位置與路徑索引同步 (如果因碰撞等原因偏離)
        if ai_current_map_tile != current_ai_tile_on_path:
            # 嘗試重新對齊到路徑上的最近點，或者重新規劃路徑
            # 簡化處理：如果嚴重偏離，則清除路徑，強制重新決策
            # print(f"[AI MOVE WARN] AI at {ai_current_map_tile} but path index points to {current_ai_tile_on_path}. Clearing path.") # DEBUG
            self.current_path = []
            self.current_path_index = 0
            self.ai_player.set_ai_movement_intent(0, 0) #
            return True # 路徑失效

        # 檢查是否已在路徑的最後一個點
        if self.current_path_index == len(self.current_path) - 1:
            # AI 已經在路徑的最終目標格子
            self.ai_player.set_ai_movement_intent(0, 0) #
            # print(f"[AI MOVE] Reached end of path: {current_ai_tile_on_path}") # DEBUG
            self.current_path = [] # 清空路徑
            self.current_path_index = 0
            return True # 路徑結束

        # 目標是路徑中的下一個點
        next_target_tile_x, next_target_tile_y = self.current_path[self.current_path_index + 1]
        
        current_ai_pixel_cx = self.ai_player.hitbox.centerx #
        current_ai_pixel_cy = self.ai_player.hitbox.centery #
        target_pixel_cx = next_target_tile_x * settings.TILE_SIZE + settings.TILE_SIZE // 2 #
        target_pixel_cy = next_target_tile_y * settings.TILE_SIZE + settings.TILE_SIZE // 2 #

        delta_x = target_pixel_cx - current_ai_pixel_cx
        delta_y = target_pixel_cy - current_ai_pixel_cy
        # ！！！到達閾值可以取得更小一點，讓 AI 更精確地停在格子中間 ！！！
        threshold = self.ai_player.speed * 0.6  # 例如，速度的60%
        if threshold < 2: threshold = 2 # 最小閾值

        if abs(delta_x) < threshold and abs(delta_y) < threshold: # 到達路徑中的下一個格子
            self.ai_player.hitbox.centerx = target_pixel_cx # 強制對齊
            self.ai_player.hitbox.centery = target_pixel_cy #
            self.ai_player.set_ai_movement_intent(0, 0) #
            self.current_path_index += 1 # 推進到路徑的下一個點
            
            # 再次檢查是否已是路徑的最後一點 (因為 index 剛增加)
            if self.current_path_index == len(self.current_path) - 1:
                # print(f"[AI MOVE] Reached final point of current path: {self.current_path[self.current_path_index]}") # DEBUG
                self.current_path = [] # 清空路徑
                self.current_path_index = 0
                return True # 路徑完全結束
            return False # 路徑片段完成，但還有後續
        else: # 尚未到達下一個格子，繼續移動
            dx_norm, dy_norm = 0, 0
            if abs(delta_x) > self.ai_player.speed * 0.1: # 只有在有足夠差異時才設定移動，避免抖動
                dx_norm = 1 if delta_x > 0 else -1
            if abs(delta_y) > self.ai_player.speed * 0.1: #
                dy_norm = 1 if delta_y > 0 else -1
            self.ai_player.set_ai_movement_intent(dx_norm, dy_norm) #
        return False # 仍在向路徑上的下一個點移動


    def update(self):
        current_time = pygame.time.get_ticks()
        if not self.ai_player.is_alive: #
            self.ai_player.set_ai_movement_intent(0,0) #
            if self.current_state != "DEAD": self.change_state("DEAD")
            return

        if current_time - self.last_decision_time >= self.ai_decision_interval:
            self.last_decision_time = current_time
            # print(f"--- AI Deciding (Time: {current_time}, Current State: {self.current_state}, Path Len: {len(self.current_path)}) ---") # DEBUG
            
            # ！！！決策總是從 EVALUATE_SITUATION 開始，由 update_state_machine 設定新狀態！！！
            # ！！！然後 perform_current_state_action 會執行新狀態的 handle 方法，通常是設定路徑！！！
            if self.current_state != AI_STATE_EVALUATE_SITUATION: # 避免不必要的 EVALUATE->EVALUATE 狀態打印
                self.change_state(AI_STATE_EVALUATE_SITUATION)
            
            self.update_state_machine() 
            self.perform_current_state_action() 
            # print(f"--- AI Decided (New State: {self.current_state}, Path Len: {len(self.current_path)}) ---") # DEBUG
        
        if self.current_path: 
            path_fully_completed = self.move_along_path()
            if path_fully_completed: 
                # print(f"AI Path Fully Completed for state {self.current_state}. Forcing re-evaluation.") # DEBUG
                # ！！！路徑走完，應立即重新評估，而不是等待下一個決策間隔！！！
                self.last_decision_time = pygame.time.get_ticks() - self.ai_decision_interval - 1 
                self.ai_player.set_ai_movement_intent(0,0) #
                self.change_state(AI_STATE_EVALUATE_SITUATION) 
        elif self.current_state not in [AI_STATE_AWAIT_OPPORTUNITY, AI_STATE_TACTICAL_RETREAT, AI_STATE_CRITICAL_ESCAPE]:
             self.ai_player.set_ai_movement_intent(0,0) #


    def debug_draw_path(self, surface):
        # (與之前版本相同)
        if self.current_path and len(self.current_path) > 1:
            path_points = [(t[0]*settings.TILE_SIZE + settings.TILE_SIZE//2, t[1]*settings.TILE_SIZE + settings.TILE_SIZE//2) for t in self.current_path] #
            try: pygame.draw.lines(surface, (255,0,255,180), False, path_points, 3)
            except TypeError: pygame.draw.lines(surface, (255,0,255), False, path_points, 3)
            if self.current_path_index + 1 < len(self.current_path):
                nx,ny = self.current_path[self.current_path_index+1]
                pygame.draw.circle(surface, (0,255,255,200), (nx*settings.TILE_SIZE+settings.TILE_SIZE//2, ny*settings.TILE_SIZE+settings.TILE_SIZE//2),7,0) #
        
        target_tile, color = None, settings.RED #
        if self.current_state == AI_STATE_CRITICAL_ESCAPE and self.current_escape_target_tile: target_tile, color = self.current_escape_target_tile, (255,0,0,200) 
        elif self.current_state == AI_STATE_TACTICAL_RETREAT and self.current_escape_target_tile: target_tile, color = self.current_escape_target_tile, (0,0,255,200) 
        elif self.current_state == AI_STATE_COLLECT_POWERUP and self.current_target_item_sprite and self.current_target_item_sprite.alive: #
            target_tile,color = (self.current_target_item_sprite.rect.centerx//settings.TILE_SIZE, self.current_target_item_sprite.rect.centery//settings.TILE_SIZE), (0,255,0,200) #
        elif self.current_state == AI_STATE_ENGAGE_TARGET and self.current_target_player_sprite and self.current_target_player_sprite.is_alive: #
            target_tile,color = (self.current_target_player_sprite.hitbox.centerx//settings.TILE_SIZE, self.current_target_player_sprite.hitbox.centery//settings.TILE_SIZE), (255,165,0,200) #
        elif self.current_state == AI_STATE_STRATEGIC_BOMBING_FOR_PATH and self.current_bombing_target_wall_sprite: #
            target_tile, color = (self.current_bombing_target_wall_sprite.tile_x, self.current_bombing_target_wall_sprite.tile_y), (128,0,128,200) #
            if self.bombing_spot_for_wall: pygame.draw.circle(surface, (200,200,0,150), (self.bombing_spot_for_wall[0]*settings.TILE_SIZE+settings.TILE_SIZE//2, self.bombing_spot_for_wall[1]*settings.TILE_SIZE+settings.TILE_SIZE//2), settings.TILE_SIZE//4, 2) #
        elif self.current_state == AI_STATE_PATROL and self.current_action_target_tile : target_tile, color = self.current_action_target_tile, (100,100,100,150) 
        
        if target_tile: 
            pygame.draw.circle(surface, color, (target_tile[0]*settings.TILE_SIZE+settings.TILE_SIZE//2, target_tile[1]*settings.TILE_SIZE+settings.TILE_SIZE//2), settings.TILE_SIZE//3+2,3) #