# oop-2025-proj-pycade/core/map_manager.py

import pygame
import settings
from sprites.wall import Wall, DestructibleWall # 從 sprites 套件中匯入 Wall

class MapManager:
    def __init__(self, game):
        self.game = game
        self.map_data = []
        self.tile_width = 0
        self.tile_height = 0

        self.walls_group = pygame.sprite.Group() # 不可破壞的牆 (Solid, non-destructible)
        self.destructible_walls_group = pygame.sprite.Group() # 可破壞的牆

    def get_simple_test_map(self):
        test_map = [
            "WWWWWWWWWWWWWWW",
            "W.D.D.D.D.D.D.W",
            "WDW.WDW.WDW.WDW",
            "W.D.D.D.D.D.D.W",
            "WDW.WDW.WDW.WDW",
            "W.D.D.D.D.D.D.W",
            "WDW.WDW.WDW.WDW",
            "W.D.D.D.D.D.D.W",
            "WDW.WDW.WDW.WDW",
            "W.............W",
            "WWWWWWWWWWWWWWW",
        ]
        return test_map

    def load_map_from_data(self, map_layout_data):
        # 清理舊的牆壁 (如果這是重載地圖的邏輯)
        # 在 Game.setup_initial_state 中，我們已經清空了 game.all_sprites 和 game.solid_obstacles_group
        # 所以這裡只需要清空 MapManager 自己的組
        self.walls_group.empty()
        self.destructible_walls_group.empty()

        self.map_data = map_layout_data
        self.tile_height = len(self.map_data)
        self.tile_width = len(self.map_data[0]) if self.tile_height > 0 else 0

        for row_index, row in enumerate(self.map_data):
            for col_index, tile_char in enumerate(row):
                if tile_char == 'W':
                    wall = Wall(col_index, row_index)
                    self.walls_group.add(wall)
                    self.game.all_sprites.add(wall)
                    self.game.solid_obstacles_group.add(wall)
                elif tile_char == 'D':
                    d_wall = DestructibleWall(col_index, row_index, self.game)
                    self.destructible_walls_group.add(d_wall)
                    self.game.all_sprites.add(d_wall)
                    self.game.solid_obstacles_group.add(d_wall)
    # ... (draw_grid, is_walkable, is_solid_wall_at - 保持不變) ...
    def draw_grid(self, surface):
        if self.tile_width > 0 and self.tile_height > 0:
            for x in range(0, self.tile_width * settings.TILE_SIZE, settings.TILE_SIZE):
                pygame.draw.line(surface, settings.GREY, (x, 0), (x, self.tile_height * settings.TILE_SIZE))
            for y in range(0, self.tile_height * settings.TILE_SIZE, settings.TILE_SIZE):
                pygame.draw.line(surface, settings.GREY, (0, y), (self.tile_width * settings.TILE_SIZE, y))

    def is_walkable(self, tile_x, tile_y):
        if 0 <= tile_y < self.tile_height and 0 <= tile_x < self.tile_width:
            tile_char = self.map_data[tile_y][tile_x]
            return tile_char == '.'
        return False

    def is_solid_wall_at(self, tile_x, tile_y):
        if not (0 <= tile_x < self.tile_width and 0 <= tile_y < self.tile_height):
            return True
        if self.map_data[tile_y][tile_x] == 'W':
            return True
        return False