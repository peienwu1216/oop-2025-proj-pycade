# test/test_ai_item_focused.py

import pygame
import pytest
import settings
from core.ai_item_focused import ItemFocusedAIController
from sprites.player import Player
from sprites.item import Item, ScoreItem, BombRangeItem # For creating mock items
from sprites.wall import DestructibleWall # For AI to target
from core.map_manager import MapManager
from core.ai_controller_base import TileNode

# --- Helper function ---
def create_test_map_data(layout_strings):
    return layout_strings

# --- Pytest Fixture for ItemFocusedAIController ---
@pytest.fixture
def mock_item_focused_ai_env(mocker):
    pygame.display.init()
    pygame.font.init()

    mock_game = mocker.Mock()
    mock_game.screen = pygame.display.set_mode((settings.SCREEN_WIDTH, settings.SCREEN_HEIGHT))
    
    mock_game.map_manager = MapManager(mock_game)
    default_map_layout = [
        "WWWWWWWWW",
        "W.I...D.W", # AI at (1,1), Item 'I' at (2,1), Destructible 'D' at (6,1)
        "W.W.W.W.W",
        "W...P...W", # Player 'P' at (4,3)
        "W.D.W.D.W",
        "W.......W",
        "WWWWWWWWW",
    ]
    mock_game.map_manager.map_data = create_test_map_data(default_map_layout)
    mock_game.map_manager.tile_height = len(default_map_layout)
    mock_game.map_manager.tile_width = len(default_map_layout[0])

    mock_player_sprite_config = {"ROW_MAP": settings.PLAYER_SPRITESHEET_ROW_MAP, "NUM_FRAMES": 1}
    
    ai_player_sprite = Player(
        game=mock_game, x_tile=1, y_tile=1, 
        spritesheet_path=settings.PLAYER2_AI_SPRITESHEET_PATH,
        sprite_config=mock_player_sprite_config, is_ai=True
    )
    ai_player_sprite.bomb_range = settings.INITIAL_BOMB_RANGE
    ai_player_sprite.max_bombs = settings.INITIAL_BOMBS
    ai_player_sprite.bombs_placed_count = 0

    human_player_sprite = Player(
        game=mock_game, x_tile=4, y_tile=3, # 'P' in map
        spritesheet_path=settings.PLAYER1_SPRITESHEET_PATH,
        sprite_config=mock_player_sprite_config, is_ai=False
    )
    mock_game.player1 = human_player_sprite
    
    mock_game.players_group = pygame.sprite.Group(ai_player_sprite, human_player_sprite)
    mock_game.bombs_group = pygame.sprite.Group()
    mock_game.explosions_group = pygame.sprite.Group()
    mock_game.items_group = pygame.sprite.Group() # For items AI can pick up
    mock_game.solid_obstacles_group = pygame.sprite.Group()
    mock_game.map_manager.destructible_walls_group = pygame.sprite.Group()

    # Populate walls and items based on map_data for the test
    for r, row_str in enumerate(mock_game.map_manager.map_data):
        for c, char_tile in enumerate(row_str):
            if char_tile == 'W':
                wall = pygame.sprite.Sprite() 
                wall.rect = pygame.Rect(c * settings.TILE_SIZE, r * settings.TILE_SIZE, settings.TILE_SIZE, settings.TILE_SIZE)
                mock_game.solid_obstacles_group.add(wall)
            elif char_tile == 'D':
                d_wall_sprite = DestructibleWall(c, r, mock_game) # Use real DestructibleWall for interaction
                mock_game.solid_obstacles_group.add(d_wall_sprite)
                mock_game.map_manager.destructible_walls_group.add(d_wall_sprite)
            elif char_tile == 'I': # Mock an item
                # Create a real item instance for the AI to target
                # Let's use BombRangeItem as it's high priority
                item_sprite = BombRangeItem(c, r, mock_game)
                mock_game.items_group.add(item_sprite)
                mock_game.all_sprites.add(item_sprite) # AI base might check all_sprites for items too
                # Ensure the map tile char is '.' where item is placed
                row_list = list(mock_game.map_manager.map_data[r])
                row_list[c] = '.'
                mock_game.map_manager.map_data[r] = "".join(row_list)


    ai_controller = ItemFocusedAIController(ai_player_sprite, mock_game)
    ai_player_sprite.ai_controller = ai_controller
    ai_controller.human_player_sprite = human_player_sprite

    pygame.event.clear()
    yield ai_controller, mock_game, ai_player_sprite, human_player_sprite
    pygame.quit()

# --- Test Class for ItemFocusedAIController ---
class TestItemFocusedAIController:

    def test_initialization_item_focused_ai(self, mock_item_focused_ai_env):
        ai_controller, _, _, _ = mock_item_focused_ai_env
        assert isinstance(ai_controller, ItemFocusedAIController)
        assert ai_controller.current_state == "PLANNING_ITEM_TARGET"
        assert ai_controller.default_planning_state_on_stuck == "PLANNING_ITEM_TARGET"
        assert ai_controller.default_state_after_evasion == "PLANNING_ITEM_TARGET"
        assert settings.ITEM_TYPE_BOMB_RANGE in ai_controller.item_type_priority

    def test_plan_item_target_finds_item_on_ground(self, mock_item_focused_ai_env, mocker):
        ai_controller, game, ai_player, _ = mock_item_focused_ai_env
        # Item 'I' is at (2,1) in the default map, AI at (1,1)
        item_on_ground = game.items_group.sprites()[0] # Should be the BombRangeItem
        
        ai_controller.change_state("PLANNING_ITEM_TARGET")
        ai_controller.handle_planning_item_target_state(ai_controller._get_ai_current_tile())

        assert ai_controller.target_item_on_ground is item_on_ground
        assert ai_controller.current_state == "MOVING_TO_COLLECT_ITEM"
        assert ai_controller.current_movement_sub_path == [(1,1), (2,1)] # Direct path

    def test_plan_item_target_finds_wall_for_item(self, mock_item_focused_ai_env, mocker):
        ai_controller, game, ai_player, _ = mock_item_focused_ai_env
        # Remove item on ground so AI targets a wall
        game.items_group.empty()
        
        # Mock _find_best_wall_to_bomb_for_items to return a specific wall
        # 'D' is at (6,1) in the default map
        target_wall_node = ai_controller._get_node_at_coords(6,1) # TileNode(6,1,'D')
        mocker.patch.object(ai_controller, '_find_best_wall_to_bomb_for_items', return_value=target_wall_node)
        
        # Ensure item_bombing_chance passes
        mocker.patch('random.random', return_value=ai_controller.item_bombing_chance - 0.01)
        
        ai_controller.change_state("PLANNING_ITEM_TARGET")
        ai_controller.handle_planning_item_target_state(ai_controller._get_ai_current_tile())
        
        ai_controller._find_best_wall_to_bomb_for_items.assert_called_once()
        assert ai_controller.potential_wall_to_bomb_for_item == target_wall_node
        assert ai_controller.current_state == "ASSESSING_OBSTACLE_FOR_ITEM"

    def test_aggression_level_increases_with_powerups(self, mock_item_focused_ai_env):
        ai_controller, game, ai_player, _ = mock_item_focused_ai_env
        
        initial_aggression = ai_controller.aggression_level
        
        ai_player.max_bombs += 1
        aggression_after_bomb_pickup = ai_controller.aggression_level
        assert aggression_after_bomb_pickup > initial_aggression

        ai_player.bomb_range += 1
        aggression_after_range_pickup = ai_controller.aggression_level
        assert aggression_after_range_pickup > aggression_after_bomb_pickup
        
        # Test cap at 1.0
        ai_player.max_bombs += 10 # Significantly increase
        ai_player.bomb_range += 10
        assert ai_controller.aggression_level <= 1.0

    def test_is_endgame_condition(self, mock_item_focused_ai_env):
        ai_controller, game, _, _ = mock_item_focused_ai_env

        # Scenario 1: Walls and items exist (not endgame)
        assert not ai_controller._is_endgame()

        # Scenario 2: No destructible walls, but items exist (not endgame)
        game.map_manager.destructible_walls_group.empty()
        assert not ai_controller._is_endgame()

        # Scenario 3: Destructible walls exist, but no items (not endgame)
        # Reset destructible walls (fixture might have already added some)
        game.map_manager.destructible_walls_group.add(DestructibleWall(3,3,game)) # Add one back
        game.items_group.empty() # Ensure items are empty
        assert not ai_controller._is_endgame()
        
        # Scenario 4: No destructible walls AND no items (endgame)
        game.map_manager.destructible_walls_group.empty()
        game.items_group.empty()
        assert ai_controller._is_endgame() is True

    def test_transitions_to_endgame_hunt(self, mock_item_focused_ai_env, mocker):
        ai_controller, game, ai_player, _ = mock_item_focused_ai_env
        
        # Make it endgame
        game.map_manager.destructible_walls_group.empty()
        game.items_group.empty()
        mocker.patch.object(ai_controller, '_is_endgame', return_value=True) # Force endgame
        
        # Spy on _reset_chain_bombing_state
        mocker.spy(ai_controller, '_reset_chain_bombing_state')

        ai_controller.change_state("PLANNING_ITEM_TARGET")
        ai_controller.handle_planning_item_target_state(ai_controller._get_ai_current_tile())
        
        ai_controller._reset_chain_bombing_state.assert_called_once()
        assert ai_controller.current_state == "ENDGAME_HUNT"

    def test_endgame_hunt_attempts_trapping_bomb(self, mock_item_focused_ai_env, mocker):
        ai_controller, game, ai_player, human_player = mock_item_focused_ai_env
        
        # Setup for endgame hunt
        game.map_manager.destructible_walls_group.empty()
        game.items_group.empty()
        ai_controller.change_state("ENDGAME_HUNT")
        
        ai_player.tile_x, ai_player.tile_y = 1,1
        human_player.tile_x, human_player.tile_y = 3,1 # Human is 2 tiles away
        ai_player.max_bombs = 1; ai_player.bombs_placed_count = 0
        ai_player.bomb_range = 1 # Bomb at (2,1) would hit (3,1)
        
        # Mock _find_trapping_bomb_spot to return a plan
        # Plan: AI moves to (2,1), bombs, retreats to (2,2)
        mock_stand_tile = (2,1)
        mock_retreat_tile = (2,2)
        mock_path_to_stand = [(1,1), (2,1)]
        mocker.patch.object(ai_controller, '_find_trapping_bomb_spot', 
                            return_value=(mock_stand_tile, mock_retreat_tile, mock_path_to_stand))
        
        ai_controller.handle_endgame_hunt_state(ai_controller._get_ai_current_tile())
        
        ai_controller._find_trapping_bomb_spot.assert_called_once()
        assert ai_controller.is_chain_bombing_active is True
        assert ai_controller.current_chain_target_stand_tile == mock_stand_tile
        assert ai_controller.final_retreat_spot_after_chain == mock_retreat_tile
        assert ai_controller.current_movement_sub_path == mock_path_to_stand

    def test_endgame_hunt_places_bomb_at_stand_tile_and_retreats(self, mock_item_focused_ai_env, mocker):
        ai_controller, game, ai_player, human_player = mock_item_focused_ai_env
        
        ai_controller.change_state("ENDGAME_HUNT")
        ai_player.max_bombs = 1; ai_player.bombs_placed_count = 0
        
        # Simulate AI has reached the stand tile for chain bombing
        stand_tile = (2,1)
        ai_player.tile_x, ai_player.tile_y = stand_tile[0], stand_tile[1]
        
        ai_controller.is_chain_bombing_active = True
        ai_controller.current_chain_target_stand_tile = stand_tile
        
        # Mock find_safe_tiles_nearby_for_retreat for the temporary retreat after this bomb
        temp_retreat_spot = (2,2)
        game.map_manager.map_data[2] = "W.W.W.W.W" # Ensure (2,2) is walkable for retreat
        mocker.patch.object(ai_controller, 'find_safe_tiles_nearby_for_retreat', return_value=[temp_retreat_spot])
        mocker.patch.object(ai_controller, 'bfs_find_direct_movement_path', return_value=[stand_tile, temp_retreat_spot])

        ai_player.place_bomb = mocker.Mock() # Spy on place_bomb

        ai_controller.handle_endgame_hunt_state(ai_controller._get_ai_current_tile())
        
        ai_player.place_bomb.assert_called_once()
        assert ai_controller.chain_bombs_placed_in_sequence == 1
        assert ai_controller.current_movement_sub_path == [stand_tile, temp_retreat_spot]
        # AI should still be in ENDGAME_HUNT, waiting for movement to temp_retreat_spot
        # Then it will check if it can place another chain bomb.

    def test_endgame_hunt_repeats_chain_bombing(self, mock_item_focused_ai_env, mocker):
        ai_controller, game, ai_player, human_player = mock_item_focused_ai_env
        
        ai_controller.change_state("ENDGAME_HUNT")
        ai_player.max_bombs = 1; ai_player.bombs_placed_count = 0
        
        # Simulate AI has placed a bomb and is now at the retreat spot
        stand_tile = (2,1)
        retreat_tile = (2,2)
        ai_player.tile_x, ai_player.tile_y = retreat_tile[0], retreat_tile[1]
        
        ai_controller.is_chain_bombing_active = True
        ai_controller.current_chain_target_stand_tile = stand_tile
        ai_controller.chain_bombs_placed_in_sequence = 1
        
        # Mock find_safe_tiles_nearby_for_retreat to return a new retreat spot
        new_retreat_spot = (3,2)
        game.map_manager.map_data[3] = "W.W.W.W.W"
        mocker.patch.object(ai_controller, 'find_safe_tiles_nearby_for_retreat', return_value=[new_retreat_spot])
        mocker.patch.object(ai_controller, 'bfs_find_direct_movement_path', return_value=[retreat_tile, new_retreat_spot])
        ai_player.place_bomb = mocker.Mock()
        ai_controller.handle_endgame_hunt_state(ai_controller._get_ai_current_tile())
        ai_player.place_bomb.assert_called_once()
        assert ai_controller.chain_bombs_placed_in_sequence == 2
        assert ai_controller.current_movement_sub_path == [retreat_tile, new_retreat_spot]
        # AI should still be in ENDGAME_HUNT, waiting for movement to new_retreat_spot
        # Then it will check if it can place another chain bomb.

    def test_endgame_hunt_ends_when_no_more_bombs_can_be_placed(self, mock_item_focused_ai_env, mocker):
        ai_controller, game, ai_player, human_player = mock_item_focused_ai_env
        
        ai_controller.change_state("ENDGAME_HUNT")
        ai_player.max_bombs = 1; ai_player.bombs_placed_count = 1
        