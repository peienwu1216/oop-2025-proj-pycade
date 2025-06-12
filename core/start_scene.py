# core/start_scene.py

import pygame
import settings
from core.menu import Menu

class StartScene:
    """
    A scene displayed at the very beginning of the game.
    It waits for user interaction to unmute the audio context in the browser
    before transitioning to the main menu.
    """
    def __init__(self, screen, audio_manager, clock):
        """
        Initializes the StartScene.

        Args:
            screen (pygame.Surface): The main screen surface to draw on.
            audio_manager (AudioManager): The game's audio manager.
            clock (pygame.time.Clock): The game's clock.
        """
        self.screen = screen
        self.audio_manager = audio_manager
        self.clock = clock
        self.next_scene = self

        try:
            # Load the background image
            self.background_image = pygame.image.load(settings.MENU_BACKGROUND_IMG).convert()
            self.background_image = pygame.transform.scale(self.background_image, (settings.SCREEN_WIDTH, settings.SCREEN_HEIGHT))

            # Try to use a prominent font from settings
            self.title_font = pygame.font.Font(settings.TITLE_FONT_PATH, 52)
            self.prompt_font = pygame.font.Font(settings.SUB_TITLE_FONT_PATH, 28)
        except (pygame.error, FileNotFoundError) as e:
            print(f"StartScene Font Error: {e}. Falling back to default.")
            # Fallback to default system font if specified fonts fail to load
            self.title_font = pygame.font.Font(None, 64)
            self.prompt_font = pygame.font.Font(None, 32)

        # Prepare the text surfaces (rendered once for efficiency)
        self.title_surf = self.title_font.render(settings.TITLE, True, settings.WHITE)
        self.title_rect = self.title_surf.get_rect(center=(settings.SCREEN_WIDTH / 2, settings.SCREEN_HEIGHT / 2 - 50))

        self.prompt_surf = self.prompt_font.render("Click or Press any key to Start", True, settings.WHITE)
        self.prompt_rect = self.prompt_surf.get_rect(center=(settings.SCREEN_WIDTH / 2, self.title_rect.bottom + 40))

        # Blinking effect for the prompt text
        self.prompt_visible = True
        self.blink_timer = 0
        self.blink_interval = 500  # milliseconds

    def update(self, events, dt):
        """
        Handles events and updates the scene's state for one frame.

        Args:
            events (list): A list of pygame events from the main loop.
            dt (float): The delta time in seconds for the last frame.

        Returns:
            The next scene to be run. Returns `self` to continue this scene.
        """
        # Update the blink timer
        self.blink_timer += dt * 1000  # convert dt to milliseconds
        if self.blink_timer >= self.blink_interval:
            self.prompt_visible = not self.prompt_visible
            self.blink_timer = 0

        # Check for user interaction to transition to the main menu
        for event in events:
            if event.type == pygame.MOUSEBUTTONDOWN or event.type == pygame.KEYDOWN:
                # --- AUDIO FIX FOR BROWSERS ---
                # Play and immediately pause the music on the first user interaction.
                # This "unlocks" the audio context for the music channel.
                try:
                    self.audio_manager.play_music(settings.MENU_MUSIC_PATH, loops=-1)
                    self.audio_manager.pause_music()
                except Exception as e:
                    print(f"Error pre-loading music for browser: {e}")
                # --- END AUDIO FIX ---

                # Transition to the Menu scene
                return Menu(self.screen, self.audio_manager, self.clock)
        
        return self # Continue running this scene

    def draw(self):
        """
        Draws the scene to the screen.
        """
        # self.screen.fill(settings.BLACK) # A simple black background
        self.screen.blit(self.background_image, (0, 0))

        # Draw the game title
        self.screen.blit(self.title_surf, self.title_rect)

        # Draw the blinking prompt text
        if self.prompt_visible:
            self.screen.blit(self.prompt_surf, self.prompt_rect)
        
        # This scene doesn't call pygame.display.flip() itself.
        # The main loop is responsible for that. 