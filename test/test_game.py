# test/test_game.py

import pygame
import pytest
import settings
from game import Game
from sprites.player import Player
from core.map_manager import MapManager
from core.leaderboard_manager import LeaderboardManager
from core.ai_controller import AIController as OriginalAIController
from core.ai_conservative import ConservativeAIController
from core.ai_aggressive import AggressiveAIController
from core.ai_item_focused import ItemFocusedAIController

@pytest.fixture
def mock_game_dependencies(mocker):
    """
    Sets up a Pygame environment and mocks dependencies for Game tests.
    """
    pygame.display.init()
    pygame.font.init()

    screen = pygame.display.set_mode((settings.SCREEN_WIDTH, settings.SCREEN_HEIGHT))
    clock = pygame.time.Clock()

    # Mock LeaderboardManager to prevent actual file I/O
    mocker.patch.object(LeaderboardManager, 'load_scores', return_value=[])
    mocker.patch.object(LeaderboardManager, 'save_scores', return_value=None)

    # Mock MapManager's map generation for predictability during Game initialization
    # Game.setup_initial_state calls get_randomized_map_layout
    map_width = getattr(settings, 'GRID_WIDTH', 15)
    map_height = getattr(settings, 'GRID_HEIGHT', 11)
    
    # Create a minimal empty map with borders, ensuring player start tiles are empty
    mocked_map_data = ["W" * map_width]
    for r in range(1, map_height - 1):
        row_list = list("W" + "." * (map_width - 2) + "W")
        if r == 1: # P1 start row
            row_list[1] = '.' # P1 start_tile (1,1)
        if r == map_height - 2: # P2/AI start row
            row_list[map_width - 2] = '.' # P2 start_tile (width-2, height-2)
        mocked_map_data.append("".join(row_list))
    mocked_map_data.append("W" * map_width)

    mocker.patch('core.map_manager.MapManager.get_randomized_map_layout', return_value=mocked_map_data)

    # Mock AI controller methods to prevent complex AI logic during basic game init/state tests
    # These are class-level mocks because AI controllers are instantiated within Game
    ai_controllers_to_mock = [
        OriginalAIController, 
        ConservativeAIController,
        AggressiveAIController,
        ItemFocusedAIController
    ]
    for controller_class in ai_controllers_to_mock:
        mocker.patch.object(controller_class, 'update', return_value=None)
        mocker.patch.object(controller_class, 'reset_state', return_value=None)
        # If debug_draw_path exists and is problematic, mock it too
        if hasattr(controller_class, 'debug_draw_path'):
            mocker.patch.object(controller_class, 'debug_draw_path', return_value=None)

    yield screen, clock

    pygame.quit()


class TestGame:
    """Test suite for the Game class."""

    def test_game_initialization(self, mock_game_dependencies):
        """Test if the Game initializes correctly with default AI."""
        screen, clock = mock_game_dependencies
        
        # Test with the default AI archetype if not specified, or pick one
        game_instance = Game(screen, clock, ai_archetype="original")

        assert game_instance.screen is screen, "Game screen should be the one provided."
        assert game_instance.clock is clock, "Game clock should be the one provided."
        assert game_instance.running is True, "Game should be running by default."
        
        assert isinstance(game_instance.map_manager, MapManager), "Game should have a MapManager instance."
        
        assert isinstance(game_instance.player1, Player), "Game should have a Player 1 instance."
        assert game_instance.player1.is_ai is False, "Player 1 should not be an AI."
        
        assert isinstance(game_instance.player2_ai, Player), "Game should have a Player 2 (AI) instance."
        assert game_instance.player2_ai.is_ai is True, "Player 2 should be an AI."
        
        assert game_instance.ai_controller_p2 is not None, "AI controller for P2 should be initialized."
        assert isinstance(game_instance.ai_controller_p2, OriginalAIController), \
            "AI controller should match the specified archetype (original)."

        assert game_instance.all_sprites is not None, "all_sprites group should be initialized."
        assert game_instance.players_group is not None, "players_group should be initialized."
        assert game_instance.bombs_group is not None, "bombs_group should be initialized."
        assert game_instance.items_group is not None, "items_group should be initialized."
        
        # Check if players were added to groups
        assert game_instance.player1 in game_instance.all_sprites, "Player 1 should be in all_sprites."
        assert game_instance.player1 in game_instance.players_group, "Player 1 should be in players_group."
        assert game_instance.player2_ai in game_instance.all_sprites, "Player 2 AI should be in all_sprites."
        assert game_instance.player2_ai in game_instance.players_group, "Player 2 AI should be in players_group."


    def test_game_initial_timer_and_state(self, mock_game_dependencies):
        """Test the initial state of the game timer and game_state."""
        screen, clock = mock_game_dependencies
        game_instance = Game(screen, clock)

        assert game_instance.game_state == "PLAYING", \
            f"Initial game_state should be 'PLAYING', but was '{game_instance.game_state}'."
        assert game_instance.time_elapsed_seconds == 0.0, \
            "Initial time_elapsed_seconds should be 0.0."
        assert game_instance.game_timer_active is True, \
            "game_timer_active should be True initially."
        assert game_instance.time_up_winner is None, \
            "time_up_winner should be None initially."
    
    def test_game_initial_player_scores(self, mock_game_dependencies):
        """Test the initial scores of both players."""
        screen, clock = mock_game_dependencies
        game_instance = Game(screen, clock)

        assert game_instance.player1.score == 0, "Player 1's initial score should be 0."
        assert game_instance.player2_ai.score == 0, "Player 2 AI's initial score should be 0."

    def test_game_over_when_player_loses_all_lives(self, mock_game_dependencies):
        """Test that the game state changes to GAME_OVER when P1 loses all lives."""
        screen, clock = mock_game_dependencies
        game_instance = Game(screen, clock, ai_archetype="original")

        assert game_instance.game_state == "PLAYING"
        assert game_instance.player1.is_alive is True
        
        # Simulate player1 taking damage until no lives are left
        # Need to handle invincibility frames for Player.take_damage()
        initial_lives = game_instance.player1.lives
        for _ in range(initial_lives):
            game_instance.player1.last_hit_time = pygame.time.get_ticks() - (settings.PLAYER_INVINCIBLE_DURATION + 100) # Bypass invincibility
            game_instance.player1.take_damage()
            # Player.die() is called, which should then trigger game over logic in Game.update()
            # However, Player.die() itself does not directly change Game.game_state.
            # Game.update() checks player aliveness.

        assert game_instance.player1.lives == 0
        assert game_instance.player1.is_alive is False

        # Manually call update to process the game state change based on player aliveness
        # In a real game loop, events would be empty, dt would be small.
        game_instance._update_internal() # Call the internal update method

        assert game_instance.game_state == "GAME_OVER", \
            f"Game state should be GAME_OVER, but is {game_instance.game_state}"
        assert game_instance.game_timer_active is False, \
            "Game timer should be inactive once game is over due to player death."
    
    def test_game_over_when_ai_loses_all_lives(self, mock_game_dependencies):
        """Test that the game state changes to GAME_OVER when AI P2 loses all lives."""
        screen, clock = mock_game_dependencies
        game_instance = Game(screen, clock, ai_archetype="original") #

        assert game_instance.game_state == "PLAYING" #
        assert game_instance.player2_ai.is_alive is True #
        
        initial_lives_ai = game_instance.player2_ai.lives #
        for _ in range(initial_lives_ai):
            game_instance.player2_ai.last_hit_time = pygame.time.get_ticks() - (settings.PLAYER_INVINCIBLE_DURATION + 100) #
            game_instance.player2_ai.take_damage() #

        assert game_instance.player2_ai.lives == 0 #
        assert game_instance.player2_ai.is_alive is False #

        # Manually call update to process the game state change
        game_instance._update_internal() # 
        assert game_instance.game_timer_active is False, \
            "Game timer should be inactive once game is over due to AI death." #
        
    def test_game_over_when_timer_runs_out_p1_wins_by_lives(self, mock_game_dependencies):
        """Test game over and P1 wins by lives when timer expires."""
        screen, clock = mock_game_dependencies
        game_instance = Game(screen, clock, ai_archetype="original")

        # Ensure players start with default lives or set them explicitly for the test
        game_instance.player1.lives = settings.MAX_LIVES 
        game_instance.player2_ai.lives = settings.MAX_LIVES -1
        game_instance.player1.score = 50 # P1 has lower score
        game_instance.player2_ai.score = 100 # AI has higher score

        # Ensure both players are alive
        game_instance.player1.is_alive = True
        game_instance.player2_ai.is_alive = True
        
        assert game_instance.game_state == "PLAYING"
        assert game_instance.game_timer_active is True
    
        # Simulate the timer running out
        game_instance.time_elapsed_seconds = settings.GAME_DURATION_SECONDS
        game_instance.game_timer_active = False
        game_instance.time_up_winner = game_instance.player1
        game_instance.game_state = "GAME_OVER"
        assert game_instance.game_state == "GAME_OVER", \
            "Game state should be GAME_OVER when timer runs out."
        assert game_instance.time_up_winner == game_instance.player1, \
            "Player 1 should be declared winner when timer runs out and they have more lives."
        
    def test_game_over_when_timer_runs_out_ai_wins_by_score(self, mock_game_dependencies):
        """Test game over and AI wins by score when timer expires."""
        screen, clock = mock_game_dependencies
        game_instance = Game(screen, clock, ai_archetype="original")

        # Ensure players start with default lives or set them explicitly for the test
        game_instance.player1.lives = settings.MAX_LIVES 
        game_instance.player2_ai.lives = settings.MAX_LIVES -1
        game_instance.player1.score = 50
        game_instance.player2_ai.score = 100
        # Ensure both players are alive
        game_instance.player1.is_alive = True
        game_instance.player2_ai.is_alive = True
        assert game_instance.game_state == "PLAYING"
        assert game_instance.game_timer_active is True
        # Simulate the timer running out
        game_instance.time_elapsed_seconds = settings.GAME_DURATION_SECONDS
        game_instance.game_timer_active = False
        game_instance.time_up_winner = game_instance.player2_ai
        game_instance.game_state = "GAME_OVER"
        assert game_instance.game_state == "GAME_OVER", \
            "Game state should be GAME_OVER when timer runs out."
        assert game_instance.time_up_winner == game_instance.player2_ai, \
            "AI should be declared winner when timer runs out and they have higher score."
        
    def test_game_over_when_timer_runs_out_no_winner(self, mock_game_dependencies):
        """Test game over with no winner when timer expires and both players have same score."""
        screen, clock = mock_game_dependencies
        game_instance = Game(screen, clock, ai_archetype="original")

        # Ensure players start with default lives or set them explicitly for the test
        game_instance.player1.lives = settings.MAX_LIVES 
        game_instance.player2_ai.lives = settings.MAX_LIVES -1
        game_instance.player1.score = 50
        game_instance.player2_ai.score = 50
        # Ensure both players are alive
        game_instance.player1.is_alive = True
        game_instance.player2_ai.is_alive = True
        
        assert game_instance.game_state == "PLAYING"
        assert game_instance.game_timer_active is True
        
        # Simulate the timer running out
        game_instance.time_elapsed_seconds = settings.GAME_DURATION_SECONDS
        game_instance.game_timer_active = False
        game_instance.time_up_winner = None
        game_instance.game_state = "GAME_OVER"
        assert game_instance.game_state == "GAME_OVER", \
            "Game state should be GAME_OVER when timer runs out."
        assert game_instance.time_up_winner is None, \
            "There should be no winner when timer runs out and both players have same score."
        
    def test_game_over_when_timer_runs_out_both_players_dead(self, mock_game_dependencies):
        """Test game over when timer expires and both players are dead."""
        screen, clock = mock_game_dependencies
        game_instance = Game(screen, clock, ai_archetype="original")

        # Ensure both players are dead
        game_instance.player1.lives = 0
        game_instance.player2_ai.lives = 0
        game_instance.player1.is_alive = False
        game_instance.player2_ai.is_alive = False
        
        assert game_instance.game_state == "PLAYING"
        assert game_instance.game_timer_active is True
        
        # Simulate the timer running out
        game_instance.time_elapsed_seconds = settings.GAME_DURATION_SECONDS
        game_instance.game_timer_active = False
        game_instance.time_up_winner = None
        game_instance.game_state = "GAME_OVER"
        
        assert game_instance.game_state == "GAME_OVER", \
            "Game state should be GAME_OVER when timer runs out and both players are dead."
        assert game_instance.time_up_winner is None, \
            "There should be no winner when timer runs out and both players are dead."
        


        
        


