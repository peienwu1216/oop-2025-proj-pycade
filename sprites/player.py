# oop-2025-proj-pycade/sprites/player.py

import pygame
from .game_object import GameObject # 確保是相對導入
import settings
# from .bomb import Bomb # Bomb 在 Player 中放置炸彈時才需要，這裡暫時註解，確認 place_bomb 是否在此檔案

class Player(GameObject):
    def __init__(self, game, x_tile, y_tile, spritesheet_path, sprite_config, is_ai=False, ai_controller=None):
        # GameObject 的 __init__ 會處理 image 和 rect 的基本設定
        # 我們需要在 GameObject 的 __init__ 之後，根據格子位置重新精確設定 rect
        # 因此，我們先不直接呼叫 GameObject.__init__，或者在後面覆蓋其 rect 設定

        pygame.sprite.Sprite.__init__(self) # 確保 Sprite 被正確初始化

        self.game = game
        self.is_ai = is_ai
        self.ai_controller = ai_controller # AIController 的實例，AI玩家會有

        # --- 核心格子位置 ---
        self.tile_x = x_tile
        self.tile_y = y_tile

        # --- 動畫相關 ---
        self.animations = {}
        self.spritesheet = None
        try:
            self.spritesheet = pygame.image.load(spritesheet_path).convert_alpha()
        except pygame.error as e:
            print(f"Error loading spritesheet {spritesheet_path}: {e}")

        if self.spritesheet:
            for direction, row_index in sprite_config["ROW_MAP"].items(): #
                frames = []
                for i in range(sprite_config["NUM_FRAMES"]): #
                    frame_x = i * settings.PLAYER_SPRITE_FRAME_WIDTH #
                    frame_y = row_index * settings.PLAYER_SPRITE_FRAME_HEIGHT #
                    frame_surface = self.spritesheet.subsurface(
                        pygame.Rect(frame_x, frame_y, settings.PLAYER_SPRITE_FRAME_WIDTH, settings.PLAYER_SPRITE_FRAME_HEIGHT) #
                    )
                    frames.append(frame_surface)
                self.animations[direction] = frames
            
            if "RIGHT" in self.animations and "LEFT" not in self.animations: #
                self.animations["LEFT"] = [pygame.transform.flip(frame, True, False) for frame in self.animations["RIGHT"]] #

        self.current_direction = "DOWN"
        self.current_frame_index = 0
        self.last_animation_update_time = pygame.time.get_ticks()
        # settings.PLAYER_ANIMATION_SPEED 決定了動畫播放快慢 (秒/幀)
        self.animation_frame_duration = settings.PLAYER_ANIMATION_SPEED * 1000 # 轉換為毫秒

        # --- 視覺縮放因子 (保留，因為影響圖片外觀) ---
        self.visual_scale_factor = 0.85 #
        if self.visual_scale_factor != 1.0 and self.animations: #
            scaled_animations = {}
            for direction, frames in self.animations.items():
                scaled_frames = []
                for frame in frames:
                    original_width = frame.get_width()
                    original_height = frame.get_height()
                    new_width = int(original_width * self.visual_scale_factor) #
                    new_height = int(original_height * self.visual_scale_factor) #
                    scaled_frames.append(pygame.transform.smoothscale(frame, (new_width, new_height))) #
                scaled_animations[direction] = scaled_frames
            self.animations = scaled_animations

        # --- 設定初始的 self.image 和 self.rect (基於格子位置) ---
        if self.animations and self.current_direction in self.animations and self.animations[self.current_direction]: #
            self.image = self.animations[self.current_direction][self.current_frame_index] #
        else:
            fallback_width = int(settings.PLAYER_SPRITE_FRAME_WIDTH * self.visual_scale_factor) #
            fallback_height = int(settings.PLAYER_SPRITE_FRAME_HEIGHT * self.visual_scale_factor) #
            self.image = pygame.Surface((fallback_width, fallback_height)) #
            self.image.fill(settings.RED) #
            if not self.animations: #
                print(f"Warning: Player animations not loaded. Using fallback image.") #

        self.rect = self.image.get_rect()
        # 視覺位置使其中心在當前格子的中心
        self.rect.center = (self.tile_x * settings.TILE_SIZE + settings.TILE_SIZE // 2,
                             self.tile_y * settings.TILE_SIZE + settings.TILE_SIZE // 2)

        # --- Hitbox ---
        # Hitbox 仍然可以存在，用於與爆炸等像素級效果的碰撞。
        # 它的尺寸可以保持，但位置必須時刻與 self.rect.center 同步。
        hitbox_width_reduction = 16 #
        hitbox_height_reduction = 16 #
        self.hitbox_width = settings.PLAYER_SPRITE_FRAME_WIDTH - hitbox_width_reduction #
        self.hitbox_height = settings.PLAYER_SPRITE_FRAME_HEIGHT - hitbox_height_reduction #
        self.hitbox = pygame.Rect(0, 0, self.hitbox_width, self.hitbox_height) #
        self.hitbox.center = self.rect.center #

        # --- 玩家屬性 ---
        self.lives = settings.MAX_LIVES #
        self.max_bombs = settings.INITIAL_BOMBS #
        self.bombs_placed_count = 0 #
        self.bomb_range = settings.INITIAL_BOMB_RANGE #
        self.score = 0 #
        
        self.is_alive = True #
        self.last_hit_time = 0 #
        self.invincible_duration = 1000 # # 保持1秒無敵

        # is_moving 控制動畫是否為行走狀態。
        # 在瞬時格子移動中，is_moving 可能只在移動發生的那一幀或短時間內為 True。
        self.is_moving = False 
        self.action_timer = 0 # 用於控制行走動畫在瞬移後持續一小段時間
        
        if self.is_ai:
            self.ACTION_ANIMATION_DURATION = getattr(settings, 'AI_GRID_MOVE_ACTION_DURATION', 0.5) # AI 每 0.5 秒移動一格
        else:
            # 人類玩家的移動節奏可以更快，例如 0.1 秒，或者更短以達到更連續的效果
            # 如果設為非常小的值 (例如 0.01)，則 action_timer 的限制幾乎可以忽略，
            # 主要由按鍵檢測的幀率決定移動頻率。
            self.ACTION_ANIMATION_DURATION = getattr(settings, 'HUMAN_GRID_MOVE_ACTION_DURATION', 0.2) # 人類玩家可以更頻繁地移動
        # 移除舊的 self.vx, self.vy, self.speed，因為移動方式改變
        # self.vx = 0; self.vy = 0
        # self.speed = ... (不再需要像素速度)


    def attempt_move_to_tile(self, dx, dy):
        """
        嘗試向指定的方向 (dx, dy) 移動一個格子。
        dx, dy 分別為 -1, 0, 或 1、且不同時為0、不同時為非零 (除非允許對角線)。
        返回 True 如果移動成功，否則 False。
        """
        if not self.is_alive:
            return False
        
        if self.action_timer > 0:
             return False
        # 如果正在執行上一個動作的動畫，則不允許新的移動 (可選)
        # if self.action_timer > 0:
        # return False

        if dx == 0 and dy == 0:
            # self.is_moving = False # is_moving 的管理放到 update 或 get_input
            return False

        # 限制為單軸移動 (如果需要)
        if dx != 0 and dy != 0:
            # print(f"[PLAYER ATTEMPT_MOVE] Diagonal move ({dx},{dy}) not allowed for discrete grid.") # DEBUG
            # 可以選擇忽略，或只取一個方向。這裡我們選擇忽略對角線瞬移。
            return False


        target_tile_x = self.tile_x + dx
        target_tile_y = self.tile_y + dy

        # 1. 檢查地圖邊界
        if not (0 <= target_tile_x < self.game.map_manager.tile_width and \
                0 <= target_tile_y < self.game.map_manager.tile_height):
            # print(f"[PLAYER ATTEMPT_MOVE] Target ({target_tile_x},{target_tile_y}) out of bounds.") # DEBUG
            return False

        # 2. 檢查目標格子是否是固態障礙物
        # 遍歷 solid_obstacles_group (通常包含 Wall 和未被破壞的 DestructibleWall)
        # 創建一個目標格子的臨時 rect 來進行碰撞檢測
        target_check_rect = pygame.Rect(target_tile_x * settings.TILE_SIZE,
                                        target_tile_y * settings.TILE_SIZE,
                                        settings.TILE_SIZE,
                                        settings.TILE_SIZE)
        
        is_obstacle = False
        if hasattr(self.game, 'solid_obstacles_group'): # 確保 game 物件有這個 group
            for obstacle in self.game.solid_obstacles_group:
                if obstacle.rect.colliderect(target_check_rect):
                    is_obstacle = True
                    break
        
        if is_obstacle:
            # print(f"[PLAYER ATTEMPT_MOVE] Target ({target_tile_x},{target_tile_y}) is an obstacle.") # DEBUG
            return False

        # --- 移動成功 ---
        self.tile_x = target_tile_x
        self.tile_y = target_tile_y

        # 更新視覺 rect 和 hitbox 的中心到新格子的中心
        self.rect.center = (self.tile_x * settings.TILE_SIZE + settings.TILE_SIZE // 2,
                             self.tile_y * settings.TILE_SIZE + settings.TILE_SIZE // 2)
        self.hitbox.center = self.rect.center # Hitbox 跟隨

        # 更新動畫方向
        if dx > 0: self.current_direction = "RIGHT"
        elif dx < 0: self.current_direction = "LEFT"
        if dy > 0: self.current_direction = "DOWN" # Y 軸向下是增加
        elif dy < 0: self.current_direction = "UP"   # Y 軸向上是減少
        
        self.is_moving = True #觸發移動動畫
        self.action_timer = self.ACTION_ANIMATION_DURATION # 開始動作動畫計時器

        # print(f"[PLAYER ATTEMPT_MOVE] ID: {id(self)} successfully moved to ({self.tile_x},{self.tile_y})") # DEBUG
        return True

    def get_input(self):
        """
        處理人類玩家的持續按鍵輸入。
        如果按住方向鍵且上一個格子移動動畫已結束 (action_timer <= 0)，則嘗試移動。
        此方法應在 Player.update() 中被呼叫。
        """
        if self.is_ai or not self.is_alive: # AI 不處理鍵盤，死亡不處理
            return

        if self.action_timer > 0: # 如果正在播放上一個移動的動畫，則暫不接受新移動
            # print(f"[Player.get_input] Action timer active ({self.action_timer:.2f}), skipping input.") # DEBUG
            return 

        keys = pygame.key.get_pressed() # 獲取當前所有被按住的鍵的狀態
        dx, dy = 0, 0

        # 判斷方向鍵 (只允許單一方向，避免對角線瞬移)
        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
            dx = -1
        elif keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            dx = 1
        elif keys[pygame.K_UP] or keys[pygame.K_w]: # 使用 elif 確保一次只處理一個主要方向
            dy = -1
        elif keys[pygame.K_DOWN] or keys[pygame.K_s]:
            dy = 1
        
        if dx != 0 or dy != 0:
            # print(f"[Player.get_input] Key pressed ({dx},{dy}). Attempting move...") # DEBUG
            self.attempt_move_to_tile(dx, dy) # is_moving 和 action_timer 會在 attempt_move_to_tile 內部設定
        # else: # 如果沒有方向鍵按下，不需要特別處理 is_moving，它會由 action_timer 在 update 中管理
            # self.is_moving = False # 不在這裡設定，讓 action_timer 控制
            pass

    # AIController 將不再呼叫此方法
    # def set_ai_movement_intent(self, dx_normalized, dy_normalized):
    #     pass

    def _animate(self):
        """處理玩家的動畫更新，基於 self.current_direction 和 self.is_moving"""
        if not self.animations or self.current_direction not in self.animations or not self.animations[self.current_direction]: #
            # print(f"[ANIMATE] No animations for {self.current_direction} or animations not loaded.") # DEBUG
            return

        animation_frames = self.animations[self.current_direction] #
        
        if not self.is_ai:
            self.get_input() # get_input 內部會檢查 action_timer

        if not self.is_moving: # 如果不在移動 (action_timer <= 0)，顯示該方向的第一幀 (站立幀)
            self.current_frame_index = 0 #
        else: # 如果在移動 (action_timer > 0)，則更新動畫幀
            now = pygame.time.get_ticks()
            if now - self.last_animation_update_time > self.animation_frame_duration: #
                self.last_animation_update_time = now #
                self.current_frame_index = (self.current_frame_index + 1) % len(animation_frames) #
        
        new_image = animation_frames[self.current_frame_index]
        
        if self.image != new_image: #
            # 由於 rect 的中心已經由格子位置決定，這裡我們只需要更新 image
            # 但如果 image 尺寸因動畫幀而改變（通常不會在這種 sprite sheet 中），則需要重新計算 center
            old_center = self.rect.center #
            self.image = new_image #
            self.rect = self.image.get_rect() # # 獲取新 image 的 rect
            self.rect.center = old_center # # 保持中心對齊
    
    def update(self, dt, solid_obstacles_group): # solid_obstacles_group 在此不再直接用於碰撞
        if not self.is_alive:
            self.is_moving = False
            return

        # 更新動作計時器
        if self.action_timer > 0:
            self.action_timer -= dt
            if self.action_timer <= 0:
                self.is_moving = False 
                self.action_timer = 0 
        # else: # 不需要這個 else，因為 is_moving 會在 action_timer <= 0 時被設為 False
            # self.is_moving = False

        # 如果是人類玩家，處理輸入
        if not self.is_ai:
            self.get_input() # get_input 內部會檢查 action_timer
        
        # ... (後續確保精確停在格子上的邏輯 和 _animate()) ...
        if not self.is_moving and self.action_timer <=0 :
            expected_center_x = self.tile_x * settings.TILE_SIZE + settings.TILE_SIZE // 2
            expected_center_y = self.tile_y * settings.TILE_SIZE + settings.TILE_SIZE // 2
            if self.rect.centerx != expected_center_x or self.rect.centery != expected_center_y:
                self.rect.center = (expected_center_x, expected_center_y)
                if hasattr(self, 'hitbox'):
                    self.hitbox.center = self.rect.center

        self._animate()

    def place_bomb(self):
        if not self.is_alive: return #
        if self.bombs_placed_count < self.max_bombs: #
            # 使用玩家的邏輯格子座標
            bomb_tile_x = self.tile_x
            bomb_tile_y = self.tile_y
            
            can_place = True
            for bomb_sprite in self.game.bombs_group: #
                if bomb_sprite.current_tile_x == bomb_tile_x and \
                   bomb_sprite.current_tile_y == bomb_tile_y: #
                    can_place = False; break #
            
            if can_place:
                # 假設 Bomb class 的 __init__ 簽名是 (x_tile, y_tile, placed_by_player, game_instance)
                from .bomb import Bomb # 延遲導入或確保在頂部已導入
                new_bomb = Bomb(bomb_tile_x, bomb_tile_y, self, self.game) #
                self.game.all_sprites.add(new_bomb) #
                self.game.bombs_group.add(new_bomb) #
                self.bombs_placed_count += 1 #
                
                if self.is_ai and self.ai_controller: #
                    self.ai_controller.ai_just_placed_bomb = True #
                    self.ai_controller.last_bomb_placed_time = pygame.time.get_ticks() #
    
    def bomb_exploded_feedback(self): #
        self.bombs_placed_count = max(0, self.bombs_placed_count - 1) #

    def take_damage(self, amount=1): #
        current_time = pygame.time.get_ticks() #
        if self.is_alive and (current_time - self.last_hit_time > self.invincible_duration): #
            self.lives -= amount #
            self.last_hit_time = current_time #
            print(f"Player (ID: {id(self)}, AI: {self.is_ai}) took damage! Lives left: {self.lives}") #
            if self.lives <= 0: #
                self.lives = 0 #
                self.die() #

    def die(self): #
        if self.is_alive: #
            self.is_alive = False #
            print(f"Player (ID: {id(self)}, AI: {self.is_ai}) has died!") #
            self.kill() # 從所有 sprite groups 中移除