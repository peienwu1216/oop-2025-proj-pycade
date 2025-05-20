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
        """
        Handles the bomb explosion logic.
        """
        if not self.exploded:
            print(f"Bomb at ({self.current_tile_x}, {self.current_tile_y}) EXPLOADED!")
            self.exploded = True
            
            # 通知放置者炸彈已爆炸 (這樣玩家才能再放新的)
            if self.placed_by_player:
                 self.placed_by_player.bomb_exploded_feedback() 

            # --- 實際的爆炸效果和傷害處理將在下一步驟中添加 ---
            # 例如: self.game.create_explosion_at(self.current_tile_x, self.current_tile_y, self.placed_by_player.bomb_range)
            
            # 爆炸範圍，從放置炸彈的玩家那裡獲取
            bomb_range = self.placed_by_player.bomb_range 
            explosion_tiles = [] # 用來儲存將要產生爆炸火焰的格子座標

            # 1. 中心點
            explosion_tiles.append((self.current_tile_x, self.current_tile_y))

            # 2. 四個方向延伸
            #    dx, dy: (0, -1) -> Up, (0, 1) -> Down, (-1, 0) -> Left, (1, 0) -> Right
            for dx, dy in [(0, -1), (0, 1), (-1, 0), (1, 0)]:
                for i in range(1, bomb_range + 1):
                    nx, ny = self.current_tile_x + dx * i, self.current_tile_y + dy * i
                    
                    # 檢查是否超出地圖邊界
                    if not (0 <= nx < self.game.map_manager.tile_width and \
                            0 <= ny < self.game.map_manager.tile_height):
                        break # 超出邊界，停止這個方向的延伸
                
                    tile_blocked = False # 標記這個方向的火焰是否應停止

                    # 檢查是否有不可破壞的牆 (Solid Wall)
                    if self.game.map_manager.is_solid_wall_at(nx, ny):
                        tile_blocked = True # 實心牆，火焰停止
                    
                    if not tile_blocked:
                        explosion_tiles.append((nx, ny)) # 火焰可以到達這個格子
                        
                        # 檢查是否有可破壞的牆 (Destructible Wall)
                        # 如果火焰到達這個格子，並且這個格子上是可破壞的牆，那麼牆被摧毀，火焰也到此為止
                        for d_wall in list(self.game.map_manager.destructible_walls_group):
                            # 檢查 d_wall 是否在 (nx, ny) 這個格子上
                            if d_wall.tile_x == nx and d_wall.tile_y == ny:
                                # d_wall.take_damage() # DestructibleWall 自己會 kill()
                                tile_blocked = True # 火焰摧毀了它，然後停止
                                break # 找到對應的可破壞牆壁，無需再檢查其他
                    
                    if tile_blocked:
                        break # 這個方向的火焰延伸停止
                    
                    # 檢查是否撞到不可破壞的牆壁 (Wall)
                    # 需要一種方法來查詢特定格子上是否有 Wall
                    # 簡單的方式是迭代 self.game.map_manager.walls_group
                    collided_with_solid_wall = False
                    for wall in self.game.map_manager.walls_group: # 假設 MapManager 有 walls_group
                        if wall.rect.collidepoint(nx * settings.TILE_SIZE + settings.TILE_SIZE // 2, 
                                                  ny * settings.TILE_SIZE + settings.TILE_SIZE // 2):
                            # 這裡假設 Wall 是不可破壞的。如果是 DestructibleWall，則火焰可以穿過一次。
                            # 我們目前只有 Wall (不可破壞)
                            collided_with_solid_wall = True
                            break 
                    
                    if collided_with_solid_wall:
                        break # 撞到不可破壞牆壁，停止這個方向的延伸

                    explosion_tiles.append((nx, ny))

                    # 如果是可破壞牆壁 (DestructibleWall)，火焰會摧毀它並停止在這個方向的延伸
                    # (我們之後會加入 DestructibleWall 的邏輯)
                    # for d_wall in self.game.map_manager.destructible_walls_group:
                    #     if d_wall.rect.collidepoint(nx_pixel + TILE_SIZE/2, ny_pixel + TILE_SIZE/2):
                    #         # d_wall.destroy() # 假設有個摧毀方法
                    #         break_further = True # 火焰到此為止
                    # if break_further: break

            # 根據 explosion_tiles 創建 Explosion Sprite
            for ex_tile_x, ex_tile_y in explosion_tiles:
                expl_sprite = Explosion(ex_tile_x, ex_tile_y, self.game)
                self.game.all_sprites.add(expl_sprite)
                self.game.explosions_group.add(expl_sprite) # Game 類需要有這個 group
                
            self.kill() # 從所有 Sprite Group 中移除此炸彈 Sprite