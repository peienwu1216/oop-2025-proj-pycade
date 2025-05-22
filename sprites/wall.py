# oop-2025-proj-pycade/sprites/wall.py

import pygame
from .game_object import GameObject # 從同一個 sprites 套件中匯入 GameObject
import settings
from .item import create_random_item # 用於掉落道具
import random # 用於 item_drop_chance 的判斷

class Wall(GameObject):
    """
    Represents an indestructible wall in the game.
    """
    def __init__(self, x, y):
        """
        Initializes a Wall object.

        Args:
            x (int): The x-coordinate (in tile units, will be converted to pixels).
            y (int): The y-coordinate (in tile units, will be converted to pixels).
        """
        # 如果你還沒準備圖片，可以用下面的 color 參數替代 image_path
        # super().__init__(
        #     x * settings.TILE_SIZE,
        #     y * settings.TILE_SIZE,
        #     settings.TILE_SIZE,
        #     settings.TILE_SIZE,
        #     color=settings.GREY # 或者其他你定義的牆壁顏色
        # )
        # 使用圖片路徑
        super().__init__(
            x * settings.TILE_SIZE,
            y * settings.TILE_SIZE,
            settings.TILE_SIZE, # width (會被圖片覆蓋，但 GameObject 需要)
            settings.TILE_SIZE, # height (會被圖片覆蓋，但 GameObject 需要)
            image_path=settings.WALL_SOLID_IMG
        )
        # Wall specific properties can be added here if needed

class DestructibleWall(Wall): # 繼承自 Wall，因為它也是一種牆
    """
    Represents a wall that can be destroyed by explosions
    and may drop an item.
    """
    def __init__(self, x_tile, y_tile, game_instance):
        """
        Initializes a DestructibleWall object.

        Args:
            x_tile (int): The x-coordinate (in tile units).
            y_tile (int): The y-coordinate (in tile units).
            game_instance (Game): The main game instance, for item spawning.
        """
        # 使用 GameObject 的 __init__，因為我們需要指定不同的圖片
        # 而不是繼承 Wall 的 __init__ (它會固定使用 WALL_SOLID_IMG)
        GameObject.__init__(self,
            x_tile * settings.TILE_SIZE,
            y_tile * settings.TILE_SIZE,
            settings.TILE_SIZE,
            settings.TILE_SIZE,
            image_path=settings.WALL_DESTRUCTIBLE_IMG # 使用可破壞牆壁的圖片
        )
        self.game = game_instance
        self.tile_x = x_tile # 儲存格子座標，方便掉落道具
        self.tile_y = y_tile
        self.is_destroyed = False
        self.item_drop_chance = settings.WALL_ITEM_DROP_CHANCE
        # 你還定義了不同道具的具體機率，我們之後會在掉落時處理

    def take_damage(self): # 或者直接命名為 destroy()
        """
        Handles the wall being hit by an explosion.
        """
        if not self.is_destroyed:
            self.is_destroyed = True
            if self.game and hasattr(self.game, 'map_manager') and self.game.map_manager:
                self.game.map_manager.update_tile_char_on_map(self.tile_x, self.tile_y, '.')
                print(f"[DestructibleWall] Wall at ({self.tile_x}, {self.tile_y}) destroyed, MapManager.map_data updated.")
            
            print(f"DestructibleWall at ({self.tile_x}, {self.tile_y}) destroyed.") # Original log
            
            self.try_drop_item()
            self.kill() 

    def try_drop_item(self):
        """
        Determines if an item should be dropped (based on item_drop_chance)
        and then creates a specific random item.
        """
        # 首先判斷這面牆本身是否掉落道具 (80% 機率)
        if random.random() < self.item_drop_chance: # random.random() 返回 [0.0, 1.0)
            print(f"DestructibleWall at ({self.tile_x}, {self.tile_y}) will attempt to drop an item.")
            # 如果觸發了掉落，再調用 create_random_item 決定掉落哪種道具
            item_to_drop = create_random_item(self.tile_x, self.tile_y, self.game)
            if item_to_drop:
                self.game.all_sprites.add(item_to_drop)
                # Game 類需要一個 items_group 來管理道具，以便玩家拾取
                if not hasattr(self.game, 'items_group'): # 為了安全，如果 Game 忘記創建
                    self.game.items_group = pygame.sprite.Group()
                self.game.items_group.add(item_to_drop)
                print(f"Dropped a {item_to_drop.type} item at ({self.tile_x}, {self.tile_y})")
        else:
            print(f"DestructibleWall at ({self.tile_x}, {self.tile_y}) did not drop an item (chance miss).")
