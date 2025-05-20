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

# class DestructibleWall(Wall): # 我們之後會實現這個
#     def __init__(self, x, y):
#         super().__init__(x, y) # 或者使用不同的圖片/顏色
#         # Add specific properties for destructible walls
#         pass