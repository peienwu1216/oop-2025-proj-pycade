# oop-2025-proj-pycade/sprites/wall.py

import pygame
from .game_object import GameObject # 從同一個 sprites 套件中匯入 GameObject
import settings

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

        # 你的 C++ 版本中，道具是在可破壞障礙物被破壞後“有機率”生成的。
        # 我們可以在這裡先定義一個掉落道具的機率。
        self.item_drop_chance = 0.8 # 80% 機率掉落道具 (參考你的 C++ 報告)
        # 你還定義了不同道具的具體機率，我們之後會在掉落時處理

    def take_damage(self): # 或者直接命名為 destroy()
        """
        Handles the wall being hit by an explosion.
        """
        if not self.is_destroyed:
            self.is_destroyed = True
            print(f"DestructibleWall at ({self.tile_x}, {self.tile_y}) destroyed.")
            
            # 處理道具掉落
            self.try_drop_item()

            self.kill() # 從所有 Sprite Group 中移除自己

    def try_drop_item(self):
        """
        Determines if an item should be dropped and creates it.
        """
        if pygame.time.get_ticks() % 100 < self.item_drop_chance * 100: # 簡單的機率實現
        # 或者更標準的: if random.random() < self.item_drop_chance: (需要 import random)
            print(f"Attempting to drop item at ({self.tile_x}, {self.tile_y})")
            # item_to_drop = create_random_item(self.tile_x, self.tile_y, self.game) # 假設有這個函數
            # if item_to_drop:
            #     self.game.all_sprites.add(item_to_drop)
            #     self.game.items_group.add(item_to_drop) # Game 類需要有 items_group
            #     print(f"Dropped an item at ({self.tile_x}, {self.tile_y})")
            # 目前我們先不實現具體的道具掉落，只打印一個訊息
            # 之後我們會在 sprites/item.py 中定義道具類和 create_random_item 函數
            pass # 佔位符，表示成功觸發掉落機率，但還未生成道具