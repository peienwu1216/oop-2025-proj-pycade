# oop-2025-proj-pycade/sprites/player.py

import pygame
from .game_object import GameObject
import settings

class Player(GameObject):
    """
    Represents the player character.
    """
    def __init__(self, x_tile, y_tile, player_image_path=settings.PLAYER_IMG):
        """
        Initializes a Player object.

        Args:
            x_tile (int): The initial x-coordinate (in tile units).
            y_tile (int): The initial y-coordinate (in tile units).
            player_image_path (str, optional): Path to the player's image.
                                               Defaults to settings.PLAYER_IMG.
        """
        super().__init__(
            x_tile * settings.TILE_SIZE,
            y_tile * settings.TILE_SIZE,
            settings.TILE_SIZE, # width (will be overridden by image)
            settings.TILE_SIZE, # height (will be overridden by image)
            image_path=player_image_path
        )

        # Player specific attributes (can be expanded from your C++ Player struct)
        self.lives = settings.MAX_LIVES if hasattr(settings, 'MAX_LIVES') else 3
        self.bombs_available = settings.INITIAL_BOMBS if hasattr(settings, 'INITIAL_BOMBS') else 1
        self.bomb_range = settings.INITIAL_BOMB_RANGE if hasattr(settings, 'INITIAL_BOMB_RANGE') else 1 # C++ is 3, check settings
        self.score = 0
        self.speed = settings.PLAYER_SPEED if hasattr(settings, 'PLAYER_SPEED') else 4 # pixels per frame

        # Movement attributes
        self.vx = 0 # Velocity x
        self.vy = 0 # Velocity y

        # Store the game instance if needed for interactions
        # self.game = game # We might pass the game instance if player needs to access it directly

    def get_input(self):
        """
        Handles player input for movement.
        This version uses continuous key pressing.
        """
        self.vx, self.vy = 0, 0
        keys = pygame.key.get_pressed()

        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
            self.vx = -self.speed
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            self.vx = self.speed
        if keys[pygame.K_UP] or keys[pygame.K_w]:
            self.vy = -self.speed
        if keys[pygame.K_DOWN] or keys[pygame.K_s]:
            self.vy = self.speed

        # Normalize diagonal movement (optional, but good practice)
        if self.vx != 0 and self.vy != 0:
            # Multiply by 1/sqrt(2) (approx 0.7071)
            self.vx *= 0.7071
            self.vy *= 0.7071

    def update(self, dt, walls_group): # Add walls_group for collision later
        """
        Updates the player's state, including movement and animation.

        Args:
            dt (float): Delta time, the time since the last frame in seconds.
                        Not strictly used for this simple pixel-based movement yet,
                        but good to have for physics-based movement later.
            walls_group (pygame.sprite.Group): Group containing all wall sprites for collision.
        """
        self.get_input() # Get movement intention

        # Update position based on velocity
        # For now, simple movement without collision
        self.rect.x += self.vx
        self.rect.y += self.vy

        # --- Collision detection will be added here in the next step ---

        # Keep player on screen (optional, or handle via map boundaries)
        # if self.rect.left < 0:
        #     self.rect.left = 0
        # if self.rect.right > settings.SCREEN_WIDTH: # This should be map width later
        #     self.rect.right = settings.SCREEN_WIDTH
        # if self.rect.top < 0:
        #     self.rect.top = 0
        # if self.rect.bottom > settings.SCREEN_HEIGHT: # This should be map height later
        #     self.rect.bottom = settings.SCREEN_HEIGHT

    # place_bomb() method will be added later