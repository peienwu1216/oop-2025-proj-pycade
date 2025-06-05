# test/test_item.py

import pygame
import pytest
import settings
import random # For testing create_random_item
from sprites.item import Item, ScoreItem, LifeItem, BombCapacityItem, BombRangeItem, create_random_item
from sprites.player import Player # Items are applied to players

@pytest.fixture
def mock_item_env(mocker):
    """
    Sets up a basic environment for testing items.
    Includes a mock game instance and a mock player.
    """
    pygame.display.init() # Required for image loading if items use images
    pygame.font.init()    # Potentially, if items drew text (though unlikely)

    # Mock Game instance
    mock_game = mocker.Mock()
    mock_game.screen = pygame.display.set_mode((settings.SCREEN_WIDTH, settings.SCREEN_HEIGHT))
    # Items might add themselves to game.all_sprites or game.items_group,
    # but for apply_effect, these are not strictly necessary if we just check player attributes.
    mock_game.all_sprites = pygame.sprite.Group()
    mock_game.items_group = pygame.sprite.Group()
    
    # Mock Player instance
    # Player needs game, x_tile, y_tile, spritesheet_path, sprite_config
    # For item tests, we mainly care about its attributes that items modify.
    player_sprite_config = {"ROW_MAP": {}, "NUM_FRAMES": 1} # Minimal config
    mock_player = Player(
        game=mock_game, 
        x_tile=1, 
        y_tile=1, 
        spritesheet_path=settings.PLAYER1_SPRITESHEET_PATH, # Needs a valid path
        sprite_config=player_sprite_config
    )
    # Reset player attributes to known defaults before each test using this fixture
    mock_player.score = 0
    mock_player.lives = settings.MAX_LIVES
    mock_player.max_bombs = settings.INITIAL_BOMBS
    mock_player.bomb_range = settings.INITIAL_BOMB_RANGE
    
    yield mock_game, mock_player

    pygame.quit()

class TestItems:
    """Test suite for various Item classes and item creation."""

    def test_score_item_initialization(self, mock_item_env):
        """Test ScoreItem initialization."""
        game, player = mock_item_env
        item_x, item_y = 2, 2
        
        score_item = ScoreItem(item_x, item_y, game)

        assert score_item.type == settings.ITEM_TYPE_SCORE
        assert score_item.game is game
        # Check if image is loaded (GameObject's responsibility, but good to see it doesn't crash)
        assert score_item.image is not None, "ScoreItem should have an image."
        assert score_item.rect.topleft == (item_x * settings.TILE_SIZE, item_y * settings.TILE_SIZE)
        assert score_item.score_value == settings.SCORE_ITEM_VALUE, \
            f"ScoreItem's score_value should be {settings.SCORE_ITEM_VALUE}"

    def test_score_item_apply_effect(self, mock_item_env):
        """Test ScoreItem's effect on player score."""
        game, player = mock_item_env
        initial_score = player.score
        
        score_item = ScoreItem(2, 2, game)
        score_item.apply_effect(player) # This also calls item.kill()

        expected_score = initial_score + settings.SCORE_ITEM_VALUE
        assert player.score == expected_score, \
            f"Player score should be {expected_score} after collecting ScoreItem, but was {player.score}."
        
        # Verify the item removes itself from groups if it was added
        # (apply_effect calls self.kill()). For this, it needs to be in a group.
        # We can add it manually to a mock group to test kill.
        mock_group = pygame.sprite.Group()
        score_item_for_kill_test = ScoreItem(3,3,game)
        mock_group.add(score_item_for_kill_test)
        
        assert score_item_for_kill_test in mock_group
        score_item_for_kill_test.apply_effect(player) # This should call kill
        assert score_item_for_kill_test not in mock_group, "Item should be removed from group after apply_effect."

    def test_life_item_initialization(self, mock_item_env):
        """Test LifeItem initialization."""
        game, player = mock_item_env
        item_x, item_y = 2, 3
        
        life_item = LifeItem(item_x, item_y, game)

        assert life_item.type == settings.ITEM_TYPE_LIFE
        assert life_item.image is not None, "LifeItem should have an image."
        assert life_item.rect.topleft == (item_x * settings.TILE_SIZE, item_y * settings.TILE_SIZE)
        # Non-score items also grant a generic score value
        assert life_item.score_value == settings.GENERIC_ITEM_SCORE_VALUE

    def test_life_item_apply_effect(self, mock_item_env):
        """Test LifeItem's effect on player lives and score."""
        game, player = mock_item_env
        initial_lives = player.lives
        initial_score = player.score
        
        life_item = LifeItem(2, 3, game)
        life_item.apply_effect(player)

        expected_lives = initial_lives + 1
        expected_score = initial_score + settings.GENERIC_ITEM_SCORE_VALUE
        
        assert player.lives == expected_lives, \
            f"Player lives should be {expected_lives} after LifeItem, but was {player.lives}."
        assert player.score == expected_score, \
            f"Player score should increase by {settings.GENERIC_ITEM_SCORE_VALUE} for LifeItem."

    def test_bomb_capacity_item_initialization(self, mock_item_env):
        """Test BombCapacityItem initialization."""
        game, player = mock_item_env
        item_x, item_y = 3, 3
        
        bomb_cap_item = BombCapacityItem(item_x, item_y, game)

        assert bomb_cap_item.type == settings.ITEM_TYPE_BOMB_CAPACITY
        assert bomb_cap_item.image is not None
        assert bomb_cap_item.score_value == settings.GENERIC_ITEM_SCORE_VALUE

    def test_bomb_capacity_item_apply_effect(self, mock_item_env):
        """Test BombCapacityItem's effect on player's max_bombs and score."""
        game, player = mock_item_env
        initial_max_bombs = player.max_bombs
        initial_score = player.score
        
        bomb_cap_item = BombCapacityItem(3, 3, game)
        bomb_cap_item.apply_effect(player)

        expected_max_bombs = initial_max_bombs + 1
        expected_score = initial_score + settings.GENERIC_ITEM_SCORE_VALUE
        
        assert player.max_bombs == expected_max_bombs, \
            f"Player max_bombs should be {expected_max_bombs}, but was {player.max_bombs}."
        assert player.score == expected_score

    def test_bomb_range_item_initialization(self, mock_item_env):
        """Test BombRangeItem initialization."""
        game, player = mock_item_env
        item_x, item_y = 4, 4
        
        bomb_range_item = BombRangeItem(item_x, item_y, game)

        assert bomb_range_item.type == settings.ITEM_TYPE_BOMB_RANGE
        assert bomb_range_item.image is not None
        assert bomb_range_item.score_value == settings.GENERIC_ITEM_SCORE_VALUE

    def test_bomb_range_item_apply_effect(self, mock_item_env):
        """Test BombRangeItem's effect on player's bomb_range and score."""
        game, player = mock_item_env
        initial_bomb_range = player.bomb_range
        initial_score = player.score
        
        bomb_range_item = BombRangeItem(4, 4, game)
        bomb_range_item.apply_effect(player)

        expected_bomb_range = initial_bomb_range + 1
        expected_score = initial_score + settings.GENERIC_ITEM_SCORE_VALUE
        
        assert player.bomb_range == expected_bomb_range, \
            f"Player bomb_range should be {expected_bomb_range}, but was {player.bomb_range}."
        assert player.score == expected_score
        
    def test_create_random_item_score(self, mock_item_env, mocker):
        """Test create_random_item creates a ScoreItem when random.choices selects it."""
        game, player = mock_item_env
        
        # Mock random.choices to always return ITEM_TYPE_SCORE
        mocker.patch('random.choices', return_value=[settings.ITEM_TYPE_SCORE])
        
        item = create_random_item(5, 5, game)
        
        assert isinstance(item, ScoreItem), "Should create a ScoreItem."
        assert item.type == settings.ITEM_TYPE_SCORE

    def test_create_random_item_life(self, mock_item_env, mocker):
        """Test create_random_item creates a LifeItem."""
        game, player = mock_item_env
        mocker.patch('random.choices', return_value=[settings.ITEM_TYPE_LIFE])
        item = create_random_item(5, 5, game)
        assert isinstance(item, LifeItem)
        assert item.type == settings.ITEM_TYPE_LIFE

    def test_create_random_item_bomb_capacity(self, mock_item_env, mocker):
        """Test create_random_item creates a BombCapacityItem."""
        game, player = mock_item_env
        mocker.patch('random.choices', return_value=[settings.ITEM_TYPE_BOMB_CAPACITY])
        item = create_random_item(5, 5, game)
        assert isinstance(item, BombCapacityItem)
        assert item.type == settings.ITEM_TYPE_BOMB_CAPACITY

    def test_create_random_item_bomb_range(self, mock_item_env, mocker):
        """Test create_random_item creates a BombRangeItem."""
        game, player = mock_item_env
        mocker.patch('random.choices', return_value=[settings.ITEM_TYPE_BOMB_RANGE])
        item = create_random_item(5, 5, game)
        assert isinstance(item, BombRangeItem)
        assert item.type == settings.ITEM_TYPE_BOMB_RANGE

    def test_create_random_item_unknown_type(self, mock_item_env, mocker):
        """Test create_random_item returns None for an unknown type."""
        game, player = mock_item_env
        mocker.patch('random.choices', return_value=["unknown_item_type"])
        item = create_random_item(5, 5, game)
        assert item is None, "Should return None for an unknown item type."

    def test_create_random_item_empty_weights(self, mock_item_env, mocker):
        """Test create_random_item returns None if ITEM_DROP_WEIGHTS is empty."""
        game, player = mock_item_env
        
        # Temporarily override settings.ITEM_DROP_WEIGHTS for this test
        original_weights = settings.ITEM_DROP_WEIGHTS
        settings.ITEM_DROP_WEIGHTS = {}
        mocker.patch('random.choices', side_effect=ValueError("Cannot choose from an empty sequence")) # Simulate error if called

        item = create_random_item(6, 6, game)
        assert item is None, "Should return None if ITEM_DROP_WEIGHTS is empty."
        
        settings.ITEM_DROP_WEIGHTS = original_weights # Restore original weights

    def test_create_random_item_zero_weights(self, mock_item_env, mocker):
        """Test create_random_item returns None if all weights in ITEM_DROP_WEIGHTS are zero."""
        game, player = mock_item_env
        
        original_weights = settings.ITEM_DROP_WEIGHTS
        settings.ITEM_DROP_WEIGHTS = {
            settings.ITEM_TYPE_SCORE: 0,
            settings.ITEM_TYPE_LIFE: 0
        }
        # random.choices might raise an error if all weights are zero,
        # or it might pick one if the implementation allows.
        # The create_random_item function has a check for sum(weights) == 0.
        
        item = create_random_item(7, 7, game)
        assert item is None, "Should return None if all item weights are zero."
        
        settings.ITEM_DROP_WEIGHTS = original_weights
    
    def test_create_random_item_randomness(self, mock_item_env, mocker):
        """Test create_random_item randomness by checking multiple calls."""
        game, player = mock_item_env
        
        # Mock random.choices to return different items on each call
        mocker.patch('random.choices', side_effect=[
            [settings.ITEM_TYPE_SCORE],
            [settings.ITEM_TYPE_LIFE],
            [settings.ITEM_TYPE_BOMB_CAPACITY],
            [settings.ITEM_TYPE_BOMB_RANGE]
        ])
        
        items = [create_random_item(9, 9, game) for _ in range(4)]
        
        assert isinstance(items[0], ScoreItem), "First item should be ScoreItem."
        assert isinstance(items[1], LifeItem), "Second item should be LifeItem."
        assert isinstance(items[2], BombCapacityItem), "Third item should be BombCapacityItem."
        assert isinstance(items[3], BombRangeItem), "Fourth item should be BombRangeItem."
        # Check types
        assert all(isinstance(item, (ScoreItem, LifeItem, BombCapacityItem, BombRangeItem)) for item in items), \
            "All created items should be valid item types."
    
        # Check types in a set to ensure all are unique
        item_types = {type(item) for item in items}
        assert len(item_types) == 4, "Should create 4 unique item types in this test."
        assert ScoreItem in item_types, "Should have created a ScoreItem."
        assert LifeItem in item_types, "Should have created a LifeItem."
        assert BombCapacityItem in item_types, "Should have created a BombCapacityItem."
        assert BombRangeItem in item_types, "Should have created a BombRangeItem."

    def test_create_random_item_invalid_type(self, mock_item_env, mocker):
        """Test create_random_item returns None for an invalid item type."""
        game, player = mock_item_env
        
        # Mock random.choices to return an invalid type
        mocker.patch('random.choices', return_value=["invalid_type"])
        
        item = create_random_item(10, 10, game)
        
        assert item is None, "Should return None for an invalid item type."
    
    