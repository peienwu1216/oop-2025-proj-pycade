# test/test_wall.py

import pygame
import pytest
import settings
from sprites.wall import Wall, DestructibleWall, Floor
from sprites.item import create_random_item # Needed for DestructibleWall.try_drop_item
from core.map_manager import MapManager # Potentially needed if walls interact with map_manager directly

@pytest.fixture
def mock_wall_env(mocker):
    """
    Sets up a basic environment for testing Wall classes.
    Includes a mock game instance.
    """
    pygame.display.init() # Required for image loading if items use images
    pygame.font.init()

    # Mock Game instance
    mock_game = mocker.Mock()
    mock_game.screen = pygame.display.set_mode((settings.SCREEN_WIDTH, settings.SCREEN_HEIGHT))
    mock_game.all_sprites = pygame.sprite.Group()
    mock_game.items_group = pygame.sprite.Group() # For items dropped by DestructibleWall

    # Mock MapManager if DestructibleWall interacts with it (e.g., to update map data)
    mock_game.map_manager = mocker.Mock(spec=MapManager)
    mock_game.map_manager.tile_width = 15
    mock_game.map_manager.tile_height = 11
    mock_game.map_manager.update_tile_char_on_map = mocker.MagicMock() # Mock the method

    # Mock create_random_item to control its behavior during tests
    mocker.patch('sprites.wall.create_random_item', return_value=None) # Default to no item drop

    yield mock_game

    pygame.quit()

class TestWallClasses:
    """Test suite for Wall, DestructibleWall, and Floor classes."""

    def test_wall_initialization(self, mock_wall_env):
        """Test Wall (indestructible) initialization."""
        game = mock_wall_env
        wall_x_tile, wall_y_tile = 2, 3
        
        wall = Wall(wall_x_tile, wall_y_tile)

        assert wall.image is not None, "Wall should have an image."
        assert wall.rect.topleft == (wall_x_tile * settings.TILE_SIZE, wall_y_tile * settings.TILE_SIZE), \
            "Wall rect position is incorrect."
        # Ensure it uses the solid wall image
        # This requires comparing surfaces or checking the loaded path, which can be tricky.
        # For simplicity, we assume GameObject loads the correct image based on settings.WALL_SOLID_IMG.

    def test_destructible_wall_initialization(self, mock_wall_env):
        """Test DestructibleWall initialization."""
        game = mock_wall_env
        dw_x_tile, dw_y_tile = 4, 5

        d_wall = DestructibleWall(dw_x_tile, dw_y_tile, game)

        assert d_wall.game is game, "DestructibleWall should store the game instance."
        assert d_wall.tile_x == dw_x_tile, "DestructibleWall tile_x is incorrect."
        assert d_wall.tile_y == dw_y_tile, "DestructibleWall tile_y is incorrect."
        assert d_wall.is_destroyed is False, "DestructibleWall should not be destroyed initially."
        assert d_wall.item_drop_chance == settings.WALL_ITEM_DROP_CHANCE, \
            "DestructibleWall item_drop_chance is incorrect."
        assert d_wall.image is not None, "DestructibleWall should have an image."
        assert d_wall.rect.topleft == (dw_x_tile * settings.TILE_SIZE, dw_y_tile * settings.TILE_SIZE), \
            "DestructibleWall rect position is incorrect."
        # Similar to Wall, assume GameObject loads settings.WALL_DESTRUCTIBLE_IMG.

    def test_destructible_wall_take_damage(self, mock_wall_env, mocker):
        """Test DestructibleWall's take_damage method."""
        game = mock_wall_env
        dw_x_tile, dw_y_tile = 3, 3
        d_wall = DestructibleWall(dw_x_tile, dw_y_tile, game)
        
        # Mock the try_drop_item and kill methods to check if they are called
        d_wall.try_drop_item = mocker.MagicMock()
        d_wall.kill = mocker.MagicMock()
        
        # Add to a group to test kill behavior (optional, but good practice)
        temp_group = pygame.sprite.Group(d_wall)
        assert d_wall in temp_group

        d_wall.take_damage()

        assert d_wall.is_destroyed is True, "is_destroyed should be True after take_damage."
        game.map_manager.update_tile_char_on_map.assert_called_once_with(dw_x_tile, dw_y_tile, '.'), \
            "MapManager.update_tile_char_on_map was not called correctly."
        d_wall.try_drop_item.assert_called_once(), "try_drop_item should be called."
        d_wall.kill.assert_called_once(), "kill should be called."
        
        # If kill was properly mocked to remove from groups:
        # assert d_wall not in temp_group # This depends on how deeply kill is mocked

    def test_destructible_wall_try_drop_item_no_drop(self, mock_wall_env, mocker):
        """Test try_drop_item when no item should drop."""
        game = mock_wall_env
        dw_x_tile, dw_y_tile = 2, 2
        d_wall = DestructibleWall(dw_x_tile, dw_y_tile, game)

        # Mock random.random to ensure item drop condition is NOT met
        mocker.patch('random.random', return_value=d_wall.item_drop_chance + 0.1) # Guarantees no drop
        
        # Re-patch create_random_item to check it's NOT called, or ensure it returns None
        # The fixture already patches it to return None by default. We can verify it wasn't called
        # if random.random causes an early exit, or that no item was added to groups.
        create_random_item_mock = mocker.patch('sprites.wall.create_random_item', return_value=None)


        initial_all_sprites_count = len(game.all_sprites)
        initial_items_group_count = len(game.items_group)

        d_wall.try_drop_item()
        
        # create_random_item might still be called if random.random() passes the first check,
        # but its return value (None) means no item is added.
        # A more robust check is that no item was added to the groups.
        assert len(game.all_sprites) == initial_all_sprites_count, \
            "all_sprites group count should not change if no item drops."
        assert len(game.items_group) == initial_items_group_count, \
            "items_group count should not change if no item drops."


    def test_floor_initialization(self, mock_wall_env):
        """Test Floor initialization."""
        # Floor doesn't use mock_wall_env directly, but we keep the fixture for consistency
        floor_x_tile, floor_y_tile = 5, 6
        
        floor_tile = Floor(floor_x_tile, floor_y_tile)

        assert floor_tile.image is not None, "Floor should have an image."
        assert floor_tile.rect.topleft == (floor_x_tile * settings.TILE_SIZE, floor_y_tile * settings.TILE_SIZE), \
            "Floor rect position is incorrect."
        # Assume GameObject loads settings.STONE_0_IMG correctly.
    
        # Similar to Wall, we assume the image is loaded based on settings.STONE_0_IMG.
    
        # If Floor has specific properties or methods, they can be tested here.
        