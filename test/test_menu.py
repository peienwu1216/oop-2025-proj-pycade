# test/test_menu.py

import pygame
import pytest
import settings
from core.menu import Menu
from game import Game # Needed for asserting the type of returned scene
from core.leaderboard_manager import LeaderboardManager # For type checking
from unittest.mock import MagicMock

# ！！！～～～
# 將 mock_audio_manager fixture 直接定義在此處
@pytest.fixture
def mock_audio_manager(mocker):
    """Provides a mocked AudioManager instance for tests."""
    mock_manager = MagicMock()
    mock_manager.play_sound = MagicMock()
    mock_manager.play_music = MagicMock()
    mock_manager.stop_music = MagicMock()
    mock_manager.stop_all_sounds = MagicMock()
    return mock_manager

# 修改 fixture，讓它接收並提供 audio_manager
@pytest.fixture
def mock_menu_env(mocker, mock_audio_manager): # <-- 接收 mock_audio_manager
    """
    Provides a basic Pygame environment (screen and clock) for menu tests.
    Mocks LeaderboardManager file operations.
    """
    pygame.display.init()
    pygame.font.init()

    screen = pygame.display.set_mode((settings.SCREEN_WIDTH, settings.SCREEN_HEIGHT))
    clock = pygame.time.Clock()

    # Mock LeaderboardManager to prevent actual file I/O
    mocker.patch.object(LeaderboardManager, 'load_scores', return_value=[])
    mocker.patch.object(LeaderboardManager, 'save_scores', return_value=None)
    
    # 將 audio_manager 一起回傳
    yield screen, clock, mock_audio_manager
    
    pygame.quit()
# ！！！～～～


class TestMenu:
    """Test suite for the Menu class."""

    def test_menu_initialization(self, mock_menu_env):
        """Test if the Menu initializes correctly."""
        screen, clock, audio_manager = mock_menu_env
        menu = Menu(screen, audio_manager, clock)

        assert menu.screen is screen
        assert menu.menu_state == "MAIN"
        assert menu.buttons
        assert len(menu.buttons) == len(settings.AVAILABLE_AI_ARCHETYPES) + 2
        assert isinstance(menu.leaderboard_manager, LeaderboardManager)
    
    def find_button_by_action(self, buttons, action_type, archetype_key=None):
        """Helper to find a button by its action_type and optionally archetype_key."""
        for button in buttons:
            if button.get("action_type") == action_type:
                if archetype_key:
                    if button.get("archetype") == archetype_key:
                        return button
                else:
                    return button
        return None
    
    def test_menu_shows_leaderboard(self, mock_menu_env):
        """Test if clicking the leaderboard button changes the menu state."""
        screen, clock, audio_manager = mock_menu_env
        menu = Menu(screen, audio_manager, clock)

        leaderboard_button = self.find_button_by_action(menu.buttons, "SHOW_LEADERBOARD")
        assert leaderboard_button is not None

        mouse_click_event = pygame.event.Event(
            pygame.MOUSEBUTTONDOWN,
            {'button': 1, 'pos': leaderboard_button["rect"].center}
        )
        
        next_scene_or_action = menu.update([mouse_click_event])
        
        assert menu.menu_state == "LEADERBOARD"
        assert next_scene_or_action is menu

    def test_menu_quit_game_action(self, mock_menu_env):
        """Test if clicking the quit button returns the 'QUIT' action."""
        screen, clock, audio_manager = mock_menu_env
        menu = Menu(screen, audio_manager, clock)

        quit_button = self.find_button_by_action(menu.buttons, "QUIT_GAME")
        assert quit_button is not None

        mouse_click_event = pygame.event.Event(
            pygame.MOUSEBUTTONDOWN,
            {'button': 1, 'pos': quit_button["rect"].center}
        )
        
        action = menu.update([mouse_click_event])
        assert action == "QUIT"
    
    def test_menu_select_ai_starts_game(self, mock_menu_env):
        """Test if selecting an AI opponent returns a Game instance."""
        screen, clock, audio_manager = mock_menu_env
        menu = Menu(screen, audio_manager, clock)

        first_ai_display_name = list(settings.AVAILABLE_AI_ARCHETYPES.keys())[0]
        first_ai_archetype_key = settings.AVAILABLE_AI_ARCHETYPES[first_ai_display_name]

        ai_button = self.find_button_by_action(menu.buttons, "SELECT_AI", first_ai_archetype_key)
        assert ai_button is not None

        mouse_click_event = pygame.event.Event(
            pygame.MOUSEBUTTONDOWN,
            {'button': 1, 'pos': ai_button["rect"].center}
        )
        
        next_scene = menu.update([mouse_click_event])
        
        assert isinstance(next_scene, Game)
        assert hasattr(next_scene, 'audio_manager')
        assert next_scene.ai_archetype == first_ai_archetype_key
        assert next_scene.screen is screen
    
    def test_menu_escape_from_leaderboard_returns_to_main(self, mock_menu_env):
        """Test if pressing ESC in leaderboard view returns to the main menu state."""
        screen, clock, audio_manager = mock_menu_env
        menu = Menu(screen, audio_manager, clock)
        menu.menu_state = "LEADERBOARD"

        escape_key_event = pygame.event.Event(pygame.KEYDOWN, {'key': pygame.K_ESCAPE})
        
        next_scene_or_action = menu.update([escape_key_event])
        
        assert menu.menu_state == "MAIN"
        assert next_scene_or_action is menu
    
    def test_menu_escape_from_main_menu_quits(self, mock_menu_env):
        """Test if pressing ESC in the main menu returns the 'QUIT' action."""
        screen, clock, audio_manager = mock_menu_env
        menu = Menu(screen, audio_manager, clock)
        
        assert menu.menu_state == "MAIN"

        escape_key_event = pygame.event.Event(pygame.KEYDOWN, {'key': pygame.K_ESCAPE})
        
        action = menu.update([escape_key_event])
        assert action == "QUIT"
    
    def test_menu_leaderboard_display(self, mock_menu_env):
        """Test if the leaderboard displays correctly."""
        screen, clock, audio_manager = mock_menu_env
        menu = Menu(screen, audio_manager, clock)

        leaderboard_button = self.find_button_by_action(menu.buttons, "SHOW_LEADERBOARD")
        mouse_click_event = pygame.event.Event(
            pygame.MOUSEBUTTONDOWN,
            {'button': 1, 'pos': leaderboard_button["rect"].center}
        )
        menu.update([mouse_click_event])
        assert menu.menu_state == "LEADERBOARD"
        assert menu.leaderboard_manager is not None
        assert menu.leaderboard_manager.scores == []
    
    def test_menu_button_positions(self, mock_menu_env):
        """Test if buttons are positioned correctly."""
        screen, clock, audio_manager = mock_menu_env
        menu = Menu(screen, audio_manager, clock)

        for button in menu.buttons:
            assert button["rect"].x >= 0
            assert button["rect"].y >= 0
            assert button["rect"].right <= settings.SCREEN_WIDTH
            assert button["rect"].bottom <= settings.SCREEN_HEIGHT
            assert button["rect"].width > 0
            assert button["rect"].height > 0