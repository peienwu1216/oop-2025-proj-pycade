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
        self.target_item = None                 # 目標道具 Sprite
        self.escape_target_tile = None          # 逃跑目標格子 (x, y)
        
        self.last_bomb_placed_time = 0          # AI 上次放置炸彈的時間
        self.ai_placed_bomb_recently = False    # AI 是否剛放了炸彈

        # 用於BFS調試繪圖 (可選)
        self.bfs_visited_visual = []

        print(f"AIController initialized for Player ID: {id(self.ai_player)}. Targeting Player ID: {id(self.target_player) if self.target_player else 'None'}")

    def change_state(self, new_state, target_player=None, target_item=None, escape_tile=None):
        """切換AI狀態並重置相關變數"""
        # 只有在狀態真正改變，或特定狀態的目標改變時才執行
        if self.current_state != new_state or \
           (new_state == AI_STATE_FETCH_ITEMS and target_item != self.target_item) or \
           (new_state == AI_STATE_ATTACK_PLAYER and target_player != self.target_player and new_state == AI_STATE_ATTACK_PLAYER) or \
           (new_state == AI_STATE_ESCAPE and escape_tile != self.escape_target_tile):

            # print(f"AI (Player {id(self.ai_player)}) state: {self.current_state} -> {new_state}")
            self.current_state = new_state
            self.state_start_time = pygame.time.get_ticks()
            self.current_path = [] # 清除舊路徑
            self.current_path_index = 0
            
            # 更新目標
            self.target_player = target_player if target_player else (self.game.player1 if self.current_state == AI_STATE_ATTACK_PLAYER else None)
            self.target_item = target_item if self.current_state == AI_STATE_FETCH_ITEMS else None
            self.escape_target_tile = escape_tile if self.current_state == AI_STATE_ESCAPE else None

            # if self.target_item: print(f"   Targeting item: {self.target_item.type} at tile ({self.target_item.rect.centerx//settings.TILE_SIZE},{self.target_item.rect.centery//settings.TILE_SIZE})")
            # if self.target_player and self.current_state == AI_STATE_ATTACK_PLAYER: print(f"   Targeting player: {id(self.target_player)}")
            # if self.escape_target_tile: print(f"   Escape target tile: {self.escape_target_tile}")

    def update_state_machine(self):
        """AI的核心決策邏輯，決定當前應該處於哪個狀態 (參考C++報告的優先級順序)"""
        if not self.ai_player.is_alive:
            return # 如果AI已死亡，不進行決策

        current_ai_tile = (self.ai_player.rect.centerx // settings.TILE_SIZE,
                           self.ai_player.rect.centery // settings.TILE_SIZE)

        # --- 優先級 1: ESCAPE ---
        if self.is_tile_dangerous(current_ai_tile[0], current_ai_tile[1], future_seconds=1.0): # 檢查未來1秒的危險
            # 即使已在逃跑，如果當前格子仍然危險，或者目標逃跑點不再安全，也需要重新評估
            needs_new_escape_plan = True
            if self.current_state == AI_STATE_ESCAPE:
                if self.escape_target_tile and not self.is_tile_dangerous(self.escape_target_tile[0], self.escape_target_tile[1], future_seconds=0.1):
                     # 如果目標逃跑點仍然安全，且有路徑，則繼續逃跑
                     if self.current_path and len(self.current_path) > 1 : # 有路徑且不只一格(代表還沒到)
                         next_step_on_path = self.current_path[self.current_path_index + 1] if self.current_path_index + 1 < len(self.current_path) else current_ai_tile
                         if not self.is_tile_dangerous(next_step_on_path[0], next_step_on_path[1], future_seconds=0.1):
                            needs_new_escape_plan = False # 繼續當前逃跑計劃
            
            if needs_new_escape_plan:
                # print(f"[AI DECISION] Player {id(self.ai_player)} at {current_ai_tile} is in DANGER or current escape is bad!")
                safe_escape_spots = self.find_safe_tiles_nearby(current_ai_tile)
                if safe_escape_spots:
                    # 選擇一個安全點 (可以加入更複雜的選擇邏輯，例如離人類玩家最遠的)
                    chosen_escape_tile = random.choice(safe_escape_spots) 
                    path_to_safe_spot = self.bfs_find_path(current_ai_tile, chosen_escape_tile, True, True)
                    if path_to_safe_spot:
                        self.current_path = path_to_safe_spot
                        self.current_path_index = 0
                        self.change_state(AI_STATE_ESCAPE, escape_tile=chosen_escape_tile)
                        return
                # 如果找不到安全點或路徑，AI可能會卡住或做出隨機移動（IDLE狀態的行為）
                print(f"[AI CRITICAL] Player {id(self.ai_player)} in danger at {current_ai_tile} but cannot find/reach a safe spot!")
                self.change_state(AI_STATE_IDLE) # 無法逃脫，進入IDLE（可能隨機移動）
                return # 結束本次決策

        # 如果當前在逃跑，但腳下已經安全了，可以考慮切換狀態
        if self.current_state == AI_STATE_ESCAPE:
            if not self.is_tile_dangerous(current_ai_tile[0], current_ai_tile[1], future_seconds=0.1):
                # print(f"[AI DECISION] Player {id(self.ai_player)} at {current_ai_tile} is no longer in immediate danger. Switching from ESCAPE.")
                self.change_state(AI_STATE_IDLE) # 逃脫成功，轉為IDLE重新評估
                # 注意：這裡可能會導致AI在安全和危險邊緣反覆橫跳，需要更細緻的條件
            else:
                return # 繼續執行當前的逃跑計劃

        # --- 優先級 2: WAIT_EXPLOSION ---
        if self.ai_placed_bomb_recently:
            time_since_bomb = pygame.time.get_ticks() - self.last_bomb_placed_time
            # 等待直到炸彈爆炸並且火焰消失一段時間
            if time_since_bomb < (settings.BOMB_TIMER + settings.EXPLOSION_DURATION + 200): # 額外200ms緩衝
                if self.current_state != AI_STATE_WAIT_EXPLOSION:
                     # 確保AI當前位置安全，否則應該由ESCAPE處理
                    if not self.is_tile_dangerous(current_ai_tile[0], current_ai_tile[1], check_bombs=True, check_explosions=True, future_seconds=0.5):
                        self.change_state(AI_STATE_WAIT_EXPLOSION)
                return # 等待時不做其他決策
            else:
                self.ai_placed_bomb_recently = False # 炸彈處理完畢

        # --- 優先級 3: ATTACK_PLAYER ---
        if self.target_player and self.target_player.is_alive:
            player_tile = (self.target_player.rect.centerx // settings.TILE_SIZE,
                           self.target_player.rect.centery // settings.TILE_SIZE)
            
            # 判斷是否適合攻擊 (例如，玩家在一定範圍內，AI有炸彈，且放炸彈後能安全撤離)
            # 簡化版：如果玩家在附近且有路徑
            path_to_player = self.bfs_find_path(current_ai_tile, player_tile, True, True)
            if path_to_player and len(path_to_player) <= self.ai_player.bomb_range + 2 : # 如果AI在炸彈波及範圍+安全距離內
                # 判斷是否可以安全地放置炸彈 (can_place_bomb_safely 是一個理想的方法)
                if self.can_place_bomb_safely_at(current_ai_tile[0], current_ai_tile[1]):
                    if self.current_state != AI_STATE_ATTACK_PLAYER or not self.current_path: # 如果不是攻擊狀態或沒有攻擊路徑
                        self.current_path = path_to_player # 可以選擇追擊或直接在當前位置放炸彈
                        self.current_path_index = 0
                        self.change_state(AI_STATE_ATTACK_PLAYER, target_player=self.target_player)
                    return # 進入或保持攻擊狀態

        # --- 優先級 4: FETCH_ITEMS ---
        closest_item = self.find_closest_item()
        if closest_item:
            item_tile = (closest_item.rect.centerx // settings.TILE_SIZE,
                         closest_item.rect.centery // settings.TILE_SIZE)
            # 如果當前不是正在拾取這個道具，或者路徑已完成/不存在
            if self.current_state != AI_STATE_FETCH_ITEMS or self.target_item != closest_item or not self.current_path:
                path_to_item = self.bfs_find_path(current_ai_tile, item_tile, True, True)
                if path_to_item:
                    self.current_path = path_to_item
                    self.current_path_index = 0
                    self.change_state(AI_STATE_FETCH_ITEMS, target_item=closest_item)
                    return

        # --- DEFAULT: IDLE ---
        if not self.current_path: # 如果沒有任何任務路徑
             if self.current_state != AI_STATE_IDLE:
                self.change_state(AI_STATE_IDLE)
        
        # 如果長時間處於IDLE狀態，可以強制執行IDLE行為（例如隨機移動）
        if self.current_state == AI_STATE_IDLE and pygame.time.get_ticks() - self.state_start_time > 3000: # 3秒
            self.state_start_time = pygame.time.get_ticks() # 重置計時器，handle_idle_state 會嘗試移動

    def perform_current_state_action(self):
        """根據當前狀態執行具體行為"""
        if not self.ai_player.is_alive: return

        if self.current_state == AI_STATE_IDLE:
            self.handle_idle_state()
        elif self.current_state == AI_STATE_ESCAPE:
            self.handle_escape_state()
        elif self.current_state == AI_STATE_ATTACK_PLAYER:
            self.handle_attack_player_state()
        elif self.current_state == AI_STATE_FETCH_ITEMS:
            self.handle_fetch_items_state()
        elif self.current_state == AI_STATE_WAIT_EXPLOSION:
            self.handle_wait_explosion_state()

    def handle_idle_state(self):
        """閒置狀態：隨機移動到鄰近安全格子"""
        if not self.current_path: # 只有在沒有當前路徑時才嘗試尋找新路徑
            ai_tile_x = self.ai_player.rect.centerx // settings.TILE_SIZE
            ai_tile_y = self.ai_player.rect.centery // settings.TILE_SIZE
            possible_moves = []
            for dx, dy in DIRECTIONS.values():
                next_x, next_y = ai_tile_x + dx, ai_tile_y + dy
                if self.game.map_manager.is_walkable(next_x, next_y) and \
                   not self.is_tile_dangerous(next_x, next_y, True, True, 0.5):
                    possible_moves.append((next_x, next_y))
            if possible_moves:
                target_tile = random.choice(possible_moves)
                path = self.bfs_find_path((ai_tile_x, ai_tile_y), target_tile, True, True)
                if path:
                    self.current_path = path
                    self.current_path_index = 0
        # 如果有路徑，move_along_path 會處理移動

    def handle_escape_state(self):
        """逃跑狀態：沿著已計算的安全路徑移動"""
        ai_current_tile = (self.ai_player.rect.centerx // settings.TILE_SIZE,
                           self.ai_player.rect.centery // settings.TILE_SIZE)
        if not self.current_path: # 如果沒有路徑（例如，update_state_machine未能找到）
            # print(f"[AI ESCAPE] No path in escape state. Will re-evaluate.")
            self.last_decision_time = 0 # 強制立即重新決策
            return
        # 檢查是否已到達目標且該目標安全
        if self.escape_target_tile and ai_current_tile == self.escape_target_tile:
            if not self.is_tile_dangerous(ai_current_tile[0], ai_current_tile[1], True, True, 0.1):
                self.change_state(AI_STATE_IDLE) # 到達安全點
            else: # 目標點不再安全
                self.current_path = [] # 清除路徑，強制重新規劃
                self.escape_target_tile = None
                self.last_decision_time = 0
        # move_along_path 由主 update 循環調用

    def handle_attack_player_state(self):
        """攻擊狀態：追蹤玩家，在合適時機放置炸彈"""
        ai_current_tile = (self.ai_player.rect.centerx // settings.TILE_SIZE,
                           self.ai_player.rect.centery // settings.TILE_SIZE)

        if not self.target_player or not self.target_player.is_alive:
            self.change_state(AI_STATE_IDLE) # 目標消失
            return

        player_tile = (self.target_player.rect.centerx // settings.TILE_SIZE,
                       self.target_player.rect.centery // settings.TILE_SIZE)

        # 如果沒有路徑，或者當前路徑的最終目標不是人類玩家，則重新計算路徑
        recalculate_path = False
        if not self.current_path:
            recalculate_path = True
        elif self.current_path[-1] != player_tile: # 路徑的終點不是當前玩家位置
             recalculate_path = True
        
        if recalculate_path:
            path_to_player = self.bfs_find_path(ai_current_tile, player_tile, True, True)
            if path_to_player:
                self.current_path = path_to_player
                self.current_path_index = 0
            else: # 沒有路徑到達玩家
                self.change_state(AI_STATE_IDLE) # 放棄攻擊
                return
        
        # 判斷是否放置炸彈 (C++中的 shouldPlaceBombToAttack 和 canEscapeAfterBomb 的組合邏輯)
        # 簡化條件：如果AI在玩家附近 (例如路徑長度小於等於AI炸彈範圍)，並且AI有多餘的炸彈，並且當前位置放炸彈後能安全撤離
        if self.current_path and len(self.current_path) -1 - self.current_path_index <= self.ai_player.bomb_range +1 : # 離玩家很近
            if self.ai_player.bombs_placed_count < self.ai_player.max_bombs:
                if self.can_place_bomb_safely_at(ai_current_tile[0], ai_current_tile[1]):
                    self.ai_player.place_bomb() # AI放置炸彈
                    # place_bomb 內部會設置 self.ai_placed_bomb_recently = True
                    # update_state_machine 會在下一輪檢測到並可能切換到 ESCAPE 或 WAIT_EXPLOSION
                    print(f"[AI ATTACK] Player {id(self.ai_player)} placed bomb targeting Player {id(self.target_player)}.")
                    # 放置炸彈後，AI應立即計算逃跑路徑
                    self.current_path = [] # 清除追擊路徑
                    self.last_decision_time = 0 # 強制立即重新決策 (可能會進入ESCAPE)
                    return 
        # 如果有路徑但還沒到放炸彈的距離，move_along_path 會處理移動

    def handle_fetch_items_state(self):
        """拾取道具狀態：沿路徑移動到道具"""
        ai_current_tile = (self.ai_player.rect.centerx // settings.TILE_SIZE,
                           self.ai_player.rect.centery // settings.TILE_SIZE)
        if not self.target_item or not self.target_item.alive():
            self.change_state(AI_STATE_IDLE) # 道具消失
            return

        item_tile = (self.target_item.rect.centerx // settings.TILE_SIZE,
                     self.target_item.rect.centery // settings.TILE_SIZE)

        if not self.current_path or self.current_path[-1] != item_tile: # 如果沒有路徑或路徑目標不對
            path_to_item = self.bfs_find_path(ai_current_tile, item_tile, True, True)
            if path_to_item:
                self.current_path = path_to_item
                self.current_path_index = 0
            else: # 找不到路徑到道具
                self.change_state(AI_STATE_IDLE)
                return
        
        # 如果AI已經在道具的格子上，碰撞檢測應該會處理拾取
        if ai_current_tile == item_tile:
            # 通常碰撞檢測會先發生，道具會消失。這裡作為一個確認。
            if not self.target_item.alive(): # 道具被撿了
                self.change_state(AI_STATE_IDLE)
        # move_along_path 由主 update 循環調用

    def handle_wait_explosion_state(self):
        """等待炸彈爆炸狀態：確保自身安全，等待爆炸結束"""
        ai_current_tile = (self.ai_player.rect.centerx // settings.TILE_SIZE,
                           self.ai_player.rect.centery // settings.TILE_SIZE)
        
        # 確保AI當前位置是安全的，如果不是，應立即觸發ESCAPE (由update_state_machine處理)
        if self.is_tile_dangerous(ai_current_tile[0], ai_current_tile[1], check_bombs=True, check_explosions=True, future_seconds=0.5):
            print(f"[AI WAIT] AI at {ai_current_tile} became dangerous while waiting. Forcing ESCAPE re-evaluation.")
            self.last_decision_time = 0 # 強制重新決策
            return # update_state_machine 會切換到 ESCAPE

        # 檢查炸彈是否已經處理完畢
        if not self.ai_placed_bomb_recently: # 標誌由 bomb_exploded_feedback 或 update_state_machine 重置
             # print(f"[AI WAIT] Bomb has exploded. Switching to IDLE from WAIT_EXPLOSION.")
             self.change_state(AI_STATE_IDLE)
        # AI 在此狀態下可以選擇靜止，或者移動到一個預設的更安全的位置（如果當前位置只是“還行”）
        # 目前的實現是，如果安全就原地等待，依賴 ESCAPE 處理突發危險

    def find_closest_item(self):
        # ... (此方法之前已提供，保持不變) ...
        if not self.game.items_group: return None
        closest_item_sprite = None
        shortest_path_len = float('inf')
        ai_tile_x = self.ai_player.rect.centerx // settings.TILE_SIZE
        ai_tile_y = self.ai_player.rect.centery // settings.TILE_SIZE
        for item_sprite in self.game.items_group:
            if not item_sprite.alive(): continue
            item_tile_x = item_sprite.rect.centerx // settings.TILE_SIZE
            item_tile_y = item_sprite.rect.centery // settings.TILE_SIZE
            path_to_item = self.bfs_find_path((ai_tile_x, ai_tile_y), (item_tile_x, item_tile_y), True, True)
            if path_to_item:
                path_len = len(path_to_item)
                if path_len < shortest_path_len:
                    shortest_path_len = path_len
                    closest_item_sprite = item_sprite
        return closest_item_sprite


    def bfs_find_path(self, start_tile, end_tile_or_tiles, avoid_danger_from_bombs=True, avoid_current_explosions=True):
        # ... (此方法之前已提供並修正，保持不變) ...
        self.bfs_visited_visual = []
        queue = deque([(start_tile, [start_tile])])
        visited = {start_tile}
        map_mgr = self.game.map_manager
        targets = []
        if isinstance(end_tile_or_tiles, list): targets.extend(end_tile_or_tiles)
        else: targets.append(end_tile_or_tiles)
        if not targets: return []
        while queue:
            (current_x, current_y), path_to_current = queue.popleft()
            self.bfs_visited_visual.append((current_x, current_y))
            if (current_x, current_y) in targets: return path_to_current
            for _, (dx, dy) in DIRECTIONS.items():
                next_x, next_y = current_x + dx, current_y + dy
                if (next_x, next_y) not in visited:
                    if map_mgr.is_walkable(next_x, next_y):
                        is_dangerous = self.is_tile_dangerous(next_x, next_y, check_bombs=avoid_danger_from_bombs, check_explosions=avoid_current_explosions)
                        if is_dangerous: continue
                        visited.add((next_x, next_y))
                        new_path = list(path_to_current)
                        new_path.append((next_x, next_y))
                        queue.append(((next_x, next_y), new_path))
        return []

    def move_along_path(self):
        # ... (此方法之前已提供並修正，保持不變) ...
        if not self.current_path or self.current_path_index >= len(self.current_path):
            self.current_path = [] 
            self.current_path_index = 0
            self.ai_player.vx, self.ai_player.vy = 0, 0 
            return False
        if self.current_path_index + 1 >= len(self.current_path):
            self.current_path = []
            self.current_path_index = 0
            self.ai_player.vx, self.ai_player.vy = 0, 0
            return False
        next_target_tile_in_path_x, next_target_tile_in_path_y = self.current_path[self.current_path_index + 1]
        current_ai_pixel_center_x = self.ai_player.rect.centerx
        current_ai_pixel_center_y = self.ai_player.rect.centery
        target_pixel_center_x = next_target_tile_in_path_x * settings.TILE_SIZE + settings.TILE_SIZE // 2
        target_pixel_center_y = next_target_tile_in_path_y * settings.TILE_SIZE + settings.TILE_SIZE // 2
        delta_x_pixel = target_pixel_center_x - current_ai_pixel_center_x
        delta_y_pixel = target_pixel_center_y - current_ai_pixel_center_y
        if abs(delta_x_pixel) < self.ai_player.speed / 2 and abs(delta_y_pixel) < self.ai_player.speed / 2 : # 更寬鬆的到達判斷
            self.ai_player.rect.centerx = target_pixel_center_x
            self.ai_player.rect.centery = target_pixel_center_y
            self.ai_player.vx, self.ai_player.vy = 0, 0 
            self.current_path_index += 1
            if self.current_path_index + 1 >= len(self.current_path):
                self.current_path = []
                self.current_path_index = 0
            return True 
        else:
            vec = pygame.math.Vector2(delta_x_pixel, delta_y_pixel)
            if vec.length_squared() > 0:
                vec.normalize_ip()
                self.ai_player.vx = vec.x * self.ai_player.speed
                self.ai_player.vy = vec.y * self.ai_player.speed
            else:
                self.ai_player.vx, self.ai_player.vy = 0,0
        return False

    def is_tile_dangerous(self, tile_x, tile_y, check_bombs=True, check_explosions=True, future_seconds=settings.BOMB_TIMER / 1000.0 + 0.3):
        # ... (此方法之前已提供並修正，保持不變) ...
        target_pixel_x = tile_x * settings.TILE_SIZE + settings.TILE_SIZE // 2
        target_pixel_y = tile_y * settings.TILE_SIZE + settings.TILE_SIZE // 2
        if check_explosions:
            for explosion in self.game.explosions_group:
                if explosion.rect.collidepoint(target_pixel_x, target_pixel_y): return True
        if check_bombs:
            for bomb in self.game.bombs_group:
                if bomb.exploded: continue
                time_until_explosion_ms = (bomb.spawn_time + bomb.timer) - pygame.time.get_ticks()
                if 0 < time_until_explosion_ms < future_seconds * 1000:
                    bomb_center_x, bomb_center_y = bomb.current_tile_x, bomb.current_tile_y
                    bomb_range = bomb.placed_by_player.bomb_range
                    if bomb_center_x == tile_x and bomb_center_y == tile_y: return True
                    if bomb_center_y == tile_y and abs(bomb_center_x - tile_x) <= bomb_range:
                        blocked = False; step = 1 if tile_x > bomb_center_x else -1
                        for i_check in range(1, abs(bomb_center_x - tile_x)):
                            if self.game.map_manager.is_solid_wall_at(bomb_center_x + i_check * step, bomb_center_y): blocked = True; break
                        if not blocked: return True
                    if bomb_center_x == tile_x and abs(bomb_center_y - tile_y) <= bomb_range:
                        blocked = False; step = 1 if tile_y > bomb_center_y else -1
                        for i_check in range(1, abs(bomb_center_y - tile_y)):
                            if self.game.map_manager.is_solid_wall_at(bomb_center_x, bomb_center_y + i_check * step): blocked = True; break
                        if not blocked: return True
        return False

    # --- 新增：判斷是否可以安全放置炸彈 ---
    def can_place_bomb_safely_at(self, tile_x, tile_y):
        """
        Checks if placing a bomb at (tile_x, tile_y) allows the AI to escape.
        This is a simplified version of C++ canEscapeAfterBomb.
        It checks if there's at least one safe escape route from an adjacent tile
        ASSUMING a bomb is placed at (tile_x, tile_y) and will explode.
        """
        # 1. 模擬放置炸彈後，該區域的危險性
        #    我們需要一個臨時的方法來判斷如果在這裡放了炸彈，周圍哪些格子會變得危險
        #    這需要模擬 is_tile_dangerous 的情況，但加入一個假設的炸彈
        
        # 2. 檢查從鄰近格子是否有逃生路徑
        #    從 AI 當前位置 (tile_x, tile_y) 的四周鄰近格子開始檢查
        for dx_adj, dy_adj in DIRECTIONS.values():
            adj_tile_x, adj_tile_y = tile_x + dx_adj, tile_y + dy_adj
            if self.game.map_manager.is_walkable(adj_tile_x, adj_tile_y):
                # 假設 AI 移動到這個鄰近格子，然後檢查從這個鄰近格子是否有安全逃脫點
                # 這裡的 "安全" 指的是 *不會* 被剛才 *假設放置* 的炸彈炸到
                
                # 為了簡化，我們先只檢查這個鄰近格子本身是否會被假設的炸彈炸到
                # 如果 (adj_tile_x, adj_tile_y) 不在假設炸彈的爆炸範圍內，就認為可以安全放置
                # 這是一個非常粗略的簡化，更精確的需要模擬爆炸範圍並找到一個實際的安全格子路徑

                # 簡化檢查：如果鄰近格子與放炸彈的格子不在同一行或同一列，
                # 或者距離超過1格，就認為它是 (相對於這個剛放的炸彈而言) 安全的第一步。
                # 但還需要考慮這個鄰近格子是否會被其他已存在的炸彈或爆炸波及。
                
                # 更完整的檢查：
                # 1. 獲取假設炸彈的爆炸範圍
                # 2. 檢查 adj_tile_x, adj_tile_y 是否在該範圍內
                # 3. 如果不在，則認為可以安全地移動到 adj_tile_x, adj_tile_y
                # 4. 然後從 adj_tile_x, adj_tile_y 尋找一個真正安全的格子 (不會被任何東西炸到)

                # 再次簡化：只要有一個鄰近的可行走格子，就假設可以放炸彈
                # （這顯然不夠安全，但作為起點）
                # 我們需要在 is_tile_dangerous 中有一個模式，可以加入一個“假設的”炸彈
                
                # 最簡化的版本：只要 AI 不是緊貼著牆壁放炸彈（即周圍有空格子），就認為可能安全
                # 實際的 C++ 版本中，canEscapeAfterBomb 是用 BFS 從 AI 當前位置開始，
                # 判斷在放置炸彈後，能否找到一個*不會*被這個新炸彈波及的安全格子。
                
                # 我們嘗試模擬 C++ 的 canEscapeAfterBomb：
                # 假設在 (tile_x, tile_y) 放了一個炸彈，其範圍是 self.ai_player.bomb_range
                # 我們需要從 (tile_x, tile_y) 開始 BFS，找到一個格子 (safe_x, safe_y) 使得：
                #   a. (safe_x, safe_y) 是可達的
                #   b. (safe_x, safe_y) 不會被位於 (tile_x, tile_y) 的炸彈炸到
                #   c. (safe_x, safe_y) 也不會被其他現存的危險源威脅

                q_escape = deque([((tile_x, tile_y), 0)]) # (tile, depth from bomb placement)
                visited_escape = {(tile_x, tile_y)}
                max_escape_search_depth = self.ai_player.bomb_range + 3 # 搜索範圍比炸彈範圍稍大

                while q_escape:
                    (curr_ex, curr_ey), depth = q_escape.popleft()
                    if depth > max_escape_search_depth: continue

                    # 檢查 (curr_ex, curr_ey) 是否會被位於 (tile_x, tile_y) 的假設炸彈炸到
                    in_hypothetical_blast = False
                    # (中心點)
                    if curr_ex == tile_x and curr_ey == tile_y: in_hypothetical_blast = True
                    # (水平)
                    if not in_hypothetical_blast and curr_ey == tile_y and abs(curr_ex - tile_x) <= self.ai_player.bomb_range:
                        # 檢查中間是否有實心牆
                        blocked_by_wall = False
                        step = 1 if curr_ex > tile_x else -1
                        for i_wall in range(1, abs(curr_ex - tile_x)):
                            if self.game.map_manager.is_solid_wall_at(tile_x + i_wall * step, tile_y):
                                blocked_by_wall = True; break
                        if not blocked_by_wall: in_hypothetical_blast = True
                    # (垂直)
                    if not in_hypothetical_blast and curr_ex == tile_x and abs(curr_ey - tile_y) <= self.ai_player.bomb_range:
                        blocked_by_wall = False
                        step = 1 if curr_ey > tile_y else -1
                        for i_wall in range(1, abs(curr_ey - tile_y)):
                            if self.game.map_manager.is_solid_wall_at(tile_x, tile_y + i_wall * step):
                                blocked_by_wall = True; break
                        if not blocked_by_wall: in_hypothetical_blast = True
                    
                    if not in_hypothetical_blast: # 找到了不會被假設炸彈炸到的格子
                        # 再檢查這個格子是否會被其他真實存在的危險威脅
                        if not self.is_tile_dangerous(curr_ex, curr_ey, check_bombs=True, check_explosions=True, future_seconds=0.5):
                            # print(f"[AI SAFETY CHECK] Placing bomb at ({tile_x},{tile_y}) is SAFE, can escape to ({curr_ex},{curr_ey}).")
                            return True # 找到了一個安全的逃脫點

                    # 擴展到鄰居
                    if depth < max_escape_search_depth:
                        for dex, dey in DIRECTIONS.values():
                            next_ex, next_ey = curr_ex + dex, curr_ey + dey
                            if (next_ex, next_ey) not in visited_escape and \
                               self.game.map_manager.is_walkable(next_ex, next_ey):
                                visited_escape.add((next_ex, next_ey))
                                q_escape.append(((next_ex, next_ey), depth + 1))
                
                # print(f"[AI SAFETY CHECK] Placing bomb at ({tile_x},{tile_y}) is UNSAFE, no escape route found from hypothetical blast.")
                return False # 遍歷完所有可達點，沒有找到安全的逃脫點
        # 如果AI被完全困住，也認為不安全
        return False


    def update(self):
        """AI的主更新迴圈"""
        current_time = pygame.time.get_ticks()
        # AI的「思考」或「決策」階段
        if current_time - self.last_decision_time > self.ai_decision_interval:
            self.last_decision_time = current_time

            if not self.ai_player.is_alive: return # AI死亡則不更新

            self.update_state_machine()        # 決定應該處於哪個狀態
            self.perform_current_state_action()# 根據狀態執行動作（可能會計算新路徑）
        
        # AI的「移動執行」階段 (如果AI有路徑要走)
        if self.current_path and self.ai_player.is_alive:
            moved_or_finished_segment = self.move_along_path()
            if moved_or_finished_segment and not self.current_path: # 如果路徑剛好走完
                # print(f"AI {id(self.ai_player)} completed path. Current state: {self.current_state}. Forcing re-evaluation.")
                self.last_decision_time = 0 # 強制立即重新決策
                self.ai_player.vx, self.ai_player.vy = 0,0 # 停止當前移動

    def debug_draw_path(self, surface):
        """(可選) 繪製AI的當前路徑和BFS訪問過的格子，用於調試。"""
        
        # ！！！修改開始：優化/控制調試繪圖！！！
        # 選項 A：暫時只繪製當前路徑，看看是否是 bfs_visited_visual 導致閃爍
        # for (vx, vy) in self.bfs_visited_visual:
        #     rect = pygame.Rect(vx * settings.TILE_SIZE, vy * settings.TILE_SIZE, settings.TILE_SIZE, settings.TILE_SIZE)
        #     # 嘗試用半透明的顏色或者只畫邊框，減少視覺干擾
        #     debug_surface = pygame.Surface((settings.TILE_SIZE, settings.TILE_SIZE), pygame.SRCALPHA)
        #     pygame.draw.rect(debug_surface, (50, 50, 50, 100), debug_surface.get_rect(), 1) # 淡灰色半透明邊框
        #     surface.blit(debug_surface, rect.topleft)

        if self.current_path and len(self.current_path) > 1:
            # 使用 pygame.draw.lines 繪製路徑
            path_points = []
            for tile_x, tile_y in self.current_path:
                center_x = tile_x * settings.TILE_SIZE + settings.TILE_SIZE // 2
                center_y = tile_y * settings.TILE_SIZE + settings.TILE_SIZE // 2
                path_points.append((center_x, center_y))
            
            try:
                # 嘗試使用帶alpha的顏色繪製線條，使其半透明
                path_color = pygame.Color(255, 0, 255, 120) # 洋紅色，半透明
                # 為了讓線條半透明，我們需要在一個帶SRCALPHA的Surface上繪製，然後再blit到主屏幕
                # 但pygame.draw.lines本身不直接支持在Surface上繪製時的alpha混合到背景
                # 更簡單的方法是直接用一個不透明但可能較細的線
                pygame.draw.lines(surface, (255, 0, 255), False, path_points, 2) # 洋紅色實線，寬度2
            except Exception as e:
                print(f"Error drawing path lines: {e}") # 以防顏色定義或繪製出錯
                pygame.draw.lines(surface, settings.RED, False, path_points, 2) # Fallback to red

            # 標記路徑上的下一個目標點 (可選)
            if self.current_path_index + 1 < len(self.current_path):
                next_target_x, next_target_y = self.current_path[self.current_path_index + 1]
                center_x = next_target_x * settings.TILE_SIZE + settings.TILE_SIZE // 2
                center_y = next_target_y * settings.TILE_SIZE + settings.TILE_SIZE // 2
                pygame.draw.circle(surface, (0, 255, 255, 150), (center_x, center_y), 6, 0) # 青色實心圓點

        # 繪製AI的最終目標 (例如逃跑點或道具點)
        target_to_draw_tile = None
        if self.current_state == AI_STATE_ESCAPE and self.escape_target_tile:
            target_to_draw_tile = self.escape_target_tile
        elif self.current_state == AI_STATE_FETCH_ITEMS and self.target_item and self.target_item.alive():
            target_to_draw_tile = (self.target_item.rect.centerx // settings.TILE_SIZE,
                                   self.target_item.rect.centery // settings.TILE_SIZE)
        elif self.current_state == AI_STATE_ATTACK_PLAYER and self.target_player and self.target_player.is_alive:
             target_to_draw_tile = (self.target_player.rect.centerx // settings.TILE_SIZE,
                                    self.target_player.rect.centery // settings.TILE_SIZE)
        
        if target_to_draw_tile:
            center_x = target_to_draw_tile[0] * settings.TILE_SIZE + settings.TILE_SIZE // 2
            center_y = target_to_draw_tile[1] * settings.TILE_SIZE + settings.TILE_SIZE // 2
            pygame.draw.circle(surface, (255, 255, 0, 200), (center_x, center_y), settings.TILE_SIZE // 3, 3) # 黃色圓圈邊框