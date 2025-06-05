# test/test_settings.py

import pytest
import os
import pygame # For color and font checks
import settings # The module we are testing

# --- Global configuration for path testing ---
# Set this to True if you want to strictly check if all defined paths exist.
# For CI/CD environments or initial setups, keeping it False might be more practical
# as not all asset paths might be populated or accessible.
CHECK_PATHS_EXIST = False # Default to False

class TestSettings:
    """Test suite for the settings.py configuration file."""

    def test_basic_game_settings_exist_and_types(self):
        """Test general game settings for existence and correct types."""
        assert hasattr(settings, 'TITLE'), "TITLE setting is missing."
        assert isinstance(settings.TITLE, str), "TITLE should be a string."

        assert hasattr(settings, 'SCREEN_WIDTH'), "SCREEN_WIDTH setting is missing."
        assert isinstance(settings.SCREEN_WIDTH, int), "SCREEN_WIDTH should be an integer."
        assert settings.SCREEN_WIDTH > 0, "SCREEN_WIDTH should be positive."

        assert hasattr(settings, 'SCREEN_HEIGHT'), "SCREEN_HEIGHT setting is missing."
        assert isinstance(settings.SCREEN_HEIGHT, int), "SCREEN_HEIGHT should be an integer."
        assert settings.SCREEN_HEIGHT > 0, "SCREEN_HEIGHT should be positive."

        assert hasattr(settings, 'FPS'), "FPS setting is missing."
        assert isinstance(settings.FPS, int), "FPS should be an integer."
        assert settings.FPS > 0, "FPS should be positive."

    def test_color_definitions(self):
        """Test color definitions for correct format (tuple of 3 or 4 ints between 0-255)."""
        colors_to_test = {
            'BLACK': settings.BLACK,
            'WHITE': settings.WHITE,
            'RED': settings.RED,
            'GREEN': settings.GREEN,
            'BLUE': settings.BLUE,
            'GREY': settings.GREY,
            'LIGHT_BROWN': settings.LIGHT_BROWN,
            'GAME_TIME_UP_MESSAGE_COLOR': settings.GAME_TIME_UP_MESSAGE_COLOR,
            'TIMER_COLOR': settings.TIMER_COLOR,
            'TIMER_URGENT_COLOR': settings.TIMER_URGENT_COLOR,
            'TEXT_INPUT_BOX_COLOR_INACTIVE': settings.TEXT_INPUT_BOX_COLOR_INACTIVE,
            'TEXT_INPUT_BOX_COLOR_ACTIVE': settings.TEXT_INPUT_BOX_COLOR_ACTIVE,
            'TEXT_INPUT_PROMPT_COLOR': settings.TEXT_INPUT_PROMPT_COLOR,
            'TEXT_INPUT_TEXT_COLOR': settings.TEXT_INPUT_TEXT_COLOR,
        }
        for color_name, color_value in colors_to_test.items():
            assert hasattr(settings, color_name), f"{color_name} setting is missing."
            assert isinstance(color_value, (tuple, pygame.Color)), \
                f"{color_name} should be a tuple or pygame.Color. Got {type(color_value)}"
            
            # If it's a pygame.Color, convert to tuple for length check
            if isinstance(color_value, pygame.Color):
                color_tuple = (color_value.r, color_value.g, color_value.b, color_value.a)
                # Pygame.Color might not always have alpha if not set, default is 255
                assert len(color_tuple) == 3 or len(color_tuple) == 4, \
                    f"{color_name} (pygame.Color) should have 3 or 4 components (RGB or RGBA)."
                components_to_check = color_tuple[:3] # Check R, G, B
            else: # It's a tuple
                assert len(color_value) == 3 or len(color_value) == 4, \
                    f"{color_name} tuple should have 3 or 4 components (RGB or RGBA)."
                components_to_check = color_value[:3]

            for component in components_to_check:
                assert isinstance(component, int), f"{color_name} components should be integers."
                assert 0 <= component <= 255, f"{color_name} components should be between 0 and 255."

    def test_gameplay_mechanics_settings(self):
        """Test gameplay mechanics settings."""
        assert isinstance(settings.GAME_DURATION_SECONDS, int) and settings.GAME_DURATION_SECONDS > 0
        assert isinstance(settings.TIMER_URGENT_THRESHOLD_SECONDS, int) and settings.TIMER_URGENT_THRESHOLD_SECONDS >= 0
        assert isinstance(settings.TILE_SIZE, int) and settings.TILE_SIZE > 0
        assert isinstance(settings.DESTRUCTIBLE_WALL_CHANCE, float) and 0.0 <= settings.DESTRUCTIBLE_WALL_CHANCE <= 1.0

    def test_player_settings(self):
        """Test player character settings."""
        assert isinstance(settings.MAX_LIVES, int) and settings.MAX_LIVES > 0
        assert isinstance(settings.INITIAL_BOMBS, int) and settings.INITIAL_BOMBS >= 0
        assert isinstance(settings.INITIAL_BOMB_RANGE, int) and settings.INITIAL_BOMB_RANGE >= 0
        assert isinstance(settings.PLAYER_SPRITE_FRAME_WIDTH, int) and settings.PLAYER_SPRITE_FRAME_WIDTH > 0
        assert isinstance(settings.PLAYER_SPRITE_FRAME_HEIGHT, int) and settings.PLAYER_SPRITE_FRAME_HEIGHT > 0
        assert isinstance(settings.PLAYER_ANIMATION_SPEED, float) and settings.PLAYER_ANIMATION_SPEED > 0
        assert isinstance(settings.PLAYER_NUM_WALK_FRAMES, int) and settings.PLAYER_NUM_WALK_FRAMES > 0
        assert isinstance(settings.PLAYER_VISUAL_SCALE_FACTOR, float) and settings.PLAYER_VISUAL_SCALE_FACTOR > 0
        assert isinstance(settings.PLAYER_HITBOX_WIDTH_REDUCTION, int)
        assert isinstance(settings.PLAYER_HITBOX_HEIGHT_REDUCTION, int)
        assert isinstance(settings.HUMAN_GRID_MOVE_ACTION_DURATION, float) and settings.HUMAN_GRID_MOVE_ACTION_DURATION >= 0
        assert isinstance(settings.PLAYER_INVINCIBLE_DURATION, int) and settings.PLAYER_INVINCIBLE_DURATION >= 0

    def test_bomb_and_explosion_settings(self):
        """Test bomb and explosion settings."""
        assert isinstance(settings.BOMB_TIMER, int) and settings.BOMB_TIMER > 0
        assert isinstance(settings.EXPLOSION_DURATION, int) and settings.EXPLOSION_DURATION > 0
        assert isinstance(settings.USE_EXPLOSION_IMAGES, bool)
        assert isinstance(settings.EXPLOSION_COLOR, tuple) # Assuming it's a color tuple if not using images

    def test_item_settings(self):
        """Test item settings."""
        item_types = [
            settings.ITEM_TYPE_SCORE, settings.ITEM_TYPE_LIFE,
            settings.ITEM_TYPE_BOMB_CAPACITY, settings.ITEM_TYPE_BOMB_RANGE
        ]
        for item_type in item_types:
            assert isinstance(item_type, str)

        assert isinstance(settings.ITEM_DROP_WEIGHTS, dict)
        for key, value in settings.ITEM_DROP_WEIGHTS.items():
            assert key in item_types, f"Unknown item type '{key}' in ITEM_DROP_WEIGHTS."
            assert isinstance(value, (int, float)) and value >= 0, f"Weight for '{key}' should be non-negative number."
        
        assert isinstance(settings.WALL_ITEM_DROP_CHANCE, float) and 0.0 <= settings.WALL_ITEM_DROP_CHANCE <= 1.0
        assert isinstance(settings.SCORE_ITEM_VALUE, int) and settings.SCORE_ITEM_VALUE >= 0
        assert isinstance(settings.GENERIC_ITEM_SCORE_VALUE, int) and settings.GENERIC_ITEM_SCORE_VALUE >= 0

    def test_ai_settings(self):
        """Test AI settings."""
        assert isinstance(settings.AVAILABLE_AI_ARCHETYPES, dict)
        for display_name, key in settings.AVAILABLE_AI_ARCHETYPES.items():
            assert isinstance(display_name, str)
            assert isinstance(key, str)
        
        assert settings.AI_OPPONENT_ARCHETYPE in settings.AVAILABLE_AI_ARCHETYPES.values()
        assert isinstance(settings.AI_MOVE_DELAY, int) and settings.AI_MOVE_DELAY >= 0
        assert isinstance(settings.AI_GRID_MOVE_ACTION_DURATION, float) and settings.AI_GRID_MOVE_ACTION_DURATION >=0

        # Basic checks for other AI params, more detailed checks would be in AI tests
        assert isinstance(settings.AI_ENGAGE_MIN_DIST_TO_PLAYER_FOR_DIRECT_PATH, int)
        assert isinstance(settings.AI_EVASION_SAFETY_CHECK_FUTURE_SECONDS, float)
        assert isinstance(settings.AI_CONSERVATIVE_RETREAT_DEPTH, int)

    def test_ui_and_display_settings(self):
        """Test UI and display settings."""
        assert isinstance(settings.TEXT_INPUT_FONT_SIZE, int) and settings.TEXT_INPUT_FONT_SIZE > 0
        assert isinstance(settings.TEXT_INPUT_MAX_LENGTH, int) and settings.TEXT_INPUT_MAX_LENGTH > 0
        assert isinstance(settings.HUD_AI_OFFSET_X, int)

    def test_leaderboard_settings(self):
        """Test leaderboard settings."""
        assert isinstance(settings.LEADERBOARD_FILE, str)
        assert settings.LEADERBOARD_FILE.endswith(".json"), "LEADERBOARD_FILE should be a .json file."
        assert isinstance(settings.LEADERBOARD_MAX_ENTRIES, int) and settings.LEADERBOARD_MAX_ENTRIES > 0
        
        if CHECK_PATHS_EXIST:
            # Check if the directory for the leaderboard file exists or can be created
            leaderboard_dir = os.path.dirname(settings.LEADERBOARD_FILE)
            assert os.path.exists(leaderboard_dir) or os.access(os.path.dirname(leaderboard_dir) or '.', os.W_OK), \
                f"Leaderboard directory {leaderboard_dir} does not exist and cannot be created."
            