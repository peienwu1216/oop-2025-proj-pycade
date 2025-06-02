import pygame
import pytest
import settings
from core.menu import Menu
from game import Game # Needed for asserting the type of returned scene
from core.leaderboard_manager import LeaderboardManager # For type checking

@pytest.fixture
def mock_menu_env(mocker):
    """
    Provides a basic Pygame environment (screen and clock) for menu tests.
    Mocks LeaderboardManager file operations.
    """
    pygame.display.init()  # Ensure display is initialized
    pygame.font.init()     # Ensure font system is initialized

    screen = pygame.display.set_mode((settings.SCREEN_WIDTH, settings.SCREEN_HEIGHT))
    clock = pygame.time.Clock() # Menu creates its own clock, but Game might need one if we test that far

    # Mock LeaderboardManager to prevent actual file I/O during tests
    mocker.patch.object(LeaderboardManager, 'load_scores', return_value=[])
    mocker.patch.object(LeaderboardManager, 'save_scores', return_value=None)
    
    yield screen, clock # Using yield to ensure pygame.quit() can be called after tests if needed
    
    pygame.quit()

class TestMenu:
    """Test suite for the Menu class."""

    def test_menu_initialization(self, mock_menu_env):
        """Test if the Menu initializes correctly."""
        screen, _ = mock_menu_env
        menu = Menu(screen)

        assert menu.screen is screen, "Menu screen should be the one provided."
        assert menu.menu_state == "MAIN", "Initial menu state should be 'MAIN'."
        assert menu.buttons, "Menu should have buttons created."
        assert len(menu.buttons) == len(settings.AVAILABLE_AI_ARCHETYPES) + 2, \
               "Menu should have a button for each AI, plus leaderboard and quit."
        assert isinstance(menu.leaderboard_manager, LeaderboardManager), \
               "Menu should have a LeaderboardManager instance."

    