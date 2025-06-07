# oop-2025-proj-pycade/sprites/bomb.py

import pygame
from .game_object import GameObject # 從同一個 sprites 套件中匯入 GameObject
import settings
from .explosion import Explosion
import math

class Bomb(GameObject):
    """
    Represents a bomb placed by a player.
    """
    def __init__(self, x_tile, y_tile, placed_by_player, game_instance): # 添加 game_instance
        """
        Initializes a Bomb object.

        Args:
            x_tile (int): The x-coordinate (in tile units) where the bomb is placed.
                          [SPS_BOMB_NO_CHANGE_NEEDED] 這與 Player.place_bomb() 中傳入的 player.tile_x 一致。
            y_tile (int): The y-coordinate (in tile units) where the bomb is placed.
                          [SPS_BOMB_NO_CHANGE_NEEDED] 這與 Player.place_bomb() 中傳入的 player.tile_y 一致。
            placed_by_player (Player): The player instance that placed this bomb.
            game_instance (Game): The main game instance.
        """
        # 判斷是否是 player1 放的炸彈
        if placed_by_player.is_player1:
            bomb_img = settings.BOMB_PLAYER_1_IMG
        else:
            bomb_img = settings.BOMB_AI_PLAYER_1_IMG  # 預設圖

        super().__init__(
            x_tile * settings.TILE_SIZE+6, # 視覺位置基於格子座標
            y_tile * settings.TILE_SIZE-2, # 視覺位置基於格子座標
            width=None, # 寬度基於圖片比例
            height=settings.TILE_SIZE,
            image_path=bomb_img
        )
        self.placed_by_player = placed_by_player
        self.game = game_instance # 儲存 Game 實例，以便訪問 Sprite Group 等
        self.spawn_time = pygame.time.get_ticks() # 記錄放置時間
        self.timer = settings.BOMB_TIMER # 毫秒
        self.exploded = False
        self.current_tile_x = x_tile # [SPS_BOMB_NO_CHANGE_NEEDED] 記錄炸彈所在的格子座標，這很好。
        self.current_tile_y = y_tile # [SPS_BOMB_NO_CHANGE_NEEDED] 記錄炸彈所在的格子座標，這很好。

        self.is_solidified = False # 炸彈初始不是固態的，允許放置者離開
        self.owner_has_left_tile = False # 標記擁有者是否已離開此格
        
        # Bomb animation
        if placed_by_player.is_player1:
            self.animation_images = [
                pygame.transform.smoothscale(
                    pygame.image.load(img).convert_alpha(),
                    (self.original_image.get_width() * (settings.TILE_SIZE / self.original_image.get_height()), settings.TILE_SIZE)
                )
                for img in settings.PLAYER1_BOMB_IMAGES
            ]
        else:
            self.animation_images = [
                pygame.transform.smoothscale(
                    pygame.image.load(img).convert_alpha(),
                    (self.original_image.get_width() * (settings.TILE_SIZE / self.original_image.get_height()), settings.TILE_SIZE)
                )
                for img in settings.AI_PLAYER_BOMB_IMAGES
            ]
        self.animation_index = 0
        self.last_animation_time = pygame.time.get_ticks()
        self.animation_interval = 300  # 毫秒，調整為你想要的動畫速度


        # For visual countdown (optional)
        try:
            self.font = pygame.font.Font(None, 20) 
        except pygame.error: 
            self.font = pygame.font.SysFont("arial", 20)
        self.text_color = settings.RED

        # [SPS_BOMB_NO_CHANGE_NEEDED] 這個 print 仍然有效。
        # print(f"Bomb placed at tile ({x_tile}, {y_tile}) by Player object ID: {id(self.placed_by_player)}")

    def draw_timer_bar(self, surface):
        """在給定 surface 上繪製炸彈倒數計時條，不受炸彈動畫縮放影響。"""
        # 計算剩餘時間比例
        time_left = max(0, self.timer - (pygame.time.get_ticks() - self.spawn_time))
        time_ratio = time_left / self.timer
        
        screen_x = self.rect.centerx
        screen_y = self.current_tile_y * settings.TILE_SIZE + settings.TILE_SIZE  # tile 的底部

        bar_width = settings.TILE_SIZE * 0.9
        bar_height = 4
        bar_x = screen_x - bar_width // 2
        bar_y = screen_y - 3 # 往下留一點距離

        # 畫背景邊框 + 前景條
        pygame.draw.rect(surface, (0, 0, 0), (bar_x, bar_y, bar_width, bar_height), 1)
        if self.placed_by_player.is_player1:
            pygame.draw.rect(surface, (50, 255, 50), (bar_x + 1, bar_y + 1, (bar_width - 2) * time_ratio, bar_height - 2))
        else:
            pygame.draw.rect(surface, (255, 50, 50), (bar_x + 1, bar_y + 1, (bar_width - 2) * time_ratio, bar_height - 2))

    def update(self, dt, *args): # dt is not used yet for timer logic, but good practice
        """
        Updates the bomb's state (timer, visual countdown).
        """
        # [SPS_BOMB_NO_CHANGE_NEEDED] 倒數計時和爆炸邏輯與玩家移動方式無直接關聯。
        current_time = pygame.time.get_ticks()

        if not self.owner_has_left_tile and self.placed_by_player:
            if self.placed_by_player.tile_x != self.current_tile_x or \
               self.placed_by_player.tile_y != self.current_tile_y:
                self.owner_has_left_tile = True
                self.is_solidified = True 
        
        if not self.exploded:
            # === 1. 計算縮放因子 ===
            elapsed = (pygame.time.get_ticks() - self.spawn_time) / 1000  # 秒
            frequency = 1  # 每秒跳動次數
            scale_variation = 0.1  # 最大縮小比例
            scale_factor = 1 - scale_variation * (0.5 * (1 + math.sin(2 * math.pi * frequency * elapsed)))

            # === 2. 圖片切換邏輯 ===
            if current_time - self.last_animation_time >= self.animation_interval:
                self.animation_index = (self.animation_index + 1) % len(self.animation_images)
                self.last_animation_time = current_time

            base_image = self.animation_images[self.animation_index]
            
            w, h = base_image.get_width(), base_image.get_height()
            new_size = (int(w * scale_factor), int(h * scale_factor))
            self.original_image = pygame.transform.smoothscale(base_image, new_size)

            # === 3. 複製圖像做為繪製對象 ===
            self.image = self.original_image.copy()

            # === 4. 計算剩餘時間條 ===
            time_left = max(0, self.timer - (pygame.time.get_ticks() - self.spawn_time))

            # === 5. 保持位置中心 ===
            old_center = self.rect.center
            self.rect = self.image.get_rect(center=old_center)

            # === 6. 爆炸判斷 ===
            if time_left <= 0:
                self.explode()

    def explode(self):
        # [SPS_BOMB_NO_CHANGE_NEEDED] 爆炸邏輯完全基於炸彈自身的 current_tile_x, current_tile_y 和放置者的 bomb_range。
        # 這些都不受玩家移動方式從像素級變為格子級的影響。
        if not self.exploded:
            # print(f"Bomb at ({self.current_tile_x}, {self.current_tile_y}) EXPLOADED by player with range {self.placed_by_player.bomb_range}!") # DEBUG
            self.exploded = True
            if self.placed_by_player:
                 self.placed_by_player.bomb_exploded_feedback()

            bomb_range = self.placed_by_player.bomb_range
            explosion_tiles = []
            explosion_tiles.append((self.current_tile_x, self.current_tile_y)) 

            for dx, dy in [(0, -1), (0, 1), (-1, 0), (1, 0)]: 
                for i in range(1, bomb_range + 1):
                    nx, ny = self.current_tile_x + dx * i, self.current_tile_y + dy * i
                    
                    if not (0 <= nx < self.game.map_manager.tile_width and \
                            0 <= ny < self.game.map_manager.tile_height):
                        break 

                    if self.game.map_manager.is_solid_wall_at(nx, ny):
                        break 
                    
                    explosion_tiles.append((nx, ny))
                    
                    is_destructible_here = False
                    # 需要確保 self.game.map_manager.destructible_walls_group 中的牆壁有 tile_x, tile_y 屬性
                    for d_wall in self.game.map_manager.destructible_walls_group:
                        if hasattr(d_wall, 'tile_x') and hasattr(d_wall, 'tile_y'): # 增加檢查
                            if d_wall.tile_x == nx and d_wall.tile_y == ny and not getattr(d_wall, 'is_destroyed', False): # 確保牆未被摧毀
                                is_destructible_here = True
                                break
                        # else:
                            # print(f"[BOMB EXPLODE WARN] Destructible wall object {d_wall} missing tile_x/tile_y attributes.") # DEBUG

                    if is_destructible_here:
                        break 

            for ex_tile_x, ex_tile_y in explosion_tiles:
                expl_sprite = Explosion(ex_tile_x, ex_tile_y, self.game)
                self.game.all_sprites.add(expl_sprite)
                self.game.explosions_group.add(expl_sprite)
            
            self.kill()