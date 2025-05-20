# oop-2025-proj-pycade/game.py

import pygame
import settings
from core.map_manager import MapManager
from sprites.player import Player # Import Player class

class Game:
    def __init__(self, screen, clock):
        self.screen = screen
        self.clock = clock
        self.running = True
        self.game_state = "PLAYING"

        self.all_sprites = pygame.sprite.Group()
        self.players_group = pygame.sprite.Group() # Group specifically for players

        self.map_manager = MapManager(self)
        self.player1 = None # Placeholder for player 1 instance

        # self.load_assets()
        self.setup_initial_state()

    # def load_assets(self):
    #     pass

    def setup_initial_state(self):
        """Sets up the initial game state."""
        # MapManager already loads the map and adds walls to self.all_sprites
        print(f"Map loaded. Number of walls: {len(self.map_manager.walls_group)}")

        # Create Player 1 - Find a walkable starting position
        # For now, let's hardcode a starting tile that should be empty on our test map
        # Test map:
        # "WWWWWWWWWWWWWWW", # 0
        # "W.............W", # 1  <- Player starts at (1,1) tile
        # "W.W.W.W.W.W.W.W", # 2
        start_tile_x, start_tile_y = 1, 1
        if self.map_manager.is_walkable(start_tile_x, start_tile_y): # Check if the spot is empty
            self.player1 = Player(start_tile_x, start_tile_y)
            self.all_sprites.add(self.player1)
            self.players_group.add(self.player1)
            print(f"Player 1 created at tile ({start_tile_x}, {start_tile_y})")
        else:
            print(f"Error: Could not find a walkable starting position for Player 1 at ({start_tile_x}, {start_tile_y})")
            # Fallback or raise an error
            # For now, let's try another spot or just print error
            self.player1 = Player(2, 1) # Try a different spot if (1,1) is blocked in future maps
            self.all_sprites.add(self.player1)
            self.players_group.add(self.player1)


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
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.running = False
            # We are using pygame.key.get_pressed() in Player.get_input()
            # so specific keydown events for movement are not strictly needed here,
            # unless you want single press actions.

    def update(self):
        # Pass necessary arguments to player's update method
        # For now, player update doesn't need walls_group, but it will soon.
        self.all_sprites.update(self.dt, self.map_manager.walls_group) # Pass walls_group

    def draw(self):
        self.screen.fill(settings.BLACK)
        self.all_sprites.draw(self.screen)
        # self.map_manager.draw_grid(self.screen)
        pygame.display.flip()