# oop-2025-proj-pycade/sprites/game_object.py

import pygame
import settings

class GameObject(pygame.sprite.Sprite):
    """
    Base class for all visible game entities.
    Inherits from pygame.sprite.Sprite.
    """
    def __init__(self, x, y, width, height, color=None, image_path=None):
        super().__init__()

        loaded_image = None
        if image_path:
            try:
                raw_image = pygame.image.load(image_path)
                loaded_image = raw_image.convert_alpha() # 使用 convert_alpha() 處理透明度
            except pygame.error as e:
                print(f"Error loading image {image_path}: {e}")
                # Fallback to a colored surface if image loading fails
        
        if loaded_image:
            self.original_image = loaded_image # 保存原始載入的圖像
            if width is None and height is not None:
                width = int(self.original_image.get_width() * (height / self.original_image.get_height()))
                self.original_image = pygame.transform.smoothscale(self.original_image, (width, height))
                self.image = self.original_image.copy() # self.image 是實際繪製和可能被修改的圖像
            elif height is None and width is not None:
                height = int(self.original_image.get_height() * (width / self.original_image.get_width()))
                self.original_image = pygame.transform.smoothscale(self.original_image, (width, height))
                self.image = self.original_image.copy() # self.image 是實際繪製和可能被修改的圖像
            elif width is not None and height is not None:
                self.original_image = pygame.transform.smoothscale(self.original_image, (width, height))
                self.image = self.original_image.copy() # self.image 是實際繪製和可能被修改的圖像
            else:
                self.image = self.original_image.copy() # self.image 是實際繪製和可能被修改的圖像
            
        elif color:
            self.original_image = pygame.Surface([width, height])
            self.original_image.fill(color)
            self.original_image.set_colorkey(settings.BLACK) # 如果顏色背景是純色且想透明化某顏色
            self.image = self.original_image.copy()
        else:
            # Default to a magenta square if neither color nor image is provided
            self.original_image = pygame.Surface([width, height])
            self.original_image.fill((255, 0, 255)) # Magenta
            self.image = self.original_image.copy()

        self.rect = self.image.get_rect()
        self.rect.topleft = (x, y)


    def update(self, *args, **kwargs):
        """
        Update method, to be overridden by subclasses for specific behavior.
        Called once per frame.
        """
        pass # Subclasses will implement their own update logic

    # Drawing is typically handled by pygame.sprite.Group.draw(screen)
    # so a specific draw() method here is often not needed unless for custom drawing.