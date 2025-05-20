# oop-2025-proj-pycade/core/map_manager.py

import pygame
import settings
from sprites.wall import Wall, DestructibleWall # 從 sprites 套件中匯入 Wall

class MapManager:
    """
    Manages loading, storing, and providing access to map data.
    Also responsible for creating map-related sprites.
    """
    def __init__(self, game):
        """
        Initializes the MapManager.

        Args:
            game (Game): The main game instance.
        """
        self.game = game # Store a reference to the main game object if needed
        self.map_data = []
        self.tile_width = 0
        self.tile_height = 0

        # Sprite groups for map objects
        self.walls_group = pygame.sprite.Group()
        self.destructible_walls_group = pygame.sprite.Group()

        self.load_map_from_data(self.get_simple_test_map())

    def get_simple_test_map(self):
        """Returns a simple hardcoded map for testing."""
        # 'W' for Wall, '.' for Empty space
        # This matches your C++ project's map dimensions roughly (21x21)
        # But for Pygame, a smaller initial map is easier to manage visually
        test_map = [
            "WWWWWWWWWWWWWWW",
            "W.D.D.D.D.D.D.W", # 在空格和 'W' 之間加入 'D'
            "WDW.WDW.WDW.WDW",
            "W.D.D.D.D.D.D.W",
            "WDW.WDW.WDW.WDW",
            "W.D.D.D.D.D.D.W",
            "WDW.WDW.WDW.WDW",
            "W.D.D.D.D.D.D.W",
            "WDW.WDW.WDW.WDW",
            "W.............W", # 留一些空格給玩家
            "WWWWWWWWWWWWWWW",
        ]
        return test_map

    def load_map_from_data(self, map_layout_data):
        """
        Loads map data from a list of strings and creates sprites.

        Args:
            map_layout_data (list): A list of strings representing the map layout.
        """
        self.map_data = map_layout_data
        self.tile_height = len(self.map_data)
        self.tile_width = len(self.map_data[0]) if self.tile_height > 0 else 0

        for row_index, row in enumerate(self.map_data):
            for col_index, tile_char in enumerate(row):
                if tile_char == 'W':
                    wall = Wall(col_index, row_index)
                    self.walls_group.add(wall)
                    self.game.all_sprites.add(wall) # Add to the game's main sprite group
                elif tile_char == 'D':
                    d_wall = DestructibleWall(col_index, row_index, self.game) # 傳遞 game instance
                    self.destructible_walls_group.add(d_wall)
                    self.game.all_sprites.add(d_wall)
                # elif tile_char == '.':
                    # Empty space, do nothing or create Floor sprite if needed
                    # pass

    def draw_grid(self, surface):
        """(Optional) Helper to draw a grid for debugging map layout."""
        if self.tile_width > 0 and self.tile_height > 0:
            for x in range(0, self.tile_width * settings.TILE_SIZE, settings.TILE_SIZE):
                pygame.draw.line(surface, settings.GREY, (x, 0), (x, self.tile_height * settings.TILE_SIZE))
            for y in range(0, self.tile_height * settings.TILE_SIZE, settings.TILE_SIZE):
                pygame.draw.line(surface, settings.GREY, (0, y), (self.tile_width * settings.TILE_SIZE, y))

    def is_walkable(self, tile_x, tile_y):
        """
        Checks if a given tile coordinate is walkable.
        (To be used by Player and AI later)
        """
        if 0 <= tile_y < self.tile_height and 0 <= tile_x < self.tile_width:
            # For now, only non-wall tiles are walkable
            # This needs to be more robust later (check for bombs, etc.)
            return self.map_data[tile_y][tile_x] == '.'
        return False

    def is_solid_wall_at(self, tile_x, tile_y):
        """Checks if there is a solid, non-destructible wall at the given tile coordinates."""
        if not (0 <= tile_x < self.tile_width and 0 <= tile_y < self.tile_height):
            return True # 地圖外視為實心牆

        # 檢查 self.walls_group (不可破壞的牆)
        # 這裡我們假設一個格子上只有一個牆體物件
        # 更精確的方法是直接查 map_data，如果 'W' 代表固態牆
        if self.map_data[tile_y][tile_x] == 'W':
            return True
        return False