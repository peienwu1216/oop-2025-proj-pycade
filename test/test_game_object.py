# test/test_game_object.py

import pygame
import pytest
import settings # For TILE_SIZE, colors, etc.
from sprites.game_object import GameObject
import os # For creating a dummy image file

@pytest.fixture
def game_object_env(tmp_path):
    """
    Sets up a basic Pygame environment for GameObject tests.
    Creates a temporary dummy image file for testing image loading.
    """
    pygame.display.init()
    pygame.font.init() # Though not strictly needed for GameObject, good practice

    # Create a dummy image file for testing
    dummy_image_path = tmp_path / "dummy_image.png"
    try:
        # Create a small, simple PNG file for testing
        surface = pygame.Surface((10, 10))
        surface.fill(settings.RED) # Fill with a known color
        pygame.image.save(surface, str(dummy_image_path))
    except pygame.error as e:
        # Fallback if pygame.image.save is not available or fails (e.g., in headless CI without full display)
        # This might happen if SDL is not fully initialized or a display is needed.
        # In such a case, tests relying on actual image loading might behave differently.
        print(f"Warning: Could not save dummy image for tests: {e}. Image loading tests might be affected.")
        dummy_image_path = None # Indicate that the dummy image is not available


    yield {
        "screen": pygame.display.set_mode((settings.SCREEN_WIDTH, settings.SCREEN_HEIGHT)),
        "dummy_image_path": str(dummy_image_path) if dummy_image_path else None
    }

    pygame.quit()

class TestGameObject:
    """Test suite for the GameObject class."""

    def test_initialization_with_image_path(self, game_object_env):
        """Test GameObject initialization with a valid image_path."""
        if not game_object_env["dummy_image_path"]:
            pytest.skip("Dummy image not available, skipping image load test.")

        x, y = 10, 20
        width, height = settings.TILE_SIZE * 2, settings.TILE_SIZE
        
        game_obj = GameObject(x, y, width, height, image_path=game_object_env["dummy_image_path"])

        assert game_obj.original_image is not None, "original_image should be loaded."
        assert game_obj.image is not None, "image should be created."
        assert game_obj.rect is not None, "rect should be created."
        
        assert game_obj.rect.topleft == (x, y), "GameObject rect position is incorrect."
        assert game_obj.image.get_width() == width, "Scaled image width is incorrect."
        assert game_obj.image.get_height() == height, "Scaled image height is incorrect."
        # original_image should have the dimensions of the loaded file (10x10 in this case)
        assert game_obj.original_image.get_width() > 0
        assert game_obj.original_image.get_height() > 0


    def test_initialization_with_image_path_no_scale(self, game_object_env):
        """Test GameObject initialization with image_path but no explicit width/height for scaling."""
        if not game_object_env["dummy_image_path"]:
            pytest.skip("Dummy image not available, skipping image load test.")

        x, y = 50, 60
        # Pass 0 or None for width/height to avoid scaling
        game_obj = GameObject(x, y, 0, 0, image_path=game_object_env["dummy_image_path"])

        assert game_obj.original_image is not None
        assert game_obj.image is not None
        assert game_obj.image.get_width() == game_obj.original_image.get_width(), "Image width should match original if not scaled."
        assert game_obj.image.get_height() == game_obj.original_image.get_height(), "Image height should match original if not scaled."
        assert game_obj.rect.topleft == (x,y)


    def test_initialization_with_color(self, game_object_env):
        """Test GameObject initialization with a color."""
        x, y = 30, 40
        width, height = settings.TILE_SIZE, settings.TILE_SIZE
        color = settings.BLUE
        
        game_obj = GameObject(x, y, width, height, color=color)

        assert game_obj.original_image is not None, "original_image should be created for color."
        assert game_obj.image is not None, "image should be created for color."
        assert game_obj.rect is not None, "rect should be created."
        
        assert game_obj.rect.topleft == (x, y), "GameObject rect position is incorrect."
        assert game_obj.image.get_width() == width, "Image width for color is incorrect."
        assert game_obj.image.get_height() == height, "Image height for color is incorrect."
        
        # Check if the image is filled with the specified color
        # Getting the color of a pixel can be tricky if the surface format is complex.
        # A simpler check for solid fill is to compare with a surface created the same way.
        expected_surface = pygame.Surface([width, height])
        expected_surface.fill(color)
        # This pixel comparison is basic and might fail for subtle reasons.
        # A more robust way would be to check a few sample pixels.
        assert game_obj.image.get_at((0,0)) == expected_surface.get_at((0,0)), "Image color is incorrect."
        assert game_obj.image.get_at((width//2, height//2)) == expected_surface.get_at((width//2, height//2))


    def test_initialization_with_no_image_or_color_fallback(self, game_object_env):
        """Test GameObject initialization fallback when no image_path or color is provided."""
        x, y = 70, 80
        width, height = 20, 25 # Different from TILE_SIZE to ensure it uses these values
        
        game_obj = GameObject(x, y, width, height) # No image_path, no color

        assert game_obj.original_image is not None
        assert game_obj.image is not None
        assert game_obj.rect is not None
        
        assert game_obj.rect.topleft == (x, y)
        assert game_obj.image.get_width() == width
        assert game_obj.image.get_height() == height
        
        # Check for fallback color (Magenta: (255, 0, 255))
        assert game_obj.image.get_at((0, 0)) == (255, 0, 255), "Fallback color is not Magenta."

    def test_initialization_with_invalid_image_path_and_no_color_fallback(self, game_object_env, mocker):
        """Test fallback when image_path is invalid and no color is provided."""
        x, y = 90, 100
        width, height = 15, 15
        
        # Mock pygame.image.load to simulate an error
        mocker.patch('pygame.image.load', side_effect=pygame.error("Simulated image load error"))
        
        game_obj = GameObject(x, y, width, height, image_path="non_existent_image.png")

        assert game_obj.original_image is not None # Should still create a fallback surface for original_image
        assert game_obj.image is not None
        assert game_obj.rect is not None
        
        assert game_obj.rect.topleft == (x, y)
        assert game_obj.image.get_width() == width
        assert game_obj.image.get_height() == height
        assert game_obj.image.get_at((0, 0)) == (255, 0, 255), "Fallback to Magenta due to image load error."

    def test_initialization_with_invalid_image_path_and_color_fallback(self, game_object_env, mocker):
        """Test fallback to color when image_path is invalid but color is provided."""
        x, y = 110, 120
        width, height = 22, 22
        fallback_color = settings.GREEN
        
        mocker.patch('pygame.image.load', side_effect=pygame.error("Simulated image load error"))
        
        game_obj = GameObject(x, y, width, height, color=fallback_color, image_path="another_invalid_image.png")

        assert game_obj.original_image is not None
        assert game_obj.image is not None
        assert game_obj.rect is not None
        
        assert game_obj.rect.topleft == (x, y)
        assert game_obj.image.get_width() == width
        assert game_obj.image.get_height() == height
        assert game_obj.image.get_at((0, 0)) == fallback_color, "Should fallback to provided color."

    def test_update_method_runs_without_error(self, game_object_env):
        """Test that the base GameObject's update method can be called without errors."""
        game_obj = GameObject(0, 0, 10, 10, color=settings.BLACK)
        try:
            game_obj.update() # Call with no arguments
            game_obj.update(dt=0.1, some_arg="test") # Call with arbitrary arguments
        except Exception as e:
            pytest.fail(f"GameObject.update() raised an exception: {e}")