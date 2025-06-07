# test/test_explosion.py

import pygame
import pytest
import settings
from sprites.explosion import Explosion # 待測試的類別

@pytest.fixture
def mock_explosion_env(mocker):
    """
    為 Explosion 測試設定一個模擬的遊戲環境。
    """
    pygame.display.init() # Explosion 是 GameObject 的子類，可能間接需要
    # pygame.font.init() # Explosion 通常不使用字體

    # 模擬 Game 實例 (Explosion 的 __init__ 需要 game_instance)
    mock_game = mocker.Mock()
    # mock_game.screen = pygame.display.set_mode((settings.SCREEN_WIDTH, settings.SCREEN_HEIGHT)) # 可能不需要螢幕
    
    # Explosion 不需要太多來自 game 的複雜互動，主要是計時器
    # 如果 Explosion 需要將自己加入到 game 的 sprite group 中，可以在這裡模擬
    mock_game.all_sprites = pygame.sprite.Group() # 假設 Explosion 會被加入
    mock_game.explosions_group = pygame.sprite.Group() # 假設 Explosion 也會被加入

    yield mock_game

    pygame.quit()

class TestExplosion:
    """Explosion 類別的測試套件。"""
    def test_explosion_disappears_after_duration(self, mock_explosion_env, mocker):
        """測試 Explosion 在其持續時間過後是否會自我移除。"""
        game = mock_explosion_env
        self.images = [
            pygame.transform.smoothscale(
                pygame.image.load(img).convert_alpha(),
                (936 * (settings.TILE_SIZE / 997), settings.TILE_SIZE)
            )
            for img in settings.EXPLOSION_IMGS
        ]
        explosion = Explosion(1, 1, game, self.images)
        
        # 將 Explosion 加入一個 group 以測試 kill() 是否將其移除
        mock_group = pygame.sprite.Group()
        mock_group.add(explosion)
        assert explosion in mock_group, "Explosion 應在測試開始時存在於群組中。"

        # 模擬 Sprite.kill 方法
        # explosion.kill = mocker.Mock() # 或者，不 mock kill，而是檢查它是否從 group 中移除

        # 1. 模擬時間未到
        mocker.patch('pygame.time.get_ticks', return_value=explosion.spawn_time + explosion.duration - 10) # 差 10ms
        explosion.update(0.01) # dt 值不直接影響此邏輯，但 update 方法需要
        # explosion.kill.assert_not_called() # 如果 mock kill
        assert explosion in mock_group, "時間未到，Explosion 不應被移除。"


        # 2. 模擬時間剛好超過
        mocker.patch('pygame.time.get_ticks', return_value=explosion.spawn_time + explosion.duration + 1) # 超過 1ms
        explosion.update(0.01)
        # explosion.kill.assert_called_once() # 如果 mock kill
        assert explosion not in mock_group, "時間超過後，Explosion 應從群組中移除 (因呼叫了 kill)。"
        # 如果沒有 mock kill，則檢查是否從 group 中移除

    def test_explosion_duration(self, mock_explosion_env):
        """測試 Explosion 的持續時間是否正確。"""
        game = mock_explosion_env
        explosion = Explosion(1, 1, game)

        # 檢查持續時間是否符合預期
        assert explosion.duration == settings.EXPLOSION_DURATION, \
            f"Explosion 的持續時間應為 {settings.EXPLOSION_DURATION}，但實際為 {explosion.duration}。"
    
    def test_explosion_position(self, mock_explosion_env):
        """測試 Explosion 的位置是否正確。"""
        game = mock_explosion_env
        x, y = 5, 10
        explosion = Explosion(x, y, game)

        # 檢查位置是否符合預期
        assert explosion.rect.x == x * settings.TILE_SIZE, \
            f"Explosion 的 X 位置應為 {x * settings.TILE_SIZE}，但實際為 {explosion.rect.x}。"
        assert explosion.rect.y == y * settings.TILE_SIZE, \
            f"Explosion 的 Y 位置應為 {y * settings.TILE_SIZE}，但實際為 {explosion.rect.y}。"
    
    def test_explosion_image_loading(self, mock_explosion_env):
        """測試 Explosion 的圖片是否正確載入。"""
        game = mock_explosion_env
        explosion = Explosion(1, 1, game)

        # 檢查圖片是否正確載入
        assert explosion.image is not None, "Explosion 的圖片應該被正確載入。"
        assert explosion.image.get_size() == (settings.TILE_SIZE, settings.TILE_SIZE), \
            f"Explosion 的圖片大小應為 ({settings.TILE_SIZE}, {settings.TILE_SIZE})，但實際為 {explosion.image.get_size()}。"

    def test_explosion_initialization(self, mock_explosion_env):
        """測試 Explosion 的初始化是否正確。"""
        game = mock_explosion_env
        explosion = Explosion(1, 1, game)

        # 檢查初始化參數是否正確
        assert explosion.spawn_time is not None, "Explosion 的 spawn_time 應該被正確設定。"
        assert explosion.rect is not None, "Explosion 的 rect 應該被正確設定。"
        assert explosion.image is not None, "Explosion 的 image 應該被正確載入。"
        assert explosion.duration == settings.EXPLOSION_DURATION, \
            f"Explosion 的持續時間應為 {settings.EXPLOSION_DURATION}，但實際為 {explosion.duration}。"

    def test_explosion_added_to_groups_and_kill_removes_it(self, mock_explosion_env):
        """測試 Explosion 被手動加入群組後，其 kill 方法是否能將其從群組中移除。"""
        game = mock_explosion_env # game 實例現在有 all_sprites 和 explosions_group
        explosion = Explosion(2, 2, game)

        # 手動將 explosion 加入到 mock_game 的群組中
        game.all_sprites.add(explosion)
        game.explosions_group.add(explosion)

        assert explosion in game.all_sprites, "Explosion 應被加入到 all_sprites。"
        assert explosion in game.explosions_group, "Explosion 應被加入到 explosions_group。"

        # 直接呼叫 kill 方法 (這通常在 update 中時間到時發生)
        explosion.kill()

        assert explosion not in game.all_sprites, "呼叫 kill 後，Explosion 應從 all_sprites 中移除。"
        assert explosion not in game.explosions_group, "呼叫 kill 後，Explosion 應從 explosions_group 中移除。"
    
    def test_explosion_update_with_no_time_passed(self, mock_explosion_env):
        """測試 Explosion 在沒有時間流逝的情況下，update 方法不應該改變狀態。"""
        game = mock_explosion_env
        explosion = Explosion(3, 3, game)

        initial_spawn_time = explosion.spawn_time
        initial_duration = explosion.duration

        # 模擬沒有時間流逝
        explosion.update(0.0)

        assert explosion.spawn_time == initial_spawn_time, "Explosion 的 spawn_time 應保持不變。"
        assert explosion.duration == initial_duration, "Explosion 的持續時間應保持不變。"
    
    def test_explosion_update_with_negative_time(self, mock_explosion_env):
        """測試 Explosion 在負時間流逝的情況下，update 方法不應該改變狀態。"""
        game = mock_explosion_env
        explosion = Explosion(4, 4, game)

        initial_spawn_time = explosion.spawn_time
        initial_duration = explosion.duration

        # 模擬負時間流逝
        explosion.update(-0.1)

        assert explosion.spawn_time == initial_spawn_time, "Explosion 的 spawn_time 應保持不變。"
        assert explosion.duration == initial_duration, "Explosion 的持續時間應保持不變。"
    
    def test_explosion_update_with_large_time_passed(self, mock_explosion_env, mocker):
        """測試 Explosion 在大量時間流逝的情況下，update 方法應該觸發自我移除。"""
        game = mock_explosion_env
        explosion = Explosion(5, 5, game)

        # 模擬一個非常大的時間流逝
        mocker.patch('pygame.time.get_ticks', return_value=explosion.spawn_time + explosion.duration + 1000)
        initial_spawn_time = explosion.spawn_time
        initial_duration = explosion.duration
        explosion.update(1.0)
        # 如果沒有 mock kill，則檢查是否從 group 中移除
        assert explosion.spawn_time == initial_spawn_time, "Explosion 的 spawn_time 應保持不變。"
        assert explosion.duration == initial_duration, "Explosion 的持續時間應保持不變。"
        # 檢查是否從群組中移除
        assert explosion not in game.all_sprites, "Explosion 應從 all_sprites 中移除。"
        assert explosion not in game.explosions_group, "Explosion 應從 explosions_group 中移除。"
    
    def test_explosion_update_with_zero_time_passed(self, mock_explosion_env):
        """測試 Explosion 在時間流逝為零的情況下，update 方法不應該改變狀態。"""
        game = mock_explosion_env
        explosion = Explosion(6, 6, game)

        initial_spawn_time = explosion.spawn_time
        initial_duration = explosion.duration

        # 模擬時間流逝為零
        explosion.update(0.0)

        assert explosion.spawn_time == initial_spawn_time, "Explosion 的 spawn_time 應保持不變。"
        assert explosion.duration == initial_duration, "Explosion 的持續時間應保持不變。"

    def test_explosion_update_with_small_time_passed(self, mock_explosion_env):
        """測試 Explosion 在小時間流逝的情況下，update 方法不應該改變狀態。"""
        game = mock_explosion_env
        explosion = Explosion(7, 7, game)

        initial_spawn_time = explosion.spawn_time
        initial_duration = explosion.duration

        # 模擬小時間流逝
        explosion.update(0.01)

        assert explosion.spawn_time == initial_spawn_time, "Explosion 的 spawn_time 應保持不變。"
        assert explosion.duration == initial_duration, "Explosion 的持續時間應保持不變。"
    
    def test_explosion_update_with_exact_duration_time_passed(self, mock_explosion_env, mocker):
        """測試 Explosion 在時間流逝剛好等於持續時間的情況下，update 方法應該觸發自我移除。"""
        game = mock_explosion_env
        explosion = Explosion(8, 8, game)

        # 模擬時間流逝剛好等於持續時間
        mocker.patch('pygame.time.get_ticks', return_value=explosion.spawn_time + explosion.duration)
        initial_spawn_time = explosion.spawn_time
        initial_duration = explosion.duration
        explosion.update(0.01)
        # 如果沒有 mock kill，則檢查是否從 group 中移除
        assert explosion.spawn_time == initial_spawn_time, "Explosion 的 spawn_time 應保持不變。"
        assert explosion.duration == initial_duration, "Explosion 的持續時間應保持不變。"
        # 檢查是否從群組中移除
        assert explosion not in game.all_sprites, "Explosion 應從 all_sprites 中移除。"
        assert explosion not in game.explosions_group, "Explosion 應從 explosions_group 中移除。"
    
    def test_explosion_update_with_non_integer_position(self, mock_explosion_env):
        """測試 Explosion 在非整數位置的情況下，update 方法不應該改變狀態。"""
        game = mock_explosion_env
        explosion = Explosion(1.5, 2.5, game)

        initial_spawn_time = explosion.spawn_time
        initial_duration = explosion.duration

        # 模擬時間流逝為零
        explosion.update(0.0)

        assert explosion.spawn_time == initial_spawn_time, "Explosion 的 spawn_time 應保持不變。"
        assert explosion.duration == initial_duration, "Explosion 的持續時間應保持不變。"
        assert explosion.rect.x == int(1.5 * settings.TILE_SIZE), \
            f"Explosion 的 X 位置應為 {int(1.5 * settings.TILE_SIZE)}，但實際為 {explosion.rect.x}。"
        assert explosion.rect.y == int(2.5 * settings.TILE_SIZE), \
            f"Explosion 的 Y 位置應為 {int(2.5 * settings.TILE_SIZE)}，但實際為 {explosion.rect.y}。"
        
    def test_explosion_update_with_large_non_integer_position(self, mock_explosion_env):
        """測試 Explosion 在大非整數位置的情況下，update 方法不應該改變狀態。"""
        game = mock_explosion_env
        explosion = Explosion(1000.5, 2000.5, game)

        initial_spawn_time = explosion.spawn_time
        initial_duration = explosion.duration

        # 模擬時間流逝為零
        explosion.update(0.0)

        assert explosion.spawn_time == initial_spawn_time, "Explosion 的 spawn_time 應保持不變。"
        assert explosion.duration == initial_duration, "Explosion 的持續時間應保持不變。"
        assert explosion.rect.x == int(1000.5 * settings.TILE_SIZE), \
            f"Explosion 的 X 位置應為 {int(1000.5 * settings.TILE_SIZE)}，但實際為 {explosion.rect.x}。"
        assert explosion.rect.y == int(2000.5 * settings.TILE_SIZE), \
            f"Explosion 的 Y 位置應為 {int(2000.5 * settings.TILE_SIZE)}，但實際為 {explosion.rect.y}。"
    
    def test_explosion_update_with_zero_position(self, mock_explosion_env):
        """測試 Explosion 在零位置的情況下，update 方法不應該改變狀態。"""
        game = mock_explosion_env
        explosion = Explosion(0, 0, game)

        initial_spawn_time = explosion.spawn_time
        initial_duration = explosion.duration

        # 模擬時間流逝為零
        explosion.update(0.0)

        assert explosion.spawn_time == initial_spawn_time, "Explosion 的 spawn_time 應保持不變。"
        assert explosion.duration == initial_duration, "Explosion 的持續時間應保持不變。"
        assert explosion.rect.x == 0, "Explosion 的 X 位置應為 0。"
        assert explosion.rect.y == 0, "Explosion 的 Y 位置應為 0。"
    
    def test_explosion_update_with_negative_position(self, mock_explosion_env):
        """測試 Explosion 在負位置的情況下，update 方法不應該改變狀態。"""
        game = mock_explosion_env
        explosion = Explosion(-1, -1, game)

        initial_spawn_time = explosion.spawn_time
        initial_duration = explosion.duration

        # 模擬時間流逝為零
        explosion.update(0.0)

        assert explosion.spawn_time == initial_spawn_time, "Explosion 的 spawn_time 應保持不變。"
        assert explosion.duration == initial_duration, "Explosion 的持續時間應保持不變。"
        assert explosion.rect.x == -settings.TILE_SIZE, "Explosion 的 X 位置應為 -TILE_SIZE。"
        assert explosion.rect.y == -settings.TILE_SIZE, "Explosion 的 Y 位置應為 -TILE_SIZE。"
    
    def test_explosion_update_with_large_negative_position(self, mock_explosion_env):
        """測試 Explosion 在大負位置的情況下，update 方法不應該改變狀態。"""
        game = mock_explosion_env
        explosion = Explosion(-1000, -2000, game)

        initial_spawn_time = explosion.spawn_time
        initial_duration = explosion.duration

        # 模擬時間流逝為零
        explosion.update(0.0)

        assert explosion.spawn_time == initial_spawn_time, "Explosion 的 spawn_time 應保持不變。"
        assert explosion.duration == initial_duration, "Explosion 的持續時間應保持不變。"
        assert explosion.rect.x == -1000 * settings.TILE_SIZE, \
            f"Explosion 的 X 位置應為 {-1000 * settings.TILE_SIZE}，但實際為 {explosion.rect.x}。"
        assert explosion.rect.y == -2000 * settings.TILE_SIZE, \
            f"Explosion 的 Y 位置應為 {-2000 * settings.TILE_SIZE}，但實際為 {explosion.rect.y}。"
    
    def test_explosion_update_with_non_integer_duration(self, mock_explosion_env):
        """測試 Explosion 在非整數持續時間的情況下，update 方法不應該改變狀態。"""
        game = mock_explosion_env
        explosion = Explosion(1, 1, game)
        
        # 模擬非整數持續時間
        explosion.duration = 2.5

        initial_spawn_time = explosion.spawn_time
        initial_duration = explosion.duration

        # 模擬時間流逝為零
        explosion.update(0.0)

        assert explosion.spawn_time == initial_spawn_time, "Explosion 的 spawn_time 應保持不變。"
        assert explosion.duration == initial_duration, "Explosion 的持續時間應保持不變。"
        assert explosion.rect.x == 1 * settings.TILE_SIZE, \
            f"Explosion 的 X 位置應為 {1 * settings.TILE_SIZE}，但實際為 {explosion.rect.x}。"
        assert explosion.rect.y == 1 * settings.TILE_SIZE, \
            f"Explosion 的 Y 位置應為 {1 * settings.TILE_SIZE}，但實際為 {explosion.rect.y}。"
    
    def test_explosion_update_with_large_non_integer_duration(self, mock_explosion_env):
        """測試 Explosion 在大非整數持續時間的情況下，update 方法不應該改變狀態。"""
        game = mock_explosion_env
        explosion = Explosion(1, 1, game)
        
        # 模擬大非整數持續時間
        explosion.duration = 1000.5

        initial_spawn_time = explosion.spawn_time
        initial_duration = explosion.duration

        # 模擬時間流逝為零
        explosion.update(0.0)

        assert explosion.spawn_time == initial_spawn_time, "Explosion 的 spawn_time 應保持不變。"
        assert explosion.duration == initial_duration, "Explosion 的持續時間應保持不變。"
        assert explosion.rect.x == 1 * settings.TILE_SIZE, \
            f"Explosion 的 X 位置應為 {1 * settings.TILE_SIZE}，但實際為 {explosion.rect.x}。"
        assert explosion.rect.y == 1 * settings.TILE_SIZE, \
            f"Explosion 的 Y 位置應為 {1 * settings.TILE_SIZE}，但實際為 {explosion.rect.y}。"
        
    def test_explosion_update_with_zero_duration(self, mock_explosion_env):
        """測試 Explosion 在持續時間為零的情況下，update 方法不應該改變狀態。"""
        game = mock_explosion_env
        explosion = Explosion(1, 1, game)
        
        # 模擬持續時間為零
        explosion.duration = 0.0

        initial_spawn_time = explosion.spawn_time
        initial_duration = explosion.duration

        # 模擬時間流逝為零
        explosion.update(0.0)

        assert explosion.spawn_time == initial_spawn_time, "Explosion 的 spawn_time 應保持不變。"
        assert explosion.duration == initial_duration, "Explosion 的持續時間應保持不變。"
        assert explosion.rect.x == 1 * settings.TILE_SIZE, \
            f"Explosion 的 X 位置應為 {1 * settings.TILE_SIZE}，但實際為 {explosion.rect.x}。"
        assert explosion.rect.y == 1 * settings.TILE_SIZE, \
            f"Explosion 的 Y 位置應為 {1 * settings.TILE_SIZE}，但實際為 {explosion.rect.y}。"
        
    def test_explosion_update_with_negative_duration(self, mock_explosion_env):
        """測試 Explosion 在持續時間為負的情況下，update 方法不應該改變狀態。"""
        game = mock_explosion_env
        explosion = Explosion(1, 1, game)
        
        # 模擬持續時間為負
        explosion.duration = -1.0

        initial_spawn_time = explosion.spawn_time
        initial_duration = explosion.duration

        # 模擬時間流逝為零
        explosion.update(0.0)

        assert explosion.spawn_time == initial_spawn_time, "Explosion 的 spawn_time 應保持不變。"
        assert explosion.duration == initial_duration, "Explosion 的持續時間應保持不變。"
        assert explosion.rect.x == 1 * settings.TILE_SIZE, \
            f"Explosion 的 X 位置應為 {1 * settings.TILE_SIZE}，但實際為 {explosion.rect.x}。"
        assert explosion.rect.y == 1 * settings.TILE_SIZE, \
            f"Explosion 的 Y 位置應為 {1 * settings.TILE_SIZE}，但實際為 {explosion.rect.y}。"
    
    def test_explosion_update_with_large_negative_duration(self, mock_explosion_env):
        """測試 Explosion 在大負持續時間的情況下，update 方法不應該改變狀態。"""
        game = mock_explosion_env
        explosion = Explosion(1, 1, game)
        
        # 模擬大負持續時間
        explosion.duration = -1000.5

        initial_spawn_time = explosion.spawn_time
        initial_duration = explosion.duration

        # 模擬時間流逝為零
        explosion.update(0.0)

        assert explosion.spawn_time == initial_spawn_time, "Explosion 的 spawn_time 應保持不變。"
        assert explosion.duration == initial_duration, "Explosion 的持續時間應保持不變。"
        assert explosion.rect.x == 1 * settings.TILE_SIZE, \
            f"Explosion 的 X 位置應為 {1 * settings.TILE_SIZE}，但實際為 {explosion.rect.x}。"
        assert explosion.rect.y == 1 * settings.TILE_SIZE, \
            f"Explosion 的 Y 位置應為 {1 * settings.TILE_SIZE}，但實際為 {explosion.rect.y}。"
    
    def test_explosion_update_with_non_integer_spawn_time(self, mock_explosion_env):
        """測試 Explosion 在非整數 spawn_time 的情況下，update 方法不應該改變狀態。"""
        game = mock_explosion_env
        explosion = Explosion(1, 1, game)
        
        # 模擬非整數 spawn_time
        explosion.spawn_time = 1234.5

        initial_spawn_time = explosion.spawn_time
        initial_duration = explosion.duration

        # 模擬時間流逝為零
        explosion.update(0.0)

        assert explosion.spawn_time == initial_spawn_time, "Explosion 的 spawn_time 應保持不變。"
        assert explosion.duration == initial_duration, "Explosion 的持續時間應保持不變。"
        assert explosion.rect.x == 1 * settings.TILE_SIZE, \
            f"Explosion 的 X 位置應為 {1 * settings.TILE_SIZE}，但實際為 {explosion.rect.x}。"
        assert explosion.rect.y == 1 * settings.TILE_SIZE, \
            f"Explosion 的 Y 位置應為 {1 * settings.TILE_SIZE}，但實際為 {explosion.rect.y}。"
    
    def test_explosion_update_with_large_non_integer_spawn_time(self, mock_explosion_env):
        """測試 Explosion 在大非整數 spawn_time 的情況下，update 方法不應該改變狀態。"""
        game = mock_explosion_env
        explosion = Explosion(1, 1, game)
        
        # 模擬大非整數 spawn_time
        explosion.spawn_time = 1234567.89

        initial_spawn_time = explosion.spawn_time
        initial_duration = explosion.duration

        # 模擬時間流逝為零
        explosion.update(0.0)

        assert explosion.spawn_time == initial_spawn_time, "Explosion 的 spawn_time 應保持不變。"
        assert explosion.duration == initial_duration, "Explosion 的持續時間應保持不變。"
        assert explosion.rect.x == 1 * settings.TILE_SIZE, \
            f"Explosion 的 X 位置應為 {1 * settings.TILE_SIZE}，但實際為 {explosion.rect.x}。"
        assert explosion.rect.y == 1 * settings.TILE_SIZE, \
            f"Explosion 的 Y 位置應為 {1 * settings.TILE_SIZE}，但實際為 {explosion.rect.y}。"
        
    

    





        
        
   


