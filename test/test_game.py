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
from unittest.mock import MagicMock

@pytest.fixture
def mock_audio_manager(mocker):
    """Provides a mocked AudioManager instance for tests."""
    mock_manager = MagicMock()
    mock_manager.play_sound = MagicMock()
    mock_manager.play_music = MagicMock()
    mock_manager.stop_music = MagicMock()
    mock_manager.stop_all_sounds = MagicMock()
    return mock_manager

@pytest.fixture
def mock_game_dependencies(mocker, mock_audio_manager):
    """
    Sets up a Pygame environment and mocks dependencies for Game tests.
    """
    pygame.display.init()
    pygame.font.init()

    screen = pygame.display.set_mode((settings.SCREEN_WIDTH, settings.SCREEN_HEIGHT))
    clock = pygame.time.Clock()

    mocker.patch.object(LeaderboardManager, 'load_scores', return_value=[])
    mocker.patch.object(LeaderboardManager, 'save_scores', return_value=None)
    mocker.patch.object(LeaderboardManager, 'is_score_high_enough', return_value=False)

    map_width = getattr(settings, 'GRID_WIDTH', 15)
    map_height = getattr(settings, 'GRID_HEIGHT', 11)
    
    mocked_map_data = ["W" * map_width]
    for r in range(1, map_height - 1):
        row_list = list("W" + "." * (map_width - 2) + "W")
        if r == 1:
            row_list[1] = '.'
        if r == map_height - 2:
            row_list[map_width - 2] = '.'
        mocked_map_data.append("".join(row_list))
    mocked_map_data.append("W" * map_width)

    mocker.patch('core.map_manager.MapManager.get_truly_random_map_layout', return_value=mocked_map_data)
    mocker.patch('core.map_manager.MapManager.get_classic_map_layout', return_value=mocked_map_data)

    ai_controllers_to_mock = [
        OriginalAIController, 
        ConservativeAIController,
        AggressiveAIController,
        ItemFocusedAIController
    ]
    for controller_class in ai_controllers_to_mock:
        mocker.patch.object(controller_class, 'update', return_value=None)
        mocker.patch.object(controller_class, 'reset_state', return_value=None)
        if hasattr(controller_class, 'debug_draw_path'):
            mocker.patch.object(controller_class, 'debug_draw_path', return_value=None)

    yield screen, clock, mock_audio_manager

    pygame.quit()


class TestGame:
    """Test suite for the Game class."""

    def test_game_initialization(self, mock_game_dependencies):
        screen, clock, audio_manager = mock_game_dependencies
        game_instance = Game(screen, clock, audio_manager, ai_archetype="original")

        assert game_instance.screen is screen
        assert game_instance.clock is clock
        assert game_instance.running is True
        assert isinstance(game_instance.map_manager, MapManager)
        assert isinstance(game_instance.player1, Player)
        assert game_instance.player1.is_ai is False
        assert isinstance(game_instance.player2_ai, Player)
        assert game_instance.player2_ai.is_ai is True
        assert game_instance.ai_controller_p2 is not None
        assert isinstance(game_instance.ai_controller_p2, OriginalAIController)
        assert game_instance.all_sprites is not None
        assert game_instance.players_group is not None
        assert game_instance.bombs_group is not None
        assert game_instance.items_group is not None
        assert game_instance.player1 in game_instance.all_sprites
        assert game_instance.player1 in game_instance.players_group
        assert game_instance.player2_ai in game_instance.all_sprites
        assert game_instance.player2_ai in game_instance.players_group

    def test_game_initial_timer_and_state(self, mock_game_dependencies):
        screen, clock, audio_manager = mock_game_dependencies
        game_instance = Game(screen, clock, audio_manager)

        assert game_instance.game_state == "PLAYING"
        assert game_instance.time_elapsed_seconds == 0.0
        assert game_instance.game_timer_active is False
        assert game_instance.time_up_winner is None
    
    def test_game_initial_player_scores(self, mock_game_dependencies):
        screen, clock, audio_manager = mock_game_dependencies
        game_instance = Game(screen, clock, audio_manager)

        assert game_instance.player1.score == 0
        assert game_instance.player2_ai.score == 0

    def test_game_over_when_player_loses_all_lives(self, mock_game_dependencies):
        screen, clock, audio_manager = mock_game_dependencies
        game_instance = Game(screen, clock, audio_manager, ai_archetype="original")
        game_instance.start_timer()

        initial_lives = game_instance.player1.lives
        for _ in range(initial_lives):
            game_instance.player1.last_hit_time = pygame.time.get_ticks() - (settings.PLAYER_INVINCIBLE_DURATION + 100)
            game_instance.player1.take_damage()

        game_instance.dt = 0.1 # 手動設定一個 dt
        game_instance._update_internal() 

        assert game_instance.game_state == "GAME_OVER"
        assert game_instance.game_timer_active is False
    
    def test_game_over_when_ai_loses_all_lives(self, mock_game_dependencies):
        screen, clock, audio_manager = mock_game_dependencies
        game_instance = Game(screen, clock, audio_manager, ai_archetype="original")
        game_instance.start_timer()

        initial_lives_ai = game_instance.player2_ai.lives
        for _ in range(initial_lives_ai):
            game_instance.player2_ai.last_hit_time = pygame.time.get_ticks() - (settings.PLAYER_INVINCIBLE_DURATION + 100)
            game_instance.player2_ai.take_damage()

        game_instance.dt = 0.1 # 手動設定一個 dt
        game_instance._update_internal()
        
        assert game_instance.game_state == "GAME_OVER"
        assert game_instance.game_timer_active is False
        
    def test_game_over_when_timer_runs_out_p1_wins_by_lives(self, mock_game_dependencies):
        screen, clock, audio_manager = mock_game_dependencies
        game_instance = Game(screen, clock, audio_manager, ai_archetype="original")
        game_instance.start_timer()

        game_instance.player1.lives = settings.MAX_LIVES 
        game_instance.player2_ai.lives = settings.MAX_LIVES - 1
        
        game_instance.time_elapsed_seconds = settings.GAME_DURATION_SECONDS
        game_instance.dt = 0.1 # 手動設定一個 dt
        game_instance._update_internal()

        assert game_instance.game_state == "GAME_OVER"
        assert game_instance.time_up_winner == "P1"
        
    def test_game_over_when_timer_runs_out_ai_wins_by_score(self, mock_game_dependencies):
        screen, clock, audio_manager = mock_game_dependencies
        game_instance = Game(screen, clock, audio_manager, ai_archetype="original")
        game_instance.start_timer()

        game_instance.player1.lives = settings.MAX_LIVES
        game_instance.player2_ai.lives = settings.MAX_LIVES
        game_instance.player1.score = 50
        game_instance.player2_ai.score = 100
        
        game_instance.time_elapsed_seconds = settings.GAME_DURATION_SECONDS
        game_instance.dt = 0.1 # 手動設定一個 dt
        game_instance._update_internal()
        
        assert game_instance.game_state == "GAME_OVER"
        assert game_instance.time_up_winner == "AI"
        
    def test_game_over_when_timer_runs_out_no_winner(self, mock_game_dependencies):
        screen, clock, audio_manager = mock_game_dependencies
        game_instance = Game(screen, clock, audio_manager, ai_archetype="original")
        game_instance.start_timer()

        game_instance.player1.lives = settings.MAX_LIVES
        game_instance.player2_ai.lives = settings.MAX_LIVES
        game_instance.player1.score = 50
        game_instance.player2_ai.score = 50

        game_instance.time_elapsed_seconds = settings.GAME_DURATION_SECONDS
        game_instance.dt = 0.1 # 手動設定一個 dt
        game_instance._update_internal()

        assert game_instance.game_state == "GAME_OVER"
        assert game_instance.time_up_winner == "DRAW"
        
    def test_game_over_when_timer_runs_out_both_players_dead(self, mock_game_dependencies):
        screen, clock, audio_manager = mock_game_dependencies
        game_instance = Game(screen, clock, audio_manager, ai_archetype="original")
        game_instance.start_timer()

        game_instance.player1.is_alive = False
        game_instance.player2_ai.is_alive = False
        
        game_instance.time_elapsed_seconds = settings.GAME_DURATION_SECONDS
        game_instance.dt = 0.1 # 手動設定一個 dt
        game_instance._update_internal()
        
        assert game_instance.game_state == "GAME_OVER"
        assert game_instance.time_up_winner == "DRAW"