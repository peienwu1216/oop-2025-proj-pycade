# test/test_draw_text.py

import pygame
import pytest
import settings
from sprites.draw_text import DIGIT_MAP, draw_text_with_shadow, draw_text_with_outline

@pytest.fixture
def mock_draw_env(mocker):
    """
    Sets up a basic Pygame environment for text drawing tests.
    """
    pygame.display.init()
    pygame.font.init()

    mock_screen = mocker.Mock(spec=pygame.Surface)
    # It's important that mock_screen.blit exists for the tests to spy on.
    # The spec=pygame.Surface should handle this if the method is part of the Surface API.
    # If not, we might need mock_screen.blit = mocker.Mock() explicitly.

    # Create a real font object for testing, as font.render is crucial.
    # Using a system font to avoid issues with file paths in tests.
    try:
        mock_font = pygame.font.Font(None, 24) # Default system font, size 24
    except pygame.error:
        mock_font = pygame.font.SysFont("arial", 24) # Fallback

    # Spy on font.render and screen.blit
    mocker.spy(mock_font, 'render')
    mocker.spy(mock_screen, 'blit')
    
    yield mock_screen, mock_font

    pygame.quit()

class TestDrawText:
    """Test suite for text drawing utilities."""

    def test_digit_map_structure(self):
        """Test the structure and content of DIGIT_MAP."""
        assert isinstance(DIGIT_MAP, dict), "DIGIT_MAP should be a dictionary."
        
        required_keys = list('0123456789') + [':']
        for key in required_keys:
            assert key in DIGIT_MAP, f"DIGIT_MAP is missing key: {key}"
            assert isinstance(DIGIT_MAP[key], list), f"Value for key '{key}' should be a list (of rows)."
            
            expected_rows = 5
            assert len(DIGIT_MAP[key]) == expected_rows, f"Digit '{key}' should have {expected_rows} rows."
            
            expected_cols = 3 if key != ':' else 1
            for i, row in enumerate(DIGIT_MAP[key]):
                assert isinstance(row, list), f"Row {i} for key '{key}' should be a list."
                assert len(row) == expected_cols, \
                    f"Row {i} for key '{key}' should have {expected_cols} columns. Got {len(row)}."
                for val in row:
                    assert val in (0, 1), f"Values in DIGIT_MAP for key '{key}' should be 0 or 1. Found {val}."

