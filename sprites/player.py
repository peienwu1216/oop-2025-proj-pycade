# oop-2025-proj-pycade/sprites/player.py

import pygame
from .game_object import GameObject
import settings

class Player(GameObject):
    def __init__(self, game, x_tile, y_tile, player_image_path=settings.PLAYER_IMG): # Add 'game'
        super().__init__(
            x_tile * settings.TILE_SIZE,
            y_tile * settings.TILE_SIZE,
            settings.TILE_SIZE,
            settings.TILE_SIZE,
            image_path=player_image_path
        )
        self.game = game # Store the game instance
        # ... (rest of __init__ remains the same)
        self.lives = settings.MAX_LIVES if hasattr(settings, 'MAX_LIVES') else 3
        self.bombs_available = settings.INITIAL_BOMBS if hasattr(settings, 'INITIAL_BOMBS') else 1
        self.bomb_range = settings.INITIAL_BOMB_RANGE if hasattr(settings, 'INITIAL_BOMB_RANGE') else 1
        self.score = 0
        self.speed = settings.PLAYER_SPEED if hasattr(settings, 'PLAYER_SPEED') else 4
        self.vx = 0
        self.vy = 0

        # ... (get_input and update methods as modified above)

    def get_input(self):
        # ... (get_input 內容不變) ...
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
        if self.vx != 0 and self.vy != 0:
            self.vx *= 0.7071
            self.vy *= 0.7071

    def collide_with_walls(self, dx, dy, walls_group):
        """
        Checks for collision with walls after a potential move.
        Adjusts player's rect if collision occurs.

        Args:
            dx (int): Change in x position.
            dy (int): Change in y position.
            walls_group (pygame.sprite.Group): Group of wall sprites.
        """
        # Move in x-direction
        self.rect.x += dx
        collided_walls_x = pygame.sprite.spritecollide(self, walls_group, False)
        for wall in collided_walls_x:
            if dx > 0: # Moving right
                self.rect.right = wall.rect.left
            elif dx < 0: # Moving left
                self.rect.left = wall.rect.right
        
        # Move in y-direction
        self.rect.y += dy
        collided_walls_y = pygame.sprite.spritecollide(self, walls_group, False)
        for wall in collided_walls_y:
            if dy > 0: # Moving down
                self.rect.bottom = wall.rect.top
            elif dy < 0: # Moving up
                self.rect.top = wall.rect.bottom

    def update(self, dt, walls_group):
        """
        Updates the player's state, including movement and collision.
        """
        self.get_input()

        # Store potential movement
        intended_dx = self.vx
        intended_dy = self.vy

        # Temporarily move rect to check collision without committing the full move yet
        # This is a common way: move x, check collision, then move y, check collision.
        
        # Apply movement and handle collisions separately for x and y axes
        # This prevents getting stuck in corners or sticking to walls.

        # Move in X direction and check for collisions
        self.rect.x += intended_dx
        hit_list_x = pygame.sprite.spritecollide(self, walls_group, False)
        for wall in hit_list_x:
            if intended_dx > 0:  # Moving right; hit the left side of the wall
                self.rect.right = wall.rect.left
            elif intended_dx < 0:  # Moving left; hit the right side of the wall
                self.rect.left = wall.rect.right
        
        # Move in Y direction and check for collisions
        self.rect.y += intended_dy
        hit_list_y = pygame.sprite.spritecollide(self, walls_group, False)
        for wall in hit_list_y:
            if intended_dy > 0:  # Moving down; hit the top side of the wall
                self.rect.bottom = wall.rect.top
            elif intended_dy < 0:  # Moving up; hit the bottom side of the wall
                self.rect.top = wall.rect.bottom

        # Keep player within map boundaries (using tile coordinates for map size)
        # This assumes map_manager provides map_pixel_width and map_pixel_height
        # For now, we can use a simplified boundary or define it in settings
        
        map_pixel_width = self.game.map_manager.tile_width * settings.TILE_SIZE if hasattr(self, 'game') else settings.SCREEN_WIDTH
        map_pixel_height = self.game.map_manager.tile_height * settings.TILE_SIZE if hasattr(self, 'game') else settings.SCREEN_HEIGHT

        if self.rect.left < 0:
            self.rect.left = 0
        if self.rect.right > map_pixel_width:
            self.rect.right = map_pixel_width
        if self.rect.top < 0:
            self.rect.top = 0
        if self.rect.bottom > map_pixel_height:
            self.rect.bottom = map_pixel_height


    # We need to pass the game instance to the Player if it needs to access game.map_manager
    # Let's modify Player.__init__ and Game.setup_initial_state