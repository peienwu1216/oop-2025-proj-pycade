# oop-2025-proj-pycade/settings.py

# Screen dimensions
SCREEN_WIDTH = 800  # 寬度 (像素) - 你可以根據你的 C++ 版本調整或先用一個常用值
SCREEN_HEIGHT = 600 # 高度 (像素)
FPS = 60             # Frames Per Second - 遊戲的目標幀率

# Colors (R, G, B)
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
RED = (255, 0, 0)
GREEN = (0, 255, 0)
BLUE = (0, 0, 255)
GREY = (128, 128, 128)

# Game Title
TITLE = "Pycade Bomber"

# Map settings (之後會更詳細)
TILE_SIZE = 32 # 每個格子的像素大小，可以根據你的喜好調整

# Initial game settings (可以從你的 C++ Globals.cpp 參考)
# 例如：
# DEFAULT_MAP_WIDTH = 21
# DEFAULT_MAP_HEIGHT = 21
# MAX_LIVES = 3
# INITIAL_BOMBS = 1
# INITIAL_BOMB_RANGE = 3

# Player settings
PLAYER_SPEED = 4         # 玩家移動速度 (像素/幀)
MAX_LIVES = 3
INITIAL_BOMBS = 2        # 初始可放置炸彈數
INITIAL_BOMB_RANGE = 1   # 炸彈初始範圍 (格子數) - 你C++是3，可以調整

# Player controls (for reference, actual input handled in Player class)
# P1_UP = pygame.K_w (Pygame key constants)
# P1_DOWN = pygame.K_s
# P1_LEFT = pygame.K_a
# P1_RIGHT = pygame.K_d
# P1_BOMB = pygame.K_f

import os # 為了處理路徑

# Asset paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__)) # 專案根目錄
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
IMAGES_DIR = os.path.join(ASSETS_DIR, "images")
SOUNDS_DIR = os.path.join(ASSETS_DIR, "sounds") # 預留
FONTS_DIR = os.path.join(ASSETS_DIR, "fonts")   # 預留
DATA_DIR = os.path.join(ASSETS_DIR, "data")     # 預留

# Image specific paths
WALL_SOLID_IMG = os.path.join(IMAGES_DIR, "walls", "wall_solid_placeholder.png")
WALL_DESTRUCTIBLE_IMG = os.path.join(IMAGES_DIR, "walls", "wall_destructible_placeholder.png")
PLAYER_IMG = os.path.join(IMAGES_DIR, "player", "player_placeholder.png")

BOMB_IMG = os.path.join(IMAGES_DIR, "bomb", "bomb_placeholder.png")
# 如果你有炸彈動畫幀，可以像這樣定義一個列表:
# BOMB_ANIM_FRAMES = [
#     os.path.join(IMAGES_DIR, "bomb", "bomb_tick_0.png"),
#     os.path.join(IMAGES_DIR, "bomb", "bomb_tick_1.png"),
# ]

# ... (之後會添加更多圖片路徑) ...

# Bomb settings
BOMB_TIMER = 3000  # 炸彈爆炸前的毫秒數 (3 秒)
EXPLOSION_DURATION = 500  # 爆炸效果持續的毫秒數 (0.5 秒)
EXPLOSION_COLOR = (255, 165, 0) # 橘色，用於繪製爆炸效果
# 如果使用圖片，可以在這裡定義路徑:
# EXPLOSION_CENTER_IMG = os.path.join(IMAGES_DIR, "explosion", "explosion_center.png")
# EXPLOSION_SEGMENT_IMG = os.path.join(IMAGES_DIR, "explosion", "explosion_segment.png") # 假設水平垂直用同一種