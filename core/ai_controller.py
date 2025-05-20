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
    settings.ITEM_TYPE_BOMB_CAPACITY: 85, # 略微提高炸彈容量價值
    settings.ITEM_TYPE_BOMB_RANGE: 75, # 略微提高炸彈範圍價值
    settings.ITEM_TYPE_SCORE: 5, # 分數道具價值最低
}

class AIController:
    def __init__(self, ai_player_sprite, game_instance):
        self.ai_player = ai_player_sprite
        self.game = game_instance
        self.current_state = AI_STATE_EVALUATE_SITUATION 
        self.state_start_time = pygame.time.get_ticks()
        self.current_path = []
        self.current_path_index = 0
        self.ai_decision_interval = settings.AI_MOVE_DELAY #
        self.last_decision_time = 0 
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
        self.stuck_in_patrol_time = 0 # 新增：用於檢測是否卡在巡邏太久

        self.bfs_visited_visual = []
        self.aggression = 0.7  
        self.caution_level = 0.5 
        self.powerup_priority_factor = 0.8 
        # print(f"AIController V2.2 (Full) initialized for Player ID: {id(self.ai_player)}.")

    def change_state(self, new_state, **kwargs):
        # ！！！注意：此函數用於改變AI狀態，並可選擇性傳遞路徑和其他目標信息！！！
        if self.current_state == new_state and not kwargs: 
            return

        # print(f"AI ({id(self.ai_player)}) state: {self.current_state} -> {new_state}") # DEBUG
        self.current_state = new_state
        self.state_start_time = pygame.time.get_ticks()
        self.current_path = kwargs.get('path', []) 
        self.current_path_index = 0
        
        self.current_target_player_sprite = kwargs.get('target_player_sprite', None)
        self.current_target_item_sprite = kwargs.get('target_item_sprite', None)
        self.current_escape_target_tile = kwargs.get('escape_target_tile', None)
        self.current_action_target_tile = kwargs.get('action_target_tile', None) # 用於 PATROL 等
        self.current_bombing_target_wall_sprite = kwargs.get('target_wall_sprite', None)
        self.bombing_spot_for_wall = kwargs.get('bombing_spot', None)

        # 當離開 PATROL 狀態時，重置 stuck_in_patrol_time
        if new_state != AI_STATE_PATROL:
            self.stuck_in_patrol_time = 0

    def _get_ai_current_tile(self):
        return (self.ai_player.hitbox.centerx // settings.TILE_SIZE, #
                self.ai_player.hitbox.centery // settings.TILE_SIZE) #

    def _is_tile_in_hypothetical_blast(self, check_tile_x, check_tile_y,
                                       bomb_placed_at_x, bomb_placed_at_y,
                                       bomb_range):
        # (與之前版本相同)
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
        # (與之前版本相同)
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
        # (與之前版本相同)
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
        if not end_tile or start_tile == end_tile : return [] if start_tile != end_tile else [start_tile] 
        self.bfs_visited_visual = [] 
        queue = deque([(start_tile, [start_tile])]) 
        visited = {start_tile}
        map_mgr = self.game.map_manager
        path_len_counter = 0
        while queue:
            (current_x, current_y), path_to_current = queue.popleft()
            self.bfs_visited_visual.append((current_x, current_y)) 
            if (current_x, current_y) == end_tile: return path_to_current
            
            path_len_counter = len(path_to_current) # path_to_current 包含起點
            if path_len_counter > max_depth : continue # 如果路徑長度已超過max_depth (步數是len-1)
            
            for _, (dx, dy) in DIRECTIONS.items(): 
                next_x, next_y = current_x + dx, current_y + dy
                if (next_x, next_y) not in visited:
                    if map_mgr.is_walkable(next_x, next_y): #
                        is_next_step_dangerous = self.is_tile_dangerous(next_x, next_y, 
                                                                      check_bombs=avoid_danger_from_bombs, 
                                                                      check_explosions=avoid_current_explosions,
                                                                      future_seconds=0.3) 
                        if is_next_step_dangerous: continue 
                        visited.add((next_x, next_y))
                        new_path = list(path_to_current); new_path.append((next_x, next_y))
                        queue.append(((next_x, next_y), new_path))
        return [] 

    def find_safe_tiles_nearby(self, start_tile, max_search_depth=5, avoid_specific_bomb_data=None):
        # avoid_specific_bomb_data = ((bomb_x, bomb_y), bomb_range)
        queue = deque([(start_tile, 0)]) 
        visited = {start_tile}      
        safe_tiles_found = []       
        map_mgr = self.game.map_manager 
        while queue:
            (current_x, current_y), depth = queue.popleft()
            if depth > max_search_depth: continue
            
            is_safe_from_general_danger = not self.is_tile_dangerous(current_x, current_y, True, True, 0.5)
            is_safe_from_specific_bomb = True
            if avoid_specific_bomb_data:
                bomb_tile, bomb_range = avoid_specific_bomb_data
                if self._is_tile_in_hypothetical_blast(current_x, current_y, bomb_tile[0], bomb_tile[1], bomb_range):
                    is_safe_from_specific_bomb = False
            
            if is_safe_from_general_danger and is_safe_from_specific_bomb:
                safe_tiles_found.append((current_x, current_y))
                if len(safe_tiles_found) >= 3: break # 找到3個就差不多了
            
            if depth < max_search_depth:
                for dx, dy in DIRECTIONS.values(): 
                    next_x, next_y = current_x + dx, current_y + dy
                    if (next_x, next_y) not in visited and map_mgr.is_walkable(next_x, next_y): #
                        path_next_safe = True
                        if avoid_specific_bomb_data:
                            bomb_tile, bomb_range = avoid_specific_bomb_data
                            if self._is_tile_in_hypothetical_blast(next_x, next_y, bomb_tile[0], bomb_tile[1], bomb_range):
                                path_next_safe = False
                        if self.is_tile_dangerous(next_x,next_y,True,True,0.3): 
                            path_next_safe = False
                        if not path_next_safe: continue
                        visited.add((next_x, next_y))
                        queue.append(((next_x, next_y), depth + 1))
        return safe_tiles_found

    def find_best_powerup(self):
        ai_tile = self._get_ai_current_tile()
        best_item_data = {'sprite': None, 'path': None, 'weighted_value': -float('inf')} # 初始值設為負無窮

        # 對道具進行優先級排序
        sorted_items = sorted(list(self.game.items_group), key=lambda item: POWERUP_VALUES.get(item.type, 0), reverse=True) #
        for item_sprite in sorted_items:
            if not item_sprite.alive(): continue #
            item_tile = (item_sprite.rect.centerx // settings.TILE_SIZE, item_sprite.rect.centery // settings.TILE_SIZE) #
            path = self.bfs_find_path(ai_tile, item_tile, True, True, max_depth=25) # 稍微放寬搜索道具的深度
            if path:
                raw_value = POWERUP_VALUES.get(item_sprite.type, 0) * self.powerup_priority_factor #
                # 懲罰路徑長度，路徑越長，加權價值越低
                path_penalty = len(path) * 0.5 
                weighted_value = raw_value - path_penalty
                
                if weighted_value > best_item_data['weighted_value']:
                    if not self.is_tile_dangerous(item_tile[0], item_tile[1], True, True, 0.2):
                        best_item_data['sprite'] = item_sprite
                        best_item_data['path'] = path
                        best_item_data['weighted_value'] = weighted_value
        
        if best_item_data['sprite']:
            return best_item_data['sprite'], best_item_data['path']
        return None, None

    def find_strategic_wall_to_bomb(self, ultimate_target_tile=None):
        # (與之前版本類似，確保路徑搜尋不被過度限制)
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
                        if ultimate_target_tile: # 如果有最終目標，評估是否朝向該目標
                            # 簡化評估：如果牆在 AI 和 ultimate_target_tile 的大致方向上
                            vec_ai_to_bomb_spot = (bomb_spot_candidate[0] - ai_tile[0], bomb_spot_candidate[1] - ai_tile[1])
                            vec_wall_to_target = (ultimate_target_tile[0] - wall_tile[0], ultimate_target_tile[1] - wall_tile[1])
                            dot_product_direction = vec_ai_to_bomb_spot[0] * vec_wall_to_target[0] + vec_ai_to_bomb_spot[1] * vec_wall_to_target[1]
                            if dot_product_direction > 0 : # 向量方向大致相同
                                value -= 5 # 獎勵朝向目標的牆
                        
                        candidate_walls_data.append({'wall_sprite': wall, 'path_to_bomb_spot': path_to_bomb_spot, 'bomb_spot': bomb_spot_candidate, 'value': value })
                        break 
        if not candidate_walls_data: return None
        candidate_walls_data.sort(key=lambda x: x['value'])
        # print(f"[AI DEBUG] Best wall to bomb: {candidate_walls_data[0]['wall_sprite'].tile_x},{candidate_walls_data[0]['wall_sprite'].tile_y} at spot {candidate_walls_data[0]['bomb_spot']} with value {candidate_walls_data[0]['value']}")
        return candidate_walls_data[0]

    # --- 主要決策與狀態處理 ---
    def update_state_machine(self):
        ai_current_tile = self._get_ai_current_tile()
        
        # ！！！ 高優先級檢查：立即危險 ！！！
        if self.is_tile_dangerous(ai_current_tile[0], ai_current_tile[1], True, True, future_seconds=0.7):
            safe_spots = self.find_safe_tiles_nearby(ai_current_tile, max_search_depth=7)
            if safe_spots:
                escape_tile = random.choice(safe_spots) # ！！！可以優化逃跑點的選擇邏輯！！！
                path = self.bfs_find_path(ai_current_tile, escape_tile, True, True)
                if path:
                    self.change_state(AI_STATE_CRITICAL_ESCAPE, escape_target_tile=escape_tile, path=path)
                    return
            # print(f"[AI FSM] CRITICAL_ESCAPE: No safe escape found! Trying PATROL as last resort.")
            self.change_state(AI_STATE_PATROL) # 無處可逃，嘗試巡邏（可能只是原地不動或小範圍移動）
            return

        # ！！！ 處理自己剛放的炸彈：必須撤退 ！！！
        if self.ai_just_placed_bomb:
            self.change_state(AI_STATE_TACTICAL_RETREAT)
            return

        # --- 根據優先級進行其他決策 ---
        # 1. 攻擊玩家
        path_to_player = None
        player_tile_target = None
        if self.human_player_sprite and self.human_player_sprite.is_alive: #
            player_tile_target = (self.human_player_sprite.hitbox.centerx // settings.TILE_SIZE, self.human_player_sprite.hitbox.centery // settings.TILE_SIZE) #
            path_to_player = self.bfs_find_path(ai_current_tile, player_tile_target, True, True) 
            if path_to_player:
                self.player_unreachable_start_time = 0 # 重置無法到達計時器
                self.change_state(AI_STATE_ENGAGE_TARGET, target_player_sprite=self.human_player_sprite, path=path_to_player)
                return
            else: # 玩家無法直接到達
                if self.player_unreachable_start_time == 0: self.player_unreachable_start_time = pygame.time.get_ticks()
        else: self.player_unreachable_start_time = 0

        # 2. 拾取道具
        powerup_data = self.find_best_powerup()
        if powerup_data:
            item_sprite, path_to_item = powerup_data
            self.change_state(AI_STATE_COLLECT_POWERUP, target_item_sprite=item_sprite, path=path_to_item)
            return
        
        # 3. 策略性轟炸開路
        if self.ai_player.bombs_placed_count < self.ai_player.max_bombs: #
            # 條件：玩家存在但無法到達，且超過一定時間；或者沒有玩家目標也沒有道具，且AI可能被困
            should_try_bombing_wall = False
            if player_tile_target and not path_to_player and (pygame.time.get_ticks() - self.player_unreachable_start_time > 3500): # 3.5秒無法到達玩家
                should_try_bombing_wall = True
            elif not player_tile_target and not powerup_data: # 無玩家目標也無道具
                 if self.current_state == AI_STATE_PATROL and not self.current_path and \
                    (pygame.time.get_ticks() - self.stuck_in_patrol_time > 4000): # 卡在巡邏且無路徑超過4秒
                     should_try_bombing_wall = True
            
            if should_try_bombing_wall:
                # print(f"[AI FSM] Considering STRATEGIC_BOMBING. Player unreachable: {not path_to_player}, No powerup: {not powerup_data}")
                wall_data = self.find_strategic_wall_to_bomb(ultimate_target_tile=player_tile_target)
                if wall_data:
                    self.change_state(AI_STATE_STRATEGIC_BOMBING_FOR_PATH, 
                                      target_wall_sprite=wall_data['wall_sprite'], 
                                      bombing_spot=wall_data['bomb_spot'],
                                      path=wall_data['path_to_bomb_spot'])
                    return
        
        # 4. 等待時機 (通常是躲完自己炸彈後)
        # 這個狀態的進入主要由 TACTICAL_RETREAT 的 handle 方法在完成躲避後觸發
        # 此處保留一個保險，如果 ai_just_placed_bomb 為 True 且當前安全，則進入等待
        if self.ai_just_placed_bomb and not self.is_tile_dangerous(ai_current_tile[0], ai_current_tile[1], True, True, 0.2):
             if pygame.time.get_ticks() - self.last_bomb_placed_time < settings.BOMB_TIMER + settings.EXPLOSION_DURATION + 100: #
                self.change_state(AI_STATE_AWAIT_OPPORTUNITY)
                return
        
        # 5. 巡邏 (預設行為)
        if self.current_state != AI_STATE_PATROL:
            self.change_state(AI_STATE_PATROL)
            if self.stuck_in_patrol_time == 0 : self.stuck_in_patrol_time = pygame.time.get_ticks()
        elif not self.current_path: # 如果已在巡邏但沒有路徑，也重置計時器
            if self.stuck_in_patrol_time == 0 : self.stuck_in_patrol_time = pygame.time.get_ticks()


    def perform_current_state_action(self):
        if not self.ai_player.is_alive: return #
        # print(f"[AI ACTION] State: {self.current_state}, Path len: {len(self.current_path)}") # DEBUG
        if self.current_state == AI_STATE_EVALUATE_SITUATION: pass
        elif self.current_state == AI_STATE_CRITICAL_ESCAPE: self.handle_critical_escape_state()
        elif self.current_state == AI_STATE_TACTICAL_RETREAT: self.handle_tactical_retreat_state()
        elif self.current_state == AI_STATE_ENGAGE_TARGET: self.handle_engage_target_state()
        elif self.current_state == AI_STATE_COLLECT_POWERUP: self.handle_collect_powerup_state()
        elif self.current_state == AI_STATE_STRATEGIC_BOMBING_FOR_PATH: self.handle_strategic_bombing_for_path_state()
        elif self.current_state == AI_STATE_AWAIT_OPPORTUNITY: self.handle_await_opportunity_state()
        elif self.current_state == AI_STATE_PATROL: self.handle_patrol_state()
    
    def handle_critical_escape_state(self):
        ai_tile = self._get_ai_current_tile()
        if not self.current_path: # 如果進入此狀態但 change_state 時未提供路徑
            safe_spots = self.find_safe_tiles_nearby(ai_tile, max_search_depth=7)
            if safe_spots:
                self.current_escape_target_tile = random.choice(safe_spots)
                path = self.bfs_find_path(ai_tile, self.current_escape_target_tile, True, True)
                if path: self.current_path = path; self.current_path_index = 0
                else: self.change_state(AI_STATE_PATROL) # 無路可逃，嘗試巡邏
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
        if self.ai_just_placed_bomb: # 確保是為了躲避自己剛放的炸彈
            if not self.current_path: 
                my_bomb_sprite = None
                # 找到AI剛放置的炸彈 (通常只有一顆)
                for bomb in self.game.bombs_group: #
                    if bomb.placed_by_player == self.ai_player and not bomb.exploded and \
                       (pygame.time.get_ticks() - bomb.spawn_time < 1000) : # 1秒內認為是剛放的
                        my_bomb_sprite = bomb; break
                
                if my_bomb_sprite:
                    # print(f"[AI TACTICAL] Retreating from own bomb at {my_bomb_sprite.current_tile_x, my_bomb_sprite.current_tile_y}") #
                    bomb_data = ((my_bomb_sprite.current_tile_x, my_bomb_sprite.current_tile_y), self.ai_player.bomb_range) #
                    safe_spots = self.find_safe_tiles_nearby(ai_tile, max_search_depth=self.ai_player.bomb_range + 4, avoid_specific_bomb_data=bomb_data) #
                    if safe_spots:
                        retreat_target = random.choice(safe_spots) # ！！！可以優化撤退點選擇！！！
                        path = self.bfs_find_path(ai_tile, retreat_target, True, True)
                        if path: self.current_path = path; self.current_path_index = 0; self.current_escape_target_tile = retreat_target
                        else: self.change_state(AI_STATE_CRITICAL_ESCAPE) 
                    else: self.change_state(AI_STATE_CRITICAL_ESCAPE) 
                else: # 找不到剛放的炸彈，異常情況
                    # print("[AI TACTICAL] ERROR: ai_just_placed_bomb is True, but couldn't find the bomb.")
                    self.ai_just_placed_bomb = False # 重置標記
                    self.change_state(AI_STATE_EVALUATE_SITUATION)
        
        # 檢查是否已到達撤退目標且安全
        if self.current_escape_target_tile and ai_tile == self.current_escape_target_tile and \
           not self.is_tile_dangerous(ai_tile[0], ai_tile[1], True, True, 0.1):
            if self.ai_just_placed_bomb : 
                self.change_state(AI_STATE_AWAIT_OPPORTUNITY) # 躲完自己的炸彈，進入等待
            else: # 躲完別人的炸彈（如果未來加入此邏輯），重新評估
                self.change_state(AI_STATE_EVALUATE_SITUATION)
        elif not self.current_path and self.ai_just_placed_bomb : # 如果沒路徑了但還是躲自己炸彈的狀態
            self.change_state(AI_STATE_EVALUATE_SITUATION) # 避免卡住

    def handle_engage_target_state(self):
        # (與之前版本類似，但確保路徑更新和放置炸彈邏輯)
        ai_tile = self._get_ai_current_tile()
        if not self.current_target_player_sprite or not self.current_target_player_sprite.is_alive: #
            self.change_state(AI_STATE_EVALUATE_SITUATION); return

        player_tile = (self.current_target_player_sprite.hitbox.centerx // settings.TILE_SIZE, self.current_target_player_sprite.hitbox.centery // settings.TILE_SIZE) #
        
        # 如果沒有路徑，或者路徑的終點不是當前玩家位置 (玩家移動了)，則重新計算路徑
        if not self.current_path or (self.current_path and self.current_path[-1] != player_tile):
            path = self.bfs_find_path(ai_tile, player_tile, True, True)
            if path: self.current_path = path; self.current_path_index = 0
            else: self.player_unreachable_start_time = pygame.time.get_ticks(); self.change_state(AI_STATE_EVALUATE_SITUATION); return
        
        # 判斷是否放置炸彈
        if self.current_path : # 必須有路徑才能判斷距離
            steps_to_player = (len(self.current_path) - 1) - self.current_path_index
            # 確保AI在路徑的當前點，或者非常接近下一步的目標點
            is_at_current_path_pos = (ai_tile == self.current_path[self.current_path_index])
            
            if is_at_current_path_pos and steps_to_player <= (self.ai_player.bomb_range + 1): #
                 if self.ai_player.bombs_placed_count < self.ai_player.max_bombs: #
                    if self.can_place_bomb_safely_at(ai_tile[0], ai_tile[1]):
                        # print(f"[AI ENGAGE] Placing bomb at {ai_tile} to attack player at {player_tile}")
                        self.ai_player.place_bomb() # Player.place_bomb 會處理 is_ai controller feedback
                        # ai_just_placed_bomb 和 last_bomb_placed_time 已在Player中設定
                        self.change_state(AI_STATE_TACTICAL_RETREAT) 
                        return
        elif ai_tile == player_tile : # AI已經和玩家重疊 (幾乎不可能，但作為保險)
             if self.ai_player.bombs_placed_count < self.ai_player.max_bombs and self.can_place_bomb_safely_at(ai_tile[0], ai_tile[1]): #
                self.ai_player.place_bomb(); self.change_state(AI_STATE_TACTICAL_RETREAT); return #


    def handle_collect_powerup_state(self):
        # (與之前版本類似)
        ai_tile = self._get_ai_current_tile()
        if not self.current_target_item_sprite or not self.current_target_item_sprite.alive(): #
            self.change_state(AI_STATE_EVALUATE_SITUATION); return
        item_tile = (self.current_target_item_sprite.rect.centerx // settings.TILE_SIZE, self.current_target_item_sprite.rect.centery // settings.TILE_SIZE) #
        if not self.current_path or (self.current_path and self.current_path[-1] != item_tile):
            path = self.bfs_find_path(ai_tile, item_tile, True, True)
            if path: self.current_path = path; self.current_path_index = 0
            else: self.change_state(AI_STATE_EVALUATE_SITUATION); return
        if ai_tile == item_tile and not self.current_target_item_sprite.alive(): #
             self.change_state(AI_STATE_EVALUATE_SITUATION)

    def handle_strategic_bombing_for_path_state(self):
        # (與之前版本類似)
        ai_tile = self._get_ai_current_tile()
        if not self.current_bombing_target_wall_sprite or \
           self.current_bombing_target_wall_sprite.is_destroyed or \
           not self.bombing_spot_for_wall: #
            self.change_state(AI_STATE_EVALUATE_SITUATION); return
        
        # 如果沒有路徑去轟炸點，或者路徑目標不是轟炸點，重新規劃
        if not self.current_path or (self.current_path and self.current_path[-1] != self.bombing_spot_for_wall):
            path_to_spot = self.bfs_find_path(ai_tile, self.bombing_spot_for_wall, True, True)
            if path_to_spot : self.current_path = path_to_spot; self.current_path_index = 0
            else : self.change_state(AI_STATE_EVALUATE_SITUATION); return # 到不了轟炸點

        if ai_tile == self.bombing_spot_for_wall:
            if self.ai_player.bombs_placed_count < self.ai_player.max_bombs: #
                if self.can_place_bomb_safely_at(ai_tile[0], ai_tile[1]):
                    self.ai_player.place_bomb() #
                    self.change_state(AI_STATE_TACTICAL_RETREAT); return
                else: self.change_state(AI_STATE_EVALUATE_SITUATION); return
            else: self.change_state(AI_STATE_EVALUATE_SITUATION); return
        # 移動由 move_along_path 處理


    def handle_await_opportunity_state(self):
        self.ai_player.set_ai_movement_intent(0,0) #
        if self.ai_just_placed_bomb and \
            (pygame.time.get_ticks() - self.last_bomb_placed_time > settings.BOMB_TIMER + settings.EXPLOSION_DURATION + 500): # 等待時間足夠長
            self.ai_just_placed_bomb = False # 重置標記，表示炸彈已處理完畢
            self.change_state(AI_STATE_EVALUATE_SITUATION)
        elif not self.ai_just_placed_bomb and pygame.time.get_ticks() - self.state_start_time > 2000: 
            self.change_state(AI_STATE_EVALUATE_SITUATION)

    def handle_patrol_state(self):
        if not self.current_path: 
            ai_tile = self._get_ai_current_tile()
            possible_targets = []
            for r_idx in range(self.game.map_manager.tile_height): #
                for c_idx in range(self.game.map_manager.tile_width): #
                    if self.game.map_manager.is_walkable(c_idx, r_idx) and \
                       not self.is_tile_dangerous(c_idx, r_idx, True, True, 1.0): #
                        distance = abs(c_idx - ai_tile[0]) + abs(r_idx - ai_tile[1])
                        if distance > 2 and distance < self.game.map_manager.tile_width / 2 : # 選擇不太近但也不過於遠的點
                            possible_targets.append((c_idx, r_idx))
            if possible_targets:
                target_patrol_tile = random.choice(possible_targets)
                path = self.bfs_find_path(ai_tile, target_patrol_tile, True, True) # 巡邏路徑不設限深度
                if path: 
                    self.change_state(AI_STATE_PATROL, action_target_tile=target_patrol_tile, path=path)
                else: self.ai_player.set_ai_movement_intent(0,0) #
            else: 
                self.ai_player.set_ai_movement_intent(0,0) #
                if self.stuck_in_patrol_time == 0: self.stuck_in_patrol_time = pygame.time.get_ticks() # 開始計時卡住
        elif self.current_action_target_tile and self._get_ai_current_tile() == self.current_action_target_tile:
            self.change_state(AI_STATE_EVALUATE_SITUATION) # 到達巡邏點，重新評估

    def move_along_path(self):
        # (與之前版本相同)
        if not self.current_path or self.current_path_index >= len(self.current_path):
            self.current_path = []; self.current_path_index = 0
            self.ai_player.set_ai_movement_intent(0, 0); return True 

        # 檢查是否已經在路徑的最後一個點上 (current_path_index 指向當前AI所在的格子)
        if self.current_path_index == len(self.current_path) - 1:
            ai_tile = self._get_ai_current_tile()
            target_tile = self.current_path[-1]
            # 確保真的到達了
            current_ai_pixel_cx = self.ai_player.hitbox.centerx #
            current_ai_pixel_cy = self.ai_player.hitbox.centery #
            target_pixel_cx = target_tile[0] * settings.TILE_SIZE + settings.TILE_SIZE // 2 #
            target_pixel_cy = target_tile[1] * settings.TILE_SIZE + settings.TILE_SIZE // 2 #
            threshold = self.ai_player.speed #
            if abs(target_pixel_cx - current_ai_pixel_cx) < threshold and abs(target_pixel_cy - current_ai_pixel_cy) < threshold:
                 self.ai_player.hitbox.center = (target_pixel_cx, target_pixel_cy) #
                 self.current_path = []; self.current_path_index = 0
                 self.ai_player.set_ai_movement_intent(0, 0); return True 
            # else: still moving towards the last point
        
        next_target_tile_x, next_target_tile_y = self.current_path[self.current_path_index + 1]
        current_ai_pixel_cx = self.ai_player.hitbox.centerx #
        current_ai_pixel_cy = self.ai_player.hitbox.centery #
        target_pixel_cx = next_target_tile_x * settings.TILE_SIZE + settings.TILE_SIZE // 2 #
        target_pixel_cy = next_target_tile_y * settings.TILE_SIZE + settings.TILE_SIZE // 2 #
        delta_x = target_pixel_cx - current_ai_pixel_cx
        delta_y = target_pixel_cy - current_ai_pixel_cy
        threshold = self.ai_player.speed / 1.5 #

        if abs(delta_x) < threshold and abs(delta_y) < threshold:
            self.ai_player.hitbox.centerx = target_pixel_cx #
            self.ai_player.hitbox.centery = target_pixel_cy #
            self.ai_player.set_ai_movement_intent(0, 0) #
            self.current_path_index += 1
            if self.current_path_index + 1 >= len(self.current_path):
                self.current_path = []; self.current_path_index = 0
                return True 
            return False 
        else:
            dx_norm, dy_norm = 0, 0
            if delta_x != 0: dx_norm = 1 if delta_x > 0 else -1
            if delta_y != 0: dy_norm = 1 if delta_y > 0 else -1
            self.ai_player.set_ai_movement_intent(dx_norm, dy_norm) #
        return False 

    def update(self):
        current_time = pygame.time.get_ticks()
        if not self.ai_player.is_alive: #
            self.ai_player.set_ai_movement_intent(0,0) #
            if self.current_state != "DEAD": self.change_state("DEAD") # 可選：新增死亡狀態
            return

        if current_time - self.last_decision_time >= self.ai_decision_interval:
            self.last_decision_time = current_time
            # print(f"--- AI Deciding (State: {self.current_state}) ---") # DEBUG
            self.change_state(AI_STATE_EVALUATE_SITUATION) # 每次決策都從評估開始
            self.update_state_machine() 
            self.perform_current_state_action() # 執行新狀態的初始動作 (通常是設定路徑)
            # print(f"--- AI Decided (New State: {self.current_state}, Path Len: {len(self.current_path)}) ---") # DEBUG
        
        if self.current_path: 
            path_ended = self.move_along_path()
            if path_ended: 
                # print(f"AI Path Ended for state {self.current_state}. Forcing re-evaluation.") # DEBUG
                self.last_decision_time = 0 
                self.ai_player.set_ai_movement_intent(0,0) #
                self.change_state(AI_STATE_EVALUATE_SITUATION) 
        elif self.current_state not in [AI_STATE_AWAIT_OPPORTUNITY, AI_STATE_TACTICAL_RETREAT]:
             self.ai_player.set_ai_movement_intent(0,0) #


    def debug_draw_path(self, surface):
        # (與之前版本相同)
        #
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
        elif self.current_state == AI_STATE_COLLECT_POWERUP and self.current_target_item_sprite and self.current_target_item_sprite.alive(): #
            target_tile,color = (self.current_target_item_sprite.rect.centerx//settings.TILE_SIZE, self.current_target_item_sprite.rect.centery//settings.TILE_SIZE), (0,255,0,200) #
        elif self.current_state == AI_STATE_ENGAGE_TARGET and self.current_target_player_sprite and self.current_target_player_sprite.is_alive(): #
            target_tile,color = (self.current_target_player_sprite.hitbox.centerx//settings.TILE_SIZE, self.current_target_player_sprite.hitbox.centery//settings.TILE_SIZE), (255,165,0,200) #
        elif self.current_state == AI_STATE_STRATEGIC_BOMBING_FOR_PATH and self.current_bombing_target_wall_sprite: #
            target_tile, color = (self.current_bombing_target_wall_sprite.tile_x, self.current_bombing_target_wall_sprite.tile_y), (128,0,128,200) #
            if self.bombing_spot_for_wall: pygame.draw.circle(surface, (200,200,0,150), (self.bombing_spot_for_wall[0]*settings.TILE_SIZE+settings.TILE_SIZE//2, self.bombing_spot_for_wall[1]*settings.TILE_SIZE+settings.TILE_SIZE//2), settings.TILE_SIZE//4, 2) #
        elif self.current_state == AI_STATE_PATROL and self.current_action_target_tile : target_tile, color = self.current_action_target_tile, (100,100,100,150) 
        if target_tile: pygame.draw.circle(surface, color, (target_tile[0]*settings.TILE_SIZE+settings.TILE_SIZE//2, target_tile[1]*settings.TILE_SIZE+settings.TILE_SIZE//2), settings.TILE_SIZE//3+2,3) #