# oop-2025-proj-pycade/game.py

import pygame
import settings
from core.map_manager import MapManager # Import MapManager

class Game:
    def __init__(self, screen, clock):
        self.screen = screen
        self.clock = clock
        self.running = True
        self.game_state = "PLAYING" # Let's start in PLAYING state for now

        self.all_sprites = pygame.sprite.Group()
        # self.walls_group will be managed by MapManager but Game needs to know about all_sprites

        self.map_manager = MapManager(self) # Pass the game instance to MapManager

        # self.load_assets()
        self.setup_initial_state()

    # def load_assets(self):
    #     pass

    def setup_initial_state(self):
        """Sets up the initial game state."""
        # MapManager already loads the map and adds walls to self.all_sprites in its __init__
        print(f"Map loaded. Number of walls: {len(self.map_manager.walls_group)}")
        print(f"Total sprites in all_sprites: {len(self.all_sprites)}")


    def run(self):
        while self.running:
            self.dt = self.clock.tick(settings.FPS) / 1000.0
            self.events()
            self.update()
            self.draw()

    def events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            if event.type == pygame.KEYDOWN: # Added for quick testing
                if event.key == pygame.K_ESCAPE:
                    self.running = False

    def update(self):
        self.all_sprites.update(self.dt)

    def draw(self):
        self.screen.fill(settings.BLACK)
        self.all_sprites.draw(self.screen)

        # Optionally draw the grid for debugging
        # self.map_manager.draw_grid(self.screen)

        pygame.display.flip()