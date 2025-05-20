# oop-2025-proj-pycade/sprites/bomb.py

import pygame
from .game_object import GameObject # 從同一個 sprites 套件中匯入 GameObject
import settings
from .explosion import Explosion

class Bomb(GameObject):
    """
    Represents a bomb placed by a player.
    """
    def __init__(self, x_tile, y_tile, placed_by_player, game_instance): # 添加 game_instance
        """
        Initializes a Bomb object.

        Args:
            x_tile (int): The x-coordinate (in tile units) where the bomb is placed.
            y_tile (int): The y-coordinate (in tile units) where the bomb is placed.
            placed_by_player (Player): The player instance that placed this bomb.
            game_instance (Game): The main game instance.
        """
        super().__init__(
            x_tile * settings.TILE_SIZE,
            y_tile * settings.TILE_SIZE,
            settings.TILE_SIZE,
            settings.TILE_SIZE,
            image_path=settings.BOMB_IMG
        )
        self.placed_by_player = placed_by_player
        self.game = game_instance # 儲存 Game 實例，以便訪問 Sprite Group 等
        self.spawn_time = pygame.time.get_ticks() # 記錄放置時間
        self.timer = settings.BOMB_TIMER # 毫秒
        self.exploded = False
        self.current_tile_x = x_tile # 記錄炸彈所在的格子座標
        self.current_tile_y = y_tile

        # For visual countdown (optional)
        try:
            self.font = pygame.font.Font(None, 20) # Default font, size 20 (稍微改小一點)
        except pygame.error: # Fallback if default font is not available (rare)
            self.font = pygame.font.SysFont("arial", 20)
        self.text_color = settings.WHITE

        print(f"Bomb placed at tile ({x_tile}, {y_tile}) by Player object ID: {id(self.placed_by_player)}")


    def update(self, dt, *args): # dt is not used yet for timer logic, but good practice
        """
        Updates the bomb's state (timer, visual countdown).
        """
        current_time = pygame.time.get_ticks()
        time_elapsed = current_time - self.spawn_time

        if not self.exploded and time_elapsed >= self.timer:
            self.explode() # 觸發爆炸
        
        # Visual countdown on the bomb sprite itself
        if not self.exploded:
            time_left_sec = max(0, (self.timer - time_elapsed) / 1000)
            
            # 為了避免每幀都重新創建 Surface，只有在秒數變化時才更新文本圖像
            # (更精確的做法是比較 time_left_sec 的整數部分或格式化後的字符串)
            # 這裡我們先簡單地每幀都畫，之後可以優化
            self.image = self.original_image.copy() # Start with a fresh copy of the base image
            countdown_text = f"{time_left_sec:.1f}" # 顯示到小數點後一位
            text_surface = self.font.render(countdown_text, True, self.text_color)
            # 將文本居中繪製在炸彈圖像上
            text_rect = text_surface.get_rect(center=(self.image.get_width() / 2, self.image.get_height() / 2))
            self.image.blit(text_surface, text_rect)

    def explode(self):
        if not self.exploded:
            print(f"Bomb at ({self.current_tile_x}, {self.current_tile_y}) EXPLOADED by player with range {self.placed_by_player.bomb_range}!")
            self.exploded = True
            if self.placed_by_player:
                 self.placed_by_player.bomb_exploded_feedback()

            bomb_range = self.placed_by_player.bomb_range
            explosion_tiles = []
            explosion_tiles.append((self.current_tile_x, self.current_tile_y)) # 中心點

            for dx, dy in [(0, -1), (0, 1), (-1, 0), (1, 0)]: # 上, 下, 左, 右
                for i in range(1, bomb_range + 1):
                    nx, ny = self.current_tile_x + dx * i, self.current_tile_y + dy * i
                    
                    # 1. 檢查是否超出地圖邊界
                    if not (0 <= nx < self.game.map_manager.tile_width and \
                            0 <= ny < self.game.map_manager.tile_height):
                        break # 超出邊界，停止這個方向的延伸

                    # 2. 檢查是否有不可破壞的牆 (Solid Wall)
                    if self.game.map_manager.is_solid_wall_at(nx, ny):
                        break # 撞到不可破壞牆壁，停止這個方向的延伸
                    
                    # 3. 如果沒有被固態牆阻擋，則火焰可以到達這個格子
                    explosion_tiles.append((nx, ny))
                    
                    # 4. 檢查這個格子是否是可破壞的牆
                    # 如果是，火焰雖然到達了這裡 (加入了 explosion_tiles)，
                    # 但這個方向的火焰延伸也應該停止 (火焰不會穿透被炸開的牆)
                    is_destructible_here = False
                    for d_wall in self.game.map_manager.destructible_walls_group:
                        if d_wall.tile_x == nx and d_wall.tile_y == ny:
                            is_destructible_here = True
                            break
                    if is_destructible_here:
                        break # 撞到可破壞牆壁，火焰也停止在這個方向的延伸

            # 根據 explosion_tiles 創建 Explosion Sprite
            for ex_tile_x, ex_tile_y in explosion_tiles:
                expl_sprite = Explosion(ex_tile_x, ex_tile_y, self.game)
                self.game.all_sprites.add(expl_sprite)
                self.game.explosions_group.add(expl_sprite)
            
            self.kill()