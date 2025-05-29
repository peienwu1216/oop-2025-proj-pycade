# test/test_player.py

import pygame
import pytest
import settings
from sprites.player import Player

# mock_game_env fixture 保持不變
@pytest.fixture
def mock_game_env(mocker):
    pygame.init()
    mock_game = mocker.Mock()
    mock_game.screen = pygame.display.set_mode((settings.SCREEN_WIDTH, settings.SCREEN_HEIGHT))
    mock_game.all_sprites = pygame.sprite.Group()
    mock_game.bombs_group = pygame.sprite.Group()
    mock_game.players_group = pygame.sprite.Group()
    mock_game.solid_obstacles_group = pygame.sprite.Group()
    mock_game.map_manager = mocker.Mock()
    mock_game.map_manager.tile_width = 15
    mock_game.map_manager.tile_height = 11
    mock_game.map_manager.is_solid_wall_at.return_value = False
    return mock_game


class TestPlayer:

    def test_initialization(self, mock_game_env):
        """測試玩家是否以正確的預設屬性被建立"""
        # ... (這個測試已通過，保持不變)
        sprite_config = {"ROW_MAP": settings.PLAYER_SPRITESHEET_ROW_MAP, "NUM_FRAMES": settings.PLAYER_NUM_WALK_FRAMES}
        player = Player(
            game=mock_game_env, 
            x_tile=1, 
            y_tile=1, 
            spritesheet_path=settings.PLAYER1_SPRITESHEET_PATH,
            sprite_config=sprite_config,
            is_ai=False
        )
        assert player.is_alive is True
        assert player.score == 0
        assert player.lives == settings.MAX_LIVES
        assert player.bomb_range == settings.INITIAL_BOMB_RANGE

    # --- 以下是被修改的測試函數 ---
    def test_take_damage_and_death(self, mock_game_env):
        """測試玩家受傷和生命歸零的邏輯"""
        sprite_config = {"ROW_MAP": settings.PLAYER_SPRITESHEET_ROW_MAP, "NUM_FRAMES": settings.PLAYER_NUM_WALK_FRAMES}
        player = Player(game=mock_game_env, x_tile=1, y_tile=1, spritesheet_path=settings.PLAYER1_SPRITESHEET_PATH, sprite_config=sprite_config)
        
        initial_lives = player.lives
        
        # 為了測試第一次受傷，手動讓無敵時間失效
        # 確保 (現在時間 - last_hit_time) > 無敵時間
        player.last_hit_time = -player.invincible_duration - 1
        
        # 現在玩家應該可以受傷了
        player.take_damage()
        assert player.lives == initial_lives - 1, "Player should lose a life after the first hit"
        
        # 受傷後，last_hit_time 會被更新，玩家進入無敵狀態
        # 所以立即再次呼叫 take_damage，生命不應再減少
        player.take_damage()
        assert player.lives == initial_lives - 1, "Player should be invincible immediately after being hit"

        # 測試死亡邏輯
        player.lives = 1
        # 同樣，需要先手動讓無敵時間失效才能測試下一次傷害
        player.last_hit_time = -player.invincible_duration - 1
        player.take_damage()
        
        assert player.lives == 0, "Player's lives should be 0 after the final hit"
        assert player.is_alive is False, "Player should be marked as not alive"

    def test_movement(self, mock_game_env):
        """測試玩家的格子移動邏輯"""
        # ... (這個測試已通過，保持不變)
        sprite_config = {"ROW_MAP": settings.PLAYER_SPRITESHEET_ROW_MAP, "NUM_FRAMES": settings.PLAYER_NUM_WALK_FRAMES}
        player = Player(game=mock_game_env, x_tile=1, y_tile=1, spritesheet_path=settings.PLAYER1_SPRITESHEET_PATH, sprite_config=sprite_config)
        
        moved = player.attempt_move_to_tile(1, 0)
        assert moved is True
        assert player.tile_x == 2
        
        mock_wall = pygame.sprite.Sprite()
        mock_wall.rect = pygame.Rect(3 * settings.TILE_SIZE, 1 * settings.TILE_SIZE, settings.TILE_SIZE, settings.TILE_SIZE)
        mock_game_env.solid_obstacles_group.add(mock_wall)

        moved_again = player.attempt_move_to_tile(1, 0)
        assert moved_again is False
        assert player.tile_x == 2