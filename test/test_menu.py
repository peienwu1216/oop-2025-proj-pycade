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