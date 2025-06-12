# oop-2025-proj-pycade/core/map_manager.py
import pygame
import settings
from sprites.wall import Wall, DestructibleWall, Floor
import random
from collections import deque


class MapManager:
    def __init__(self, game):
        self.game = game
        self.map_data = [] # 儲存地圖佈局的字符列表
        self.tile_width = 0
        self.tile_height = 0
        self.walls_group = pygame.sprite.Group()
        self.destructible_walls_group = pygame.sprite.Group()
        self.floor_group = pygame.sprite.Group() # 用於地板或空格子
        # self.load_map_from_data(self.get_simple_test_map()) # 不在這裡調用，由 Game.setup_initial_state 調用

    def get_classic_map_layout(self, width, height, p1_start_tile, p2_start_tile, safe_radius=1):
        """
        生成一個經典的、有固定棋盤格障礙物的地圖。
        """
        layout = [['.' for _ in range(width)] for _ in range(height)]

        # 1. 設置邊界牆壁
        for r in range(height):
            for c in range(width):
                if r == 0 or r == height - 1 or c == 0 or c == width - 1:
                    layout[r][c] = 'W'

        # 2. 創建固定的不可破壞障礙物 (棋盤格)
        for r in range(2, height - 2, 2):
            for c in range(2, width - 2, 2):
                layout[r][c] = 'W'
        
        # 3. 定義安全區域
        safe_zones = self._get_safe_zones([p1_start_tile, p2_start_tile], safe_radius)
        
        # 4. 隨機放置可破壞的障礙物
        destructible_wall_chance = settings.CLASSIC_DESTRUCTIBLE_WALL_CHANCE
        for r in range(1, height - 1):
            for c in range(1, width - 1):
                if layout[r][c] == '.':
                    if (c, r) not in safe_zones:
                        if random.random() < destructible_wall_chance:
                            layout[r][c] = 'D'
        
        return ["".join(row) for row in layout]

    def _is_path_between_points(self, layout, start_pos, end_pos):
        """使用廣度優先搜尋 (BFS) 檢查兩點之間是否有路徑。"""
        width = len(layout[0])
        height = len(layout)
        queue = deque([start_pos])
        visited = {start_pos}
        
        while queue:
            x, y = queue.popleft()
            if (x, y) == end_pos:
                return True
            for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                nx, ny = x + dx, y + dy
                if 0 <= nx < width and 0 <= ny < height and (nx, ny) not in visited and layout[ny][nx] == '.':
                    visited.add((nx, ny))
                    queue.append((nx, ny))
        return False

    def _get_safe_zones(self, player_starts, safe_radius):
        """計算並返回玩家出生點周圍的安全區域集合。"""
        safe_zones = set()
        for start_x, start_y in player_starts:
            if start_x is None or start_y is None: continue
            for r_offset in range(-safe_radius, safe_radius + 1):
                for c_offset in range(-safe_radius, safe_radius + 1):
                    safe_zones.add((start_x + c_offset, start_y + r_offset))
        return safe_zones

    def get_truly_random_map_layout(self, width, height, p1_start_tile, p2_start_tile, safe_radius=1):
        """
        生成一個隨機包含不可破壞和可破壞障礙物的地圖，並確保連通性。
        """
        layout = []
        is_playable = False
        max_retries = 50
        retry_count = 0

        safe_zones = self._get_safe_zones([p1_start_tile, p2_start_tile], safe_radius)

        while not is_playable and retry_count < max_retries:
            layout = [['.' for _ in range(width)] for _ in range(height)]
            for r in range(height):
                for c in range(width):
                    if r == 0 or r == height - 1 or c == 0 or c == width - 1:
                        layout[r][c] = 'W'

            solid_wall_chance = 0.22
            for r in range(2, height - 2):
                for c in range(2, width - 2):
                    if (c, r) not in safe_zones:
                        if random.random() < solid_wall_chance:
                            layout[r][c] = 'W'
            
            if self._is_path_between_points(layout, p1_start_tile, p2_start_tile):
                is_playable = True
            else:
                retry_count += 1
        
        if not is_playable:
            print("[MapManager] Could not generate a playable random map. Falling back to classic map.")
            return self.get_classic_map_layout(width, height, p1_start_tile, p2_start_tile, safe_radius)

        destructible_wall_chance = settings.DESTRUCTIBLE_WALL_CHANCE
        # 可破壞的牆壁仍然可以在整個內部區域生成
        for r in range(1, height - 1):
            for c in range(1, width - 1):
                if layout[r][c] == '.' and (c, r) not in safe_zones:
                    if random.random() < destructible_wall_chance:
                        layout[r][c] = 'D'
        
        print("[MapManager] Successfully generated a truly random map with a walkable perimeter.")
        return ["".join(row) for row in layout]

    def load_map_from_data(self, map_layout_data):
        self.walls_group.empty()
        self.destructible_walls_group.empty()
        self.floor_group.empty()
        # 在 Game.setup_initial_state 中，solid_obstacles_group 和 all_sprites 也會被清空

        self.map_data = map_layout_data
        print("[MapManager DEBUG] map_data loaded in load_map_from_data:") # 新增
        for r_idx, row_str in enumerate(self.map_data): # 新增
            print(f"Row {r_idx:02d}: {row_str}") # 新增

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
    
    def update_tile_char_on_map(self, tile_x, tile_y, new_char):
        """Updates the character representing a tile in the internal map_data."""
        if 0 <= tile_y < self.tile_height and 0 <= tile_x < self.tile_width:
            # map_data is a list of strings. Convert row to list, modify, then join back.
            if isinstance(self.map_data[tile_y], str):
                row_list = list(self.map_data[tile_y])
                row_list[tile_x] = new_char
                self.map_data[tile_y] = "".join(row_list)
                print(f"[MapManager] Tile ({tile_x},{tile_y}) updated to '{new_char}' in map_data.")
            else:
                print(f"[MapManager_ERROR] map_data row {tile_y} is not a string. Cannot update.")
        else:
            print(f"[MapManager_ERROR] update_tile_char_on_map: Coords ({tile_x},{tile_y}) out of bounds.")