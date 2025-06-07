import pytest
from unittest.mock import MagicMock
import pygame.mixer

@pytest.fixture(autouse=True)
def mock_pygame_mixer():
    pygame.mixer.init = MagicMock()
    pygame.mixer.Sound = MagicMock()
    pygame.mixer.music.load = MagicMock()
    pygame.mixer.music.play = MagicMock()
    pygame.mixer.music.stop = MagicMock()
    pygame.mixer.music.set_volume = MagicMock()
