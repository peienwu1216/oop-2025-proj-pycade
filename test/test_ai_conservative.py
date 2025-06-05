# test/test_ai_conservative.py

import pygame
import pytest
import settings
from core.ai_conservative import ConservativeAIController
from sprites.player import Player
from core.map_manager import MapManager
from core.ai_controller_base import TileNode # Import TileNode

# --- Helper function (can be shared or duplicated if not in a common test utils file) ---
def create_test_map_data(layout_strings):
    """Creates map data from a list of strings."""
    return layout_strings

# --- Pytest Fixture for ConservativeAIController ---
@pytest.fixture
def mock_conservative_ai_env(mocker):
    """
    Sets up a simulated game environment for ConservativeAIController tests.
    """
    pygame.display.init()
    pygame.font.init()

    mock_game = mocker.Mock()
    mock_game.screen = pygame.display.set_mode((settings.SCREEN_WIDTH, settings.SCREEN_HEIGHT))
    
    mock_game.map_manager = MapManager(mock_game)
    # A map with some open spaces and some destructible walls
    default_map_layout = [
        "WWWWWWWWW",
        "W.......W", # AI at (1,1)
        "W.D.D.D.W", # Destructible walls 'D'
        "W.......W",
        "W.D.W.D.W",
        "W.......W",
        "WWWWWWWWW",
    ]
    mock_game.map_manager.map_data = create_test_map_data(default_map_layout)
    mock_game.map_manager.tile_height = len(default_map_layout)
    mock_game.map_manager.tile_width = len(default_map_layout[0])

    mock_player_sprite_config = {"ROW_MAP": settings.PLAYER_SPRITESHEET_ROW_MAP, "NUM_FRAMES": 1}
    
    ai_player_sprite = Player(
        game=mock_game, 
        x_tile=1, 
        y_tile=1, 
        spritesheet_path=settings.PLAYER2_AI_SPRITESHEET_PATH,
        sprite_config=mock_player_sprite_config,
        is_ai=True
    )
    ai_player_sprite.bomb_range = settings.INITIAL_BOMB_RANGE
    ai_player_sprite.max_bombs = settings.INITIAL_BOMBS
    ai_player_sprite.bombs_placed_count = 0

    # Mock a human player (Conservative AI tries to avoid it, but needs its presence for context)
    human_player_sprite = Player(
        game=mock_game, 
        x_tile=7, 
        y_tile=5, 
        spritesheet_path=settings.PLAYER1_SPRITESHEET_PATH,
        sprite_config=mock_player_sprite_config,
        is_ai=False
    )
    mock_game.player1 = human_player_sprite
    
    mock_game.players_group = pygame.sprite.Group(ai_player_sprite, human_player_sprite)
    mock_game.bombs_group = pygame.sprite.Group()
    mock_game.explosions_group = pygame.sprite.Group()
    mock_game.solid_obstacles_group = pygame.sprite.Group() 
    # For ConservativeAI, destructible walls are important targets
    mock_game.map_manager.destructible_walls_group = pygame.sprite.Group()

    # Populate solid_obstacles_group and destructible_walls_group based on map_data
    for r, row_str in enumerate(mock_game.map_manager.map_data):
        for c, char_tile in enumerate(row_str):
            if char_tile == 'W':
                wall = pygame.sprite.Sprite() 
                wall.rect = pygame.Rect(c * settings.TILE_SIZE, r * settings.TILE_SIZE, settings.TILE_SIZE, settings.TILE_SIZE)
                mock_game.solid_obstacles_group.add(wall)
            elif char_tile == 'D':
                # Mock a DestructibleWall sprite (simplified for testing AI logic)
                d_wall_sprite = pygame.sprite.Sprite()
                d_wall_sprite.rect = pygame.Rect(c * settings.TILE_SIZE, r * settings.TILE_SIZE, settings.TILE_SIZE, settings.TILE_SIZE)
                # Add attributes AI might check
                d_wall_sprite.tile_x = c
                d_wall_sprite.tile_y = r
                d_wall_sprite.is_destroyed = False 
                mock_game.solid_obstacles_group.add(d_wall_sprite) # Also solid until destroyed
                mock_game.map_manager.destructible_walls_group.add(d_wall_sprite)


    ai_controller = ConservativeAIController(ai_player_sprite, mock_game)
    ai_player_sprite.ai_controller = ai_controller 
    ai_controller.human_player_sprite = human_player_sprite

    pygame.event.clear()
    yield ai_controller, mock_game, ai_player_sprite, human_player_sprite
    pygame.quit()

# --- Test Class for ConservativeAIController ---
class TestConservativeAIController:
    """
    Test suite for the ConservativeAIController.
    """

    def test_initialization_conservative_ai(self, mock_conservative_ai_env):
        """Test ConservativeAIController specific initialization."""
        ai_controller, _, _, _ = mock_conservative_ai_env

        assert isinstance(ai_controller, ConservativeAIController)
        assert ai_controller.current_state == "PLANNING_ROAM"
        assert ai_controller.obstacle_bombing_chance == 0.15
        assert ai_controller.default_planning_state_on_stuck == "PLANNING_ROAM"
        assert ai_controller.default_state_after_evasion == "PLANNING_ROAM"

    def test_handle_planning_roam_state_finds_roam_target(self, mock_conservative_ai_env, mocker):
        """Test PLANNING_ROAM state attempts to find a roam target."""
        ai_controller, game, ai_player, _ = mock_conservative_ai_env
        
        ai_player.tile_x, ai_player.tile_y = 1, 1
        
        # Mock _find_safe_roaming_spots to return a specific target
        mock_roam_target = (3,1)
        mocker.patch.object(ai_controller, '_find_safe_roaming_spots', return_value=[mock_roam_target])
        # Mock bfs_find_direct_movement_path to return a valid path to this target
        mock_path_to_roam = [(1,1), (2,1), mock_roam_target]
        mocker.patch.object(ai_controller, 'bfs_find_direct_movement_path', return_value=mock_path_to_roam)
        
        # Ensure obstacle_bombing_chance does not trigger
        mocker.patch('random.random', return_value=ai_controller.obstacle_bombing_chance + 0.1)

        ai_controller.change_state("PLANNING_ROAM")
        ai_controller.handle_planning_roam_state(ai_controller._get_ai_current_tile())

        ai_controller._find_safe_roaming_spots.assert_called_once()
        ai_controller.bfs_find_direct_movement_path.assert_called_with(ai_controller._get_ai_current_tile(), mock_roam_target)
        assert ai_controller.roaming_target_tile == mock_roam_target
        assert ai_controller.current_movement_sub_path == mock_path_to_roam
        assert ai_controller.current_state == "ROAMING"

    def test_handle_planning_roam_state_chooses_to_assess_obstacle(self, mock_conservative_ai_env, mocker):
        """Test PLANNING_ROAM transitions to ASSESSING_OBSTACLE if chance and obstacle found."""
        ai_controller, game, ai_player, _ = mock_conservative_ai_env
        
        # Ensure obstacle_bombing_chance triggers
        mocker.patch('random.random', return_value=ai_controller.obstacle_bombing_chance - 0.01)
        
        # Mock _find_nearby_worthwhile_obstacle to return a mock obstacle node
        mock_obstacle_node = TileNode(2,1,'D') # Assume (2,1) is 'D' in map_data
        mocker.patch.object(ai_controller, '_find_nearby_worthwhile_obstacle', return_value=mock_obstacle_node)

        ai_controller.change_state("PLANNING_ROAM")
        ai_controller.handle_planning_roam_state(ai_controller._get_ai_current_tile())
        
        ai_controller._find_nearby_worthwhile_obstacle.assert_called_once()
        assert ai_controller.target_obstacle_to_bomb == mock_obstacle_node
        assert ai_controller.current_state == "ASSESSING_OBSTACLE"

    def test_handle_moving_to_bomb_obstacle_places_bomb_and_retreats(self, mock_conservative_ai_env, mocker):
        """Test MOVING_TO_BOMB_OBSTACLE places bomb and sets retreat path."""
        ai_controller, game, ai_player, _ = mock_conservative_ai_env
        
        ai_player.tile_x, ai_player.tile_y = 1,1 # AI is at the bomb spot
        ai_controller.chosen_bombing_spot_coords = (1,1)
        ai_controller.chosen_retreat_spot_coords = (1,2) # Retreat to (1,2)
        game.map_manager.map_data[2] = "W.......W" # Ensure (1,2) is empty

        ai_player.max_bombs = 1
        ai_player.bombs_placed_count = 0
        ai_player.place_bomb = mocker.Mock() # Mock place_bomb to check call

        # Mock BFS for the retreat path
        mock_retreat_path = [(1,1), (1,2)]
        mocker.patch.object(ai_controller, 'bfs_find_direct_movement_path', return_value=mock_retreat_path)

        ai_controller.change_state("MOVING_TO_BOMB_OBSTACLE")
        ai_controller.current_movement_sub_path = [] # Simulate arrival at bomb spot

        ai_controller.handle_moving_to_bomb_obstacle_state(ai_controller._get_ai_current_tile())

        ai_player.place_bomb.assert_called_once()
        ai_controller.bfs_find_direct_movement_path.assert_called_with(ai_controller._get_ai_current_tile(), (1,2))
        assert ai_controller.current_movement_sub_path == mock_retreat_path
        assert ai_controller.current_state == "TACTICAL_RETREAT_AND_WAIT"

    def test_handle_tactical_retreat_and_wait_waits_then_replans(self, mock_conservative_ai_env, mocker):
        """Test TACTICAL_RETREAT_AND_WAIT waits for bomb then replans."""
        ai_controller, game, ai_player, _ = mock_conservative_ai_env

        ai_player.tile_x, ai_player.tile_y = 1,2 # AI is at retreat spot
        ai_controller.chosen_retreat_spot_coords = (1,2)
        ai_controller.ai_just_placed_bomb = True
        ai_controller.last_bomb_placed_time = pygame.time.get_ticks()

        # Scenario 1: Bomb is still active
        mocker.patch.object(ai_controller, 'is_bomb_still_active', return_value=True)
        ai_controller.change_state("TACTICAL_RETREAT_AND_WAIT")
        ai_controller.current_movement_sub_path = [] # Simulate arrival
        
        ai_controller.handle_tactical_retreat_and_wait_state(ai_controller._get_ai_current_tile())
        assert ai_controller.current_state == "TACTICAL_RETREAT_AND_WAIT" # Should remain waiting

        # Scenario 2: Bomb has cleared
        mocker.patch.object(ai_controller, 'is_bomb_still_active', return_value=False)
        ai_controller.handle_tactical_retreat_and_wait_state(ai_controller._get_ai_current_tile())
        
        assert ai_controller.ai_just_placed_bomb is False
        assert ai_controller.current_state == "PLANNING_ROAM" # Conservative AI should go back to roaming

    def test_evading_danger_finds_and_moves_to_safe_spot(self, mock_conservative_ai_env, mocker):
        """Test EVADING_DANGER state finds a safe spot and sets path."""
        ai_controller, game, ai_player, _ = mock_conservative_ai_env
        
        ai_player.tile_x, ai_player.tile_y = 1,1 # AI current position
        
        # Simulate current tile is dangerous
        mocker.patch.object(ai_controller, 'is_tile_dangerous', side_effect=lambda x,y,future_seconds: (x,y) == (1,1) if future_seconds > 0 else False)

        # Mock find_safe_tiles_nearby_for_retreat to return a safe spot
        mock_safe_spot = (0,1) # Assume (0,1) is safe
        game.map_manager.map_data[1] = ".W.D.D.D.W" # (0,1) is '.'
        mocker.patch.object(ai_controller, 'find_safe_tiles_nearby_for_retreat', return_value=[mock_safe_spot])
        
        # Mock BFS to path to this safe spot
        mock_evasion_path = [(1,1), (0,1)]
        mocker.patch.object(ai_controller, 'bfs_find_direct_movement_path', return_value=mock_evasion_path)
        
        ai_controller.change_state("EVADING_DANGER")
        ai_controller.handle_evading_danger_state(ai_controller._get_ai_current_tile())

        ai_controller.find_safe_tiles_nearby_for_retreat.assert_called_once()
        ai_controller.bfs_find_direct_movement_path.assert_called_with(ai_controller._get_ai_current_tile(), mock_safe_spot, max_depth=ai_controller.retreat_search_depth + 1)
        assert ai_controller.current_movement_sub_path == mock_evasion_path
        # State remains EVADING_DANGER while moving, base class handles transition once safe or path ends