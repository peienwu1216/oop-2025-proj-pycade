# test/test_ai_controller_base.py

import pygame
import pytest
import settings
from core.ai_controller_base import AIControllerBase, TileNode, DIRECTIONS
from sprites.player import Player # AI的玩家精靈通常是Player類別的實例
from core.map_manager import MapManager # AI需要地圖資訊

# --- 輔助函式：創建一個簡單的地圖供測試 ---
def create_test_map_data(layout_strings):
    """根據字串列表創建地圖資料。"""
    return layout_strings

# --- Pytest Fixture 設定 ---
@pytest.fixture
def mock_ai_base_env(mocker):
    """
    為 AIControllerBase 測試設定一個模擬的遊戲環境。
    """
    pygame.display.init() # AI 控制器本身可能不直接用 display，但其依賴 (如 Player) 可能會
    pygame.font.init()    # 同上

    # 模擬 Game 實例
    mock_game = mocker.Mock()
    mock_game.screen = pygame.display.set_mode((settings.SCREEN_WIDTH, settings.SCREEN_HEIGHT)) # 以防萬一需要
    
    # 模擬 MapManager
    mock_game.map_manager = MapManager(mock_game) # MapManager 需要 game 實例
    
    # 預設一個簡單的地圖供測試
    # W = Wall, . = Empty, D = Destructible
    default_map_layout = [
        "WWWWW",
        "W.D.W", # (1,1) is '.', (2,1) is 'D', (3,1) is '.'
        "W.W.W", # (1,2) is '.', (2,2) is 'W', (3,2) is '.'
        "W...W", # (1,3), (2,3), (3,3) are '.'
        "WWWWW"
    ]
    mock_game.map_manager.map_data = create_test_map_data(default_map_layout)
    mock_game.map_manager.tile_height = len(default_map_layout)
    mock_game.map_manager.tile_width = len(default_map_layout[0]) if default_map_layout else 0

    # 模擬 AI 控制的 Player 精靈
    # Player 的初始化需要 game, x_tile, y_tile, spritesheet_path, sprite_config
    # 為了簡化，我們只提供必要的 game 和初始位置
    # spritesheet 和 config 可以是 None 或 mock，因為 AIControllerBase 主要關心地圖和邏輯
    mock_player_sprite_config = {"ROW_MAP": {}, "NUM_FRAMES": 1} # 最小化設定
    
    # 讓 AI 玩家出生在一個已知可走的位置，例如 (1,1)
    ai_player_sprite = Player(
        game=mock_game, 
        x_tile=1, 
        y_tile=1, 
        spritesheet_path=settings.PLAYER1_SPRITESHEET_PATH, # 隨便給一個有效的路徑
        sprite_config=mock_player_sprite_config,
        is_ai=True
    )
    ai_player_sprite.bomb_range = settings.INITIAL_BOMB_RANGE # 設定預設炸彈範圍

    mock_game.players_group = pygame.sprite.Group(ai_player_sprite)
    mock_game.bombs_group = pygame.sprite.Group()
    mock_game.explosions_group = pygame.sprite.Group()
    
    # 模擬人類玩家 (如果 AIControllerBase 需要參考)
    human_player_sprite = Player(
        game=mock_game, x_tile=3, y_tile=3, 
        spritesheet_path=settings.PLAYER1_SPRITESHEET_PATH,
        sprite_config=mock_player_sprite_config,
        is_ai=False
    )
    mock_game.player1 = human_player_sprite # 假設 game 實例有個 player1 屬性
    mock_game.players_group.add(human_player_sprite)


    # 初始化 AI 控制器
    ai_controller = AIControllerBase(ai_player_sprite, mock_game)
    
    # 確保 Pygame 事件佇列是乾淨的
    pygame.event.clear()

    yield ai_controller, mock_game, ai_player_sprite

    pygame.quit()


# --- 測試類別 ---
class TestAIControllerBase:
    """
    AIControllerBase 的測試套件。
    """

    def test_initialization_and_reset_state(self, mock_ai_base_env):
        """測試 AIControllerBase 的初始化和 reset_state 方法。"""
        ai_controller, game, ai_player = mock_ai_base_env

        assert ai_controller.ai_player is ai_player
        assert ai_controller.game is game
        assert ai_controller.map_manager is game.map_manager
        assert ai_controller.current_state == "PLANNING_PATH" # 預設初始狀態
        assert ai_controller.astar_planned_path == []
        assert ai_controller.current_movement_sub_path == []
        
        # 測試 reset_state
        ai_controller.current_state = "EVADING_DANGER"
        ai_controller.astar_planned_path = [TileNode(1,2,'D')]
        ai_controller.reset_state()
        
        assert ai_controller.current_state == "PLANNING_PATH"
        assert ai_controller.astar_planned_path == []
        assert ai_controller.current_movement_sub_path == []
        assert ai_controller.last_known_tile == (ai_player.tile_x, ai_player.tile_y)

    def test_astar_find_path_simple_clear_path(self, mock_ai_base_env):
        """測試 A* 演算法在簡單、無障礙地圖上的路徑尋找。"""
        ai_controller, game, ai_player = mock_ai_base_env
        
        # 地圖:
        # WWWWW
        # W.D.W  (AI start at (1,1) which is '.')
        # W.W.W
        # W...W  (Target (1,3) which is '.')
        # WWWWW
        
        ai_player.tile_x, ai_player.tile_y = 1, 1 # 設定 AI 起點
        start_coords = (1, 1)
        target_coords = (1, 3) # 目標是一個可直接到達的空格

        # 更新 map_data 以確保 (1,2) 是可通行的 '.'
        game.map_manager.map_data = [
            "WWWWW",
            "W...W", # (1,1) (2,1) (3,1) are '.'
            "W.W.W",
            "W...W", # (1,3) is '.'
            "WWWWW"
        ]
        game.map_manager.tile_height = len(game.map_manager.map_data)
        game.map_manager.tile_width = len(game.map_manager.map_data[0])
        
        # 重新設定 AI 控制器的 map_manager 參考 (如果 MapManager 是深度複製的話)
        # 或者確保 AIControllerBase 中的 _get_node_at_coords 使用最新的 map_data
        # 這裡假設 AIControllerBase 會動態查詢 MapManager

        path_nodes = ai_controller.astar_find_path(start_coords, target_coords)
        
        assert path_nodes is not None, "A* 演算法應找到一條路徑。"
        assert len(path_nodes) > 0, "路徑不應為空。"
        
        # 驗證路徑的起點和終點
        assert (path_nodes[0].x, path_nodes[0].y) == start_coords, "路徑起點應為 AI 目前位置。"
        assert (path_nodes[-1].x, path_nodes[-1].y) == target_coords, "路徑終點應為目標位置。"
        
        # 驗證路徑的連續性和每個節點的類型 (在這個簡單例子中，應該都是 '.')
        expected_path_coords = [(1,1), (1,2), (1,3)] # 這是針對修改後的地圖
        
        # 針對修改後的地圖，(1,2) 應該是 '.'
        game.map_manager.map_data = [  # 確保 (1,2) 是 '.'
            "WWWWW",
            "W...W", 
            "W.W.W", # (1,2) 這裡還是 '.', 但 A* 應該走 (1,1)->(2,1)->(3,1)->(3,2)->(3,3)->(2,3)->(1,3)
                     # 不對，如果目標是 (1,3)，且 (1,1) (1,2) (1,3) 都是 '.'
                     # 那路徑應該是 (1,1) -> (1,2) -> (1,3)
            "W...W", 
            "WWWWW"
        ]
        # 為了讓 (1,1) -> (1,2) -> (1,3) 成立，我們需要確保 (1,2) 也是 '.'
        # 讓我們修改地圖讓這條路更直接
        game.map_manager.map_data = [
            "WWWWW", # Row 0
            "W...W", # Row 1: (1,1) is '.', (2,1) is '.', (3,1) is '.'
            "W.W.W", # Row 2: (1,2) is '.', (2,2) is 'W', (3,2) is '.'
            "W...W", # Row 3: (1,3) is '.', (2,3) is '.', (3,3) is '.'
            "WWWWW"  # Row 4
        ]
        # 修正：如果 (1,2) 是牆，A* 會繞路。我們測試的是簡單清晰路徑。
        # 假設地圖是：
        # WWWWW
        # W.W.W  <-- AI 在 (1,1)
        # W...W  <-- 目標在 (1,2)
        # WWWWW
        game.map_manager.map_data = [
            "WWWWW", #0
            "W.W.W", #1  (1,1) is '.'
            "W...W", #2  (1,2) is '.'
            "WWWWW"  #3
        ]
        game.map_manager.tile_height = len(game.map_manager.map_data)
        game.map_manager.tile_width = len(game.map_manager.map_data[0])
        ai_player.tile_x, ai_player.tile_y = 1, 1
        start_coords = (1,1)
        target_coords = (1,2) # 目標現在是 (1,2)
        
        path_nodes = ai_controller.astar_find_path(start_coords, target_coords)
        assert path_nodes is not None
        assert len(path_nodes) == 2 # (1,1) -> (1,2)
        assert (path_nodes[0].x, path_nodes[0].y) == start_coords
        assert (path_nodes[1].x, path_nodes[1].y) == target_coords
        assert path_nodes[0].tile_char == '.'
        assert path_nodes[1].tile_char == '.'

        # 測試一個稍微長一點的清晰路徑
        # WWWWW
        # W...W  <-- AI 在 (1,1), 目標 (3,1)
        # WWWWW
        game.map_manager.map_data = [
            "WWWWW",
            "W...W", # (1,1), (2,1), (3,1) are all '.'
            "WWWWW"
        ]
        game.map_manager.tile_height = len(game.map_manager.map_data)
        game.map_manager.tile_width = len(game.map_manager.map_data[0])
        ai_player.tile_x, ai_player.tile_y = 1, 1
        start_coords = (1,1)
        target_coords = (3,1)
        path_nodes = ai_controller.astar_find_path(start_coords, target_coords)
        assert path_nodes is not None
        assert len(path_nodes) == 3 # (1,1) -> (2,1) -> (3,1)
        actual_path_coords = [(n.x, n.y) for n in path_nodes]
        expected_path_coords = [(1,1), (2,1), (3,1)]
        assert actual_path_coords == expected_path_coords
        for node in path_nodes:
            assert node.tile_char == '.', f"Node {node} in clear path should be '.' but is '{node.tile_char}'"
    
    def test_astar_find_path_with_obstacles(self, mock_ai_base_env):
        """測試 A* 演算法在有障礙物的地圖上的路徑尋找。"""
        ai_controller, game, ai_player = mock_ai_base_env
        
        # 地圖:
        # WWWWW
        # W.D.W  (AI start at (1,1) which is '.')
        # W.W.W
        # W...W  (Target (1,3) which is '.')
        # WWWWW
        
        ai_player.tile_x, ai_player.tile_y = 1, 1 # 設定 AI 起點
        start_coords = (1, 1)
        target_coords = (1, 3)
        # 更新 map_data 以確保 (1,2) 是可通行的 '.'
        game.map_manager.map_data = [
            "WWWWW",
            "W.W.W", # (1,1) is '.', (2,1) is 'W', (3,1) is '.'
            "W.W.W", # (1,2) is '.', (2,2) is 'W', (3,2) is '.'
            "W...W", # (1,3) is '.', (2,3) is '.', (3,3) is '.'
            "WWWWW"
        ]
        game.map_manager.tile_height = len(game.map_manager.map_data)
        game.map_manager.tile_width = len(game.map_manager.map_data[0])
        # 重新設定 AI 控制器的 map_manager 參考 (如果 MapManager 是深度複製的話)
        # 或者確保 AIControllerBase 中的 _get_node_at_coords 使用最新的 map_data
        path_nodes = ai_controller.astar_find_path(start_coords, target_coords)
        assert path_nodes is not None, "A* 演算法應找到一條路徑。"
        assert len(path_nodes) > 0, "路徑不應為空。"
        # 驗證路徑的起點和終點
        assert (path_nodes[0].x, path_nodes[0].y) == start_coords, "路徑起點應為 AI 目前位置。"
        assert (path_nodes[-1].x, path_nodes[-1].y) == target_coords, "路徑終點應為目標位置。"
        # 驗證路徑的連續性和每個節點的類型 (在這個例子中，應該是 '.' 或 'D')
        expected_path_coords = [(1,1), (1,2), (1,3)]
        actual_path_coords = [(n.x, n.y) for n in path_nodes]
        assert actual_path_coords == expected_path_coords, \
            f"預期路徑 {expected_path_coords}，但實際路徑為 {actual_path_coords}。"
        for node in path_nodes:
            assert node.tile_char in ['.', 'D'], \
                f"Node {node} in path should be '.' or 'D' but is '{node.tile_char}'"
            
    

        