# oop-2025-proj-pycade/game.py

import pygame
import settings

class Game:
    """
    Main game class sorumlusu for the game loop, event handling,
    updating game state, and rendering.
    """
    def __init__(self, screen, clock):
        """
        Initializes the game.

        Args:
            screen (pygame.Surface): The main display surface.
            clock (pygame.time.Clock): The Pygame clock for managing FPS.
        """
        self.screen = screen
        self.clock = clock
        self.running = True
        self.game_state = "MENU" # Possible states: MENU, PLAYING, GAME_OVER, etc.

        # Sprite groups
        self.all_sprites = pygame.sprite.Group()
        # self.walls = pygame.sprite.Group() # We'll add more groups later
        # self.players = pygame.sprite.Group()
        # self.bombs = pygame.sprite.Group()

        # self.load_assets() # Method to load game assets (images, sounds)
        # self.setup_initial_state() # Method to setup the initial game (e.g., map, player)

    # def load_assets(self):
    #     """Load all game assets."""
    #     # Placeholder for asset loading
    #     pass

    # def setup_initial_state(self):
    #     """Sets up the initial game state, like loading a map or creating a player."""
    #     # Placeholder for initial setup
    #     pass

    def run(self):
        """Main game loop."""
        while self.running:
            self.dt = self.clock.tick(settings.FPS) / 1000.0 # Delta time in seconds

            self.events()
            self.update()
            self.draw()

    def events(self):
        """Handles all game events (input, system events)."""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            # Add more event handling here (e.g., keyboard input)
            # if event.type == pygame.KEYDOWN:
            #     if event.key == pygame.K_ESCAPE:
            #         self.running = False

    def update(self):
        """Updates the game state."""
        # This will update all sprites in the self.all_sprites group
        self.all_sprites.update(self.dt) # Pass delta time to sprites if needed for physics
        # Add more game logic updates here based on game_state

    def draw(self):
        """Draws everything to the screen."""
        self.screen.fill(settings.BLACK)  # Fill screen with a background color

        self.all_sprites.draw(self.screen) # Draw all sprites

        # Add more drawing here (e.g., HUD, menus)

        pygame.display.flip() # Update the full display