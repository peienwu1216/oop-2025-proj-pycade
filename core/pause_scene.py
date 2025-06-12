# core/pause_scene.py

import pygame
import settings

class PauseScene:
    """
    A scene that overlays the game to show pause menu options.
    """
    def __init__(self, screen, audio_manager):
        """
        Initializes the PauseScene.

        Args:
            screen (pygame.Surface): The main screen surface to draw on.
            audio_manager (AudioManager): The game's audio manager.
        """
        self.screen = screen
        self.audio_manager = audio_manager
        
        self.overlay = pygame.Surface((settings.SCREEN_WIDTH, settings.SCREEN_HEIGHT), pygame.SRCALPHA)
        self.overlay.fill((0, 0, 0, 180))

        try:
            self.title_font = pygame.font.Font(settings.TITLE_FONT_PATH, 60)
            self.option_font = pygame.font.Font(settings.CHINESE_FONT_PATH, 32)
        except Exception as e:
            print(f"PauseScene Font Error: {e}. Falling back to default.")
            self.title_font = pygame.font.Font(None, 70)
            self.option_font = pygame.font.Font(None, 40)

        self.options = ["Continue", "Back to Menu"]
        self.buttons = []
        self._create_buttons()
        self.last_hovered_button = None

    def _create_buttons(self):
        self.buttons = []
        button_width = 280
        button_height = 60
        start_y = settings.SCREEN_HEIGHT // 2 - 50
        button_spacing = 70

        for i, option_text in enumerate(self.options):
            y_pos = start_y + i * button_spacing
            rect = pygame.Rect(
                (settings.SCREEN_WIDTH - button_width) // 2,
                y_pos,
                button_width,
                button_height
            )
            self.buttons.append({"rect": rect, "text": option_text, "action": option_text.upper().replace(" ", "_")})

    def update(self, events):
        mouse_pos = pygame.mouse.get_pos()
        current_hover_target = None
        for button in self.buttons:
            if button["rect"].collidepoint(mouse_pos):
                current_hover_target = button
                break
        
        if current_hover_target and current_hover_target != self.last_hovered_button:
            self.audio_manager.play_sound('hover')
        self.last_hovered_button = current_hover_target

        for event in events:
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return "CONTINUE"

            if event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:
                    for button in self.buttons:
                        if button["rect"].collidepoint(mouse_pos):
                            return button["action"]
        return None

    def draw(self):
        self.screen.blit(self.overlay, (0, 0))

        title_surf = self.title_font.render("Paused", True, settings.WHITE)
        title_rect = title_surf.get_rect(center=(settings.SCREEN_WIDTH / 2, settings.SCREEN_HEIGHT / 4))
        self.screen.blit(title_surf, title_rect)

        mouse_pos = pygame.mouse.get_pos()
        for button in self.buttons:
            rect = button["rect"]
            text = button["text"]
            is_hovering = rect.collidepoint(mouse_pos)
            
            border_color = settings.WHITE if is_hovering else settings.GREY
            bg_color = settings.DARK_GREY if is_hovering else settings.BLACK

            pygame.draw.rect(self.screen, bg_color, rect, border_radius=10)
            pygame.draw.rect(self.screen, border_color, rect, 2, border_radius=10)
            
            text_surf = self.option_font.render(text, True, settings.WHITE)
            text_rect = text_surf.get_rect(center=rect.center)
            self.screen.blit(text_surf, text_rect) 