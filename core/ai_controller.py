# oop-2025-proj-pycade/core/ai_controller.py

import pygame
import settings
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
AI_STATE_DEAD = "DEAD" # 新增死亡狀態

DIRECTIONS = {"UP": (0, -1), "DOWN": (0, 1), "LEFT": (-1, 0), "RIGHT": (1, 0)} # (dx, dy)
POWERUP_VALUES = {
    settings.ITEM_TYPE_LIFE: 100,
    settings.ITEM_TYPE_BOMB_CAPACITY: 85,
    settings.ITEM_TYPE_BOMB_RANGE: 75,
    settings.ITEM_TYPE_SCORE: 5,
}

class AIController:
    def __init__(self, ai_player_sprite, game_instance):
        self.ai_player = ai_player_sprite # Player 物件的實例
        self.game = game_instance
        self.current_state = AI_STATE_EVALUATE_SITUATION
        self.state_start_time = pygame.time.get_ticks()
        self.current_path = []
        self.current_path_index = 0 # 指向路徑中 AI *下一個* 要移動到的格子
        self.ai_decision_interval = settings.AI_MOVE_DELAY # 毫秒
        self.last_decision_time = pygame.time.get_ticks() - self.ai_decision_interval # 確保第一次決策發生

        self.human_player_sprite = self.game.player1 # Player 物件的實例

        self.current_target_player_sprite = None # Player 物件
        self.current_target_item_sprite = None   # Item 物件
        self.current_escape_target_tile = None      # (x,y) 格子座標
        self.current_action_target_tile = None # (x,y) 格子座標 (例如巡邏目標)
        self.current_bombing_target_wall_sprite = None # Wall 物件
        self.bombing_spot_for_wall = None           # (x,y) 格子座標

        self.last_bomb_placed_time = 0
        self.ai_just_placed_bomb = False # AI 是否剛放了炸彈 (用於觸發戰術撤退)
        self.player_unreachable_start_time = 0 # 計時玩家無法到達的時間
        self.stuck_in_patrol_start_time = 0    # 計時在巡邏狀態卡住的時間

        # print(f"AIController (Grid Movement) initialized for Player ID: {id(self.ai_player)}.") # DEBUG

    def reset_state(self): # Game.setup_initial_state 時可能呼叫
        self.current_state = AI_STATE_EVALUATE_SITUATION
        self.state_start_time = pygame.time.get_ticks()
        self.current_path = []
        self.current_path_index = 0
        self.last_decision_time = pygame.time.get_ticks() - self.ai_decision_interval
        self.ai_just_placed_bomb = False
        self.player_unreachable_start_time = 0
        self.stuck_in_patrol_start_time = 0
        # print(f"AIController for Player ID: {id(self.ai_player)} has been reset.") # DEBUG


    def change_state(self, new_state, **kwargs):
        # if self.current_state == new_state and not kwargs.get('force_reset', False): return # 避免不必要的狀態重設
        # print(f"[AI CHANGE_STATE] ID: {id(self.ai_player)} From {self.current_state} -> {new_state}. Path in kwargs: {'path' in kwargs}") # DEBUG
        
        self.current_state = new_state
        self.state_start_time = pygame.time.get_ticks()

        # 只有在 kwargs 中明確提供了 path 時才更新 path，否則清除舊路徑 (除非是重新進入同狀態且不強制重設路徑)
        if 'path' in kwargs:
            self.current_path = kwargs.get('path', [])
            # print(f"  Path set from kwargs: {self.current_path}") # DEBUG
        # elif self.current_state != old_state: # 如果狀態確實改變了，清除路徑
        else: # 預設清除路徑，除非特定邏輯保留
             self.current_path = []
             # print(f"  Path cleared for new state {new_state} (or no path in kwargs).") # DEBUG

        self.current_path_index = 0 # 新路徑或無路徑，索引都歸零

        # 更新目標參照
        self.current_target_player_sprite = kwargs.get('target_player_sprite', self.current_target_player_sprite if new_state == self.current_state else None)
        self.current_target_item_sprite = kwargs.get('target_item_sprite', self.current_target_item_sprite if new_state == self.current_state else None)
        self.current_escape_target_tile = kwargs.get('escape_target_tile', None)
        self.current_action_target_tile = kwargs.get('action_target_tile', None)
        self.current_bombing_target_wall_sprite = kwargs.get('target_wall_sprite', self.current_bombing_target_wall_sprite if new_state == self.current_state else None)
        self.bombing_spot_for_wall = kwargs.get('bombing_spot', None)


        if new_state == AI_STATE_PATROL and not self.current_path:
            if self.stuck_in_patrol_start_time == 0:
                 self.stuck_in_patrol_start_time = pygame.time.get_ticks()
        elif new_state != AI_STATE_PATROL: # 離開巡邏狀態，重置計時器
            self.stuck_in_patrol_start_time = 0

    def _get_ai_current_tile(self):
        """獲取 AI 玩家當前的邏輯格子位置"""
        if self.ai_player:
            return (self.ai_player.tile_x, self.ai_player.tile_y)
        return (None, None) # Fallback

    def _get_player_tile(self, player_sprite):
        """獲取指定玩家精靈的邏輯格子位置"""
        if player_sprite and hasattr(player_sprite, 'tile_x') and hasattr(player_sprite, 'tile_y'):
            return (player_sprite.tile_x, player_sprite.tile_y)
        # Fallback if player_sprite doesn't have tile_x/tile_y (e.g., old version or different object)
        # This should ideally not be needed if all Player objects are updated
        elif player_sprite and hasattr(player_sprite, 'hitbox'):
            # print(f"[AI WARNING] _get_player_tile using hitbox fallback for player {id(player_sprite)}") # DEBUG
            return (player_sprite.hitbox.centerx // settings.TILE_SIZE,
                    player_sprite.hitbox.centery // settings.TILE_SIZE)
        return (None, None)


    def _is_tile_in_hypothetical_blast(self, check_tile_x, check_tile_y,
                                       bomb_placed_at_x, bomb_placed_at_y,
                                       bomb_range):
        # [AIC_NO_CHANGE_NEEDED] 此方法基於格子座標，不受移動方式改變影響
        if check_tile_x == bomb_placed_at_x and check_tile_y == bomb_placed_at_y: return True
        # ... (其餘邏輯不變) ...
        if check_tile_y == bomb_placed_at_y and abs(check_tile_x - bomb_placed_at_x) <= bomb_range:
            blocked = False; step = 1 if check_tile_x > bomb_placed_at_x else -1
            for i in range(1, abs(check_tile_x - bomb_placed_at_x) + 1): # Check up to and including the tile itself (for walls)
                current_check_x = bomb_placed_at_x + i * step
                if self.game.map_manager.is_solid_wall_at(current_check_x, bomb_placed_at_y):
                    if current_check_x != check_tile_x : blocked = True # Wall is before target tile
                    break 
            if not blocked: return True
        if check_tile_x == bomb_placed_at_x and abs(check_tile_y - bomb_placed_at_y) <= bomb_range:
            blocked = False; step = 1 if check_tile_y > bomb_placed_at_y else -1
            for i in range(1, abs(check_tile_y - bomb_placed_at_y) + 1):
                current_check_y = bomb_placed_at_y + i * step
                if self.game.map_manager.is_solid_wall_at(bomb_placed_at_x, current_check_y):
                    if current_check_y != check_tile_y: blocked = True
                    break
            if not blocked: return True
        return False


    def is_tile_dangerous(self, tile_x, tile_y, check_bombs=True, check_explosions=True, future_seconds=None):
        # [AIC_NO_CHANGE_NEEDED] 此方法基於格子座標和時間，不受移動方式改變影響
        if future_seconds is None:
            future_seconds = (settings.BOMB_TIMER / 1000.0) + (settings.EXPLOSION_DURATION / 1000.0) + 0.3
        
        # 檢查是否有現存的爆炸火焰在該格子上
        if check_explosions:
            # Explosion sprites rects are in pixel coordinates. Check if tile_x, tile_y falls within any.
            tile_rect = pygame.Rect(tile_x * settings.TILE_SIZE, tile_y * settings.TILE_SIZE, settings.TILE_SIZE, settings.TILE_SIZE)
            for exp in self.game.explosions_group:
                if exp.rect.colliderect(tile_rect):
                    # print(f"[AI DANGER] Tile ({tile_x},{tile_y}) is dangerous due to active explosion.") # DEBUG
                    return True
        
        # 檢查是否有即將爆炸的炸彈會影響該格子
        if check_bombs:
            for bomb in self.game.bombs_group:
                if bomb.exploded: continue
                time_to_exp_ms = (bomb.spawn_time + bomb.timer) - pygame.time.get_ticks()
                if 0 < time_to_exp_ms < future_seconds * 1000: # 在預測時間內爆炸
                    if self._is_tile_in_hypothetical_blast(tile_x, tile_y,
                                                           bomb.current_tile_x, bomb.current_tile_y,
                                                           bomb.placed_by_player.bomb_range):
                        # print(f"[AI DANGER] Tile ({tile_x},{tile_y}) is dangerous due to bomb at ({bomb.current_tile_x},{bomb.current_tile_y}) exploding in {time_to_exp_ms/1000:.2f}s.") # DEBUG
                        return True
        return False

    def can_place_bomb_safely_at(self, bomb_placement_x, bomb_placement_y):
        # [AIC_NO_CHANGE_NEEDED] 此方法基於格子座標和 is_walkable, is_tile_dangerous，不受移動方式改變影響
        # 它內部使用 BFS (find_safe_tiles_nearby 的變體) 來尋找逃生路線，這仍是基於格子的。
        ai_bomb_range = self.ai_player.bomb_range
        
        # 檢查放置點本身是否已經危險 (除了自己即將放的炸彈外)
        if self.is_tile_dangerous(bomb_placement_x, bomb_placement_y, True, True, 0.2): # 短時間檢查
             # print(f"[AI CAN_PLACE_BOMB_SAFELY] Bomb placement tile ({bomb_placement_x},{bomb_placement_y}) is ALREADY dangerous.") # DEBUG
             return False

        # 尋找一個在放置炸彈後，AI 可以安全移動到的格子
        # 這個 BFS 需要模擬炸彈放置後的情況
        # (簡化：直接使用 find_safe_tiles_nearby，並將剛放的炸彈作為 avoid_specific_bomb_data)
        # print(f"[AI CAN_PLACE_BOMB_SAFELY] Checking safety for bomb at ({bomb_placement_x},{bomb_placement_y}) with range {ai_bomb_range}") # DEBUG
        safe_escape_spots = self.find_safe_tiles_nearby(
            start_tile=(bomb_placement_x, bomb_placement_y), # 逃生起始點是炸彈放置點
            max_search_depth=ai_bomb_range + 3, # 搜索深度
            avoid_specific_bomb_data=((bomb_placement_x, bomb_placement_y), ai_bomb_range) # 需要避開自己剛放的這顆炸彈的爆炸範圍
        )
        
        if not safe_escape_spots:
            # print(f"  No safe escape spots found from ({bomb_placement_x},{bomb_placement_y}).") # DEBUG
            return False

        # 檢查從當前AI位置是否能到達這個"安全"的炸彈放置點
        # (這一步其實可以省略，因為通常是AI在某處決定放炸彈，然後才檢查是否安全)
        # current_ai_pos = self._get_ai_current_tile()
        # path_to_placement_spot = self.bfs_find_path(current_ai_pos, (bomb_placement_x, bomb_placement_y), step_future_check_seconds=0.1)
        # if not path_to_placement_spot:
        #     print(f"  Cannot find path from AI current pos {current_ai_pos} to bombing spot ({bomb_placement_x},{bomb_placement_y}).") # DEBUG
        #     return False # 雖然可以安全逃離，但AI本身到不了放置點

        # print(f"  Found safe escape spots: {safe_escape_spots}. Bombing deemed safe.") # DEBUG
        return True


    def bfs_find_path(self, start_tile, end_tile, avoid_danger_from_bombs=True,
                      avoid_current_explosions=True, max_depth=float('inf'),
                      step_future_check_seconds=0.15):
        # [AIC_NO_CHANGE_NEEDED] 此方法返回格子列表，與新移動系統兼容。
        # 內部的 is_walkable 和 is_tile_dangerous 判斷仍然有效。
        if not start_tile or not end_tile or start_tile == (None,None) or end_tile == (None,None):
            # print(f"[BFS] Invalid start or end tile: start={start_tile}, end={end_tile}") #DEBUG
            return []
        if start_tile == end_tile : return [start_tile]
        # ... (其餘邏輯不變，使用 step_future_check_seconds) ...
        queue = deque([(start_tile, [start_tile])])
        visited = {start_tile}
        map_mgr = self.game.map_manager

        while queue:
            (current_x, current_y), path_to_current = queue.popleft()
            if (current_x, current_y) == end_tile: return path_to_current
            if len(path_to_current) -1 >= max_depth: continue

            shuffled_directions = list(DIRECTIONS.items())
            random.shuffle(shuffled_directions)

            for _, (dx, dy) in shuffled_directions:
                next_x, next_y = current_x + dx, current_y + dy
                if (next_x, next_y) not in visited:
                    if map_mgr.is_walkable(next_x, next_y):
                        is_next_step_dangerous = self.is_tile_dangerous(next_x, next_y,
                                                                      check_bombs=avoid_danger_from_bombs,
                                                                      check_explosions=avoid_current_explosions,
                                                                      future_seconds=step_future_check_seconds)
                        if is_next_step_dangerous:
                            continue
                        visited.add((next_x, next_y))
                        new_path = list(path_to_current); new_path.append((next_x, next_y))
                        queue.append(((next_x, next_y), new_path))
        return []


    def find_safe_tiles_nearby(self, start_tile, max_search_depth=5, avoid_specific_bomb_data=None):
        # [AIC_NO_CHANGE_NEEDED] 此方法尋找安全的格子，邏輯不變。
        if not start_tile or start_tile == (None,None): return []
        # ... (其餘邏輯不變) ...
        queue = deque([(start_tile, 0)])
        visited = {start_tile}
        safe_tiles_found = []
        map_mgr = self.game.map_manager
        while queue:
            (current_x, current_y), depth = queue.popleft()
            if depth > max_search_depth: continue

            is_safe_from_general_danger = not self.is_tile_dangerous(current_x, current_y, True, True, 0.2) # Check if tile itself will be safe soon
            is_safe_from_specific_bomb = True
            if avoid_specific_bomb_data:
                bomb_tile, bomb_range = avoid_specific_bomb_data
                if self._is_tile_in_hypothetical_blast(current_x, current_y, bomb_tile[0], bomb_tile[1], bomb_range):
                    is_safe_from_specific_bomb = False # This tile is in the blast of the bomb we are avoiding

            if is_safe_from_general_danger and is_safe_from_specific_bomb:
                safe_tiles_found.append((current_x, current_y))
            
            if len(safe_tiles_found) >= 5 + depth : break # Optimization: found enough diverse options

            if depth < max_search_depth:
                shuffled_directions = list(DIRECTIONS.values())
                random.shuffle(shuffled_directions)
                for dx, dy in shuffled_directions:
                    next_x, next_y = current_x + dx, current_y + dy
                    if (next_x, next_y) not in visited and map_mgr.is_walkable(next_x, next_y):
                        # For a step to be valid towards a safe spot, the step itself must be safe in the very near term
                        step_safe = not self.is_tile_dangerous(next_x,next_y,True,True,0.1) # Very short check for step
                        if avoid_specific_bomb_data:
                             bomb_tile, bomb_range = avoid_specific_bomb_data
                             if self._is_tile_in_hypothetical_blast(next_x, next_y, bomb_tile[0], bomb_tile[1], bomb_range):
                                 step_safe = False # Step is into the specific bomb's blast
                        if not step_safe: continue
                        visited.add((next_x, next_y))
                        queue.append(((next_x, next_y), depth + 1))
        return safe_tiles_found


    def find_best_powerup(self):
        ai_tile = self._get_ai_current_tile()
        if ai_tile == (None,None): return None, None
        best_item = None
        best_path_to_item = None
        highest_weighted_value = -float('inf')

        if not all(isinstance(item, pygame.sprite.Sprite) and hasattr(item, 'type') and hasattr(item, 'rect') and hasattr(item, 'alive') for item in self.game.items_group): #
            # print("[AI WARNING] items_group contains invalid objects or items missing attributes!") # DEBUG
            return None, None
            
        sorted_items = sorted([item for item in list(self.game.items_group) if item.alive()], 
                              key=lambda item: POWERUP_VALUES.get(item.type, 0), reverse=True)

        for item_sprite in sorted_items:
            item_tile_x = item_sprite.rect.centerx // settings.TILE_SIZE
            item_tile_y = item_sprite.rect.centery // settings.TILE_SIZE
            item_tile = (item_tile_x, item_tile_y)
            
            path = self.bfs_find_path(ai_tile, item_tile, True, True, step_future_check_seconds=0.3) # Path to item

            if path:
                raw_value = POWERUP_VALUES.get(item_sprite.type, 0) * self.powerup_priority_factor
                path_penalty = len(path) * 0.7 # Slightly higher penalty for longer paths
                weighted_value = raw_value - path_penalty

                if weighted_value > highest_weighted_value:
                    if not self.is_tile_dangerous(item_tile[0], item_tile[1], True, True, 0.15): # Target item tile itself should be safe
                        highest_weighted_value = weighted_value
                        best_item = item_sprite
                        best_path_to_item = path
        
        if best_item and best_path_to_item:
            return best_item, best_path_to_item
        return None, None

    def find_strategic_wall_to_bomb(self, ultimate_target_tile=None):
        ai_tile = self._get_ai_current_tile()
        if ai_tile == (None,None): return None
        candidate_walls_data = []
        if not self.game.map_manager.destructible_walls_group: return None

        for wall in self.game.map_manager.destructible_walls_group:
            if not wall.alive() or (hasattr(wall, 'is_destroyed') and wall.is_destroyed): continue
            if not (hasattr(wall, 'tile_x') and hasattr(wall, 'tile_y')): continue

            wall_tile = (wall.tile_x, wall.tile_y)
            shuffled_directions = list(DIRECTIONS.values())
            random.shuffle(shuffled_directions)

            for dx, dy in shuffled_directions: # dx, dy is direction from bomb_spot to wall
                bomb_spot_candidate = (wall_tile[0] - dx, wall_tile[1] - dy)
                
                if not self.game.map_manager.is_walkable(bomb_spot_candidate[0], bomb_spot_candidate[1]): continue
                if self.is_tile_dangerous(bomb_spot_candidate[0], bomb_spot_candidate[1], True, True, 0.3): continue # Bombing spot safety
                
                path_to_bomb_spot = self.bfs_find_path(ai_tile, bomb_spot_candidate, True, True, step_future_check_seconds=0.3)
                
                if path_to_bomb_spot:
                    if self.can_place_bomb_safely_at(bomb_spot_candidate[0], bomb_spot_candidate[1]):
                        value = len(path_to_bomb_spot) 
                        if ultimate_target_tile:
                            dist_to_ult_target_after_bomb = abs(ultimate_target_tile[0] - (wall_tile[0]+dx)) + abs(ultimate_target_tile[1] - (wall_tile[1]+dy))
                            value += dist_to_ult_target_after_bomb * 0.5 # Prefer opening towards ultimate target

                        candidate_walls_data.append({'wall_sprite': wall, 'path_to_bomb_spot': path_to_bomb_spot, 'bomb_spot': bomb_spot_candidate, 'value': value })
                        break 
        
        if not candidate_walls_data: return None
        candidate_walls_data.sort(key=lambda x: x['value'])
        return candidate_walls_data[0]


    def update_state_machine(self):
        ai_current_tile = self._get_ai_current_tile()
        if ai_current_tile == (None,None) or not self.ai_player or not self.ai_player.is_alive: # AI might have been killed
            if self.current_state != AI_STATE_DEAD: self.change_state(AI_STATE_DEAD)
            return

        # 1. 最高優先級：檢查立即危險並逃生
        if self.is_tile_dangerous(ai_current_tile[0], ai_current_tile[1], True, True, future_seconds=0.6): # 0.6s 預判危險
            if self.current_state != AI_STATE_CRITICAL_ESCAPE: # 避免重複進入
                # print(f"[AI FSM] DANGER at {ai_current_tile}! -> CRITICAL_ESCAPE.") # DEBUG
                self.change_state(AI_STATE_CRITICAL_ESCAPE)
            return # CRITICAL_ESCAPE 的 handle 會處理路徑

        # 2. 如果剛放了炸彈，必須戰術撤退
        if self.ai_just_placed_bomb:
            if self.current_state != AI_STATE_TACTICAL_RETREAT:
                # print(f"[AI FSM] Just placed bomb. -> TACTICAL_RETREAT.") # DEBUG
                self.change_state(AI_STATE_TACTICAL_RETREAT)
            return # TACTICAL_RETREAT 的 handle 會處理路徑

        # --- 根據優先級進行其他決策 ---
        human_player_tile = self._get_player_tile(self.human_player_sprite) if self.human_player_sprite and self.human_player_sprite.is_alive else None

        # 3. 攻擊人類玩家 (如果可達)
        if human_player_tile:
            path_to_player = self.bfs_find_path(ai_current_tile, human_player_tile, True, True, step_future_check_seconds=0.25)
            if path_to_player:
                self.player_unreachable_start_time = 0 # 重置計時器
                self.change_state(AI_STATE_ENGAGE_TARGET, target_player_sprite=self.human_player_sprite, path=path_to_player)
                # print(f"[AI FSM] Player reachable at {human_player_tile}. Path len {len(path_to_player)}. -> ENGAGE_TARGET.") # DEBUG
                return
            else: # 玩家存在但目前無法到達
                if self.player_unreachable_start_time == 0: self.player_unreachable_start_time = pygame.time.get_ticks()
        else: # 沒有人類玩家或人類玩家已死亡
            self.player_unreachable_start_time = 0


        # 4. 拾取道具
        powerup_data = self.find_best_powerup()
        if powerup_data:
            item_sprite, path_to_item = powerup_data
            if item_sprite and path_to_item : # 確保兩者都有效
                self.change_state(AI_STATE_COLLECT_POWERUP, target_item_sprite=item_sprite, path=path_to_item)
                # print(f"[AI FSM] Found powerup {item_sprite.type}. Path len {len(path_to_item)}. -> COLLECT_POWERUP.") # DEBUG
                return

        # 5. 策略性轟炸開路
        if self.ai_player.bombs_placed_count < self.ai_player.max_bombs:
            should_try_bombing_wall = False
            current_time = pygame.time.get_ticks()
            
            # 如果玩家無法到達已達一段時間
            if human_player_tile and self.player_unreachable_start_time > 0 and \
               (current_time - self.player_unreachable_start_time > 2000): # 2秒後考慮炸牆去玩家那裡
                should_try_bombing_wall = True
                # print(f"[AI FSM] Player unreachable for >2s. Considering bombing wall.") # DEBUG
            # 或者如果沒事做且巡邏卡住
            elif not human_player_tile and not powerup_data: # 沒玩家目標，沒道具
                if self.current_state == AI_STATE_PATROL and not self.current_path and \
                   self.stuck_in_patrol_start_time > 0 and \
                   (current_time - self.stuck_in_patrol_start_time > 3000): # 巡邏卡住3秒
                    should_try_bombing_wall = True
                    # print(f"[AI FSM] Stuck in PATROL with no path for >3s. Considering bombing wall.") # DEBUG
            
            if should_try_bombing_wall:
                ultimate_target_for_bombing_decision = human_player_tile if human_player_tile else None # 如果有玩家，以玩家為最終目標
                wall_data = self.find_strategic_wall_to_bomb(ultimate_target_tile=ultimate_target_for_bombing_decision)
                if wall_data:
                    self.change_state(AI_STATE_STRATEGIC_BOMBING_FOR_PATH,
                                      target_wall_sprite=wall_data['wall_sprite'],
                                      bombing_spot=wall_data['bomb_spot'],
                                      path=wall_data['path_to_bomb_spot'])
                    # print(f"[AI FSM] Decided to break wall: {wall_data['wall_sprite'].tile_x},{wall_data['wall_sprite'].tile_y}. -> STRATEGIC_BOMBING.") # DEBUG
                    return

        # 6. 等待時機 (通常是躲完自己炸彈後，或者戰術性等待)
        # AWAIT_OPPORTUNITY 的進入主要由 TACTICAL_RETREAT 成功後觸發，或AI覺得需要等待時
        # 此處的邏輯是：如果 ai_just_placed_bomb 為 True，則 TACTICAL_RETREAT 會優先處理。
        # 如果 tactical_retreat 完成並轉到 AWAIT_OPPORTUNITY，則 AWAIT_OPPORTUNITY 的 handle 會處理持續時間。
        # 此處僅處理一個 fallback: 如果長時間沒事做，也許進入 AWAIT (但通常是 PATROL)
        time_since_ai_bomb = pygame.time.get_ticks() - self.last_bomb_placed_time
        is_safe_at_current_spot = not self.is_tile_dangerous(ai_current_tile[0], ai_current_tile[1], True, True, 0.1)

        if self.ai_just_placed_bomb : # 此 flag 理論上應在 AWAIT_OPPORTUNITY 結束時或 TACTICAL_RETREAT 失敗時重設
            if is_safe_at_current_spot and \
               (time_since_ai_bomb < settings.BOMB_TIMER + settings.EXPLOSION_DURATION + 300):
                if self.current_state != AI_STATE_AWAIT_OPPORTUNITY: # 避免重複進入
                    # print(f"[AI FSM] Own bomb still active, safe spot. -> AWAIT_OPPORTUNITY.") # DEBUG
                    self.change_state(AI_STATE_AWAIT_OPPORTUNITY)
                return
            elif time_since_ai_bomb >= settings.BOMB_TIMER + settings.EXPLOSION_DURATION + 300:
                # print(f"[AI FSM] Own bomb cycle likely finished. Resetting ai_just_placed_bomb.") # DEBUG
                self.ai_just_placed_bomb = False 
                # 清除此狀態後，會重新評估，可能進入 Patrol 或其他

        # 7. 巡邏 (預設行為)
        if self.current_state != AI_STATE_PATROL or not self.current_path: # 如果不在巡邏，或在巡邏但沒路徑
            # print(f"[AI FSM] No other actions. Defaulting/Re-evaluating -> PATROL.") # DEBUG
            self.change_state(AI_STATE_PATROL) # PATROL 的 handle 會計算路徑


    def perform_current_state_action(self): # 各狀態的具體行為邏輯
        if not self.ai_player or not self.ai_player.is_alive:
            if self.current_state != AI_STATE_DEAD: self.change_state(AI_STATE_DEAD)
            return
        
        # 確保 AI 玩家物件存在
        if not self.ai_player:
            # print("[AI ERROR] ai_player is None in perform_current_state_action!") # DEBUG
            return

        # 根據當前狀態執行對應的處理函數
        # 這些 handle 方法現在主要負責設定目標、計算初始路徑 (如果 change_state 時未提供)
        # 以及執行該狀態下的特定動作 (例如，在 ENGAGE 時判斷是否放炸彈)
        # 實際的格子移動由 move_along_path 統一處理
        
        handler_map = {
            AI_STATE_EVALUATE_SITUATION: lambda: None, # 主要由 update_state_machine 驅動
            AI_STATE_CRITICAL_ESCAPE: self.handle_critical_escape_state,
            AI_STATE_TACTICAL_RETREAT: self.handle_tactical_retreat_state,
            AI_STATE_ENGAGE_TARGET: self.handle_engage_target_state,
            AI_STATE_COLLECT_POWERUP: self.handle_collect_powerup_state,
            AI_STATE_STRATEGIC_BOMBING_FOR_PATH: self.handle_strategic_bombing_for_path_state,
            AI_STATE_AWAIT_OPPORTUNITY: self.handle_await_opportunity_state,
            AI_STATE_PATROL: self.handle_patrol_state,
            AI_STATE_DEAD: lambda: None # 死亡狀態不做任何事
        }
        
        action_handler = handler_map.get(self.current_state)
        if action_handler:
            action_handler()
        # else:
            # print(f"[AI WARNING] No handler for state: {self.current_state}") # DEBUG


    def handle_critical_escape_state(self): # 修改版：如果找不到路徑，則原地不動等待下次評估
        ai_tile = self._get_ai_current_tile()
        if ai_tile == (None,None): return

        re_evaluate_escape = False
        if not self.current_path: re_evaluate_escape = True
        elif self.current_escape_target_tile and self.is_tile_dangerous(self.current_escape_target_tile[0], self.current_escape_target_tile[1], True, True, 0.1):
            self.current_path = []; re_evaluate_escape = True
        elif self.current_escape_target_tile and ai_tile == self.current_escape_target_tile:
            if self.is_tile_dangerous(ai_tile[0], ai_tile[1], True, True, 0.1):
                re_evaluate_escape = True
            else:
                self.change_state(AI_STATE_EVALUATE_SITUATION); return
        
        if re_evaluate_escape:
            safe_spots = self.find_safe_tiles_nearby(ai_tile, max_search_depth=5, avoid_specific_bomb_data=None)
            if safe_spots:
                potential_spots = [s for s in safe_spots if s != ai_tile] or safe_spots
                escape_tile_candidate = random.choice(potential_spots)
                path = self.bfs_find_path(ai_tile, escape_tile_candidate, True, True, step_future_check_seconds=0.05) # 極度謹慎的逃生步伐
                if path and len(path) > 1:
                    self.current_path = path; self.current_path_index = 0; self.current_escape_target_tile = escape_tile_candidate
                else: self.current_path = [] # 找不到路徑，清除路徑以停止移動
            else: self.current_path = [] # 找不到安全點，清除路徑以停止移動
        
        if not self.current_path: # 如果最終沒有路徑（無論是初始就沒有，還是重新評估後沒有）
            if self.ai_player: self.ai_player.is_moving = False # 確保動畫停止
            # AI 會停在原地，等待下一次 update_state_machine (如果依然危險，會再次進入此狀態)


    def handle_tactical_retreat_state(self): # 修改版：類似 critical_escape
        ai_tile = self._get_ai_current_tile()
        if ai_tile == (None,None) or not self.ai_just_placed_bomb:
             if self.ai_just_placed_bomb: # 如果只是 ai_tile 是 None 但剛放了炸彈，則先重設狀態
                  # print(f"[AI TACTICAL RETREAT] AI tile is None, but ai_just_placed_bomb is True. Resetting state.") # DEBUG
                  self.ai_just_placed_bomb = False # 避免卡在此狀態
             self.change_state(AI_STATE_EVALUATE_SITUATION); return

        re_evaluate_retreat = False
        if not self.current_path: re_evaluate_retreat = True
        elif self.current_escape_target_tile and self.is_tile_dangerous(self.current_escape_target_tile[0], self.current_escape_target_tile[1], True, True, 0.1):
            self.current_path = []; re_evaluate_retreat = True
        elif self.current_escape_target_tile and ai_tile == self.current_escape_target_tile:
            my_bomb_data = None # 找到 AI 自己剛放的炸彈
            for bomb in self.game.bombs_group:
                if bomb.placed_by_player == self.ai_player and not bomb.exploded and (pygame.time.get_ticks() - bomb.spawn_time < settings.BOMB_TIMER + 200):
                    my_bomb_data = ((bomb.current_tile_x, bomb.current_tile_y), self.ai_player.bomb_range); break
            
            is_safe_here = True
            if my_bomb_data and self._is_tile_in_hypothetical_blast(ai_tile[0], ai_tile[1], my_bomb_data[0][0], my_bomb_data[0][1], my_bomb_data[1]):
                is_safe_here = False
            if self.is_tile_dangerous(ai_tile[0],ai_tile[1], True, True, 0.1): is_safe_here = False # 也檢查其他危險

            if is_safe_here:
                self.change_state(AI_STATE_AWAIT_OPPORTUNITY); return
            else: re_evaluate_retreat = True

        if re_evaluate_retreat:
            my_bomb_sprite_info = None
            for bomb in self.game.bombs_group:
                if bomb.placed_by_player == self.ai_player and not bomb.exploded:
                    if my_bomb_sprite_info is None or bomb.spawn_time > my_bomb_sprite_info['spawn_time']:
                        my_bomb_sprite_info = {'tile': (bomb.current_tile_x, bomb.current_tile_y), 'range': self.ai_player.bomb_range, 'spawn_time': bomb.spawn_time}
            
            if my_bomb_sprite_info:
                bomb_data_for_escape = (my_bomb_sprite_info['tile'], my_bomb_sprite_info['range'])
                safe_spots = self.find_safe_tiles_nearby(ai_tile, max_search_depth=my_bomb_sprite_info['range'] + 2, avoid_specific_bomb_data=bomb_data_for_escape)
                if safe_spots:
                    retreat_target = random.choice(safe_spots)
                    path = self.bfs_find_path(ai_tile, retreat_target, True, True, step_future_check_seconds=0.05) # 極度謹慎
                    if path and len(path) > 1 :
                        self.current_path = path; self.current_path_index = 0; self.current_escape_target_tile = retreat_target
                    else: self.current_path = []
                else: self.current_path = []
            else: # 找不到自己的炸彈了 (可能已爆或出錯)
                self.ai_just_placed_bomb = False; self.change_state(AI_STATE_EVALUATE_SITUATION); return
        
        if not self.current_path:
            if self.ai_player: self.ai_player.is_moving = False


    def handle_engage_target_state(self): # 與格子移動系統兼容
        ai_tile = self._get_ai_current_tile()
        if ai_tile == (None,None) or not self.current_target_player_sprite or not self.current_target_player_sprite.is_alive:
            self.change_state(AI_STATE_EVALUATE_SITUATION); return

        player_tile = self._get_player_tile(self.current_target_player_sprite)
        if player_tile == (None,None):
            self.change_state(AI_STATE_EVALUATE_SITUATION); return

        # 如果路徑丟失或目標已不在路徑終點，重新規劃
        if not self.current_path or (len(self.current_path)>0 and self.current_path[-1] != player_tile):
            new_path = self.bfs_find_path(ai_tile, player_tile, True, True, step_future_check_seconds=0.25)
            if new_path: self.current_path = new_path; self.current_path_index = 0
            else: self.change_state(AI_STATE_EVALUATE_SITUATION); return
        
        if not self.current_path: self.change_state(AI_STATE_EVALUATE_SITUATION); return


        # 判斷是否放置炸彈 (基於格子距離)
        # current_path_index 是下一個要去的地方。所以 (len(path) - 1 - index) 是剩餘步數。
        # ai_tile 是 AI 目前的格子。
        
        # 如果AI就在玩家的格子上，或者在可以炸到玩家的位置
        can_bomb_now = False
        if ai_tile == player_tile:
            can_bomb_now = True
        elif self._is_tile_in_hypothetical_blast(player_tile[0], player_tile[1], ai_tile[0], ai_tile[1], self.ai_player.bomb_range):
             # 並且AI 當前位置是安全的（除了自己即將放的炸彈）
            if not self.is_tile_dangerous(ai_tile[0], ai_tile[1], True, True, 0.1):
                can_bomb_now = True
        
        # 或者，如果AI在路徑上的一個點，且這個點可以炸到路徑的終點（玩家位置）
        # 且這個點離玩家不遠
        if not can_bomb_now and self.current_path:
            # 檢查AI是否在其路徑的當前邏輯位置
            if self.current_path_index < len(self.current_path) and ai_tile == self.current_path[self.current_path_index]:
                remaining_steps = (len(self.current_path) - 1) - self.current_path_index
                if remaining_steps <= self.ai_player.bomb_range + 1: # 在炸彈範圍加一兩格內
                    # 檢查從當前格子放炸彈是否能炸到路徑終點的玩家
                    if self._is_tile_in_hypothetical_blast(player_tile[0], player_tile[1], ai_tile[0], ai_tile[1], self.ai_player.bomb_range):
                        if not self.is_tile_dangerous(ai_tile[0], ai_tile[1], True, True, 0.1):
                             can_bomb_now = True
        
        if can_bomb_now:
            if self.ai_player.bombs_placed_count < self.ai_player.max_bombs:
                if self.can_place_bomb_safely_at(ai_tile[0], ai_tile[1]):
                    # print(f"[AI ENGAGE] Player at {player_tile}. AI at {ai_tile}. Placing bomb.") # DEBUG
                    self.ai_player.place_bomb()
                    # ai_just_placed_bomb 和 last_bomb_placed_time 會在 Player.place_bomb 中設定
                    self.change_state(AI_STATE_TACTICAL_RETREAT) # 放完炸彈立刻撤退
                    return
        # 如果不能放炸彈，則會透過 move_along_path 繼續向玩家移動 (如果路徑存在)


    def handle_collect_powerup_state(self): # 與格子移動系統兼容
        ai_tile = self._get_ai_current_tile()
        if ai_tile == (None,None) or not self.current_target_item_sprite or not self.current_target_item_sprite.alive():
            self.change_state(AI_STATE_EVALUATE_SITUATION); return

        item_tile_x = self.current_target_item_sprite.rect.centerx // settings.TILE_SIZE
        item_tile_y = self.current_target_item_sprite.rect.centery // settings.TILE_SIZE
        item_tile = (item_tile_x, item_tile_y)

        if not self.current_path or (len(self.current_path)>0 and self.current_path[-1] != item_tile):
            new_path = self.bfs_find_path(ai_tile, item_tile, True, True, step_future_check_seconds=0.3)
            if new_path: self.current_path = new_path; self.current_path_index = 0
            else: self.change_state(AI_STATE_EVALUATE_SITUATION); return

        if not self.current_path: self.change_state(AI_STATE_EVALUATE_SITUATION); return
            
        if ai_tile == item_tile: # AI 已經在道具的格子上了
            # 道具拾取由 Game.update 中的碰撞檢測處理
            # AI 到達後，可以認為任務完成，重新評估
            # print(f"[AI COLLECT] Reached item tile {item_tile}. Item should be collected by Game logic. Re-evaluating.") # DEBUG
            self.current_path = [] # 清除路徑
            self.change_state(AI_STATE_EVALUATE_SITUATION)


    def handle_strategic_bombing_for_path_state(self): # 與格子移動系統兼容
        ai_tile = self._get_ai_current_tile()
        if ai_tile == (None,None) or not self.current_bombing_target_wall_sprite or \
           not self.current_bombing_target_wall_sprite.alive() or \
           (hasattr(self.current_bombing_target_wall_sprite, 'is_destroyed') and self.current_bombing_target_wall_sprite.is_destroyed) or \
           not self.bombing_spot_for_wall:
            self.change_state(AI_STATE_EVALUATE_SITUATION); return

        if not self.current_path or (len(self.current_path)>0 and self.current_path[-1] != self.bombing_spot_for_wall):
            new_path = self.bfs_find_path(ai_tile, self.bombing_spot_for_wall, True, True, step_future_check_seconds=0.3)
            if new_path: self.current_path = new_path; self.current_path_index = 0
            else: self.change_state(AI_STATE_EVALUATE_SITUATION); return
        
        if not self.current_path: self.change_state(AI_STATE_EVALUATE_SITUATION); return

        if ai_tile == self.bombing_spot_for_wall: # AI 已到達放置炸彈的地點
            if self.ai_player.bombs_placed_count < self.ai_player.max_bombs:
                if self.can_place_bomb_safely_at(ai_tile[0], ai_tile[1]):
                    # print(f"[AI BOMB_WALL] At bombing spot {ai_tile} for wall. Placing bomb.") # DEBUG
                    self.ai_player.place_bomb()
                    self.change_state(AI_STATE_TACTICAL_RETREAT)
                    return
                else: # 放置點不安全
                    # print(f"[AI BOMB_WALL] Bombing spot {ai_tile} is not safe to place bomb. Re-evaluating.") # DEBUG
                    self.current_path = [] # 清除去往不安全放置點的路徑
                    self.change_state(AI_STATE_EVALUATE_SITUATION)
                    return
            else: # 沒有炸彈了
                self.change_state(AI_STATE_EVALUATE_SITUATION)
                return


    def handle_await_opportunity_state(self): # 與格子移動系統兼容 (主要是不動)
        ai_tile = self._get_ai_current_tile()
        if ai_tile == (None,None) : self.change_state(AI_STATE_EVALUATE_SITUATION); return

        if self.ai_player: self.ai_player.is_moving = False # 確保等待時沒有行走動畫

        time_since_last_bomb = pygame.time.get_ticks() - self.last_bomb_placed_time
        # 等待時間可以稍微靈活一點，或者有其他觸發條件
        bomb_clear_time_estimate = settings.BOMB_TIMER + settings.EXPLOSION_DURATION + 300 #ms

        if time_since_last_bomb > bomb_clear_time_estimate:
            # print(f"[AI AWAIT] Bomb likely cleared (timeout: {time_since_last_bomb} > {bomb_clear_time_estimate}). Resetting flag.") # DEBUG
            self.ai_just_placed_bomb = False # 重置標記
            self.change_state(AI_STATE_EVALUATE_SITUATION)
        elif not self.is_tile_dangerous(ai_tile[0], ai_tile[1], True, True, 0.1) and \
             time_since_last_bomb > settings.BOMB_TIMER + settings.EXPLOSION_DURATION - 300: # 炸彈剛爆完，且目前位置安全
            # print(f"[AI AWAIT] Current tile {ai_tile} safe after explosion. Resetting flag.") # DEBUG
            self.ai_just_placed_bomb = False
            self.change_state(AI_STATE_EVALUATE_SITUATION)
        elif pygame.time.get_ticks() - self.state_start_time > bomb_clear_time_estimate + 1000: # 狀態本身的超時
            # print(f"[AI AWAIT] General timeout in AWAIT_OPPORTUNITY. Resetting flag.") # DEBUG
            self.ai_just_placed_bomb = False
            self.change_state(AI_STATE_EVALUATE_SITUATION)


    def handle_patrol_state(self): # 修改版：適應格子移動
        ai_tile = self._get_ai_current_tile()
        if ai_tile == (None,None): self.change_state(AI_STATE_EVALUATE_SITUATION); return

        if not self.current_path: # 如果沒有當前巡邏路徑，則尋找一個
            # print(f"[AI PATROL] No current patrol path from {ai_tile}. Finding new target.") # DEBUG
            possible_targets = []
            for r_idx in range(self.game.map_manager.tile_height):
                for c_idx in range(self.game.map_manager.tile_width):
                    if self.game.map_manager.is_walkable(c_idx, r_idx) and \
                       not self.is_tile_dangerous(c_idx, r_idx, True, True, 0.5): # 巡邏目標點本身不應太危險
                        distance = abs(c_idx - ai_tile[0]) + abs(r_idx - ai_tile[1])
                        if 3 < distance < 10 : # 找一個中等距離的點
                            possible_targets.append((c_idx, r_idx))
            
            patrol_path_found = False
            if possible_targets:
                random.shuffle(possible_targets)
                for target_patrol_tile in possible_targets[:3]: # 嘗試幾個候選點
                    path = self.bfs_find_path(ai_tile, target_patrol_tile, True, True, step_future_check_seconds=0.4)
                    if path and len(path) > 1: # 確保路徑有效且不是原地
                        self.current_path = path
                        self.current_path_index = 0
                        self.current_action_target_tile = target_patrol_tile # 記錄巡邏的最終目標
                        self.stuck_in_patrol_start_time = 0 # 重置計時器
                        patrol_path_found = True
                        # print(f"[AI PATROL] Found patrol path to {target_patrol_tile}") # DEBUG
                        break 
            
            if not patrol_path_found: # 如果找不到合適的遠距離巡邏點，嘗試「擺動」到相鄰格子
                # print(f"[AI PATROL] No distant patrol path. Attempting wiggle.") # DEBUG
                found_wiggle_move = False
                shuffled_directions = list(DIRECTIONS.values())
                random.shuffle(shuffled_directions)
                for dx, dy in shuffled_directions:
                    next_x, next_y = ai_tile[0] + dx, ai_tile[1] + dy
                    if self.game.map_manager.is_walkable(next_x, next_y) and \
                       not self.is_tile_dangerous(next_x, next_y, True, True, 0.1): # 擺動目標點的即時安全檢查
                        self.current_path = [ai_tile, (next_x, next_y)] # 創建一個只有兩步的路徑
                        self.current_path_index = 0
                        self.current_action_target_tile = (next_x, next_y)
                        self.stuck_in_patrol_start_time = 0
                        found_wiggle_move = True
                        # print(f"[AI PATROL] Found wiggle path to {(next_x,next_y)}") # DEBUG
                        break
                if not found_wiggle_move:
                    # print(f"[AI PATROL] No wiggle move found. AI stationary.") # DEBUG
                    if self.ai_player: self.ai_player.is_moving = False
                    if self.stuck_in_patrol_start_time == 0: self.stuck_in_patrol_start_time = pygame.time.get_ticks()

        elif self.current_action_target_tile and ai_tile == self.current_action_target_tile: # 已到達巡邏目標點
            # print(f"[AI PATROL] Reached patrol target {self.current_action_target_tile}. Re-evaluating.") # DEBUG
            self.current_path = [] # 清除當前路徑，以便下次重新規劃
            self.change_state(AI_STATE_EVALUATE_SITUATION)
        # 如果有路徑，且未到達目標，則 move_along_path 會處理移動


    def move_along_path(self): # 重寫以適應格子移動
        if not self.ai_player or not self.ai_player.is_alive:
            self.current_path = []
            return True

        # 如果 AI 正在執行上一個格子的移動動畫 (action_timer > 0)，則等待
        if self.ai_player.action_timer > 0:
            # print(f"[AI MOVE] Player action_timer ({self.ai_player.action_timer:.2f}) > 0. Waiting for current move to animate.") # DEBUG
            return False # 表示移動正在進行中（動畫層面），AIController 等待

        if not self.current_path:
            if self.ai_player: self.ai_player.is_moving = False # 確保動畫停止
            return True # 路徑已空或處理完畢

        ai_current_logic_tile_x = self.ai_player.tile_x
        ai_current_logic_tile_y = self.ai_player.tile_y

        # 確保路徑索引有效
        if not (0 <= self.current_path_index < len(self.current_path)):
            # print(f"[AI MOVE WARN] Invalid path index {self.current_path_index} for path len {len(self.current_path)}. Clearing path.") # DEBUG
            self.current_path = []; self.current_path_index = 0
            if self.ai_player: self.ai_player.is_moving = False
            return True

        path_expected_current_tile = self.current_path[self.current_path_index]

        # 同步AI的邏輯位置與路徑期望位置
        if ai_current_logic_tile_x != path_expected_current_tile[0] or \
           ai_current_logic_tile_y != path_expected_current_tile[1]:
            # print(f"[AI MOVE WARN] AI at ({ai_current_logic_tile_x},{ai_current_logic_tile_y}), path expects ({path_expected_current_tile}). Attempting re-sync.") # DEBUG
            try:
                self.current_path_index = self.current_path.index((ai_current_logic_tile_x, ai_current_logic_tile_y), self.current_path_index)
                # print(f"  Resynced path index to {self.current_path_index}.") # DEBUG
            except ValueError:
                # print(f"  Resync failed. Clearing path.") # DEBUG
                self.current_path = []; self.current_path_index = 0
                if self.ai_player: self.ai_player.is_moving = False
                return True # 路徑失效

        # 如果已經在路徑的最後一個格子
        if self.current_path_index >= len(self.current_path) - 1:
            # print(f"[AI MOVE] Already at the end of path: {self.current_path[self.current_path_index]}") # DEBUG
            self.current_path = []
            self.current_path_index = 0
            if self.ai_player: self.ai_player.is_moving = False
            return True

        # 獲取路徑上的下一個目標格子
        next_target_tile_x, next_target_tile_y = self.current_path[self.current_path_index + 1]
        
        # 計算移動方向 (dx, dy)
        dx = next_target_tile_x - ai_current_logic_tile_x
        dy = next_target_tile_y - ai_current_logic_tile_y

        # print(f"[AI MOVE] AI at ({ai_current_logic_tile_x},{ai_current_logic_tile_y}). Path index {self.current_path_index}. Next target: ({next_target_tile_x},{next_target_tile_y}). Moving by ({dx},{dy}).") # DEBUG

        # 命令 Player 物件移動到下一個格子
        moved_successfully = self.ai_player.attempt_move_to_tile(dx, dy)

        if moved_successfully:
            # 成功發起移動，Player.attempt_move_to_tile 會更新 player.tile_x/y
            # 並設定 player.is_moving = True 和 action_timer
            # AIController 的 current_path_index 現在應該指向 AI *剛剛移動到* 或 *正在動畫去往* 的格子
            # 所以，如果 attempt_move_to_tile 成功，AI 的邏輯位置 tile_x/y 已經是 next_target_tile 了。
            # 因此，我們需要將 path_index 推進到這個新到達的格子。
            self.current_path_index += 1 
            # print(f"  AI successfully initiated move to ({next_target_tile_x},{next_target_tile_y}). New path index: {self.current_path_index}.") # DEBUG
            return False # 移動已開始，但路徑可能尚未結束 (除非這是最後一步，會在下一輪檢查中處理)
        else:
            # print(f"  AI failed to move from ({ai_current_logic_tile_x},{ai_current_logic_tile_y}) by ({dx},{dy}). Path likely blocked. Clearing path.") # DEBUG
            # 如果 Player.attempt_move_to_tile 返回 False (例如撞牆，或目標無效)
            self.current_path = [] # 清除路徑，迫使 AI 重新評估
            self.current_path_index = 0
            if self.ai_player: self.ai_player.is_moving = False
            return True # 視為路徑處理失敗/結束


    def update(self):
        current_time = pygame.time.get_ticks()
        if not self.ai_player or not self.ai_player.is_alive:
            if self.current_state != AI_STATE_DEAD: self.change_state(AI_STATE_DEAD)
            return

        # 決策邏輯
        if current_time - self.last_decision_time >= self.ai_decision_interval:
            self.last_decision_time = current_time
            # print(f"--- AI Deciding (Time: {current_time}, State: {self.current_state}, PathLen: {len(self.current_path)}, AI Tile: {self._get_ai_current_tile()}) ---") # DEBUG
            
            if self.current_state not in [AI_STATE_AWAIT_OPPORTUNITY, AI_STATE_CRITICAL_ESCAPE, AI_STATE_TACTICAL_RETREAT] or \
               (self.current_state == AI_STATE_AWAIT_OPPORTUNITY and pygame.time.get_ticks() - self.state_start_time > (settings.BOMB_TIMER + settings.EXPLOSION_DURATION + 1500)): # AWAIT 超時
                if self.current_state != AI_STATE_EVALUATE_SITUATION:
                     self.change_state(AI_STATE_EVALUATE_SITUATION) # 進入評估
            
            self.update_state_machine() # 決定新狀態和可能的新路徑 (透過 change_state)
            self.perform_current_state_action() # 執行新狀態的初始化邏輯 (也可能修改路徑)
            # print(f"--- AI Decided (New State: {self.current_state}, PathLen: {len(self.current_path)}) ---") # DEBUG
        
        # 移動執行邏輯
        # 只有當 AI 有路徑，並且 Player 物件不在格子移動動畫中時，才嘗試執行路徑的下一步
        if self.current_path and self.ai_player and (self.ai_player.action_timer <= 0):
            path_ended_or_failed = self.move_along_path() # move_along_path 會呼叫 player.attempt_move_to_tile
            
            if path_ended_or_failed: # 如果路徑走完或失敗
                # print(f"[AI UPDATE] Path ended or failed for state {self.current_state}. Forcing re-evaluation.") # DEBUG
                # 強制立即重新決策，而不是等待下一個 decision_interval
                self.last_decision_time = pygame.time.get_ticks() - self.ai_decision_interval -1 
                if self.ai_player: self.ai_player.is_moving = False # 確保動畫停止
                # current_path 應該已在 move_along_path 中被清除
        
        # 如果 AI 沒有路徑，並且不在動作動畫中，確保其 is_moving 為 False
        elif not self.current_path and self.ai_player and (self.ai_player.action_timer <= 0):
            if self.ai_player.is_moving: # 如果因為某些原因 is_moving 還是 True
                self.ai_player.is_moving = False
                # print(f"[AI UPDATE] AI has no path and action_timer is zero. Set is_moving=False.") # DEBUG


    def debug_draw_path(self, surface): # 與格子移動系統兼容
        if not self.ai_player: return

        # 繪製 AI 當前邏輯格子 (方便觀察)
        ai_tile_now = self._get_ai_current_tile()
        if ai_tile_now != (None,None) :
            rect = pygame.Rect(ai_tile_now[0] * settings.TILE_SIZE, ai_tile_now[1] * settings.TILE_SIZE, settings.TILE_SIZE, settings.TILE_SIZE)
            pygame.draw.rect(surface, (0, 255, 255, 50), rect, 1) # 青色框標記AI邏輯位置

        if self.current_path and len(self.current_path) > 0 :
            path_points = []
            # 路徑的第一點應該是 AI 當前格子，或者 AI 即將離開的格子
            # self.current_path_index 指向 AI *已經移到* 的路徑點
            # 所以要繪製的路徑是從 current_path[current_path_index] 到終點
            
            # 確保索引有效
            valid_path_segment = []
            if 0 <= self.current_path_index < len(self.current_path):
                valid_path_segment = self.current_path[self.current_path_index:]
            elif not self.current_path and self.current_path_index == 0 and len(self.current_path) > 0 : #剛設定好路徑，還沒開始走
                 valid_path_segment = self.current_path
            
            if len(valid_path_segment) > 0:
                 # 將路徑的起始點強制設為 AI 的當前 tile_x, tile_y，以確保線條從 AI 當前位置開始畫
                start_draw_point = (ai_tile_now[0] * settings.TILE_SIZE + settings.TILE_SIZE // 2,
                                    ai_tile_now[1] * settings.TILE_SIZE + settings.TILE_SIZE // 2)
                
                path_points.append(start_draw_point)
                
                # 只加入路徑中從AI下一個目標點開始的部分
                idx_offset = 0
                if valid_path_segment[0] == ai_tile_now and len(valid_path_segment)>1: #如果路徑的第一點就是AI當前位置
                    idx_offset = 1 # 那我們從路徑的第二個點開始加入pixel座標

                for i in range(idx_offset, len(valid_path_segment)):
                    t = valid_path_segment[i]
                    path_points.append((t[0]*settings.TILE_SIZE + settings.TILE_SIZE//2, t[1]*settings.TILE_SIZE + settings.TILE_SIZE//2))

                if len(path_points) > 1:
                    try:
                        pygame.draw.lines(surface, (255,0,255,180), False, path_points, 3) # 紫紅色路徑
                    except TypeError:
                        pygame.draw.lines(surface, (255,0,255), False, path_points, 3)

                # 標記路徑的最終目標點 (如果路徑非空)
                final_target_in_path = self.current_path[-1]
                pygame.draw.circle(surface, (0,0,255,200), 
                                   (final_target_in_path[0]*settings.TILE_SIZE+settings.TILE_SIZE//2, 
                                    final_target_in_path[1]*settings.TILE_SIZE+settings.TILE_SIZE//2),
                                   settings.TILE_SIZE//4, 3) # 藍色圓圈標記路徑終點
        
        # 標記 AIController 的各種目標 (current_action_target_tile 等)
        display_target_tile, display_color = None, settings.RED
        # ... (這部分邏輯與之前類似，但要確保獲取 target_player_sprite 的 tile_x/y)
        player_display_tile = self._get_player_tile(self.current_target_player_sprite)

        if self.current_state == AI_STATE_ENGAGE_TARGET and player_display_tile:
            display_target_tile, display_color = player_display_tile, (255,100,0,200) # 橘紅色標記攻擊目標
        elif self.current_state == AI_STATE_COLLECT_POWERUP and self.current_target_item_sprite and self.current_target_item_sprite.alive():
             item_t_x = self.current_target_item_sprite.rect.centerx // settings.TILE_SIZE
             item_t_y = self.current_target_item_sprite.rect.centery // settings.TILE_SIZE
             display_target_tile, display_color = (item_t_x, item_t_y), (0,200,0,200) # 亮綠色標記道具
        elif self.current_state == AI_STATE_STRATEGIC_BOMBING_FOR_PATH and self.bombing_spot_for_wall:
            display_target_tile = self.bombing_spot_for_wall # 目標是去放置炸彈的位置
            display_color = (128,0,128,200) # 深紫色標記炸牆放置點
            if self.current_bombing_target_wall_sprite: # 同時標記要炸的牆
                 wall_r = pygame.Rect(self.current_bombing_target_wall_sprite.tile_x * settings.TILE_SIZE,
                                      self.current_bombing_target_wall_sprite.tile_y * settings.TILE_SIZE,
                                      settings.TILE_SIZE, settings.TILE_SIZE)
                 pygame.draw.rect(surface, (200,0,200,100), wall_r, 2)
        elif self.current_escape_target_tile and (self.current_state == AI_STATE_CRITICAL_ESCAPE or self.current_state == AI_STATE_TACTICAL_RETREAT) :
            display_target_tile = self.current_escape_target_tile
            display_color = (255,0,0,200) if self.current_state == AI_STATE_CRITICAL_ESCAPE else (0,0,200,200) # 紅色/深藍色標記逃跑點
        elif self.current_state == AI_STATE_PATROL and self.current_action_target_tile:
             display_target_tile = self.current_action_target_tile
             display_color = (100,100,100,150) # 灰色標記巡邏點

        if display_target_tile and display_target_tile != (None,None):
            pygame.draw.circle(surface, display_color, 
                               (display_target_tile[0]*settings.TILE_SIZE+settings.TILE_SIZE//2, 
                                display_target_tile[1]*settings.TILE_SIZE+settings.TILE_SIZE//2), 
                               settings.TILE_SIZE//3, 3)