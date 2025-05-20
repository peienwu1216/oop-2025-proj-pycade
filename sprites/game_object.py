# oop-2025-proj-pycade/sprites/game_object.py

import pygame

class GameObject(pygame.sprite.Sprite):
    """
    Base class for all visible game entities.
    Inherits from pygame.sprite.Sprite.
    """
    def __init__(self, x, y, width, height, color=None, image_path=None):
        """
        Initializes a GameObject.

        Args:
            x (int): The x-coordinate of the top-left corner.
            y (int): The y-coordinate of the top-left corner.
            width (int): The width of the object.
            height (int): The height of the object.
            color (tuple, optional): RGB color tuple if creating a colored surface. Defaults to None.
            image_path (str, optional): Path to an image file. Defaults to None.
        """
        super().__init__() # Call the parent class (Sprite) constructor

        if image_path:
            try:
                self.original_image = pygame.image.load(image_path).convert_alpha()
                # convert_alpha() is good for images with transparency
            except pygame.error as e:
                print(f"Error loading image {image_path}: {e}")
                # Fallback to a colored surface if image loading fails
                self.original_image = pygame.Surface([width, height])
                self.original_image.fill(color if color else (255, 0, 255)) # Magenta for error
        elif color:
            self.original_image = pygame.Surface([width, height])
            self.original_image.fill(color)
        else:
            # Default to a magenta square if neither color nor image is provided
            self.original_image = pygame.Surface([width, height])
            self.original_image.fill((255, 0, 255)) # Magenta indicates missing asset or config

        self.image = self.original_image # This is the image that will be drawn
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