# oop-2025-proj-pycade/sprites/player.py

import pygame
from .game_object import GameObject # 確保是相對導入
import settings
from .bomb import Bomb # 假設 Bomb 在同一個 sprites 套件中

class Player(GameObject):
    def __init__(self, game, x_tile, y_tile, spritesheet_path, sprite_config, is_ai=False, ai_controller=None):
        # ！！！ Player 初始化不再直接載入單一圖片 ！！！
        # GameObject 的 __init__ 將被用來設定初始位置和空的 self.image, self.rect
        # 我們將在 Player.__init__ 中自己處理圖像和動畫幀的載入

        self.game = game
        self.is_ai = is_ai
        self.ai_controller = ai_controller

        # --- 載入並切割 Sprite Sheet ---
        self.animations = {} # 儲存所有方向的動畫幀列表: {"DOWN": [frame1, frame2...], "UP": [...]}
        self.spritesheet = None
        try:
            self.spritesheet = pygame.image.load(spritesheet_path).convert_alpha()
        except pygame.error as e:
            print(f"Error loading spritesheet {spritesheet_path}: {e}")
            # 如果 sprite sheet 載入失敗，創建一個紅色方塊作為備用
            self.image = pygame.Surface((settings.PLAYER_SPRITE_FRAME_WIDTH, settings.PLAYER_SPRITE_FRAME_HEIGHT))
            self.image.fill(settings.RED)
            self.rect = self.image.get_rect()
        
        if self.spritesheet:
            for direction, row_index in sprite_config["ROW_MAP"].items():
                frames = []
                for i in range(sprite_config["NUM_FRAMES"]):
                    frame_x = i * settings.PLAYER_SPRITE_FRAME_WIDTH
                    frame_y = row_index * settings.PLAYER_SPRITE_FRAME_HEIGHT
                    frame_surface = self.spritesheet.subsurface(
                        pygame.Rect(frame_x, frame_y, settings.PLAYER_SPRITE_FRAME_WIDTH, settings.PLAYER_SPRITE_FRAME_HEIGHT)
                    )
                    frames.append(frame_surface)
                self.animations[direction] = frames
            
            # 創建 "LEFT" 方向的動畫幀 (通過翻轉 "RIGHT" 方向的幀)
            if "RIGHT" in self.animations:
                self.animations["LEFT"] = [pygame.transform.flip(frame, True, False) for frame in self.animations["RIGHT"]]
            else: # Fallback if RIGHT is missing
                 self.animations["LEFT"] = self.animations.get("DOWN", []) # Or some other default

        # 初始化動畫相關屬性
        self.current_direction = "DOWN" # 初始方向
        self.current_frame_index = 0
        self.last_animation_update_time = pygame.time.get_ticks()
        self.animation_speed = settings.PLAYER_ANIMATION_SPEED # 秒/幀

        # 設定初始圖像和 rect (使用 GameObject 的 __init__ 的部分功能)
        if self.animations and self.current_direction in self.animations and self.animations[self.current_direction]:
            self.image = self.animations[self.current_direction][self.current_frame_index]
        elif hasattr(self, 'image'): # 如果 spritesheet 載入失敗，image 已經是紅色方塊
            pass
        else: # 極端情況的備用
            self.image = pygame.Surface((settings.PLAYER_SPRITE_FRAME_WIDTH, settings.PLAYER_SPRITE_FRAME_HEIGHT))
            self.image.fill(settings.RED)

        self.rect = self.image.get_rect()
        self.rect.topleft = (x_tile * settings.TILE_SIZE, y_tile * settings.TILE_SIZE)
        # ！！！ GameObject 的 super().__init__ 不需要再調用，因為我們自己處理了 image 和 rect ！！！
        # 如果 GameObject 基類有其他重要的初始化邏輯，你需要考慮如何整合，
        # 但對於 image 和 rect，Player 現在自己完全控制。
        # 一種方式是 Player 不繼承 GameObject，而是直接繼承 pygame.sprite.Sprite
        # 或者 GameObject 的 __init__ 變得更通用，只做 Sprite 的基礎初始化。
        # 為了保持簡單，我們假設 Player 直接處理 image/rect，不再依賴 GameObject 的 image_path 參數。
        # 因此，GameObject 的 __init__ 在這裡的 Player 中不再被 `super().__init__` 調用來載入圖片。
        # 我們需要確保 Player 仍然是 Sprite。所以 Player 應該繼承 pygame.sprite.Sprite。
        # 我們之前的 GameObject 已經繼承了 pygame.sprite.Sprite，所以 Player 繼承 GameObject 是可以的。
        # 關鍵是 Player 的 __init__ 現在自己負責 image 和 rect 的最終設定。
        pygame.sprite.Sprite.__init__(self) # 確保 Sprite 被正確初始化

        # --- 圖像縮放邏輯 (在所有幀被載入和切割之後，對每一幀進行縮放) ---
        self.scale_factor = 0.25 # 你之前設定的縮小比例
        if self.animations:
            for direction, frames in self.animations.items():
                scaled_frames = []
                for frame in frames:
                    original_width = frame.get_width()
                    original_height = frame.get_height()
                    new_width = int(original_width * self.scale_factor)
                    new_height = int(original_height * self.scale_factor)
                    scaled_frames.append(pygame.transform.smoothscale(frame, (new_width, new_height)))
                self.animations[direction] = scaled_frames
            
            # 更新當前的 self.image 和 self.rect 以使用縮放後的幀
            if self.current_direction in self.animations and self.animations[self.current_direction]:
                self.image = self.animations[self.current_direction][self.current_frame_index]
                old_center = self.rect.center # 縮放前 rect 的中心點
                self.rect = self.image.get_rect() # 從縮放後的圖像獲取新的 rect
                self.rect.center = old_center # 保持中心點不變
        # --- 縮放邏輯結束 ---

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
        self.is_moving = False # 新增：追蹤玩家是否正在移動，用於動畫

    def get_input(self):
        if self.is_ai:
            return
        self.vx, self.vy = 0, 0
        keys = pygame.key.get_pressed()
        if keys[pygame.K_LEFT] or keys[pygame.K_a]: self.vx = -self.speed
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]: self.vx = self.speed
        if keys[pygame.K_UP] or keys[pygame.K_w]: self.vy = -self.speed
        if keys[pygame.K_DOWN] or keys[pygame.K_s]: self.vy = self.speed
        if self.vx != 0 and self.vy != 0:
            self.vx *= 0.7071
            self.vy *= 0.7071

    def set_ai_movement_intent(self, dx_normalized, dy_normalized):
        if not self.is_ai: return
        self.vx = dx_normalized * self.speed
        self.vy = dy_normalized * self.speed
        if dx_normalized != 0 and dy_normalized != 0:
             self.vx *= 0.7071
             self.vy *= 0.7071
    
    def _animate(self):
        """處理玩家的動畫更新"""
        if not self.animations or not self.is_moving: # 如果沒有動畫幀或不在移動，則使用靜止幀（如果有的話）或第一幀
            # 可以設定一個站立的動畫幀，例如 self.animations[self.current_direction][0]
            # 或者如果想在停止時固定朝向，可以不改變 current_frame_index
            # 為了簡化，如果停止移動，我們將動畫幀索引重置為0，並顯示該方向的第一幀
            self.current_frame_index = 0
            if self.current_direction in self.animations and self.animations[self.current_direction]:
                 self.image = self.animations[self.current_direction][self.current_frame_index]
            return

        now = pygame.time.get_ticks()
        if now - self.last_animation_update_time > self.animation_speed * 1000: # 轉換為毫秒
            self.last_animation_update_time = now
            self.current_frame_index = (self.current_frame_index + 1) % len(self.animations[self.current_direction])
            
            # 確保在切換圖像後保持 rect 的中心點，以避免圖像因幀尺寸細微差異而跳動
            old_center = self.rect.center
            self.image = self.animations[self.current_direction][self.current_frame_index]
            self.rect = self.image.get_rect()
            self.rect.center = old_center
    
    # ！！！ update 方法的再次強化版本 ！！！
    def update(self, dt, solid_obstacles_group):
        if not self.is_alive:
            self.vx = 0; self.vy = 0
            return

        if not self.is_ai:
            self.get_input()
        
        # ！！！修改：根據 vx, vy 更新朝向和 is_moving 狀態！！！
        previous_direction = self.current_direction
        if self.vx > 0: self.current_direction = "RIGHT"
        elif self.vx < 0: self.current_direction = "LEFT"
        # Y 軸的判斷應該在 X 之後，這樣在對角線移動時，上下方向優先（或根據你的喜好調整優先級）
        if self.vy > 0: self.current_direction = "DOWN" # Y 軸向下為正
        elif self.vy < 0: self.current_direction = "UP"
        
        self.is_moving = (self.vx != 0 or self.vy != 0)
        
        if not self.is_moving: # 如果沒有移動，可以將方向重置為一個預設的站立方向，例如 "DOWN"
            # 或者保持最後的移動方向，取決於你想要的視覺效果
            # self.current_direction = "DOWN" # 例如，閒置時總是朝下
            # 為了讓玩家停下時保持最後的朝向，我們可以不修改 current_direction
            pass


        # --- 移動和碰撞邏輯 (保持我們上次修正的版本) ---
        move_x = round(self.vx); self.rect.x += move_x
        hit_list_x = pygame.sprite.spritecollide(self, solid_obstacles_group, False)
        for obstacle in hit_list_x:
            if move_x > 0: self.rect.right = obstacle.rect.left
            elif move_x < 0: self.rect.left = obstacle.rect.right
            self.vx = 0
        move_y = round(self.vy); self.rect.y += move_y
        hit_list_y = pygame.sprite.spritecollide(self, solid_obstacles_group, False)
        for obstacle in hit_list_y:
            if move_y > 0: self.rect.bottom = obstacle.rect.top
            elif move_y < 0: self.rect.top = obstacle.rect.bottom
            self.vy = 0
        # --- 地圖邊界限制 (保持我們上次修正的版本) ---
        map_pixel_width = self.game.map_manager.tile_width * settings.TILE_SIZE
        map_pixel_height = self.game.map_manager.tile_height * settings.TILE_SIZE
        if self.rect.left < 0: self.rect.left = 0; self.vx = 0 if self.vx < 0 else self.vx
        if self.rect.right > map_pixel_width: self.rect.right = map_pixel_width; self.vx = 0 if self.vx > 0 else self.vx
        if self.rect.top < 0: self.rect.top = 0; self.vy = 0 if self.vy < 0 else self.vy
        if self.rect.bottom > map_pixel_height: self.rect.bottom = map_pixel_height; self.vy = 0 if self.vy > 0 else self.vy
        # ！！！修改結束：動畫處理！！！
        self._animate() # 在所有位置更新後調用動畫處理


    def place_bomb(self):
        if not self.is_alive: return
        if self.bombs_placed_count < self.max_bombs:
            bomb_tile_x = self.rect.centerx // settings.TILE_SIZE
            bomb_tile_y = self.rect.centery // settings.TILE_SIZE
            can_place = True
            for bomb_sprite in self.game.bombs_group:
                if bomb_sprite.current_tile_x == bomb_tile_x and \
                   bomb_sprite.current_tile_y == bomb_tile_y:
                    can_place = False; break
            if can_place:
                new_bomb = Bomb(bomb_tile_x, bomb_tile_y, self, self.game)
                self.game.all_sprites.add(new_bomb)
                self.game.bombs_group.add(new_bomb)
                self.bombs_placed_count += 1
                if self.is_ai and self.ai_controller:
                    self.ai_controller.ai_placed_bomb_recently = True
                    self.ai_controller.last_bomb_placed_time = pygame.time.get_ticks()

    def bomb_exploded_feedback(self):
        self.bombs_placed_count = max(0, self.bombs_placed_count - 1)
        if self.is_ai and self.ai_controller:
            self.ai_controller.ai_placed_bomb_recently = False

    def take_damage(self, amount=1):
        current_time = pygame.time.get_ticks()
        if self.is_alive and (current_time - self.last_hit_time > self.invincible_duration):
            self.lives -= amount
            self.last_hit_time = current_time
            print(f"Player (ID: {id(self)}, AI: {self.is_ai}) took damage! Lives left: {self.lives}")
            if self.lives <= 0: self.lives = 0; self.die()

    def die(self):
        if self.is_alive:
            self.is_alive = False
            print(f"Player (ID: {id(self)}, AI: {self.is_ai}) has died!")
            self.kill()