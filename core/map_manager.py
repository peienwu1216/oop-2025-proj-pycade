# oop-2025-proj-pycade/core/map_manager.py
import pygame
import settings
from sprites.wall import Wall, DestructibleWall
import random # ！！！需要 random 模組！！！

class MapManager:
    def __init__(self, game):
        self.game = game
        self.map_data = [] # 儲存地圖佈局的字符列表
        self.tile_width = 0
        self.tile_height = 0
        self.walls_group = pygame.sprite.Group()
        self.destructible_walls_group = pygame.sprite.Group()
        # self.load_map_from_data(self.get_simple_test_map()) # 不在這裡調用，由 Game.setup_initial_state 調用

    def get_randomized_map_layout(self, width, height, p1_start_tile, p2_start_tile, safe_radius=1):
        """
        生成一個隨機包含可破壞障礙物的地圖佈局，並保護玩家出生點。
        'W' = 不可破壞, 'D' = 可破壞, '.' = 空
        """
        layout = [['.' for _ in range(width)] for _ in range(height)]

        # 1. 設置邊界牆壁
        for r in range(height):
            for c in range(width):
                if r == 0 or r == height - 1 or c == 0 or c == width - 1:
                    layout[r][c] = 'W' # 邊界是不可破壞的牆

        # 2. 創建固定的不可破壞障礙物 (類似炸彈人經典地圖的棋盤格)
        for r in range(2, height - 2, 2): # 從第2行/列開始，每隔一行/列
            for c in range(2, width - 2, 2):
                layout[r][c] = 'W'
        
        # 3. 定義安全區域 (玩家出生點周圍不生成可破壞障礙物)
        player_starts = [p1_start_tile, p2_start_tile]
        safe_zones = []
        for start_x, start_y in player_starts:
            if start_x is None or start_y is None: continue # 如果某個玩家不存在
            for r_offset in range(-safe_radius, safe_radius + 1):
                for c_offset in range(-safe_radius, safe_radius + 1):
                    safe_zones.append((start_x + c_offset, start_y + r_offset))
        
        # 4. 隨機放置可破壞的障礙物 ('D')
        #    參考你的 C++ 報告，可破壞障礙物內部有80%機率生成道具
        #    這裡我們先決定哪些位置是可破壞障礙物
        #    你的 C++ 報告中提到隨機生成障礙物是在困難地圖，我們這裡可以先用一個固定機率
        destructible_wall_chance = 0.6 # !!! 你可以調整這個機率 !!!

        for r in range(1, height - 1): # 不在最外層邊界生成
            for c in range(1, width - 1):
                if layout[r][c] == '.': # 只在空格子生成
                    if (c, r) not in safe_zones: # 確保不在安全區域內
                        if random.random() < destructible_wall_chance:
                            layout[r][c] = 'D'
        
        # 將二維列表轉換為字符串列表
        string_layout = ["".join(row) for row in layout]
        # print("[DEBUG MAP GEN] Generated map layout:")
        # for row_str in string_layout:
        #     print(row_str)
        return string_layout

    def load_map_from_data(self, map_layout_data):
        self.walls_group.empty()
        self.destructible_walls_group.empty()
        # 在 Game.setup_initial_state 中，solid_obstacles_group 和 all_sprites 也會被清空

        self.map_data = map_layout_data
        self.tile_height = len(self.map_data)
        self.tile_width = len(self.map_data[0]) if self.tile_height > 0 else 0

        for row_index, row_content in enumerate(self.map_data):
            for col_index, tile_char in enumerate(row_content):
                if tile_char == 'W':
                    wall = Wall(col_index, row_index) # Wall 的 __init__ 只需要格子座標
                    self.walls_group.add(wall)
                    self.game.all_sprites.add(wall)
                    self.game.solid_obstacles_group.add(wall)
                elif tile_char == 'D':
                    d_wall = DestructibleWall(col_index, row_index, self.game)
                    self.destructible_walls_group.add(d_wall)
                    self.game.all_sprites.add(d_wall)
                    self.game.solid_obstacles_group.add(d_wall)

    # ... (draw_grid, is_walkable, is_solid_wall_at 保持不變) ...
    def draw_grid(self, surface):
        if self.tile_width > 0 and self.tile_height > 0:
            for x_pos in range(0, self.tile_width * settings.TILE_SIZE, settings.TILE_SIZE):
                pygame.draw.line(surface, settings.GREY, (x_pos, 0), (x_pos, self.tile_height * settings.TILE_SIZE))
            for y_pos in range(0, self.tile_height * settings.TILE_SIZE, settings.TILE_SIZE):
                pygame.draw.line(surface, settings.GREY, (0, y_pos), (self.tile_width * settings.TILE_SIZE, y_pos))

    def is_walkable(self, tile_x, tile_y):
        if 0 <= tile_y < self.tile_height and 0 <= tile_x < self.tile_width:
            return self.map_data[tile_y][tile_x] == '.'
        return False

    def is_solid_wall_at(self, tile_x, tile_y): # 用於炸彈爆炸阻擋
        if not (0 <= tile_x < self.tile_width and 0 <= tile_y < self.tile_height):
            return True # 地圖外視為實心牆
        return self.map_data[tile_y][tile_x] == 'W' # 只有 'W' 是不可穿透的實心牆