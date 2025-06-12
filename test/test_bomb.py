# test/test_bomb.py

import pygame
import pytest
import settings
from sprites.bomb import Bomb
from sprites.player import Player
from sprites.explosion import Explosion
from core.map_manager import MapManager # Bomb.explode() interacts with MapManager

@pytest.fixture
def mock_bomb_env(mocker):
    """
    為 Bomb 測試設定一個模擬的遊戲環境。
    """
    pygame.display.init()
    pygame.font.init() # Bomb might use fonts for countdown text

    # 模擬 Game 實例
    mock_game = mocker.Mock()
    mock_game.screen = pygame.display.set_mode((settings.SCREEN_WIDTH, settings.SCREEN_HEIGHT))
    
    # 設定必要的 Sprite Groups
    mock_game.all_sprites = pygame.sprite.Group()
    mock_game.bombs_group = pygame.sprite.Group() # Bomb adds itself here (implicitly via Player.place_bomb)
    mock_game.explosions_group = pygame.sprite.Group() # Bomb.explode() adds Explosions here
    mock_game.solid_obstacles_group = pygame.sprite.Group() # For explosion collision
    
    # 模擬 MapManager
    mock_game.map_manager = mocker.Mock(spec=MapManager)
    mock_game.map_manager.tile_width = 15 # 假設地圖寬度
    mock_game.map_manager.tile_height = 11 # 假設地圖高度
    # 預設 is_solid_wall_at 和 is_destructible_wall_at 都返回 False，除非特別設定
    mock_game.map_manager.is_solid_wall_at = mocker.MagicMock(return_value=False)
    # DestructibleWall 相關的模擬 (如果 Bomb.explode() 需要)
    mock_game.map_manager.destructible_walls_group = pygame.sprite.Group() 
    # 模擬 update_tile_char_on_map (如果 DestructibleWall.take_damage 被呼叫且修改地圖)
    mock_game.map_manager.update_tile_char_on_map = mocker.MagicMock()
    # 【新增】為我對 bomb.update 的修改提供一個 game.paused 屬性
    mock_game.paused = False


    # 模擬放置炸彈的 Player
    player_sprite_config = {"ROW_MAP": {}, "NUM_FRAMES": 1} # 最小化設定
    mock_player = Player(
        game=mock_game, 
        x_tile=1, 
        y_tile=1, 
        spritesheet_path=settings.PLAYER1_SPRITESHEET_PATH, # 有效路徑
        sprite_config=player_sprite_config
    )
    mock_player.bomb_range = settings.INITIAL_BOMB_RANGE # 設定玩家的炸彈範圍
    # mock_player.bomb_exploded_feedback = mocker.Mock() # 模擬回饋函式

    # 將 mock_player 加入 mock_game 的 players_group (如果 Bomb 或其相關邏輯需要)
    mock_game.players_group = pygame.sprite.Group(mock_player)


    yield mock_game, mock_player

    pygame.quit()

class TestBomb:
    """Bomb 類別的測試套件。"""

    def test_bomb_initialization(self, mock_bomb_env):
        """測試炸彈是否以正確的預設屬性被建立。"""
        game, player = mock_bomb_env
        bomb_x_tile, bomb_y_tile = 3, 4

        bomb = Bomb(bomb_x_tile, bomb_y_tile, player, game)

        assert bomb.current_tile_x == bomb_x_tile
        assert bomb.current_tile_y == bomb_y_tile
        assert bomb.placed_by_player is player
        assert bomb.game is game
        assert bomb.timer == settings.BOMB_TIMER
        assert bomb.exploded is False
        assert bomb.image is not None, "炸彈應有圖片。"
        expected_rect_pos = (bomb_x_tile * settings.TILE_SIZE + 6, bomb_y_tile * settings.TILE_SIZE - 2)
        assert bomb.rect.topleft == expected_rect_pos, "炸彈 rect 位置不正確。"
        assert bomb.owner_has_left_tile is False, "初始時，owner_has_left_tile 應為 False。"
        assert bomb.is_solidified is False, "初始時，is_solidified 應為 False。"

    def test_bomb_update_timer(self, mock_bomb_env, mocker):
        """測試炸彈計時器是否隨時間更新，並在時間到時爆炸。"""
        game, player = mock_bomb_env
        bomb = Bomb(1, 1, player, game)
        
        # 模擬時間流逝，但未達到爆炸時間 (BOMB_TIMER 是 3000ms)
        # dt 是秒，所以傳入 2.999 秒
        bomb.update(dt=(settings.BOMB_TIMER / 1000.0) - 0.001)
        assert bomb.exploded is False, "炸彈在計時器結束前不應爆炸。"

        # 模擬時間流逝，剛好達到爆炸時間
        bomb.explode = mocker.Mock() # 模擬 explode() 以避免其副作用
        
        # 再經過 0.001 秒，總時間達到 BOMB_TIMER
        bomb.update(dt=0.001)
        
        bomb.explode.assert_called_once(), "時間到時，Bomb.explode() 應被呼叫一次。"

    def test_bomb_explode_triggers_feedback_and_kills_self(self, mock_bomb_env, mocker):
        """測試炸彈爆炸時是否觸發玩家回饋並自我銷毀。"""
        game, player = mock_bomb_env
        bomb = Bomb(2, 2, player, game)
        
        # 模擬玩家的回饋函式
        player.bomb_exploded_feedback = mocker.Mock()
        
        # 模擬 Sprite.kill，因為它會從 Group 中移除
        bomb.kill = mocker.Mock() 
        
        # 為了測試，我們需要將炸彈加入一個 group
        game.all_sprites.add(bomb) # 假設 Bomb 會被加入到 all_sprites
        game.bombs_group.add(bomb)  # 以及 bombs_group

        # 直接呼叫 explode 進行測試
        bomb.explode()

        player.bomb_exploded_feedback.assert_called_once(), "玩家的 bomb_exploded_feedback 應被呼叫。"
        bomb.kill.assert_called_once(), "炸彈爆炸後應呼叫 self.kill()。"
        assert bomb.exploded is True, "炸彈的 exploded 屬性應設為 True。"


    def test_bomb_explode_creates_explosion_sprites_no_walls(self, mock_bomb_env, mocker):
        """測試炸彈爆炸時是否在無牆壁阻擋的情況下，根據範圍產生正確的 Explosion 精靈。"""
        game, player = mock_bomb_env
        player.bomb_range = 2 # 設定一個已知的炸彈範圍
        bomb_x, bomb_y = 5, 5
        bomb = Bomb(bomb_x, bomb_y, player, game)

        # 清空 game.explosions_group 以確保只計算本次爆炸產生的
        game.explosions_group.empty()
        
        # 模擬 MapManager 的 is_solid_wall_at 總是返回 False (無固定牆)
        game.map_manager.is_solid_wall_at.return_value = False
        # 模擬 MapManager 的 destructible_walls_group 為空 (無可破壞牆)
        game.map_manager.destructible_walls_group.empty()

        bomb.explode()

        # 預期的爆炸格子數量：中心點 + 4個方向 * 範圍
        # 中心點 = 1
        # 每個方向延伸 player.bomb_range 格
        expected_explosion_count = 1 + (4 * player.bomb_range)
        
        assert len(game.explosions_group) == expected_explosion_count, \
            f"爆炸應產生 {expected_explosion_count} 個 Explosion 精靈，實際產生 {len(game.explosions_group)} 個。"

        # 驗證爆炸中心點
        center_explosion_exists = any(
            exp.rect.collidepoint(bomb_x * settings.TILE_SIZE + settings.TILE_SIZE // 2, 
                                  bomb_y * settings.TILE_SIZE + settings.TILE_SIZE // 2)
            for exp in game.explosions_group
        )
        assert center_explosion_exists, "爆炸中心點應有 Explosion 精靈。"

        # 驗證每個方向的延伸
        for dx, dy in [(0, -1), (0, 1), (-1, 0), (1, 0)]: # 上、下、左、右
            for i in range(1, player.bomb_range + 1):
                ex_x, ex_y = bomb_x + dx * i, bomb_y + dy * i
                explosion_at_coord_exists = any(
                    exp.rect.collidepoint(ex_x * settings.TILE_SIZE + settings.TILE_SIZE // 2,
                                          ex_y * settings.TILE_SIZE + settings.TILE_SIZE // 2)
                    for exp in game.explosions_group
                )
                assert explosion_at_coord_exists, f"在 ({ex_x},{ex_y}) 應有 Explosion 精靈。"


    def test_bomb_owner_leaves_tile_solidifies_bomb(self, mock_bomb_env):
        """測試當炸彈擁有者離開炸彈所在格子後，炸彈是否固化。"""
        game, player = mock_bomb_env
        bomb_tile_x, bomb_tile_y = player.tile_x, player.tile_y # 炸彈放在玩家當前位置
        
        bomb = Bomb(bomb_tile_x, bomb_tile_y, player, game)
        assert bomb.owner_has_left_tile is False
        assert bomb.is_solidified is False

        # 模擬玩家移動到不同的格子
        player.tile_x += 1
        bomb.update(0.1) # 呼叫 update 以觸發 owner_has_left_tile 的檢查

        assert bomb.owner_has_left_tile is True, "玩家離開後，owner_has_left_tile 應為 True。"
        assert bomb.is_solidified is True, "玩家離開後，is_solidified 應為 True。"

        # 模擬玩家又回到炸彈格 (不應影響已固化的狀態)
        player.tile_x -=1
        bomb.update(0.1)
        assert bomb.owner_has_left_tile is True, "即使玩家返回，owner_has_left_tile 應保持 True。"
        assert bomb.is_solidified is True, "即使玩家返回，is_solidified 應保持 True。"
    
