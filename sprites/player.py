# oop-2025-proj-pycade/sprites/player.py

import pygame
from .game_object import GameObject # 確保是相對導入
import settings
from .bomb import Bomb

class Player(GameObject):
    def __init__(self, game, x_tile, y_tile, spritesheet_path, sprite_config, is_ai=False, ai_controller=None):
        pygame.sprite.Sprite.__init__(self) # 確保 Sprite 被正確初始化

        self.game = game
        self.is_ai = is_ai
        self.ai_controller = ai_controller

        # --- 載入並切割 Sprite Sheet (這部分邏輯與你提供的一致) ---
        self.animations = {} 
        self.spritesheet = None
        try:
            self.spritesheet = pygame.image.load(spritesheet_path).convert_alpha()
        except pygame.error as e:
            print(f"Error loading spritesheet {spritesheet_path}: {e}")
        
        if self.spritesheet:
            for direction, row_index in sprite_config["ROW_MAP"].items():
                frames = []
                for i in range(sprite_config["NUM_FRAMES"]):
                    frame_x = i * settings.PLAYER_SPRITE_FRAME_WIDTH
                    frame_y = row_index * settings.PLAYER_SPRITE_FRAME_HEIGHT
                    frame_surface = self.spritesheet.subsurface(
                        pygame.Rect(frame_x, frame_y, settings.PLAYER_SPRITE_FRAME_WIDTH, settings.PLAYER_SPRITE_FRAME_HEIGHT)
                    )
                    frames.append(frame_surface) # 此時 frames 裡是原始大小的幀
                self.animations[direction] = frames
            
            if "RIGHT" in self.animations and "LEFT" not in self.animations:
                self.animations["LEFT"] = [pygame.transform.flip(frame, True, False) for frame in self.animations["RIGHT"]]
        
        self.current_direction = "DOWN" 
        self.current_frame_index = 0
        self.last_animation_update_time = pygame.time.get_ticks()
        self.animation_speed = settings.PLAYER_ANIMATION_SPEED

        # --- ！！！步驟 A：定義視覺縮放因子！！！ ---
        # ！！！ 在這裡設定你想要的視覺大小比例 ！！！
        self.visual_scale_factor = 0.85  # 1.0 = 原始大小, 0.8 = 80% 大小, 1.2 = 120% 大小
        # ！！！ 視覺縮放因子設定結束 ！！！

        # --- 根據 visual_scale_factor 縮放所有動畫幀 ---
        if self.visual_scale_factor != 1.0 and self.animations:
            scaled_animations = {}
            for direction, frames in self.animations.items():
                scaled_frames = []
                for frame in frames: # frame 此時是原始大小
                    original_width = frame.get_width()
                    original_height = frame.get_height()
                    # 使用 visual_scale_factor 進行縮放
                    new_width = int(original_width * self.visual_scale_factor)
                    new_height = int(original_height * self.visual_scale_factor)
                    scaled_frames.append(pygame.transform.smoothscale(frame, (new_width, new_height)))
                scaled_animations[direction] = scaled_frames
            self.animations = scaled_animations # 用縮放後的幀替換原始幀列表
        
        # --- 設定初始的 self.image 和 self.rect (基於可能已縮放的動畫幀) ---
        if self.animations and self.current_direction in self.animations and self.animations[self.current_direction]:
            self.image = self.animations[self.current_direction][self.current_frame_index]
        else: 
            # Fallback: 如果動畫載入失敗或特定方向缺失，創建一個基於原始幀大小的紅色方塊
            # 並也應用 visual_scale_factor (如果不是1.0)
            fallback_width = int(settings.PLAYER_SPRITE_FRAME_WIDTH * self.visual_scale_factor)
            fallback_height = int(settings.PLAYER_SPRITE_FRAME_HEIGHT * self.visual_scale_factor)
            self.image = pygame.Surface((fallback_width, fallback_height))
            self.image.fill(settings.RED)
            if not self.animations: # 只有在完全沒有動畫時才打印警告
                print(f"Warning: Player animations not loaded. Using fallback image.")

        self.rect = self.image.get_rect() # 這是視覺圖像的 rect，其尺寸已根據 visual_scale_factor 調整
        initial_pixel_x = x_tile * settings.TILE_SIZE
        initial_pixel_y = y_tile * settings.TILE_SIZE
        self.rect.topleft = (initial_pixel_x, initial_pixel_y) # 視覺圖像的初始位置

        # --- ！！！步驟 B：定義並初始化 Hitbox (基於原始幀尺寸)！！！---
        # Hitbox 的尺寸基於 settings.PLAYER_SPRITE_FRAME_WIDTH/HEIGHT (原始幀大小)
        # 然後通過 reduction 參數來縮小它，使其比視覺圖像的原始大小更小。
        # ！！！ 在這裡設定 hitbox 的縮減量，讓玩家更容易通過通道 ！！！
        hitbox_width_reduction = 16  # 例如：左右各縮小 6 像素 (32-12 = 20 寬)
        hitbox_height_reduction = 16 # 例如：上下各縮小 4 像素 (32-8 = 24 高)
        # ！！！ Hitbox 縮減量設定結束 ！！！
        
        # 計算 hitbox 的實際寬高
        self.hitbox_width = settings.PLAYER_SPRITE_FRAME_WIDTH - hitbox_width_reduction
        self.hitbox_height = settings.PLAYER_SPRITE_FRAME_HEIGHT - hitbox_height_reduction
        
        # Hitbox 初始位置使其中心與視覺 rect 的初始中心對齊
        self.hitbox = pygame.Rect(0, 0, self.hitbox_width, self.hitbox_height)
        self.hitbox.center = self.rect.center # 使用視覺 rect 的初始中心來定位 hitbox 的初始中心
        # --- ！！！Hitbox 定義結束 ！！！---

        # 根據是否為 AI 調整速度
        if self.is_ai and hasattr(settings, 'AI_PLAYER_SPEED_FACTOR'):
            base_speed = settings.PLAYER_SPEED if hasattr(settings, 'PLAYER_SPEED') else 4
            self.speed = int(base_speed * settings.AI_PLAYER_SPEED_FACTOR)
        else:
            self.speed = settings.PLAYER_SPEED if hasattr(settings, 'PLAYER_SPEED') else 4
        
        self.lives = settings.MAX_LIVES if hasattr(settings, 'MAX_LIVES') else 3
        self.max_bombs = settings.INITIAL_BOMBS
        self.bombs_placed_count = 0
        self.bomb_range = settings.INITIAL_BOMB_RANGE if hasattr(settings, 'INITIAL_BOMB_RANGE') else 1
        self.score = 0
        self.vx = 0; self.vy = 0 
        self.is_alive = True; self.last_hit_time = 0; self.invincible_duration = 1000
        self.is_moving = False

    def get_input(self):
        if self.is_ai: return
        self.vx, self.vy = 0, 0
        keys = pygame.key.get_pressed()
        if keys[pygame.K_LEFT] or keys[pygame.K_a]: self.vx = -self.speed
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]: self.vx = self.speed
        if keys[pygame.K_UP] or keys[pygame.K_w]: self.vy = -self.speed
        if keys[pygame.K_DOWN] or keys[pygame.K_s]: self.vy = self.speed
        if self.vx != 0 and self.vy != 0: self.vx *= 0.7071; self.vy *= 0.7071

    def set_ai_movement_intent(self, dx_normalized, dy_normalized):
        if not self.is_ai: return
        self.vx = dx_normalized * self.speed
        self.vy = dy_normalized * self.speed
        if dx_normalized != 0 and dy_normalized != 0: self.vx *= 0.7071; self.vy *= 0.7071
    
    def _animate(self):
        """處理玩家的動畫更新，基於 self.current_direction 和 self.is_moving"""
        if not self.animations or self.current_direction not in self.animations or not self.animations[self.current_direction]:
            return # 如果沒有有效的動畫幀，則不進行動畫

        animation_frames = self.animations[self.current_direction]
        
        if not self.is_moving: # 如果不在移動，顯示該方向的第一幀 (站立幀)
            self.current_frame_index = 0
        else: # 如果在移動，則更新動畫幀
            now = pygame.time.get_ticks()
            if now - self.last_animation_update_time > self.animation_speed * 1000:
                self.last_animation_update_time = now
                self.current_frame_index = (self.current_frame_index + 1) % len(animation_frames)
        
        new_image = animation_frames[self.current_frame_index]
        
        # 只有在圖像實際改變時才更新 self.image 和 self.rect，以保持中心
        if self.image != new_image:
            old_center = self.rect.center # 視覺 rect 的中心
            self.image = new_image
            self.rect = self.image.get_rect() # 更新視覺 rect
            self.rect.center = old_center # 保持視覺中心

    # ！！！ update 方法的最終強化版本，使用 Hitbox ！！！
    def update(self, dt, solid_obstacles_group):
        if not self.is_alive:
            self.vx = 0; self.vy = 0
            return

        # 1. 獲取移動意圖 (vx, vy)
        if not self.is_ai:
            self.get_input()
        # AI 玩家的 self.vx, self.vy 由 AIController 設定

        # 2. 更新朝向和 is_moving 狀態，用於動畫
        new_direction = self.current_direction # 預設不改變朝向
        if abs(self.vx) > abs(self.vy): # 優先判斷水平移動
            if self.vx > 0: new_direction = "RIGHT"
            elif self.vx < 0: new_direction = "LEFT"
        elif self.vy != 0: # 如果垂直速度不為零 (處理純垂直或對角線時的垂直分量)
            if self.vy > 0: new_direction = "DOWN"
            elif self.vy < 0: new_direction = "UP"
        
        self.is_moving = (self.vx != 0 or self.vy != 0)
        
        if not self.is_moving: # 如果停止移動
            # 可以選擇讓角色朝向預設的 IDLE 方向，或者保持最後的移動方向
            # 這裡我們讓動畫的 _animate 方法處理靜止時的幀 (通常是第0幀)
            pass 
        
        if new_direction != self.current_direction and new_direction in self.animations:
            self.current_direction = new_direction
            self.current_frame_index = 0 # 切換方向時重置動畫幀
        
        # 3. 移動 Hitbox 並進行碰撞檢測
        # --- X 軸移動和碰撞 (基於 Hitbox) ---
        self.hitbox.x += round(self.vx) 
        hit_list_x = []
        for obstacle in solid_obstacles_group:
            if self.hitbox.colliderect(obstacle.rect):
                hit_list_x.append(obstacle)
        
        for obstacle in hit_list_x:
            if self.vx > 0: # 向右撞
                self.hitbox.right = obstacle.rect.left
            elif self.vx < 0: # 向左撞
                self.hitbox.left = obstacle.rect.right
            self.vx = 0 # 撞牆後 X 軸速度歸零
        
        # --- Y 軸移動和碰撞 (基於 Hitbox) ---
        self.hitbox.y += round(self.vy)
        hit_list_y = []
        for obstacle in solid_obstacles_group:
            if self.hitbox.colliderect(obstacle.rect):
                hit_list_y.append(obstacle)

        for obstacle in hit_list_y:
            if self.vy > 0: # 向下撞
                self.hitbox.bottom = obstacle.rect.top
            elif self.vy < 0: # 向上撞
                self.hitbox.top = obstacle.rect.bottom
            self.vy = 0 # 撞牆後 Y 軸速度歸零

        # 4. 地圖邊界限制 (基於 Hitbox)
        map_pixel_width = self.game.map_manager.tile_width * settings.TILE_SIZE
        map_pixel_height = self.game.map_manager.tile_height * settings.TILE_SIZE

        if self.hitbox.left < 0:
            self.hitbox.left = 0
            if self.vx < 0: self.vx = 0
        if self.hitbox.right > map_pixel_width:
            self.hitbox.right = map_pixel_width
            if self.vx > 0: self.vx = 0
        if self.hitbox.top < 0:
            self.hitbox.top = 0
            if self.vy < 0: self.vy = 0
        if self.hitbox.bottom > map_pixel_height:
            self.hitbox.bottom = map_pixel_height
            if self.vy > 0: self.vy = 0
        
        # 5. 更新視覺 self.rect 的位置以匹配 self.hitbox 的中心
        self.rect.center = self.hitbox.center
        
        # 6. 更新動畫幀
        self._animate()
    # ！！！ update 方法結束 ！！！

    def place_bomb(self):
        if not self.is_alive: return #
        if self.bombs_placed_count < self.max_bombs: #
            bomb_tile_x = self.hitbox.centerx // settings.TILE_SIZE #
            bomb_tile_y = self.hitbox.centery // settings.TILE_SIZE #
            can_place = True
            for bomb_sprite in self.game.bombs_group: #
                if bomb_sprite.current_tile_x == bomb_tile_x and \
                   bomb_sprite.current_tile_y == bomb_tile_y: #
                    can_place = False; break
            if can_place:
                new_bomb = Bomb(bomb_tile_x, bomb_tile_y, self, self.game) #
                self.game.all_sprites.add(new_bomb) #
                self.game.bombs_group.add(new_bomb) #
                self.bombs_placed_count += 1 #
                
                # --- AI Controller Feedback ---
                if self.is_ai and self.ai_controller: #
                    self.ai_controller.ai_just_placed_bomb = True # 使用新的標記名稱
                    self.ai_controller.last_bomb_placed_time = pygame.time.get_ticks() #
    
    def bomb_exploded_feedback(self): #
        self.bombs_placed_count = max(0, self.bombs_placed_count - 1) #
        # ai_just_placed_bomb 的重置主要由 AWAIT_OPPORTUNITY 狀態結束時處理
        # 或者在 TACTICAL_RETREAT 完成且確認非自己炸彈時處理
        # if self.is_ai and self.ai_controller:
        #    self.ai_controller.ai_just_placed_bomb = False # 暫時不由這裡重置

    def take_damage(self, amount=1):
        current_time = pygame.time.get_ticks()
        if self.is_alive and (current_time - self.last_hit_time > self.invincible_duration):
            self.lives -= amount; self.last_hit_time = current_time
            print(f"Player (ID: {id(self)}, AI: {self.is_ai}) took damage! Lives left: {self.lives}")
            if self.lives <= 0: self.lives = 0; self.die()

    def die(self):
        if self.is_alive:
            self.is_alive = False
            print(f"Player (ID: {id(self)}, AI: {self.is_ai}) has died!")
            self.kill()