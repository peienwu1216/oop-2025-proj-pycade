# oop-2025-proj-pycade/core/ai_controller.py

import pygame
import settings
import random
from collections import deque

# --- AI 狀態定義 ---
AI_STATE_IDLE = "IDLE"
AI_STATE_ESCAPE = "ESCAPE"
AI_STATE_ATTACK_PLAYER = "ATTACK_PLAYER"
AI_STATE_FETCH_ITEMS = "FETCH_ITEMS"
AI_STATE_WAIT_EXPLOSION = "WAIT_EXPLOSION"
AI_STATE_BREAK_WALL = "BREAK_WALL"  # 新增狀態：破壞牆壁以開路

# --- 方向向量 (格子單位) ---
DIRECTIONS = {
    "UP": (0, -1), "DOWN": (0, 1), "LEFT": (-1, 0), "RIGHT": (1, 0)
}

class AIController:
    def __init__(self, ai_player_sprite, game_instance):
        self.ai_player = ai_player_sprite
        self.game = game_instance
        self.current_state = AI_STATE_IDLE
        self.state_start_time = pygame.time.get_ticks()
        
        self.current_path = []
        self.current_path_index = 0
        
        self.ai_decision_interval = settings.AI_MOVE_DELAY # AI "思考" 的間隔 (毫秒)
        self.last_decision_time = pygame.time.get_ticks()
        
        self.target_player = self.game.player1 # 預設攻擊目標
        self.target_item = None                 
        self.escape_target_tile = None          
        
        self.last_bomb_placed_time = 0          
        self.ai_placed_bomb_recently = False    

        # 新增：用於 BREAK_WALL 狀態的目標資訊
        self.target_wall_data = None # 格式: {'wall_sprite': sprite, 'path_to_bomb_spot': list, 'bomb_spot': tuple}

        self.bfs_visited_visual = []

        print(f"AIController initialized for Player ID: {id(self.ai_player)}. Targeting Player ID: {id(self.target_player) if self.target_player else 'None'}")

    def change_state(self, new_state, target_player=None, target_item=None, escape_tile=None, wall_data=None): # 新增 wall_data 參數
        """切換AI狀態並重置相關變數"""
        # 只有在狀態真正改變，或特定狀態的目標改變時才執行
        # (確保不會因為 wall_data 不同而頻繁重置其他狀態)
        condition_changed = False
        if self.current_state != new_state:
            condition_changed = True
        elif new_state == AI_STATE_FETCH_ITEMS and target_item != self.target_item:
            condition_changed = True
        elif new_state == AI_STATE_ATTACK_PLAYER and target_player != self.target_player:
            condition_changed = True
        elif new_state == AI_STATE_ESCAPE and escape_tile != self.escape_target_tile:
            condition_changed = True
        elif new_state == AI_STATE_BREAK_WALL and wall_data != self.target_wall_data : # 檢查 wall_data 是否改變
             condition_changed = True


        if condition_changed:
            # print(f"AI (Player {id(self.ai_player)}) state: {self.current_state} -> {new_state}")
            self.current_state = new_state
            self.state_start_time = pygame.time.get_ticks()
            self.current_path = [] 
            self.current_path_index = 0
            
            self.target_player = target_player if target_player else (self.game.player1 if self.current_state == AI_STATE_ATTACK_PLAYER else None) #
            self.target_item = target_item if self.current_state == AI_STATE_FETCH_ITEMS else None
            self.escape_target_tile = escape_tile if self.current_state == AI_STATE_ESCAPE else None
            
            # 重置 wall_data，除非是進入 BREAK_WALL 狀態且提供了新的 wall_data
            self.target_wall_data = None
            if new_state == AI_STATE_BREAK_WALL and wall_data:
                self.target_wall_data = wall_data
    
    def find_safe_tiles_nearby(self, start_tile, max_search_depth=5):
        queue = deque([(start_tile, 0)]) 
        visited = {start_tile}      
        safe_tiles_found = []       
        map_mgr = self.game.map_manager 
        while queue:
            (current_x, current_y), depth = queue.popleft()
            if depth > max_search_depth: continue
            if not self.is_tile_dangerous(current_x, current_y, check_bombs=True, check_explosions=True, future_seconds=0.5):
                safe_tiles_found.append((current_x, current_y))
                if len(safe_tiles_found) >= 5: break 
            if depth < max_search_depth:
                for dx, dy in DIRECTIONS.values(): 
                    next_x, next_y = current_x + dx, current_y + dy
                    if (next_x, next_y) not in visited and map_mgr.is_walkable(next_x, next_y): #
                        visited.add((next_x, next_y))
                        queue.append(((next_x, next_y), depth + 1))
        return safe_tiles_found
    
    def update_state_machine(self):
        if not self.ai_player.is_alive: return #

        current_ai_tile = (self.ai_player.hitbox.centerx // settings.TILE_SIZE, # 使用 hitbox
                           self.ai_player.hitbox.centery // settings.TILE_SIZE) #

        # --- 優先級 1: ESCAPE ---
        if self.is_tile_dangerous(current_ai_tile[0], current_ai_tile[1], True, True, future_seconds=1.0):
            safe_escape_spots = self.find_safe_tiles_nearby(current_ai_tile)
            if safe_escape_spots:
                chosen_escape_tile = random.choice(safe_escape_spots) 
                path_to_safe_spot = self.bfs_find_path(current_ai_tile, chosen_escape_tile, True, True)
                if path_to_safe_spot:
                    self.change_state(AI_STATE_ESCAPE, escape_tile=chosen_escape_tile)
                    self.current_path = path_to_safe_spot; self.current_path_index = 0
                    return 
            self.change_state(AI_STATE_IDLE) 
            return

        if self.current_state == AI_STATE_ESCAPE:
            if self.escape_target_tile:
                if current_ai_tile == self.escape_target_tile and \
                   not self.is_tile_dangerous(self.escape_target_tile[0], self.escape_target_tile[1], True, True, 0.2):
                    self.change_state(AI_STATE_IDLE); return 
                elif self.is_tile_dangerous(self.escape_target_tile[0], self.escape_target_tile[1], True, True, 0.5):
                    self.current_path = []; self.escape_target_tile = None 
            elif not self.is_tile_dangerous(current_ai_tile[0], current_ai_tile[1], True, True, 0.2):
                self.change_state(AI_STATE_IDLE); return
            return 

        # --- 優先級 2: WAIT_EXPLOSION ---
        if self.ai_placed_bomb_recently:
            time_since_bomb = pygame.time.get_ticks() - self.last_bomb_placed_time
            if time_since_bomb < (settings.BOMB_TIMER + settings.EXPLOSION_DURATION + 300): #
                if self.current_state != AI_STATE_WAIT_EXPLOSION and \
                   not self.is_tile_dangerous(current_ai_tile[0], current_ai_tile[1], True, True, 0.5):
                    self.change_state(AI_STATE_WAIT_EXPLOSION)
                return 
            else:
                self.ai_placed_bomb_recently = False

        # --- 優先級 3: ATTACK_PLAYER ---
        path_to_player = None
        player_tile_for_attack = None
        if self.target_player and self.target_player.is_alive: #
            player_tile_for_attack = (self.target_player.hitbox.centerx // settings.TILE_SIZE, #
                                      self.target_player.hitbox.centery // settings.TILE_SIZE) #
            path_to_player = self.bfs_find_path(current_ai_tile, player_tile_for_attack, True, True)
            if path_to_player and (len(path_to_player) -1) <= (self.ai_player.bomb_range + 2): #
                if self.can_place_bomb_safely_at(current_ai_tile[0], current_ai_tile[1]):
                    self.change_state(AI_STATE_ATTACK_PLAYER, target_player=self.target_player)
                    self.current_path = path_to_player; self.current_path_index = 0
                    return 
        
        # --- 優先級 4: FETCH_ITEMS ---
        path_to_item = None
        closest_item_for_fetch = self.find_closest_item()
        if closest_item_for_fetch:
            item_tile = (closest_item_for_fetch.rect.centerx // settings.TILE_SIZE, #
                         closest_item_for_fetch.rect.centery // settings.TILE_SIZE) #
            path_to_item = self.bfs_find_path(current_ai_tile, item_tile, True, True)
            if path_to_item:
                self.change_state(AI_STATE_FETCH_ITEMS, target_item=closest_item_for_fetch)
                self.current_path = path_to_item; self.current_path_index = 0
                return

        # --- 優先級 5: BREAK_WALL ---
        # 只有在無法直接攻擊玩家或拾取道具，且AI有炸彈時，才考慮破牆
        if not path_to_player and not path_to_item: # 確認主要目標路徑不存在
            if self.ai_player.bombs_placed_count < self.ai_player.max_bombs: #
                # 嘗試找一個牆來破壞，優先破壞能通向玩家的牆，其次是隨便開路
                ultimate_target = player_tile_for_attack if player_tile_for_attack else None
                wall_to_break_data = self.find_target_destructible_wall(ultimate_target_tile=ultimate_target)
                if wall_to_break_data:
                    self.change_state(AI_STATE_BREAK_WALL, wall_data=wall_to_break_data)
                    self.current_path = wall_to_break_data['path_to_bomb_spot'] 
                    self.current_path_index = 0
                    return

        # --- DEFAULT: IDLE ---
        if self.current_state != AI_STATE_IDLE: 
            self.change_state(AI_STATE_IDLE)


    def perform_current_state_action(self):
        if not self.ai_player.is_alive: return #
        # print(f"AI ({id(self.ai_player)}) performing action for state: {self.current_state}")
        if self.current_state == AI_STATE_IDLE: self.handle_idle_state()
        elif self.current_state == AI_STATE_ESCAPE: self.handle_escape_state()
        elif self.current_state == AI_STATE_ATTACK_PLAYER: self.handle_attack_player_state()
        elif self.current_state == AI_STATE_FETCH_ITEMS: self.handle_fetch_items_state()
        elif self.current_state == AI_STATE_WAIT_EXPLOSION: self.handle_wait_explosion_state()
        elif self.current_state == AI_STATE_BREAK_WALL: self.handle_break_wall_state()


    def handle_idle_state(self):
        if not self.current_path and (pygame.time.get_ticks() - self.last_decision_time < self.ai_decision_interval / 2):
            ai_tile_x = self.ai_player.hitbox.centerx // settings.TILE_SIZE #
            ai_tile_y = self.ai_player.hitbox.centery // settings.TILE_SIZE #
            possible_moves = []
            for dx, dy in DIRECTIONS.values():
                next_x, next_y = ai_tile_x + dx, ai_tile_y + dy
                if self.game.map_manager.is_walkable(next_x, next_y) and \
                   not self.is_tile_dangerous(next_x, next_y, True, True, 0.5): #
                    possible_moves.append((next_x, next_y))
            if possible_moves:
                target_tile = random.choice(possible_moves)
                path = self.bfs_find_path((ai_tile_x, ai_tile_y), target_tile, True, True)
                if path: self.current_path = path; self.current_path_index = 0
            else: # 如果沒有可移動的安全鄰近格子 (可能被完全困住，且BREAK_WALL也沒觸發)
                self.ai_player.set_ai_movement_intent(0,0) #


    def handle_escape_state(self):
        if not self.current_path and self.escape_target_tile:
            self.last_decision_time = 0 
        elif not self.escape_target_tile:
            self.last_decision_time = 0


    def handle_attack_player_state(self):
        ai_current_tile = (self.ai_player.hitbox.centerx // settings.TILE_SIZE, self.ai_player.hitbox.centery // settings.TILE_SIZE) #
        if not self.target_player or not self.target_player.is_alive: #
            self.change_state(AI_STATE_IDLE); return

        player_tile = (self.target_player.hitbox.centerx // settings.TILE_SIZE, self.target_player.hitbox.centery // settings.TILE_SIZE) #
        
        steps_to_player = float('inf')
        if self.current_path and len(self.current_path) > self.current_path_index:
             steps_to_player = (len(self.current_path) - 1) - self.current_path_index
        elif not self.current_path and ai_current_tile == player_tile: 
            steps_to_player = 0

        if steps_to_player <= (self.ai_player.bomb_range + 1): #
            if self.ai_player.bombs_placed_count < self.ai_player.max_bombs: #
                if self.can_place_bomb_safely_at(ai_current_tile[0], ai_current_tile[1]):
                    self.ai_player.place_bomb() #
                    self.current_path = []; self.last_decision_time = 0 
                    return 
        
        if not self.current_path and ai_current_tile != player_tile : 
            path = self.bfs_find_path(ai_current_tile, player_tile, True, True)
            if path: self.current_path = path; self.current_path_index = 0
            else: self.change_state(AI_STATE_IDLE)


    def handle_fetch_items_state(self):
        ai_current_tile = (self.ai_player.hitbox.centerx // settings.TILE_SIZE, self.ai_player.hitbox.centery // settings.TILE_SIZE) #
        if not self.target_item or not self.target_item.alive(): #
            self.change_state(AI_STATE_IDLE); return

        item_tile = (self.target_item.rect.centerx // settings.TILE_SIZE, self.target_item.rect.centery // settings.TILE_SIZE) #
        if not self.current_path or self.current_path[-1] != item_tile: 
            path = self.bfs_find_path(ai_current_tile, item_tile, True, True)
            if path: self.current_path = path; self.current_path_index = 0
            else: self.change_state(AI_STATE_IDLE); return
        
        if ai_current_tile == item_tile and not self.target_item.alive(): #
            self.change_state(AI_STATE_IDLE)


    def handle_wait_explosion_state(self):
        ai_current_tile = (self.ai_player.hitbox.centerx // settings.TILE_SIZE, self.ai_player.hitbox.centery // settings.TILE_SIZE) #
        if self.is_tile_dangerous(ai_current_tile[0], ai_current_tile[1], True, True, 0.5):
            self.last_decision_time = 0; return 
        if not self.ai_placed_bomb_recently: 
             self.change_state(AI_STATE_IDLE)
        self.ai_player.set_ai_movement_intent(0,0) #


    def handle_break_wall_state(self):
        if not self.target_wall_data or \
           not self.target_wall_data.get('wall_sprite') or \
           self.target_wall_data['wall_sprite'].is_destroyed: #
            self.change_state(AI_STATE_IDLE)
            return

        ai_current_tile = (self.ai_player.hitbox.centerx // settings.TILE_SIZE, self.ai_player.hitbox.centery // settings.TILE_SIZE) #
        bomb_spot_tile = self.target_wall_data['bomb_spot']

        if ai_current_tile == bomb_spot_tile:
            if self.ai_player.bombs_placed_count < self.ai_player.max_bombs: #
                if self.can_place_bomb_safely_at(ai_current_tile[0], ai_current_tile[1]):
                    self.ai_player.place_bomb() #
                    self.current_path = []; self.last_decision_time = 0 
                    return
                else: self.change_state(AI_STATE_IDLE); return
            else: self.change_state(AI_STATE_IDLE); return
        else:
            if not self.current_path: # 如果到轟炸點的路徑沒了，強制重新決策
                self.last_decision_time = 0


    def find_closest_item(self): #
        if not self.game.items_group: return None #
        closest_item_sprite = None; shortest_path_len = float('inf')
        ai_tile = (self.ai_player.hitbox.centerx // settings.TILE_SIZE, self.ai_player.hitbox.centery // settings.TILE_SIZE) #
        for item_sprite in self.game.items_group: #
            if not item_sprite.alive(): continue #
            item_tile = (item_sprite.rect.centerx // settings.TILE_SIZE, item_sprite.rect.centery // settings.TILE_SIZE) #
            path = self.bfs_find_path(ai_tile, item_tile, True, True)
            if path and len(path) < shortest_path_len:
                shortest_path_len = len(path); closest_item_sprite = item_sprite
        return closest_item_sprite

    def find_target_destructible_wall(self, ultimate_target_tile=None):
        """
        尋找一個可破壞的牆作為目標。
        如果提供了 ultimate_target_tile，會嘗試找到能幫助到達該目標的牆。
        否則，會尋找附近最容易安全炸掉的牆（例如為了開路或擺脫困境）。
        返回: {'wall_sprite': sprite, 'path_to_bomb_spot': list, 'bomb_spot': tuple} 或 None
        """
        ai_tile = (self.ai_player.hitbox.centerx // settings.TILE_SIZE, self.ai_player.hitbox.centery // settings.TILE_SIZE) #
        
        candidate_walls = []

        for wall in self.game.map_manager.destructible_walls_group: #
            if wall.is_destroyed: continue #
            wall_tile = (wall.tile_x, wall.tile_y) #

            for dx, dy in DIRECTIONS.values(): # 檢查牆的四周是否有可站立放炸彈的點
                bomb_spot_candidate = (wall_tile[0] - dx, wall_tile[1] - dy) 
                # 確保 bomb_spot_candidate 是空格且 AI 可以站立
                if not self.game.map_manager.is_walkable(bomb_spot_candidate[0], bomb_spot_candidate[1]): continue #
                if self.is_tile_dangerous(bomb_spot_candidate[0], bomb_spot_candidate[1], True, True, 0.5): continue

                path_to_bomb_spot = self.bfs_find_path(ai_tile, bomb_spot_candidate, True, True)
                if path_to_bomb_spot:
                    if self.can_place_bomb_safely_at(bomb_spot_candidate[0], bomb_spot_candidate[1]):
                        # 評估這個牆的價值 (簡單版本：路徑長度；進階：是否朝向 ultimate_target_tile)
                        value = len(path_to_bomb_spot) 
                        if ultimate_target_tile:
                            # 嘗試估計炸掉牆後到目標的距離 (這需要更複雜的BFS或启发式搜索)
                            # 簡化：如果牆在AI和目標之間，給予更高優先級（減小value）
                            # 這裡僅用路徑長度作為基礎排序
                            pass
                        candidate_walls.append({
                            'wall_sprite': wall, 
                            'path_to_bomb_spot': path_to_bomb_spot, 
                            'bomb_spot': bomb_spot_candidate, 
                            'value': value  # 值越小越好 (例如路徑短)
                        })
                        break # 找到一個這個牆的可轟炸點就夠了
        
        if not candidate_walls: return None
        
        # 選擇最有價值的牆 (value 最小的)
        candidate_walls.sort(key=lambda x: x['value'])
        return candidate_walls[0]


    def bfs_find_path(self, start_tile, end_tile_or_tiles, avoid_danger_from_bombs=True, avoid_current_explosions=True): #
        self.bfs_visited_visual = [] 
        queue = deque([(start_tile, [start_tile])]) 
        visited = {start_tile}
        map_mgr = self.game.map_manager
        targets = []
        if isinstance(end_tile_or_tiles, list): targets.extend(end_tile_or_tiles)
        else: targets.append(end_tile_or_tiles)
        if not targets or targets[0] is None : return [] # 確保目標有效

        while queue:
            (current_x, current_y), path_to_current = queue.popleft()
            self.bfs_visited_visual.append((current_x, current_y)) 
            if (current_x, current_y) in targets: return path_to_current
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

    def move_along_path(self): #
        if not self.current_path or self.current_path_index >= len(self.current_path):
            self.current_path = []; self.current_path_index = 0
            self.ai_player.set_ai_movement_intent(0, 0); return False #

        if self.current_path_index + 1 >= len(self.current_path):
            self.current_path = []; self.current_path_index = 0
            self.ai_player.set_ai_movement_intent(0, 0); return False #

        next_target_tile_x, next_target_tile_y = self.current_path[self.current_path_index + 1]
        
        current_ai_pixel_cx = self.ai_player.hitbox.centerx #
        current_ai_pixel_cy = self.ai_player.hitbox.centery #
        
        target_pixel_cx = next_target_tile_x * settings.TILE_SIZE + settings.TILE_SIZE // 2 #
        target_pixel_cy = next_target_tile_y * settings.TILE_SIZE + settings.TILE_SIZE // 2 #

        delta_x = target_pixel_cx - current_ai_pixel_cx
        delta_y = target_pixel_cy - current_ai_pixel_cy
        threshold = self.ai_player.speed / 1.8 # 稍微放寬一點到達閾值，避免抖動

        if abs(delta_x) < threshold and abs(delta_y) < threshold:
            self.ai_player.hitbox.centerx = target_pixel_cx #
            self.ai_player.hitbox.centery = target_pixel_cy #
            self.ai_player.set_ai_movement_intent(0, 0) #
            self.current_path_index += 1
            if self.current_path_index + 1 >= len(self.current_path):
                self.current_path = []; self.current_path_index = 0
            return True 
        else:
            dx_norm, dy_norm = 0, 0
            if delta_x != 0: dx_norm = 1 if delta_x > 0 else -1
            if delta_y != 0: dy_norm = 1 if delta_y > 0 else -1
            self.ai_player.set_ai_movement_intent(dx_norm, dy_norm) #
        return False


    def is_tile_dangerous(self, tile_x, tile_y, check_bombs=True, check_explosions=True, future_seconds=None): #
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

    def _is_tile_in_hypothetical_blast(self, check_tile_x, check_tile_y, #
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

    def can_place_bomb_safely_at(self, bomb_placement_x, bomb_placement_y): #
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

    def update(self): #
        now = pygame.time.get_ticks()
        if now - self.last_decision_time > self.ai_decision_interval:
            self.last_decision_time = now
            if self.ai_player.is_alive: #
                self.update_state_machine()
                self.perform_current_state_action()
        if self.current_path and self.ai_player.is_alive: #
            path_done = self.move_along_path()
            if path_done and not self.current_path: 
                self.last_decision_time = 0 
                self.ai_player.set_ai_movement_intent(0,0) #

    def debug_draw_path(self, surface): #
        if self.current_path and len(self.current_path) > 1:
            path_points = [(t[0]*settings.TILE_SIZE + settings.TILE_SIZE//2, t[1]*settings.TILE_SIZE + settings.TILE_SIZE//2) for t in self.current_path] #
            try: pygame.draw.lines(surface, (255,0,255,180), False, path_points, 3)
            except TypeError: pygame.draw.lines(surface, (255,0,255), False, path_points, 3)
            if self.current_path_index + 1 < len(self.current_path):
                nx,ny = self.current_path[self.current_path_index+1]
                pygame.draw.circle(surface, (0,255,255,200), (nx*settings.TILE_SIZE+settings.TILE_SIZE//2, ny*settings.TILE_SIZE+settings.TILE_SIZE//2),7,0) #
        
        target_tile, color = None, settings.RED #
        if self.current_state == AI_STATE_ESCAPE and self.escape_target_tile: target_tile, color = self.escape_target_tile, (0,0,255,200)
        elif self.current_state == AI_STATE_FETCH_ITEMS and self.target_item and self.target_item.alive(): #
            target_tile,color = (self.target_item.rect.centerx//settings.TILE_SIZE, self.target_item.rect.centery//settings.TILE_SIZE), (0,255,0,200) #
        elif self.current_state == AI_STATE_ATTACK_PLAYER and self.target_player and self.target_player.is_alive(): #
            target_tile,color = (self.target_player.hitbox.centerx//settings.TILE_SIZE, self.target_player.hitbox.centery//settings.TILE_SIZE), (255,165,0,200) #
        elif self.current_state == AI_STATE_BREAK_WALL and self.target_wall_data:
            target_tile, color = (self.target_wall_data['wall_sprite'].tile_x, self.target_wall_data['wall_sprite'].tile_y), (128,0,128,200) # 紫色代表目標牆
            # 也可以繪製轟炸點
            bomb_spot_for_wall = self.target_wall_data['bomb_spot']
            pygame.draw.circle(surface, (200,200,0,150), (bomb_spot_for_wall[0]*settings.TILE_SIZE+settings.TILE_SIZE//2, bomb_spot_for_wall[1]*settings.TILE_SIZE+settings.TILE_SIZE//2), settings.TILE_SIZE//4, 2) #


        if target_tile:
            pygame.draw.circle(surface, color, (target_tile[0]*settings.TILE_SIZE+settings.TILE_SIZE//2, target_tile[1]*settings.TILE_SIZE+settings.TILE_SIZE//2), settings.TILE_SIZE//3+2,3) #