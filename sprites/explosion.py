# oop-2025-proj-pycade/sprites/explosion.py

import pygame
from .game_object import GameObject
import settings

class Explosion(GameObject):
    """
    Represents a single segment of a bomb's explosion.
    """
    def __init__(self, x_tile, y_tile, game_instance, explode_imgs):
        """
        Initializes an Explosion segment.

        Args:
            x_tile (int): The x-coordinate (in tile units) of this explosion segment.
            y_tile (int): The y-coordinate (in tile units) of this explosion segment.
            game_instance (Game): The main game instance.
            explode_imgs (list): List of image paths for explosion animation.
        """

        if settings.USE_EXPLOSION_IMAGES:
            super().__init__(
                x_tile * settings.TILE_SIZE,
                y_tile * settings.TILE_SIZE,
                settings.TILE_SIZE, # width (會被圖片覆蓋，但 GameObject 需要)
                settings.TILE_SIZE, # height (會被圖片覆蓋，但 GameObject 需要)
                image_path=settings.EXPLOSION_1_IMG # 使用單一張爆炸圖片
            )
        else: # 如果不使用圖片，則使用顏色
            super().__init__(
                x_tile * settings.TILE_SIZE,
                y_tile * settings.TILE_SIZE,
                settings.TILE_SIZE,
                settings.TILE_SIZE,
                color=settings.EXPLOSION_COLOR
            )
        self.game = game_instance
        self.spawn_time = pygame.time.get_ticks()
        self.duration = settings.EXPLOSION_DURATION
        
        if settings.USE_EXPLOSION_IMAGES:
            self.images = explode_imgs
            self.animation_index = 0
            self.frame_interval = 100  # 每張圖顯示 100 毫秒
            self.last_frame_switch = pygame.time.get_ticks()
            self.image = self.images[self.animation_index]
            self.rect = self.image.get_rect(topleft=(x_tile * settings.TILE_SIZE, y_tile * settings.TILE_SIZE))
        else:
            self.image = pygame.Surface((settings.TILE_SIZE, settings.TILE_SIZE))
            self.image.fill(settings.EXPLOSION_COLOR)
            self.rect = self.image.get_rect()

        # 如果將來使用圖片，可以在這裡處理圖片載入和可能的動畫
        # if settings.USE_EXPLOSION_IMAGES: # 假設有個設定決定是否用圖片
        #     self.image = pygame.image.load(settings.EXPLOSION_SEGMENT_IMG).convert_alpha()
        #     self.rect = self.image.get_rect(topleft=(x_tile * settings.TILE_SIZE, y_tile * settings.TILE_SIZE))

    def update(self, dt, *args): # dt is not used yet, but good practice
        """
        Checks if the explosion duration has passed. If so, removes itself.
        """
        current_time = pygame.time.get_ticks()
        
        if settings.USE_EXPLOSION_IMAGES:
            if current_time - self.last_frame_switch > self.frame_interval:
                self.animation_index = (self.animation_index + 1) % len(self.images)
                self.image = self.images[self.animation_index]
                self.last_frame_switch = current_time
            
        if current_time - self.spawn_time > self.duration:
            self.kill() # Remove from all sprite groups