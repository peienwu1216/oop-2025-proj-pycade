# oop-2025-proj-pycade/sprites/explosion.py

import pygame
from .game_object import GameObject
import settings

class Explosion(GameObject):
    """
    Represents a single segment of a bomb's explosion.
    """
    def __init__(self, x_tile, y_tile, game_instance):
        """
        Initializes an Explosion segment.

        Args:
            x_tile (int): The x-coordinate (in tile units) of this explosion segment.
            y_tile (int): The y-coordinate (in tile units) of this explosion segment.
            game_instance (Game): The main game instance.
        """
        # 使用顏色繪製，不使用圖片路徑參數
        super().__init__(
            x_tile * settings.TILE_SIZE,
            y_tile * settings.TILE_SIZE,
            settings.TILE_SIZE,
            settings.TILE_SIZE,
            color=settings.EXPLOSION_COLOR # 使用設定中的爆炸顏色
        )
        self.game = game_instance
        self.spawn_time = pygame.time.get_ticks()
        self.duration = settings.EXPLOSION_DURATION

        # 如果將來使用圖片，可以在這裡處理圖片載入和可能的動畫
        # if settings.USE_EXPLOSION_IMAGES: # 假設有個設定決定是否用圖片
        #     self.image = pygame.image.load(settings.EXPLOSION_SEGMENT_IMG).convert_alpha()
        #     self.rect = self.image.get_rect(topleft=(x_tile * settings.TILE_SIZE, y_tile * settings.TILE_SIZE))

    def update(self, dt, *args): # dt is not used yet, but good practice
        """
        Checks if the explosion duration has passed. If so, removes itself.
        """
        current_time = pygame.time.get_ticks()
        if current_time - self.spawn_time > self.duration:
            self.kill() # Remove from all sprite groups