# test/test_ai_aggressive.py

import pygame
import pytest
import settings
from core.ai_aggressive import AggressiveAIController
from sprites.player import Player
from core.map_manager import MapManager
from core.ai_controller_base import TileNode # Import TileNode from base

# --- Helper function from test_ai_controller.py ---
def create_test_map_data(layout_strings):
    """Creates map data from a list of strings."""
    return layout_strings

# --- Pytest Fixture for AggressiveAIController ---
@pytest.fixture
def mock_aggressive_ai_env(mocker):
    """
    Sets up a simulated game environment for AggressiveAIController tests.
    """
    pygame.display.init()
    pygame.font.init()

    mock_game = mocker.Mock()
    mock_game.screen = pygame.display.set_mode((settings.SCREEN_WIDTH, settings.SCREEN_HEIGHT))
    
    mock_game.map_manager = MapManager(mock_game)
    default_map_layout = [
        "WWWWWWWWWWWWWWW",
        "W.............W", # AI at (1,1), Human at (13,1) or (1,9)
        "W.W.W.W.W.W.W.W",
        "W.............W",
        "W.W.W.W.W.W.W.W",
        "W.............W",
        "W.W.W.W.W.W.W.W",
        "W.............W",
        "W.W.W.W.W.W.W.W",
        "W.............W", # Human at (1,9)
        "WWWWWWWWWWWWWWW",
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


    human_player_sprite = Player(
        game=mock_game, 
        x_tile=13, # Far end for path planning
        y_tile=1, 
        spritesheet_path=settings.PLAYER1_SPRITESHEET_PATH,
        sprite_config=mock_player_sprite_config,
        is_ai=False
    )
    
    mock_game.player1 = human_player_sprite # Human player
    mock_game.player1_start_tile = (human_player_sprite.tile_x, human_player_sprite.tile_y) # For AI to know initial target

    mock_game.players_group = pygame.sprite.Group(ai_player_sprite, human_player_sprite)
    mock_game.bombs_group = pygame.sprite.Group()
    mock_game.explosions_group = pygame.sprite.Group()
    mock_game.solid_obstacles_group = pygame.sprite.Group() # For walls
    # Add actual Wall objects to solid_obstacles_group if needed for pathing tests
    for r, row_str in enumerate(mock_game.map_manager.map_data):
        for c, char_tile in enumerate(row_str):
            if char_tile == 'W':
                wall = pygame.sprite.Sprite() # Simple mock sprite for solid wall
                wall.rect = pygame.Rect(c * settings.TILE_SIZE, r * settings.TILE_SIZE, settings.TILE_SIZE, settings.TILE_SIZE)
                mock_game.solid_obstacles_group.add(wall)


    ai_controller = AggressiveAIController(ai_player_sprite, mock_game)
    ai_player_sprite.ai_controller = ai_controller # Link back if Player needs it
    
    # Ensure AI knows about the human player
    ai_controller.human_player_sprite = human_player_sprite

    pygame.event.clear()
    yield ai_controller, mock_game, ai_player_sprite, human_player_sprite
    pygame.quit()

# --- Test Class for AggressiveAIController ---
class TestAggressiveAIController:
    """
    Test suite for the AggressiveAIController.
    """

    def test_handle_planning_path_to_player_state_clear_path(self, mock_aggressive_ai_env, mocker):
        """Test planning path to player when a clear A* path exists."""
        ai_controller, game, ai_player, human_player = mock_aggressive_ai_env
        
        # Place human player somewhere reachable without breaking walls
        human_player.tile_x, human_player.tile_y = 3, 1 
        game.player1_start_tile = (human_player.tile_x, human_player.tile_y)
        ai_player.tile_x, ai_player.tile_y = 1, 1
        
        # Ensure map allows this path (e.g., (1,1) -> (2,1) -> (3,1) are all '.')
        game.map_manager.map_data = [
            "WWWWWWW",
            "W.....W", # (1,1) to (5,1) are '.'
            "WWWWWWW",
        ]
        game.map_manager.tile_height = len(game.map_manager.map_data)
        game.map_manager.tile_width = len(game.map_manager.map_data[0])
        # Re-initialize solid_obstacles_group for the new map
        game.solid_obstacles_group.empty()
        for r, row_str in enumerate(game.map_manager.map_data):
            for c, char_tile in enumerate(row_str):
                if char_tile == 'W':
                    wall = pygame.sprite.Sprite()
                    wall.rect = pygame.Rect(c * settings.TILE_SIZE, r * settings.TILE_SIZE, settings.TILE_SIZE, settings.TILE_SIZE)
                    game.solid_obstacles_group.add(wall)
        
        ai_controller.change_state("PLANNING_PATH_TO_PLAYER") # Force state
        ai_controller.handle_planning_path_to_player_state(ai_controller._get_ai_current_tile())

        assert ai_controller.astar_planned_path is not None
        assert len(ai_controller.astar_planned_path) > 0
        # Path should be [(1,1), (2,1), (3,1)] approximately
        path_coords = [(node.x, node.y) for node in ai_controller.astar_planned_path]
        assert path_coords[0] == (1,1)
        assert path_coords[-1] == (3,1)
        
        assert ai_controller.current_state == "ENGAGING_PLAYER", \
            f"State should be ENGAGING_PLAYER, but is {ai_controller.current_state}"
        assert ai_controller.current_movement_sub_path is not None
        assert len(ai_controller.current_movement_sub_path) > 0
        assert ai_controller.current_movement_sub_path == path_coords # Path should be directly set

    def test_handle_planning_path_to_player_state_blocked_path(self, mock_aggressive_ai_env, mocker):
        """Test planning path to player when path requires breaking obstacles."""
        ai_controller, game, ai_player, human_player = mock_aggressive_ai_env

        human_player.tile_x, human_player.tile_y = 3, 1
        game.player1_start_tile = (human_player.tile_x, human_player.tile_y)
        ai_player.tile_x, ai_player.tile_y = 1, 1
        
        game.map_manager.map_data = [ # D is destructible
            "WWWWWWW",
            "W.D...W", # Path from (1,1) to (3,1) requires breaking D at (2,1)
            "WWWWWWW",
        ]
        game.map_manager.tile_height = len(game.map_manager.map_data)
        game.map_manager.tile_width = len(game.map_manager.map_data[0])
        game.solid_obstacles_group.empty() # Clear previous walls
        # Add destructible wall to solid_obstacles_group for A* planning
        # In the actual game, DestructibleWall instances would be in game.map_manager.destructible_walls_group
        # and also in game.solid_obstacles_group.
        # For A* pathing, AIControllerBase._get_node_at_coords uses map_data.
        # Let's ensure map_data is correctly interpreted.

        ai_controller.change_state("PLANNING_PATH_TO_PLAYER")
        ai_controller.handle_planning_path_to_player_state(ai_controller._get_ai_current_tile())
        
        assert ai_controller.astar_planned_path is not None
        assert len(ai_controller.astar_planned_path) > 0
        path_coords = [(node.x, node.y) for node in ai_controller.astar_planned_path]
        assert path_coords[0] == (1,1)
        assert path_coords[-1] == (3,1) # A* should still find a path through 'D'
        
        assert ai_controller.current_state == "EXECUTING_PATH_CLEARANCE", \
            f"State should be EXECUTING_PATH_CLEARANCE, but is {ai_controller.current_state}"
        assert not ai_controller.current_movement_sub_path # No sub-path initially in this state

    def test_engaging_player_attempts_to_move_towards_player(self, mock_aggressive_ai_env, mocker):
        """Test ENGAGING_PLAYER state tries to move towards the human player if not bombing."""
        ai_controller, game, ai_player, human_player = mock_aggressive_ai_env

        ai_player.tile_x, ai_player.tile_y = 1, 1
        human_player.tile_x, human_player.tile_y = 5, 1 # Human is a few steps away
        
        # Ensure clear path for BFS
        game.map_manager.map_data = [
            "WWWWWWWWW",
            "W.......W", # (1,1) to (7,1) are '.'
            "WWWWWWWWW",
        ]
        # ... (re-init solid_obstacles_group for the new map if necessary, but BFS doesn't use it directly)

        ai_controller.change_state("ENGAGING_PLAYER")
        # Assume AI has bombs but conditions for bombing are not met (e.g., player not in blast)
        ai_player.max_bombs = 1
        ai_player.bombs_placed_count = 0
        ai_controller.ai_just_placed_bomb = False
        
        # Mock _is_tile_in_hypothetical_blast to return False to prevent bombing
        mocker.patch.object(ai_controller, '_is_tile_in_hypothetical_blast', return_value=False)
        
        ai_controller.handle_engaging_player_state(ai_controller._get_ai_current_tile())

        assert ai_controller.current_movement_sub_path is not None
        assert len(ai_controller.current_movement_sub_path) > 1 # Should be a path
        # Expected path: [(1,1), (2,1), (3,1), (4,1), (5,1)] or similar BFS result
        assert ai_controller.current_movement_sub_path[0] == (1,1)
        assert ai_controller.current_movement_sub_path[-1] == (5,1) # BFS should target human
    
    def test_close_quarters_combat_attempts_to_bomb(self, mock_aggressive_ai_env, mocker):
        """Test CLOSE_QUARTERS_COMBAT state attempts to bomb if player is in range."""
        ai_controller, game, ai_player, human_player = mock_aggressive_ai_env

        ai_player.tile_x, ai_player.tile_y = 1, 1
        human_player.tile_x, human_player.tile_y = 2, 1 # Human is 1 tile away (CQC distance)
        ai_controller.cqc_engagement_distance = 1 # Ensure this distance triggers CQC

        ai_player.max_bombs = 1
        ai_player.bombs_placed_count = 0
        ai_controller.ai_just_placed_bomb = False
        ai_player.bomb_range = 1 # Bomb range of 1 will hit tile (2,1) if bomb at (1,1)

        # Mock _is_tile_in_hypothetical_blast to return True
        mocker.patch.object(ai_controller, '_is_tile_in_hypothetical_blast', return_value=True)
        # Mock can_place_bomb_and_retreat to simulate a safe bombing scenario
        mock_retreat_spot = (0,1) # Example safe spot
        mocker.patch.object(ai_controller, 'can_place_bomb_and_retreat', return_value=(True, mock_retreat_spot))
        
        # Mock player's place_bomb method to check if it's called
        ai_player.place_bomb = mocker.Mock()

        # Mock random.random to ensure CQC bomb chance passes
        mocker.patch('random.random', return_value=ai_controller.cqc_bomb_chance - 0.01)

        ai_controller.change_state("CLOSE_QUARTERS_COMBAT")
        ai_controller.handle_close_quarters_combat_state(ai_controller._get_ai_current_tile())

        ai_player.place_bomb.assert_called_once()
        assert ai_controller.chosen_bombing_spot_coords == (1,1)
        assert ai_controller.chosen_retreat_spot_coords == mock_retreat_spot
        assert ai_controller.current_state == "TACTICAL_RETREAT_AND_WAIT"
        assert ai_controller.current_movement_sub_path is not None # Should have a path to retreat_spot


    def test_tactical_retreat_and_wait_state(self, mock_aggressive_ai_env, mocker):
        """Test TACTICAL_RETREAT_AND_WAIT state: waits for bomb, then re-plans."""
        ai_controller, game, ai_player, human_player = mock_aggressive_ai_env

        ai_player.tile_x, ai_player.tile_y = 1, 1
        ai_controller.chosen_retreat_spot_coords = (0,1) # Set a retreat spot
        ai_controller.ai_just_placed_bomb = True # Simulate a bomb was just placed
        ai_controller.last_bomb_placed_time = pygame.time.get_ticks() # Record bomb time

        # Scenario 1: Bomb is still active
        mocker.patch.object(ai_controller, 'is_bomb_still_active', return_value=True)
        
        ai_controller.change_state("TACTICAL_RETREAT_AND_WAIT")
        # Simulate AI has reached the retreat spot
        ai_player.tile_x, ai_player.tile_y = ai_controller.chosen_retreat_spot_coords[0], ai_controller.chosen_retreat_spot_coords[1]
        ai_controller.current_movement_sub_path = [] # No active sub-path

        ai_controller.handle_tactical_retreat_and_wait_state(ai_controller._get_ai_current_tile())
        assert ai_controller.current_state == "TACTICAL_RETREAT_AND_WAIT", "Should remain in retreat state if bomb active."

        # Scenario 2: Bomb has cleared
        mocker.patch.object(ai_controller, 'is_bomb_still_active', return_value=False)
        # Ensure target_destructible_wall_node_in_astar is None to simplify transition
        ai_controller.target_destructible_wall_node_in_astar = None

        ai_controller.handle_tactical_retreat_and_wait_state(ai_controller._get_ai_current_tile())
        
        assert ai_controller.ai_just_placed_bomb is False, "ai_just_placed_bomb flag should be cleared."
        assert ai_controller.current_state == "PLANNING_PATH_TO_PLAYER", \
            "Should re-plan to player after bomb clears (default for AggressiveAI)."